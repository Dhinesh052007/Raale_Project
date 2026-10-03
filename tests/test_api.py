"""Integration tests for FastAPI REST endpoints using TestClient."""
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.models.db import Base, get_db, init_db
from src.api.main import app


@pytest.fixture
def client():
    # Use isolated shared in-memory SQLite database for API tests
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    init_db(test_engine)
    TestingSession = sessionmaker(bind=test_engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_endpoint(client):
    """Verify health check returns healthy status."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "counts" in data


def test_branch_endpoints(client):
    """Verify seeding and listing branches."""
    # Seed 50 branches
    seed_res = client.post("/api/v1/simulation/seed-branches?count=50")
    assert seed_res.status_code == 200

    # List branches
    list_res = client.get("/api/v1/branches")
    assert list_res.status_code == 200
    branches = list_res.json()
    assert len(branches) == 50
    assert branches[0]["branch_id"] == "B001"

    # Get single branch
    single_res = client.get("/api/v1/branches/B001")
    assert single_res.status_code == 200
    b_data = single_res.json()
    assert b_data["branch_id"] == "B001"
    assert b_data["current_status"] == "HEALTHY"


def test_event_ingestion_and_query(client):
    """Verify single and batch ingestion via API."""
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "event_id": "API-EVT-001",
        "event_time": now,
        "arrival_time": now,
        "branch_id": "B001",
        "source": "ACTIVE_PROBE",
        "latency_ms": 38.5,
        "packet_loss_percent": 0.0
    }
    post_res = client.post("/api/v1/events", json=payload)
    assert post_res.status_code == 200
    res_json = post_res.json()
    assert res_json["success"] is True
    assert res_json["status"] == "VALID"

    # Query events
    query_res = client.get("/api/v1/events?branch_id=B001")
    assert query_res.status_code == 200
    events = query_res.json()
    assert len(events) >= 1
    assert events[0]["event_id"] == "API-EVT-001"


def test_failure_injection_and_incident_evidence_window_api(client):
    """Verify failure injection triggers incident detection, correlation, and full evidence window via API."""
    # Seed branches
    client.post("/api/v1/simulation/seed-branches?count=10")

    # Inject WAN degradation on B003
    inject_res = client.post("/api/v1/simulation/inject-failure?branch_id=B003&failure_type=WAN_DEGRADATION&duration_seconds=90")
    assert inject_res.status_code == 200
    inj_data = inject_res.json()
    assert inj_data["incident_detected"] is True
    assert inj_data["probable_cause"] == "WAN degradation"
    incident_id = inj_data["incident_id"]

    # Query incidents list
    inc_res = client.get("/api/v1/incidents?branch_id=B003")
    assert inc_res.status_code == 200
    incidents = inc_res.json()
    assert len(incidents) >= 1

    # Query complete forensic evidence window
    detail_res = client.get(f"/api/v1/incidents/{incident_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["incident_id"] == incident_id
    assert detail["probable_cause"] == "WAN degradation"
    assert "timeline_events" in detail
    assert len(detail["timeline_events"]) > 0

    # Verify user reports recorded in evidence bundle
    assert "user_reports" in detail
    assert len(detail["user_reports"]) >= 1


def test_buffer_outage_simulation_and_recovery_api(client):
    """Verify collector buffer outage toggle and recovery via API."""
    # Turn ON interruption mode
    outage_on = client.post("/api/v1/buffer/simulate-outage?interrupted=true")
    assert outage_on.status_code == 200
    assert outage_on.json()["collector_link_interrupted"] is True

    # Ingest event while disconnected -> should be buffered
    now = datetime.now(timezone.utc).isoformat()
    buf_payload = {
        "event_id": "API-EVT-BUF-1",
        "event_time": now,
        "arrival_time": now,
        "branch_id": "B002",
        "source": "ACTIVE_PROBE",
        "latency_ms": 32.0
    }
    ing_res = client.post("/api/v1/events", json=buf_payload)
    assert ing_res.json()["status"] == "BUFFERED"

    # Turn OFF interruption mode
    outage_off = client.post("/api/v1/buffer/simulate-outage?interrupted=false")
    assert outage_off.status_code == 200
    assert outage_off.json()["collector_link_interrupted"] is False

    # Recover buffer
    rec_res = client.post("/api/v1/buffer/recover")
    assert rec_res.status_code == 200
    assert rec_res.json()["recovered_count"] >= 1
