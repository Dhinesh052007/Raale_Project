"""FastAPI API routes for Experience Recorder backend."""
import os
import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.models.db import get_db, Branch, Event, Incident, UserReport, EventProcessingLog, init_db
from src.models.schemas import (
    BranchResponse,
    EventCreate,
    EventResponse,
    IncidentResponse,
    IncidentDetailResponse,
    UserReportCreate,
    UserReportResponse,
    ProcessingLogResponse,
    IntegrityStats,
    IngestionResult,
    BatchIngestionResult,
    ExperimentScenarioRequest
)
from src.collector.collector import EventCollector
from src.collector.buffer import EventBuffer
from src.engine.recorder import ExperienceRecorder
from src.simulator.branch_generator import generate_branch_inventory
from src.simulator.branch_simulator import BranchSimulator
from src.simulator.failure_scenarios import FailureScenario, FailureType

router = APIRouter()

# Global in-memory edge buffer instance for collector disconnection simulation
global_event_buffer = EventBuffer()


@router.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint returning system status and basic telemetry counts."""
    total_events = db.query(Event).count()
    total_incidents = db.query(Incident).count()
    total_branches = db.query(Branch).count()
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "connected",
        "counts": {
            "branches": total_branches,
            "events": total_events,
            "incidents": total_incidents,
            "buffered_events": global_event_buffer.size()
        },
        "collector_link_interrupted": global_event_buffer.is_interrupted
    }


@router.post("/simulation/seed-branches", tags=["Simulation"])
def seed_branches(count: int = 50, seed: int = 42, db: Session = Depends(get_db)):
    """Initialize branch topology database with 50+ deterministic branches."""
    branch_defs = generate_branch_inventory(num_branches=count, seed=seed)
    created = 0
    for b in branch_defs:
        existing = db.query(Branch).filter(Branch.branch_id == b["branch_id"]).first()
        if not existing:
            new_branch = Branch(
                branch_id=b["branch_id"],
                name=b["name"],
                region=b["region"],
                wan_type=b["wan_type"]
            )
            db.add(new_branch)
            created += 1
    db.commit()
    return {"message": f"Successfully seeded {created} branches (total {len(branch_defs)})"}


@router.get("/branches", response_model=List[BranchResponse], tags=["Branches"])
def list_branches(db: Session = Depends(get_db)):
    """List all configured branches."""
    branches = db.query(Branch).order_by(Branch.branch_id.asc()).all()
    if not branches:
        # Seed if empty
        seed_branches(count=50, seed=42, db=db)
        branches = db.query(Branch).order_by(Branch.branch_id.asc()).all()
    return branches


@router.get("/branches/{branch_id}", tags=["Branches"])
def get_branch_detail(branch_id: str, db: Session = Depends(get_db)):
    """Retrieve detailed telemetry overview and status for a specific branch."""
    branch = db.query(Branch).filter(Branch.branch_id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail=f"Branch {branch_id} not found")

    recent_events = db.query(Event).filter(Event.branch_id == branch_id).order_by(Event.event_time.desc()).limit(20).all()
    active_incident = db.query(Incident).filter(Incident.branch_id == branch_id, Incident.status == "ACTIVE").first()
    recent_reports = db.query(UserReport).filter(UserReport.branch_id == branch_id).order_by(UserReport.event_time.desc()).limit(5).all()

    return {
        "branch_id": branch.branch_id,
        "name": branch.name,
        "region": branch.region,
        "wan_type": branch.wan_type,
        "current_status": "DEGRADED" if active_incident else "HEALTHY",
        "active_incident": {
            "incident_id": active_incident.incident_id,
            "probable_cause": active_incident.probable_cause,
            "severity": active_incident.severity,
            "start_time": active_incident.start_time.isoformat()
        } if active_incident else None,
        "recent_event_count": len(recent_events),
        "recent_user_reports": [
            {
                "report_id": r.report_id,
                "event_time": r.event_time.isoformat(),
                "description": r.description,
                "severity": r.severity
            }
            for r in recent_reports
        ]
    }


@router.post("/events", tags=["Collector"])
def ingest_event(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """Ingest a single telemetry event through collector (validation, idempotency, ordering)."""
    collector = EventCollector(db_session=db, buffer=global_event_buffer)
    success, status_code, message = collector.ingest_event(payload)

    # Trigger Experience Recorder state evaluation if valid
    if success and status_code in ("VALID", "OUT_OF_ORDER", "DELAYED", "RECOVERED"):
        recorder = ExperienceRecorder(db_session=db)
        recorder.process_telemetry_batch(payload.get("branch_id"))

    return {
        "success": success,
        "status": status_code,
        "message": message,
        "event_id": payload.get("event_id")
    }


@router.post("/events/batch", response_model=BatchIngestionResult, tags=["Collector"])
def ingest_events_batch(events: List[Dict[str, Any]], db: Session = Depends(get_db)):
    """Batch ingest multiple telemetry events."""
    collector = EventCollector(db_session=db, buffer=global_event_buffer)
    recorder = ExperienceRecorder(db_session=db)

    accepted = 0
    duplicates = 0
    out_of_order = 0
    delayed = 0
    rejected = 0
    details = []
    affected_branches = set()

    for item in events:
        success, proc_status, msg = collector.ingest_event(item)
        evt_id = item.get("event_id", "UNKNOWN")
        if proc_status in ("VALID", "RECOVERED"):
            accepted += 1
            affected_branches.add(item.get("branch_id"))
        elif proc_status == "DUPLICATE_REJECTED":
            duplicates += 1
        elif proc_status == "OUT_OF_ORDER":
            out_of_order += 1
            affected_branches.add(item.get("branch_id"))
        elif proc_status == "DELAYED":
            delayed += 1
            affected_branches.add(item.get("branch_id"))
        else:
            rejected += 1

        details.append(IngestionResult(success=success, status=proc_status, event_id=evt_id, message=msg))

    # Evaluate recorder for each branch
    for b_id in affected_branches:
        if b_id:
            recorder.process_telemetry_batch(b_id)

    return BatchIngestionResult(
        total_received=len(events),
        accepted=accepted,
        duplicates_ignored=duplicates,
        out_of_order_accepted=out_of_order,
        delayed_accepted=delayed,
        rejected=rejected,
        details=details
    )


@router.get("/events", response_model=List[EventResponse], tags=["Collector"])
def list_events(
    branch_id: Optional[str] = Query(None, description="Filter by branch ID"),
    source: Optional[str] = Query(None, description="Filter by telemetry source"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Retrieve raw telemetry events with optional filters."""
    query = db.query(Event)
    if branch_id:
        query = query.filter(Event.branch_id == branch_id)
    if source:
        query = query.filter(Event.source == source)
    return query.order_by(desc(Event.event_time)).limit(limit).all()


@router.get("/incidents", response_model=List[IncidentResponse], tags=["Incidents"])
def list_incidents(
    branch_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """List recorded incidents (both active and historical recovered incidents)."""
    query = db.query(Incident)
    if branch_id:
        query = query.filter(Incident.branch_id == branch_id)
    if status:
        query = query.filter(Incident.status == status)
    return query.order_by(desc(Incident.start_time)).all()


@router.get("/incidents/{incident_id}", tags=["Incidents"])
def get_incident_detail(incident_id: str, db: Session = Depends(get_db)):
    """
    Retrieve an incident with complete forensic evidence window:
    Includes 2 minutes BEFORE start + INCIDENT DURATION + 2 minutes AFTER recovery.
    """
    recorder = ExperienceRecorder(db_session=db)
    window = recorder.get_incident_evidence_window(incident_id)
    if "error" in window:
        raise HTTPException(status_code=404, detail=window["error"])
    return window


@router.post("/user-reports", tags=["User Reports"])
def create_user_report(report: UserReportCreate, db: Session = Depends(get_db)):
    """Submit a user complaint/report from branch."""
    import uuid
    report_id = report.report_id or f"URP-{uuid.uuid4().hex[:8].upper()}"
    new_report = UserReport(
        report_id=report_id,
        branch_id=report.branch_id,
        event_time=report.event_time.replace(tzinfo=None) if report.event_time.tzinfo else report.event_time,
        location=report.location,
        description=report.description,
        severity=report.severity
    )
    db.add(new_report)
    db.commit()

    # Also evaluate recorder
    recorder = ExperienceRecorder(db_session=db)
    recorder.process_telemetry_batch(report.branch_id)

    return {"message": "User report recorded successfully", "report_id": report_id}


@router.get("/user-reports", response_model=List[UserReportResponse], tags=["User Reports"])
def list_user_reports(branch_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """List user complaints."""
    query = db.query(UserReport)
    if branch_id:
        query = query.filter(UserReport.branch_id == branch_id)
    return query.order_by(desc(UserReport.event_time)).all()


@router.get("/collector/stats", response_model=IntegrityStats, tags=["Collector Integrity"])
def get_collector_integrity_stats(db: Session = Depends(get_db)):
    """Retrieve event integrity statistics (valid, duplicates, out of order, delayed, rejected, recovered)."""
    collector = EventCollector(db_session=db, buffer=global_event_buffer)
    stats = collector.get_integrity_stats()
    return IntegrityStats(**stats)


@router.post("/buffer/simulate-outage", tags=["Collector Integrity"])
def toggle_collector_outage(interrupted: bool = Query(..., description="True to simulate network cut, False to restore")):
    """Toggle edge buffer mode simulating collector network disconnection."""
    global_event_buffer.set_interrupted(interrupted)
    return {
        "collector_link_interrupted": global_event_buffer.is_interrupted,
        "buffered_events_count": global_event_buffer.size(),
        "message": "Collector link marked INTERRUPTED. Incoming events will be queued locally." if interrupted else "Collector link RESTORED. Buffered events can now be recovered."
    }


@router.post("/buffer/recover", tags=["Collector Integrity"])
def recover_buffered_events(db: Session = Depends(get_db)):
    """Flush and replay all buffered events through validation, deduplication, and ordered insertion."""
    collector = EventCollector(db_session=db, buffer=global_event_buffer)
    recovery_result = collector.recover_buffer()

    # Re-evaluate all branches that may have recovered events
    branches = db.query(Branch.branch_id).all()
    recorder = ExperienceRecorder(db_session=db)
    for (b_id,) in branches:
        recorder.process_telemetry_batch(b_id)

    return recovery_result


@router.post("/simulation/inject-failure", tags=["Simulation"])
def inject_failure_scenario(
    branch_id: str,
    failure_type: str = Query("WAN_DEGRADATION", enum=["WAN_DEGRADATION", "WIFI_DEGRADATION", "APPLICATION_DEGRADATION", "MULTIPLE_DEGRADATION"]),
    duration_seconds: int = 120,
    db: Session = Depends(get_db)
):
    """
    Inject a realistic intermittent service degradation into a branch and run
    a full simulation sequence: Normal (pre-baseline) -> Degraded -> Normal (post-baseline).
    """
    sim = BranchSimulator(num_branches=50, seed=42)
    collector = EventCollector(db_session=db, buffer=global_event_buffer)
    recorder = ExperienceRecorder(db_session=db)

    now = datetime.now(timezone.utc)
    t_start = now - timedelta(seconds=duration_seconds + 120)

    # 1. Generate 2 minutes of normal pre-incident baseline
    generated_events = []
    for s in range(0, 120, 10):
        t = t_start + timedelta(seconds=s)
        generated_events.append(sim.generate_probe_metric(branch_id, t))
        generated_events.append(sim.generate_wifi_metric(branch_id, t))
        generated_events.append(sim.generate_application_metric(branch_id, t))

    # 2. Generate Degraded failure period
    f_scenario = FailureScenario(
        failure_type=FailureType(failure_type),
        target_branch_id=branch_id,
        start_seconds=120,
        duration_seconds=duration_seconds
    )
    for s in range(120, 120 + duration_seconds, 10):
        t = t_start + timedelta(seconds=s)
        generated_events.append(sim.generate_probe_metric(branch_id, t, failure=f_scenario))
        generated_events.append(sim.generate_wifi_metric(branch_id, t, failure=f_scenario))
        generated_events.append(sim.generate_application_metric(branch_id, t, failure=f_scenario))

    # Ingest a user complaint in the middle of degradation
    user_report_bundle = sim.generate_user_report(
        branch_id,
        t_start + timedelta(seconds=120 + (duration_seconds // 2)),
        description=f"Intermittent degradation experienced during {failure_type} scenario."
    )
    generated_events.append(user_report_bundle["event"])
    # Store user report record
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

    # 3. Generate 2 minutes of post-recovery baseline
    for s in range(120 + duration_seconds, 120 + duration_seconds + 120, 10):
        t = t_start + timedelta(seconds=s)
        generated_events.append(sim.generate_probe_metric(branch_id, t))
        generated_events.append(sim.generate_wifi_metric(branch_id, t))
        generated_events.append(sim.generate_application_metric(branch_id, t))

    # Ingest all events
    for evt in generated_events:
        collector.ingest_event(evt)

    # Process through recorder
    incident = recorder.process_telemetry_batch(branch_id, current_time=t_start + timedelta(seconds=120 + duration_seconds + 60))

    return {
        "status": "Simulation completed",
        "branch_id": branch_id,
        "failure_type": failure_type,
        "total_events_generated": len(generated_events),
        "incident_detected": incident is not None,
        "incident_id": incident.incident_id if incident else None,
        "incident_status": incident.status if incident else None,
        "probable_cause": incident.probable_cause if incident else None
    }


@router.post("/experiments/run", tags=["Experiments"])
def trigger_benchmark_suite(
    num_incidents: int = Query(100, ge=10, le=500),
    num_normal_controls: int = Query(50, ge=5, le=100),
    random_seed: int = Query(42),
    db: Session = Depends(get_db)
):
    """
    Run automated 100-incident benchmark suite comparing Baseline vs Experience Recorder.
    Calculates actual mathematical metrics (Detection rate, Miss rate, Localisation accuracy,
    False positive rate, Event integrity) and generates structured error analysis.
    """
    from src.experiments.benchmark import ExperimentRunner
    runner = ExperimentRunner(db=db, seed=random_seed)
    results = runner.run_benchmark(num_incidents=num_incidents, num_normal_controls=num_normal_controls)
    return results


@router.get("/experiments/results", tags=["Experiments"])
def get_benchmark_results(db: Session = Depends(get_db)):
    """Retrieve the latest experimental benchmark report."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    results_path = os.path.join(base_dir, "data", "experiment_results.json")
    if os.path.exists(results_path):
        with open(results_path, "r") as f:
            return json.load(f)

    # Run on-demand if not yet executed
    from src.experiments.benchmark import ExperimentRunner
    runner = ExperimentRunner(db=db, seed=42)
    return runner.run_benchmark(num_incidents=100, num_normal_controls=50)

