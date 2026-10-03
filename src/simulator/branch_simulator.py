"""Branch telemetry simulators for Active Probes, Wi-Fi, Application, and User Reports."""
import random
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from src.simulator.failure_scenarios import FailureType, FailureScenario
from src.simulator.branch_generator import generate_branch_inventory


class BranchSimulator:
    """
    Simulates multi-source telemetry across branch networks.
    Generates realistic normal baselines and handles dynamic failure injection.
    """

    def __init__(self, num_branches: int = 50, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)
        self.branches = generate_branch_inventory(num_branches=num_branches, seed=seed)
        self.branch_map = {b["branch_id"]: b for b in self.branches}
        self.sequence_counters: Dict[str, int] = {b["branch_id"]: 0 for b in self.branches}

    def _next_sequence(self, branch_id: str) -> int:
        self.sequence_counters[branch_id] = self.sequence_counters.get(branch_id, 0) + 1
        return self.sequence_counters[branch_id]

    def generate_probe_metric(
        self,
        branch_id: str,
        timestamp: datetime,
        failure: Optional[FailureScenario] = None
    ) -> Dict[str, Any]:
        """
        Active Network Probe: Latency, Jitter, Packet Loss, DNS Response.
        Normal: Latency 20-70ms, Jitter 1-15ms, Loss 0-1%, DNS 10-80ms.
        """
        branch = self.branch_map.get(branch_id, {})
        lat_offset = branch.get("baseline_latency_offset", 0.0)

        # Baseline normal values
        latency = max(15.0, self.rng.uniform(25.0, 65.0) + lat_offset)
        jitter = self.rng.uniform(1.0, 10.0)
        packet_loss = 0.0 if self.rng.random() > 0.08 else self.rng.uniform(0.1, 0.8)
        dns_response = self.rng.uniform(12.0, 70.0)

        # Apply failure perturbations if active
        if failure and failure.target_branch_id == branch_id:
            if failure.failure_type == FailureType.WAN_DEGRADATION:
                latency = self.rng.uniform(180.0, 420.0)
                jitter = self.rng.uniform(25.0, 80.0)
                packet_loss = self.rng.uniform(5.0, 28.0)
                dns_response = self.rng.uniform(140.0, 380.0)
            elif failure.failure_type == FailureType.MULTIPLE_DEGRADATION:
                # Concurrent WAN degradation
                latency = self.rng.uniform(200.0, 450.0)
                jitter = self.rng.uniform(30.0, 90.0)
                packet_loss = self.rng.uniform(8.0, 35.0)
                dns_response = self.rng.uniform(150.0, 400.0)

        seq = self._next_sequence(branch_id)
        return {
            "event_id": f"PRB-{uuid.uuid4().hex[:12].upper()}",
            "event_time": timestamp,
            "arrival_time": timestamp,
            "branch_id": branch_id,
            "source": "ACTIVE_PROBE",
            "latency_ms": round(latency, 2),
            "jitter_ms": round(jitter, 2),
            "packet_loss_percent": round(packet_loss, 2),
            "dns_response_ms": round(dns_response, 2),
            "wifi_rssi": None,
            "wifi_retry_rate": None,
            "channel_utilisation": None,
            "application_response_ms": None,
            "http_status": None,
            "transaction_duration_ms": None,
            "user_report": None,
            "sequence_number": seq
        }

    def generate_wifi_metric(
        self,
        branch_id: str,
        timestamp: datetime,
        failure: Optional[FailureScenario] = None
    ) -> Dict[str, Any]:
        """
        Wi-Fi Infrastructure: RSSI, Retry Rate, Channel Utilisation.
        Normal: RSSI -40 to -65 dBm, Retry 0-5%, Channel Utilisation 10-50%.
        """
        branch = self.branch_map.get(branch_id, {})
        rssi_offset = branch.get("baseline_rssi_offset", 0.0)

        # Baseline normal values
        rssi = min(-42.0, self.rng.uniform(-62.0, -48.0) + rssi_offset)
        retry_rate = self.rng.uniform(0.5, 4.5)
        channel_util = self.rng.uniform(15.0, 48.0)

        # Apply failure perturbations if active
        if failure and failure.target_branch_id == branch_id:
            if failure.failure_type == FailureType.WIFI_DEGRADATION:
                rssi = self.rng.uniform(-92.0, -78.0)  # Severely degraded signal
                retry_rate = self.rng.uniform(22.0, 68.0)  # High collisions/retries
                channel_util = self.rng.uniform(78.0, 98.0)  # Radio saturation
            elif failure.failure_type == FailureType.MULTIPLE_DEGRADATION:
                # Concurrent Wi-Fi degradation
                rssi = self.rng.uniform(-88.0, -76.0)
                retry_rate = self.rng.uniform(20.0, 60.0)
                channel_util = self.rng.uniform(75.0, 95.0)

        seq = self._next_sequence(branch_id)
        return {
            "event_id": f"WFI-{uuid.uuid4().hex[:12].upper()}",
            "event_time": timestamp,
            "arrival_time": timestamp,
            "branch_id": branch_id,
            "source": "WIFI",
            "latency_ms": None,
            "jitter_ms": None,
            "packet_loss_percent": None,
            "dns_response_ms": None,
            "wifi_rssi": round(rssi, 2),
            "wifi_retry_rate": round(retry_rate, 2),
            "channel_utilisation": round(channel_util, 2),
            "application_response_ms": None,
            "http_status": None,
            "transaction_duration_ms": None,
            "user_report": None,
            "sequence_number": seq
        }

    def generate_application_metric(
        self,
        branch_id: str,
        timestamp: datetime,
        failure: Optional[FailureScenario] = None
    ) -> Dict[str, Any]:
        """
        Application Monitoring: Response Time, HTTP Status, Transaction Duration.
        Normal: Response Time 150-500ms, HTTP 200, Transaction 200-700ms.
        """
        branch = self.branch_map.get(branch_id, {})
        app_offset = branch.get("baseline_app_offset", 0.0)

        # Baseline normal values
        app_response = max(100.0, self.rng.uniform(180.0, 450.0) + app_offset)
        http_status = 200
        tx_duration = app_response + self.rng.uniform(50.0, 200.0)

        # Apply failure perturbations if active
        if failure and failure.target_branch_id == branch_id:
            if failure.failure_type == FailureType.WAN_DEGRADATION:
                # Collateral network latency impact on app
                app_response = self.rng.uniform(1600.0, 4200.0)
                tx_duration = app_response + self.rng.uniform(200.0, 600.0)
                http_status = 200 if self.rng.random() > 0.15 else 504  # occasional Gateway Timeout
            elif failure.failure_type == FailureType.APPLICATION_DEGRADATION:
                # Core server / database stall
                app_response = self.rng.uniform(2500.0, 8500.0)
                tx_duration = app_response + self.rng.uniform(500.0, 2500.0)
                http_status = self.rng.choice([500, 503, 504, 200]) if self.rng.random() > 0.35 else 200
            elif failure.failure_type == FailureType.MULTIPLE_DEGRADATION:
                app_response = self.rng.uniform(2200.0, 6500.0)
                tx_duration = app_response + self.rng.uniform(400.0, 1800.0)
                http_status = 503 if self.rng.random() > 0.4 else 200

        seq = self._next_sequence(branch_id)
        return {
            "event_id": f"APP-{uuid.uuid4().hex[:12].upper()}",
            "event_time": timestamp,
            "arrival_time": timestamp,
            "branch_id": branch_id,
            "source": "APPLICATION",
            "latency_ms": None,
            "jitter_ms": None,
            "packet_loss_percent": None,
            "dns_response_ms": None,
            "wifi_rssi": None,
            "wifi_retry_rate": None,
            "channel_utilisation": None,
            "application_response_ms": round(app_response, 2),
            "http_status": http_status,
            "transaction_duration_ms": round(tx_duration, 2),
            "user_report": None,
            "sequence_number": seq
        }

    def generate_user_report(
        self,
        branch_id: str,
        timestamp: datetime,
        severity: str = "HIGH",
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """User complaint submitted from branch counter/teller."""
        desc = description or f"Teller terminal experienced significant delay processing customer transactions at {branch_id}."
        seq = self._next_sequence(branch_id)
        report_id = f"URP-{uuid.uuid4().hex[:8].upper()}"

        event_payload = {
            "event_id": f"EVT-{report_id}",
            "event_time": timestamp,
            "arrival_time": timestamp + timedelta(seconds=self.rng.uniform(5.0, 25.0)),
            "branch_id": branch_id,
            "source": "USER_REPORT",
            "latency_ms": None,
            "jitter_ms": None,
            "packet_loss_percent": None,
            "dns_response_ms": None,
            "wifi_rssi": None,
            "wifi_retry_rate": None,
            "channel_utilisation": None,
            "application_response_ms": None,
            "http_status": None,
            "transaction_duration_ms": None,
            "user_report": f"[{report_id}] {desc}",
            "sequence_number": seq
        }

        report_payload = {
            "report_id": report_id,
            "branch_id": branch_id,
            "event_time": timestamp,
            "location": f"{branch_id} Counter {self.rng.randint(1, 5)}",
            "description": desc,
            "severity": severity
        }

        return {"event": event_payload, "report": report_payload}
