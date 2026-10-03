"""Data validation engine for ingested telemetry events."""
from datetime import datetime
from typing import Tuple, Dict, Any, Optional
from pydantic import ValidationError
from src.models.schemas import EventCreate


def validate_event_data(data: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validates an incoming event dictionary.
    Returns:
        (is_valid: bool, error_reason: Optional[str], validated_dict: Optional[dict])
    Ensures that invalid data never crashes the collector and generates structured audit logs.
    """
    if not isinstance(data, dict):
        return False, "Malformed payload: payload must be a JSON/dict object", None

    event_id = data.get("event_id")
    if not event_id or not str(event_id).strip():
        return False, "Missing or empty mandatory field: event_id", None

    branch_id = data.get("branch_id")
    if not branch_id or not str(branch_id).strip():
        return False, "Missing or empty mandatory field: branch_id", None

    source = data.get("source")
    valid_sources = {"ACTIVE_PROBE", "WIFI", "APPLICATION", "USER_REPORT"}
    if not source or source not in valid_sources:
        return False, f"Invalid source '{source}'; must be one of {valid_sources}", None

    event_time = data.get("event_time")
    if not event_time:
        return False, "Missing mandatory field: event_time", None

    # Handle string timestamp parsing if received via HTTP JSON
    if isinstance(event_time, str):
        try:
            # Replace Z with UTC offset if present
            cleaned_time = event_time.replace("Z", "+00:00")
            parsed_time = datetime.fromisoformat(cleaned_time)
            data["event_time"] = parsed_time
        except Exception as e:
            return False, f"Invalid ISO timestamp format for event_time: {str(e)}", None

    try:
        # Validate through Pydantic model for range checks
        validated = EventCreate(**data)
        return True, None, validated.model_dump()
    except ValidationError as ve:
        error_msgs = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in ve.errors()])
        return False, f"Validation constraint violation: {error_msgs}", None
    except Exception as ex:
        return False, f"Unexpected validation exception: {str(ex)}", None
