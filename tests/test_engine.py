"""Unit tests for Baseline Monitor, Localisation Engine, and Experience Recorder lifecycle."""
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.db import Base, Branch, Event, Incident, UserReport, init_db
from src.engine.baseline import BaselineMonitor
from src.engine.localisation import LocalisationEngine
from src.engine.recorder import ExperienceRecorder


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    # Add test branch
    branch = Branch(branch_id="B007", name="Branch B007 Metro", region="Metro", wan_type="MPLS Primary")
    session.add(branch)
    session.commit()
    yield session
    session.close()


def test_baseline_threshold_monitor():
    """Verify baseline monitor detects threshold violation naively without cross-domain context."""
    baseline = BaselineMonitor(latency_threshold_ms=150.0, loss_threshold_percent=5.0)

    normal_result = baseline.evaluate_event({"latency_ms": 45.0, "packet_loss_percent": 0.0})
    assert normal_result["status"] == "NORMAL"
    assert normal_result["alert_active"] is False

    degraded_result = baseline.evaluate_event({"latency_ms": 280.0, "packet_loss_percent": 12.0})
    assert degraded_result["status"] == "DEGRADED"
    assert degraded_result["alert_active"] is True


def test_localisation_rules():
    """Verify rule-based localisation across all 4 fault domains."""
    loc = LocalisationEngine()

    # 1. WAN Degradation
    wan_events = [
        {"latency_ms": 320.0, "packet_loss_percent": 14.0, "jitter_ms": 45.0, "dns_response_ms": 210.0,
         "wifi_rssi": -52.0, "wifi_retry_rate": 2.0, "channel_utilisation": 30.0,
         "application_response_ms": 2200.0, "http_status": 200}
    ]
    res_wan = loc.localise(wan_events)
    assert res_wan["probable_cause"] == "WAN degradation"
    assert res_wan["confidence"] > 0.8
    assert res_wan["evidence"]["domain_states"]["wan_abnormal"] is True
    assert res_wan["evidence"]["domain_states"]["wifi_abnormal"] is False

    # 2. Wi-Fi Degradation
    wifi_events = [
        {"latency_ms": 35.0, "packet_loss_percent": 0.0, "jitter_ms": 4.0, "dns_response_ms": 25.0,
         "wifi_rssi": -85.0, "wifi_retry_rate": 45.0, "channel_utilisation": 88.0,
         "application_response_ms": 320.0, "http_status": 200}
    ]
    res_wifi = loc.localise(wifi_events)
    assert res_wifi["probable_cause"] == "Wi-Fi degradation"
    assert res_wifi["evidence"]["domain_states"]["wifi_abnormal"] is True
    assert res_wifi["evidence"]["domain_states"]["wan_abnormal"] is False

    # 3. Application Degradation
    app_events = [
        {"latency_ms": 38.0, "packet_loss_percent": 0.0, "jitter_ms": 5.0, "dns_response_ms": 22.0,
         "wifi_rssi": -55.0, "wifi_retry_rate": 2.5, "channel_utilisation": 35.0,
         "application_response_ms": 4500.0, "http_status": 503, "transaction_duration_ms": 5000.0}
    ]
    res_app = loc.localise(app_events)
    assert res_app["probable_cause"] == "Application degradation"
    assert res_app["evidence"]["domain_states"]["application_abnormal"] is True
    assert res_app["evidence"]["domain_states"]["wan_abnormal"] is False

    # 4. Multiple Contributing Signals
    multi_events = [
        {"latency_ms": 340.0, "packet_loss_percent": 18.0, "jitter_ms": 50.0,
         "wifi_rssi": -88.0, "wifi_retry_rate": 48.0, "channel_utilisation": 92.0,
         "application_response_ms": 4000.0, "http_status": 503}
    ]
    res_multi = loc.localise(multi_events)
    assert res_multi["probable_cause"] == "Multiple contributing signals"


def test_experience_recorder_lifecycle_and_evidence_window(db_session):
    """Verify complete lifecycle: Normal -> Incident Active -> Recovered -> Evidence Window retrieval."""
    recorder = ExperienceRecorder(db_session=db_session)
    t0 = datetime(2026, 10, 1, 10, 0, 0)

    # 1. Add 2 minutes of normal pre-incident baseline events (10:00 to 10:02)
    for i in range(12):
        t = t0 + timedelta(seconds=i * 10)
        evt = Event(
            event_id=f"EVT-PRE-{i}",
            event_time=t,
            arrival_time=t,
            branch_id="B007",
            source="ACTIVE_PROBE",
            latency_ms=45.0,
            packet_loss_percent=0.0
        )
        db_session.add(evt)
    db_session.commit()

    # Process baseline: no incident should be formed
    inc = recorder.process_telemetry_batch("B007", current_time=t0 + timedelta(minutes=2))
    assert inc is None

    # 2. Injected WAN degradation begins at 10:02:10 (duration 2 minutes)
    incident_start = t0 + timedelta(minutes=2, seconds=10)
    for i in range(12):
        t = incident_start + timedelta(seconds=i * 10)
        evt = Event(
            event_id=f"EVT-DEG-{i}",
            event_time=t,
            arrival_time=t,
            branch_id="B007",
            source="ACTIVE_PROBE",
            latency_ms=310.0,
            packet_loss_percent=15.0
        )
        db_session.add(evt)
    db_session.commit()

    # Add a user report during degradation
    user_report = UserReport(
        report_id="URP-TEST-007",
        branch_id="B007",
        event_time=incident_start + timedelta(seconds=30),
        location="Branch B007 Counter 1",
        description="Transactions failing with gateway timeout",
        severity="HIGH"
    )
    db_session.add(user_report)
    db_session.commit()

    # Process during degradation: should create and update ACTIVE incident
    inc_active = recorder.process_telemetry_batch("B007", current_time=incident_start + timedelta(seconds=60))
    assert inc_active is not None
    assert inc_active.status == "ACTIVE"
    assert inc_active.probable_cause == "WAN degradation"
    assert inc_active.peak_latency == 310.0
    incident_id = inc_active.incident_id

    # 3. Failure disappears; normal events resume for 2 minutes (10:04:10 to 10:06:10)
    recovery_start = incident_start + timedelta(minutes=2)
    for i in range(12):
        t = recovery_start + timedelta(seconds=i * 10)
        evt = Event(
            event_id=f"EVT-POST-{i}",
            event_time=t,
            arrival_time=t,
            branch_id="B007",
            source="ACTIVE_PROBE",
            latency_ms=42.0,
            packet_loss_percent=0.0
        )
        db_session.add(evt)
    db_session.commit()

    # Process after recovery: should transition status to RECOVERED
    inc_recovered = recorder.process_telemetry_batch("B007", current_time=recovery_start + timedelta(minutes=1))
    assert inc_recovered is not None
    assert inc_recovered.status == "RECOVERED"
    assert inc_recovered.incident_id == incident_id
    assert inc_recovered.end_time is not None

    # 4. Forensic Evidence Window Verification
    evidence_bundle = recorder.get_incident_evidence_window(incident_id)
    assert evidence_bundle["incident_id"] == incident_id
    assert evidence_bundle["probable_cause"] == "WAN degradation"
    assert len(evidence_bundle["timeline_events"]) > 0

    # Verify timeline phases: PRE_INCIDENT_BASELINE, INCIDENT_PERIOD, POST_RECOVERY_BASELINE
    phases = {e["phase"] for e in evidence_bundle["timeline_events"]}
    assert "PRE_INCIDENT_BASELINE" in phases
    assert "INCIDENT_PERIOD" in phases
    assert "POST_RECOVERY_BASELINE" in phases

    # Verify associated user reports preserved
    assert len(evidence_bundle["user_reports"]) == 1
    assert evidence_bundle["user_reports"][0]["report_id"] == "URP-TEST-007"
