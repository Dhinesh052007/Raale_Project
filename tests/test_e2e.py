"""Comprehensive End-to-End integration test simulating complete intermittent degradation lifecycle."""
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.models.db import Base, init_db, Branch, Event, Incident, UserReport
from src.simulator.branch_simulator import BranchSimulator
from src.simulator.failure_scenarios import FailureScenario, FailureType
from src.collector.collector import EventCollector
from src.collector.buffer import EventBuffer
from src.engine.recorder import ExperienceRecorder


@pytest.fixture
def e2e_env():
    """Isolated in-memory test database and environment."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    init_db(test_engine)
    TestingSession = sessionmaker(bind=test_engine)
    session = TestingSession()

    sim = BranchSimulator(num_branches=50, seed=42)
    # Seed 50 branches
    for b in sim.branches:
        session.add(Branch(
            branch_id=b["branch_id"],
            name=b["name"],
            region=b["region"],
            wan_type=b["wan_type"]
        ))
    session.commit()

    edge_buffer = EventBuffer()
    collector = EventCollector(db_session=session, buffer=edge_buffer)
    recorder = ExperienceRecorder(db_session=session)

    yield {
        "db": session,
        "sim": sim,
        "buffer": edge_buffer,
        "collector": collector,
        "recorder": recorder
    }
    session.close()


def test_complete_end_to_end_intermittent_scenario(e2e_env):
    """
    Simulate full realistic scenario:
    Normal -> WAN degradation injected -> Probe spikes -> App slows -> Wi-Fi healthy ->
    User report filed -> Correlated -> Incident ACTIVE -> Localised to 'WAN degradation' ->
    Failure clears -> Recovered -> Full historical evidence window preserved for investigation.
    """
    db = e2e_env["db"]
    sim = e2e_env["sim"]
    collector = e2e_env["collector"]
    recorder = e2e_env["recorder"]

    branch_id = "B007"
    t0 = datetime(2026, 10, 1, 10, 18, 0)  # 10:18 AM

    # Phase 1: 10:18 - 10:20 (Normal Baseline, 2 min before)
    for s in range(0, 120, 10):
        t = t0 + timedelta(seconds=s)
        collector.ingest_event(sim.generate_probe_metric(branch_id, t))
        collector.ingest_event(sim.generate_wifi_metric(branch_id, t))
        collector.ingest_event(sim.generate_application_metric(branch_id, t))

    # Evaluate at 10:20 AM: No incident should exist
    inc_pre = recorder.process_telemetry_batch(branch_id, current_time=t0 + timedelta(minutes=2))
    assert inc_pre is None

    # Phase 2: 10:20 - 10:22 (WAN Degradation Injected)
    wan_scenario = FailureScenario(
        failure_type=FailureType.WAN_DEGRADATION,
        target_branch_id=branch_id,
        start_seconds=120,
        duration_seconds=120
    )
    for s in range(120, 240, 10):
        t = t0 + timedelta(seconds=s)
        collector.ingest_event(sim.generate_probe_metric(branch_id, t, failure=wan_scenario))
        collector.ingest_event(sim.generate_wifi_metric(branch_id, t, failure=wan_scenario))
        collector.ingest_event(sim.generate_application_metric(branch_id, t, failure=wan_scenario))

    # User reports slowness at 10:21 AM
    user_report_bundle = sim.generate_user_report(
        branch_id,
        t0 + timedelta(minutes=3),  # 10:21 AM
        severity="HIGH",
        description="Transactions are timing out at teller station 2."
    )
    collector.ingest_event(user_report_bundle["event"])
    ur_dict = user_report_bundle["report"]
    db.add(UserReport(
        report_id=ur_dict["report_id"],
        branch_id=ur_dict["branch_id"],
        event_time=ur_dict["event_time"].replace(tzinfo=None) if ur_dict["event_time"].tzinfo else ur_dict["event_time"],
        location=ur_dict["location"],
        description=ur_dict["description"],
        severity=ur_dict["severity"]
    ))
    db.commit()

    # Experience Recorder evaluates during degradation:
    # Detects -> Correlates -> Localises to WAN degradation -> Status ACTIVE
    active_inc = recorder.process_telemetry_batch(branch_id, current_time=t0 + timedelta(minutes=3, seconds=30))
    assert active_inc is not None
    assert active_inc.status == "ACTIVE"
    assert active_inc.probable_cause == "WAN degradation"
    assert active_inc.peak_latency >= 180.0
    assert active_inc.peak_packet_loss >= 5.0
    incident_id = active_inc.incident_id

    # Phase 3: 10:22 - 10:25 (Failure Clears; Normal Baseline Resumes)
    for s in range(240, 420, 10):
        t = t0 + timedelta(seconds=s)
        collector.ingest_event(sim.generate_probe_metric(branch_id, t))
        collector.ingest_event(sim.generate_wifi_metric(branch_id, t))
        collector.ingest_event(sim.generate_application_metric(branch_id, t))

    # 10:25 AM: Engineer begins investigation.
    # The active failure is gone from the live network, but Experience Recorder has preserved it!
    recovered_inc = recorder.process_telemetry_batch(branch_id, current_time=t0 + timedelta(minutes=6))
    assert recovered_inc is not None
    assert recovered_inc.status == "RECOVERED"
    assert recovered_inc.end_time is not None

    # Engineer queries the Forensic Evidence Window
    evidence_bundle = recorder.get_incident_evidence_window(incident_id)
    assert evidence_bundle["incident_id"] == incident_id
    assert evidence_bundle["status"] == "RECOVERED"
    assert evidence_bundle["probable_cause"] == "WAN degradation"

    # Verify 3 timeline phases exist in preserved evidence
    phases = {e["phase"] for e in evidence_bundle["timeline_events"]}
    assert "PRE_INCIDENT_BASELINE" in phases
    assert "INCIDENT_PERIOD" in phases
    assert "POST_RECOVERY_BASELINE" in phases

    # Verify user report is preserved alongside technical telemetry
    assert len(evidence_bundle["user_reports"]) == 1
    assert "teller station 2" in evidence_bundle["user_reports"][0]["description"]


def test_edge_case_resilience_matrix(e2e_env):
    """
    Test pathological delivery cases:
    - Duplicates
    - Delayed events
    - Out-of-order events
    - Disconnection buffering and recovery
    """
    db = e2e_env["db"]
    buffer = e2e_env["buffer"]
    collector = e2e_env["collector"]

    now = datetime(2026, 10, 1, 11, 0, 0)

    # 1. Duplicate Ingestion Test (Idempotency)
    dup_evt = {
        "event_id": "EVT-IDEMPOTENT-100",
        "event_time": now,
        "arrival_time": now,
        "branch_id": "B001",
        "source": "ACTIVE_PROBE",
        "latency_ms": 33.0
    }
    s1, st1, _ = collector.ingest_event(dup_evt)
    s2, st2, _ = collector.ingest_event(dup_evt)
    assert s1 is True and st1 == "VALID"
    assert s2 is True and st2 == "DUPLICATE_REJECTED"
    assert db.query(Event).filter_by(event_id="EVT-IDEMPOTENT-100").count() == 1

    # 2. Out-of-order Ingestion Test
    t1 = now + timedelta(seconds=10)
    t2 = now + timedelta(seconds=20)
    collector.ingest_event({
        "event_id": "EVT-SEQ-2",
        "event_time": t2,
        "arrival_time": t2,
        "branch_id": "B001",
        "source": "ACTIVE_PROBE",
        "latency_ms": 35.0
    })
    s_ooo, st_ooo, _ = collector.ingest_event({
        "event_id": "EVT-SEQ-1",
        "event_time": t1,
        "arrival_time": t2 + timedelta(seconds=1),
        "branch_id": "B001",
        "source": "ACTIVE_PROBE",
        "latency_ms": 34.0
    })
    assert st_ooo == "OUT_OF_ORDER"

    # 3. Disconnection Buffering & Recovery Test
    buffer.set_interrupted(True)
    for i in range(3):
        t_buf = now + timedelta(seconds=100 + i)
        collector.ingest_event({
            "event_id": f"EVT-OFFLINE-{i}",
            "event_time": t_buf,
            "arrival_time": t_buf,
            "branch_id": "B002",
            "source": "WIFI",
            "wifi_rssi": -55.0
        })
    assert buffer.size() == 3

    buffer.set_interrupted(False)
    rec_res = collector.recover_buffer()
    assert rec_res["recovered_count"] == 3
    assert buffer.size() == 0
    assert db.query(Event).filter(Event.event_id.like("EVT-OFFLINE%")).count() == 3
