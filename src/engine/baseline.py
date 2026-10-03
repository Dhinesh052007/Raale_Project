"""Traditional baseline threshold monitoring (without multi-signal correlation or evidence retention)."""
from typing import Dict, Any, Optional


class BaselineMonitor:
    """
    Simulates a traditional, naive threshold-based monitoring system.
    Evaluates only instantaneous thresholds (e.g. latency > 150ms).
    Lacks multi-source correlation, historical evidence windows, and root-cause localisation.
    """

    def __init__(self, latency_threshold_ms: float = 150.0, loss_threshold_percent: float = 5.0):
        self.latency_threshold_ms = latency_threshold_ms
        self.loss_threshold_percent = loss_threshold_percent

    def evaluate_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Instantaneous alert evaluation.
        When transient failure passes, state immediately reverts to NORMAL with no preserved history.
        """
        latency = event_data.get("latency_ms")
        loss = event_data.get("packet_loss_percent")

        is_alert = False
        reasons = []

        if latency is not None and latency > self.latency_threshold_ms:
            is_alert = True
            reasons.append(f"Latency ({latency}ms) > {self.latency_threshold_ms}ms")

        if loss is not None and loss > self.loss_threshold_percent:
            is_alert = True
            reasons.append(f"Packet Loss ({loss}%) > {self.loss_threshold_percent}%")

        return {
            "status": "DEGRADED" if is_alert else "NORMAL",
            "alert_active": is_alert,
            "detected_cause": "GENERIC_NETWORK_ALERT" if is_alert else "NONE",
            "details": "; ".join(reasons) if reasons else "All metrics within threshold"
        }
