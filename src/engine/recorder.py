"""Experience Recorder engine orchestrating correlation, incident lifecycles, and forensic evidence windows."""
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from src.models.db import Event, Incident, UserReport, Branch
from src.engine.localisation import LocalisationEngine


class ExperienceRecorder:
    """
    Core Experience Recorder engine.
    Continuously correlates multi-source signals, manages incident lifecycles
    (NORMAL -> SUSPECTED -> ACTIVE -> RECOVERED), performs explainable fault localisation,
    and preserves forensic evidence windows (2 min before + incident + 2 min after).
    """

    def __init__(self, db_session: Session):
        self.db = db_session
        self.localisation_engine = LocalisationEngine()
        self.correlation_window_seconds = 180.0  # Events within 3 min clustered into same incident
        self.recovery_cooldown_seconds = 60.0    # 60s of normal events triggers recovery

    def process_telemetry_batch(self, branch_id: str, current_time: Optional[datetime] = None) -> Optional[Incident]:
        """
        Evaluate recent events for a branch, update or create active incidents,
        and trigger recovery when branch telemetry returns to normal baseline.
        """
        now = current_time or datetime.now(timezone.utc)
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)

        # Look for any open (SUSPECTED or ACTIVE) incident for this branch
        active_incident = self.db.query(Incident).filter(
            Incident.branch_id == branch_id,
            Incident.status.in_(["SUSPECTED", "ACTIVE"])
        ).order_by(Incident.start_time.desc()).first()

        # Query recent events for this branch within correlation window
        window_start = now - timedelta(seconds=self.correlation_window_seconds)
        recent_events = self.db.query(Event).filter(
            Event.branch_id == branch_id,
            Event.event_time >= window_start
        ).order_by(Event.event_time.asc()).all()

        recent_dicts = [
            {
                "event_id": e.event_id,
                "event_time": e.event_time,
                "source": e.source,
                "latency_ms": e.latency_ms,
                "jitter_ms": e.jitter_ms,
                "packet_loss_percent": e.packet_loss_percent,
                "dns_response_ms": e.dns_response_ms,
                "wifi_rssi": e.wifi_rssi,
                "wifi_retry_rate": e.wifi_retry_rate,
                "channel_utilisation": e.channel_utilisation,
                "application_response_ms": e.application_response_ms,
                "http_status": e.http_status,
                "transaction_duration_ms": e.transaction_duration_ms,
                "user_report": e.user_report
            }
            for e in recent_events
        ]

        # Query associated user reports
        user_reports = self.db.query(UserReport).filter(
            UserReport.branch_id == branch_id,
            UserReport.event_time >= window_start
        ).all()
        user_report_count = len(user_reports)

        # Evaluate localisation over the recent correlation window
        analysis = self.localisation_engine.localise(recent_dicts, user_report_count=user_report_count)
        is_abnormal = analysis["probable_cause"] not in ("Normal / Transient noise", "Insufficient evidence")

        # Check cooldown window (last 60s) to see if failure has subsided
        cooldown_start = now - timedelta(seconds=self.recovery_cooldown_seconds)
        cooldown_events = [e for e in recent_events if e.event_time >= cooldown_start]
        cooldown_dicts = [
            e for e in recent_dicts
            if (e["event_time"] >= cooldown_start if isinstance(e["event_time"], datetime) else True)
        ]
        cooldown_analysis = self.localisation_engine.localise(cooldown_dicts)
        cooldown_is_normal = cooldown_analysis["probable_cause"] in ("Normal / Transient noise", "Insufficient evidence")

        # Lifecycle state machine
        if is_abnormal and not (active_incident and cooldown_is_normal and len(cooldown_dicts) >= 3):
            # Check highest metric peaks
            latencies = [e["latency_ms"] for e in recent_dicts if e.get("latency_ms") is not None]
            losses = [e["packet_loss_percent"] for e in recent_dicts if e.get("packet_loss_percent") is not None]
            apps = [e["application_response_ms"] for e in recent_dicts if e.get("application_response_ms") is not None]

            peak_lat = max(latencies) if latencies else None
            peak_loss = max(losses) if losses else None
            peak_app = max(apps) if apps else None

            if not active_incident:
                # Create NEW incident
                incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
                earliest_time = recent_events[0].event_time if recent_events else now
                new_incident = Incident(
                    incident_id=incident_id,
                    branch_id=branch_id,
                    start_time=earliest_time,
                    end_time=None,
                    status="ACTIVE",
                    probable_cause=analysis["probable_cause"],
                    peak_latency=peak_lat,
                    peak_packet_loss=peak_loss,
                    peak_application_response=peak_app,
                    user_report_count=user_report_count,
                    severity=analysis["severity"],
                    supporting_evidence=json.dumps(analysis["evidence"])
                )
                self.db.add(new_incident)
                self.db.commit()
                return new_incident
            else:
                # Update existing ACTIVE incident
                active_incident.status = "ACTIVE"
                active_incident.probable_cause = analysis["probable_cause"]
                if peak_lat and (active_incident.peak_latency is None or peak_lat > active_incident.peak_latency):
                    active_incident.peak_latency = peak_lat
                if peak_loss and (active_incident.peak_packet_loss is None or peak_loss > active_incident.peak_packet_loss):
                    active_incident.peak_packet_loss = peak_loss
                if peak_app and (active_incident.peak_application_response is None or peak_app > active_incident.peak_application_response):
                    active_incident.peak_application_response = peak_app
                active_incident.user_report_count = max(active_incident.user_report_count, user_report_count)
                active_incident.severity = analysis["severity"]
                active_incident.supporting_evidence = json.dumps(analysis["evidence"])
                self.db.commit()
                return active_incident

        else:
            # Baseline is normal or cooldown shows complete recovery
            if active_incident:
                active_incident.status = "RECOVERED"
                active_incident.end_time = now
                active_incident.duration_seconds = max(10.0, (now - active_incident.start_time).total_seconds())
                self.db.commit()
                return active_incident

        return active_incident

    def get_incident_evidence_window(self, incident_id: str) -> Dict[str, Any]:
        """
        Forensic Evidence Window:
        Captures 2 minutes BEFORE start_time + INCIDENT DURATION + 2 minutes AFTER end_time.
        Reconstructs the full historical context for root-cause analysis.
        """
        incident = self.db.query(Incident).filter(Incident.incident_id == incident_id).first()
        if not incident:
            return {"error": f"Incident {incident_id} not found"}

        pre_window_start = incident.start_time - timedelta(minutes=2)
        end_ref = incident.end_time or datetime.now(timezone.utc).replace(tzinfo=None)
        post_window_end = end_ref + timedelta(minutes=2)

        # Query all events in the 2-min before + incident + 2-min after window
        events = self.db.query(Event).filter(
            Event.branch_id == incident.branch_id,
            Event.event_time >= pre_window_start,
            Event.event_time <= post_window_end
        ).order_by(Event.event_time.asc()).all()

        # Query user reports in this timeline
        user_reports = self.db.query(UserReport).filter(
            UserReport.branch_id == incident.branch_id,
            UserReport.event_time >= pre_window_start,
            UserReport.event_time <= post_window_end
        ).order_by(UserReport.event_time.asc()).all()

        # Classify events by window phase
        timeline = []
        for e in events:
            phase = "INCIDENT_PERIOD"
            if e.event_time < incident.start_time:
                phase = "PRE_INCIDENT_BASELINE"
            elif incident.end_time and e.event_time > incident.end_time:
                phase = "POST_RECOVERY_BASELINE"

            timeline.append({
                "phase": phase,
                "event_id": e.event_id,
                "event_time": e.event_time.isoformat(),
                "source": e.source,
                "latency_ms": e.latency_ms,
                "jitter_ms": e.jitter_ms,
                "packet_loss_percent": e.packet_loss_percent,
                "dns_response_ms": e.dns_response_ms,
                "wifi_rssi": e.wifi_rssi,
                "wifi_retry_rate": e.wifi_retry_rate,
                "channel_utilisation": e.channel_utilisation,
                "application_response_ms": e.application_response_ms,
                "http_status": e.http_status,
                "transaction_duration_ms": e.transaction_duration_ms,
                "user_report": e.user_report
            })

        evidence_payload = json.loads(incident.supporting_evidence) if incident.supporting_evidence else {}

        return {
            "incident_id": incident.incident_id,
            "branch_id": incident.branch_id,
            "start_time": incident.start_time.isoformat(),
            "end_time": incident.end_time.isoformat() if incident.end_time else None,
            "status": incident.status,
            "duration_seconds": incident.duration_seconds,
            "probable_cause": incident.probable_cause,
            "severity": incident.severity,
            "peak_latency": incident.peak_latency,
            "peak_packet_loss": incident.peak_packet_loss,
            "peak_application_response": incident.peak_application_response,
            "user_report_count": incident.user_report_count,
            "evidence_breakdown": evidence_payload,
            "window_bounds": {
                "pre_window_start": pre_window_start.isoformat(),
                "post_window_end": post_window_end.isoformat()
            },
            "timeline_events": timeline,
            "user_reports": [
                {
                    "report_id": ur.report_id,
                    "event_time": ur.event_time.isoformat(),
                    "location": ur.location,
                    "description": ur.description,
                    "severity": ur.severity
                }
                for ur in user_reports
            ]
        }
