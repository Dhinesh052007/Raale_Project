"""Failure injection models and scenario definitions."""
from enum import Enum
from typing import Dict, Any


class FailureType(str, Enum):
    NONE = "NONE"
    WAN_DEGRADATION = "WAN_DEGRADATION"
    WIFI_DEGRADATION = "WIFI_DEGRADATION"
    APPLICATION_DEGRADATION = "APPLICATION_DEGRADATION"
    MULTIPLE_DEGRADATION = "MULTIPLE_DEGRADATION"


class FailureScenario:
    """Represents an active or configured failure injection instance."""

    def __init__(
        self,
        failure_type: FailureType,
        target_branch_id: str,
        start_seconds: int = 120,
        duration_seconds: int = 180,
        severity: str = "HIGH"
    ):
        self.failure_type = failure_type
        self.target_branch_id = target_branch_id
        self.start_seconds = start_seconds
        self.duration_seconds = duration_seconds
        self.end_seconds = start_seconds + duration_seconds
        self.severity = severity

    def is_active(self, current_second: int) -> bool:
        """Check if failure injection is currently active."""
        return self.start_seconds <= current_second < self.end_seconds

    def get_progress(self, current_second: int) -> float:
        """Returns 0.0 to 1.0 indicating progression through the failure window."""
        if not self.is_active(current_second):
            return 0.0
        return (current_second - self.start_seconds) / float(self.duration_seconds)
