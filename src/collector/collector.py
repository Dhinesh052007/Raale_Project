"""Event collector service coordinating validation, deduplication, ordering, and buffer recovery."""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Tuple, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.models.db import Event, EventProcessingLog, Branch
from src.collector.validator import validate_event_data
from src.collector.buffer import EventBuffer


class EventCollector:
    """
    Central collector service that ingests multi-source branch telemetry.
    Guarantees validation, idempotent deduplication, out-of-order handling,
    delayed event reconciliation, and safe recovery of buffered events.
    """

    def __init__(self, db_session: Session, buffer: Optional[EventBuffer] = None):
        self.db = db_session
        self.buffer = buffer or EventBuffer()
        # In-memory tracking of the latest observed event timestamp per branch for out-of-order detection
        self.latest_event_times: Dict[str, datetime] = {}
        # Delay threshold: events arriving more than 60s after occurrence are flagged as DELAYED
        self.delay_threshold_seconds = 60.0

    def ingest_event(
        self,
        raw_data: Dict[str, Any],
        is_recovered: bool = False
    ) -> Tuple[bool, str, str]:
        """
        Ingest a single event.
        Returns:
            (success: bool, status: str, message: str)
            status can be:
                'VALID', 'DUPLICATE_REJECTED', 'OUT_OF_ORDER', 'DELAYED',
                'VALIDATION_FAILED', 'BUFFERED', 'RECOVERED'
        """
        # 1. If collector network connection is interrupted, divert to buffer
        if self.buffer.is_interrupted and not is_recovered:
            self.buffer.push(raw_data)
            evt_id = raw_data.get("event_id", "UNKNOWN")
            self._log_processing(evt_id, "BUFFERED", "Collector link interrupted; queued in local edge buffer")
            return True, "BUFFERED", f"Event {evt_id} buffered during link interruption"

        # 2. Validate payload
        is_valid, error_reason, validated = validate_event_data(raw_data)
        event_id = raw_data.get("event_id", "UNKNOWN") if isinstance(raw_data, dict) else "UNKNOWN"

        if not is_valid:
            self._log_processing(event_id, "VALIDATION_FAILED", error_reason)
            return False, "VALIDATION_FAILED", f"Validation rejected: {error_reason}"

        # 3. Deduplication check (Idempotency)
        existing = self.db.query(Event).filter(Event.event_id == validated["event_id"]).first()
        if existing:
            reason = f"Duplicate event ID {validated['event_id']} received. Discarded idempotently."
            self._log_processing(validated["event_id"], "DUPLICATE_REJECTED", reason)
            return True, "DUPLICATE_REJECTED", reason

        # Ensure branch exists in database to satisfy foreign keys
        branch_id = validated["branch_id"]
        branch_exists = self.db.query(Branch).filter(Branch.branch_id == branch_id).first()
        if not branch_exists:
            new_branch = Branch(
                branch_id=branch_id,
                name=f"Branch {branch_id}",
                region="Default Region",
                wan_type="MPLS Primary"
            )
            self.db.add(new_branch)
            self.db.commit()

        # 4. Out-of-order and Delayed Event Detection
        event_time = validated["event_time"]
        arrival_time = validated.get("arrival_time") or datetime.now(timezone.utc)

        # Make timestamps timezone-aware for fair comparison
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        if arrival_time.tzinfo is None:
            arrival_time = arrival_time.replace(tzinfo=timezone.utc)

        processing_status = "VALID"
        log_reason = "Successfully processed and stored"

        # Check if event arrived out-of-order compared to previously seen events for this branch
        last_seen = self.latest_event_times.get(branch_id)
        if last_seen and event_time < last_seen:
            processing_status = "OUT_OF_ORDER"
            log_reason = f"Event arrived out of order (event_time {event_time} < latest seen {last_seen})"
        else:
            self.latest_event_times[branch_id] = event_time

        # Check if event was significantly delayed in transit
        delta_seconds = (arrival_time - event_time).total_seconds()
        if delta_seconds > self.delay_threshold_seconds:
            processing_status = "DELAYED"
            log_reason = f"Event arrived with significant transit delay ({delta_seconds:.1f}s > {self.delay_threshold_seconds}s)"

        if is_recovered:
            processing_status = "RECOVERED"
            log_reason = "Recovered from edge buffer after collector link restoration"

        # SQLite stores naive datetimes; strip tzinfo for DB persistence
        db_event_time = event_time.replace(tzinfo=None) if event_time.tzinfo else event_time
        db_arrival_time = arrival_time.replace(tzinfo=None) if arrival_time.tzinfo else arrival_time

        # 5. Persist Event
        try:
            event_record = Event(
                event_id=validated["event_id"],
                event_time=db_event_time,
                arrival_time=db_arrival_time,
                branch_id=validated["branch_id"],
                source=validated["source"],
                latency_ms=validated.get("latency_ms"),
                jitter_ms=validated.get("jitter_ms"),
                packet_loss_percent=validated.get("packet_loss_percent"),
                dns_response_ms=validated.get("dns_response_ms"),
                wifi_rssi=validated.get("wifi_rssi"),
                wifi_retry_rate=validated.get("wifi_retry_rate"),
                channel_utilisation=validated.get("channel_utilisation"),
                application_response_ms=validated.get("application_response_ms"),
                http_status=validated.get("http_status"),
                transaction_duration_ms=validated.get("transaction_duration_ms"),
                user_report=validated.get("user_report"),
                sequence_number=validated.get("sequence_number")
            )
            self.db.add(event_record)
            self.db.commit()
            self._log_processing(validated["event_id"], processing_status, log_reason)
            return True, processing_status, log_reason
        except IntegrityError:
            self.db.rollback()
            reason = f"Integrity collision for event {validated['event_id']}. Deduplicated."
            self._log_processing(validated["event_id"], "DUPLICATE_REJECTED", reason)
            return True, "DUPLICATE_REJECTED", reason
        except Exception as e:
            self.db.rollback()
            err_msg = f"Database insertion error: {str(e)}"
            self._log_processing(validated["event_id"], "VALIDATION_FAILED", err_msg)
            return False, "VALIDATION_FAILED", err_msg

    def recover_buffer(self) -> Dict[str, Any]:
        """
        Drain all buffered events, sort chronologically by event_time,
        and ingest them sequentially through validation, deduplication, and persistence.
        """
        buffered = self.buffer.drain_all()
        if not buffered:
            return {"recovered_count": 0, "message": "Buffer is empty; nothing to recover."}

        # Sort chronologically by event_time to reconstruct ground-truth order
        def get_event_time(item):
            t = item.get("event_time")
            if isinstance(t, str):
                return datetime.fromisoformat(t.replace("Z", "+00:00"))
            return t or datetime.min

        buffered.sort(key=get_event_time)

        recovered_count = 0
        duplicates_count = 0
        rejected_count = 0

        for item in buffered:
            success, status, _ = self.ingest_event(item, is_recovered=True)
            if status == "RECOVERED":
                recovered_count += 1
            elif status == "DUPLICATE_REJECTED":
                duplicates_count += 1
            elif not success:
                rejected_count += 1

        return {
            "recovered_count": recovered_count,
            "duplicates_ignored": duplicates_count,
            "rejected_count": rejected_count,
            "total_processed": len(buffered)
        }

    def _log_processing(self, event_id: str, status: str, reason: Optional[str] = None):
        """Append to the processing log for auditability."""
        try:
            log_entry = EventProcessingLog(
                event_id=event_id,
                processing_status=status,
                reason=reason,
                processed_at=datetime.now(timezone.utc)
            )
            self.db.add(log_entry)
            self.db.commit()
        except Exception:
            self.db.rollback()

    def get_integrity_stats(self) -> Dict[str, int]:
        """Returns summary counts across all processed event statuses."""
        from sqlalchemy import func
        stats = {
            "total_events": 0,
            "valid_events": 0,
            "duplicate_events": 0,
            "delayed_events": 0,
            "out_of_order_events": 0,
            "rejected_events": 0,
            "recovered_events": 0,
            "buffered_events": self.buffer.size()
        }
        query = self.db.query(EventProcessingLog.processing_status, func.count(EventProcessingLog.id)).group_by(EventProcessingLog.processing_status).all()
        for status, count in query:
            if status == "VALID":
                stats["valid_events"] += count
            elif status == "DUPLICATE_REJECTED":
                stats["duplicate_events"] += count
            elif status == "DELAYED":
                stats["delayed_events"] += count
            elif status == "OUT_OF_ORDER":
                stats["out_of_order_events"] += count
            elif status == "VALIDATION_FAILED":
                stats["rejected_events"] += count
            elif status == "RECOVERED":
                stats["recovered_events"] += count

        stats["total_events"] = self.db.query(Event).count()
        return stats
