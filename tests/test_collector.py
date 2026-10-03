"""Unit tests for Event Collector: validation, deduplication, out-of-order, delayed, and buffer recovery."""
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.db import Base, Event, EventProcessingLog, Branch, init_db
from src.collector.collector import EventCollector
from src.collector.buffer import EventBuffer


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    # Seed default branch B001
    branch = Branch(branch_id="B001", name="Branch B001", region="Metro", wan_type="MPLS Primary")
    session.add(branch)
    session.commit()
    yield session
    session.close()


def test_valid_event_ingestion(db_session):
    """Verify standard valid event ingestion into database."""
    collector = EventCollector(db_session=db_session)
    now = datetime.now(timezone.utc)
    event_payload = {
        "event_id": "EVT-TEST-001",
        "event_time": now,
        "arrival_time": now,
        "branch_id": "B001",
        "source": "ACTIVE_PROBE",
        "latency_ms": 42.5,
        "packet_loss_percent": 0.0
    }

    success, status, msg = collector.ingest_event(event_payload)
    assert success is True
    assert status == "VALID"

    db_evt = db_session.query(Event).filter_by(event_id="EVT-TEST-001").first()
    assert db_evt is not None
    assert db_evt.latency_ms == 42.5


def test_malformed_event_rejection(db_session):
    """Verify validation rejects missing event_id or negative metrics without crashing."""
    collector = EventCollector(db_session=db_session)
    now = datetime.now(timezone.utc)

    # Missing event_id
    success, status, msg = collector.ingest_event({
        "event_time": now,
        "branch_id": "B001",
        "source": "ACTIVE_PROBE"
    })
    assert success is False
    assert status == "VALIDATION_FAILED"

    # Negative latency
    success, status, msg = collector.ingest_event({
        "event_id": "EVT-BAD-LAT",
        "event_time": now,
        "branch_id": "B001",
        "source": "ACTIVE_PROBE",
        "latency_ms": -50.0
    })
    assert success is False
    assert status == "VALIDATION_FAILED"

    # Packet loss > 100%
    success, status, msg = collector.ingest_event({
        "event_id": "EVT-BAD-LOSS",
        "event_time": now,
        "branch_id": "B001",
        "source": "ACTIVE_PROBE",
        "packet_loss_percent": 120.0
    })
    assert success is False
    assert status == "VALIDATION_FAILED"

    # Database remains uncorrupted
    assert db_session.query(Event).filter_by(event_id="EVT-BAD-LAT").first() is None


def test_duplicate_event_handling_idempotency(db_session):
    """Verify duplicate events are rejected idempotently without database duplication."""
    collector = EventCollector(db_session=db_session)
    now = datetime.now(timezone.utc)
    event_payload = {
        "event_id": "EVT-DUP-001",
        "event_time": now,
        "arrival_time": now,
        "branch_id": "B001",
        "source": "ACTIVE_PROBE",
        "latency_ms": 35.0
    }

    # First delivery
    success1, status1, _ = collector.ingest_event(event_payload)
    assert success1 is True
    assert status1 == "VALID"

    # Duplicate delivery
    success2, status2, _ = collector.ingest_event(event_payload)
    assert success2 is True
    assert status2 == "DUPLICATE_REJECTED"

    # Verify only ONE event row exists
    matching_events = db_session.query(Event).filter_by(event_id="EVT-DUP-001").all()
    assert len(matching_events) == 1

    # Verify audit log recorded duplicate rejection
    log_entry = db_session.query(EventProcessingLog).filter_by(event_id="EVT-DUP-001", processing_status="DUPLICATE_REJECTED").first()
    assert log_entry is not None


def test_out_of_order_event_handling(db_session):
    """Verify events arriving out of chronological order are detected and properly timestamped."""
    collector = EventCollector(db_session=db_session)
    t0 = datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=10)
    t2 = t0 + timedelta(seconds=20)
    t3 = t0 + timedelta(seconds=30)

    # Ingest t1 (10:00:10)
    collector.ingest_event({
        "event_id": "EVT-ORD-1",
        "event_time": t1,
        "arrival_time": t1,
        "branch_id": "B001",
        "source": "ACTIVE_PROBE",
        "latency_ms": 40.0
    })

    # Ingest t3 (10:00:30) - jumped ahead
    collector.ingest_event({
        "event_id": "EVT-ORD-3",
        "event_time": t3,
        "arrival_time": t3,
        "branch_id": "B001",
        "source": "ACTIVE_PROBE",
        "latency_ms": 42.0
    })

    # Ingest t2 (10:00:20) - arrived late/out of order
    success, status, msg = collector.ingest_event({
        "event_id": "EVT-ORD-2",
        "event_time": t2,
        "arrival_time": t3 + timedelta(seconds=1),
        "branch_id": "B001",
        "source": "ACTIVE_PROBE",
        "latency_ms": 41.0
    })

    assert success is True
    assert status == "OUT_OF_ORDER"

    # Query all events ordered by event_time to verify reconstruction
    ordered_events = db_session.query(Event).filter(Event.event_id.like("EVT-ORD%")).order_by(Event.event_time.asc()).all()
    assert [e.event_id for e in ordered_events] == ["EVT-ORD-1", "EVT-ORD-2", "EVT-ORD-3"]


def test_delayed_event_handling(db_session):
    """Verify events arriving after significant transit delay are flagged without losing historical position."""
    collector = EventCollector(db_session=db_session)
    event_time = datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc)
    # Arrived 120s later (delay threshold is 60s)
    arrival_time = event_time + timedelta(seconds=120)

    success, status, msg = collector.ingest_event({
        "event_id": "EVT-DELAYED-1",
        "event_time": event_time,
        "arrival_time": arrival_time,
        "branch_id": "B001",
        "source": "ACTIVE_PROBE",
        "latency_ms": 45.0
    })

    assert success is True
    assert status == "DELAYED"

    db_evt = db_session.query(Event).filter_by(event_id="EVT-DELAYED-1").first()
    assert db_evt.event_time == event_time.replace(tzinfo=None)


def test_event_buffering_and_recovery(db_session):
    """Simulate collector disconnection, local buffering, and ordered recovery."""
    buffer = EventBuffer()
    collector = EventCollector(db_session=db_session, buffer=buffer)
    now = datetime.now(timezone.utc)

    # 1. Simulate interruption
    buffer.set_interrupted(True)

    events_to_buffer = [
        {
            "event_id": f"EVT-BUF-{i}",
            "event_time": now + timedelta(seconds=i * 5),
            "arrival_time": now + timedelta(seconds=i * 5),
            "branch_id": "B001",
            "source": "ACTIVE_PROBE",
            "latency_ms": 30.0 + i
        }
        for i in range(5)
    ]

    for evt in events_to_buffer:
        success, status, _ = collector.ingest_event(evt)
        assert status == "BUFFERED"

    assert buffer.size() == 5
    assert db_session.query(Event).filter(Event.event_id.like("EVT-BUF%")).count() == 0

    # 2. Restore connectivity and recover buffer
    buffer.set_interrupted(False)
    recovery_result = collector.recover_buffer()

    assert recovery_result["recovered_count"] == 5
    assert buffer.size() == 0
    # All 5 events now persisted in database
    recovered_in_db = db_session.query(Event).filter(Event.event_id.like("EVT-BUF%")).order_by(Event.event_time.asc()).all()
    assert len(recovered_in_db) == 5
    assert [e.event_id for e in recovered_in_db] == [f"EVT-BUF-{i}" for i in range(5)]
