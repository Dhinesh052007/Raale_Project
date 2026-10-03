"""Unit tests for database initialization, models, and Pydantic validation."""
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.db import Base, Branch, Event, Incident, UserReport, EventProcessingLog, init_db
from src.models.schemas import EventCreate, UserReportCreate
from pydantic import ValidationError


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    yield session
    session.close()


def test_database_initialization(test_db):
    """Verify that all core tables can be created and queried in SQLite."""
    branch = Branch(branch_id="B001", name="Downtown Branch", region="North", wan_type="MPLS Primary")
    test_db.add(branch)
    test_db.commit()

    queried_branch = test_db.query(Branch).filter_by(branch_id="B001").first()
    assert queried_branch is not None
    assert queried_branch.name == "Downtown Branch"


def test_event_persistence_with_foreign_key(test_db):
    """Verify event creation associated with a branch."""
    branch = Branch(branch_id="B007", name="Financial Center B007", region="Metro")
    test_db.add(branch)
    test_db.commit()

    now = datetime.now(timezone.utc)
    event = Event(
        event_id="EVT-001",
        event_time=now,
        arrival_time=now,
        branch_id="B007",
        source="ACTIVE_PROBE",
        latency_ms=45.2,
        jitter_ms=3.1,
        packet_loss_percent=0.0,
        dns_response_ms=25.0
    )
    test_db.add(event)
    test_db.commit()

    queried_event = test_db.query(Event).filter_by(event_id="EVT-001").first()
    assert queried_event is not None
    assert queried_event.branch_id == "B007"
    assert queried_event.latency_ms == 45.2
    assert queried_event.branch.name == "Financial Center B007"


def test_event_pydantic_validation():
    """Verify validation for negative metrics or out-of-range packet loss."""
    now = datetime.now(timezone.utc)

    # Valid event
    valid_data = {
        "event_id": "EVT-TEST-1",
        "event_time": now,
        "branch_id": "B001",
        "source": "ACTIVE_PROBE",
        "latency_ms": 50.0,
        "packet_loss_percent": 2.5
    }
    event_schema = EventCreate(**valid_data)
    assert event_schema.latency_ms == 50.0

    # Negative latency should fail validation
    with pytest.raises(ValidationError):
        EventCreate(
            event_id="EVT-BAD-1",
            event_time=now,
            branch_id="B001",
            source="ACTIVE_PROBE",
            latency_ms=-10.0
        )

    # Packet loss > 100% should fail validation
    with pytest.raises(ValidationError):
        EventCreate(
            event_id="EVT-BAD-2",
            event_time=now,
            branch_id="B001",
            source="ACTIVE_PROBE",
            packet_loss_percent=150.0
        )
