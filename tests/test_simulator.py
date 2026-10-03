"""Unit tests for synthetic branch generation and failure injection simulator."""
from datetime import datetime, timezone
import pytest
from src.simulator.branch_generator import generate_branch_inventory
from src.simulator.failure_scenarios import FailureType, FailureScenario
from src.simulator.branch_simulator import BranchSimulator


def test_branch_inventory_generation():
    """Verify 50 branches generated with required metadata and deterministic seed."""
    branches_a = generate_branch_inventory(num_branches=50, seed=123)
    branches_b = generate_branch_inventory(num_branches=50, seed=123)

    assert len(branches_a) == 50
    assert branches_a[0]["branch_id"] == "B001"
    assert branches_a[49]["branch_id"] == "B050"
    # Determinism check
    assert branches_a == branches_b


def test_normal_telemetry_ranges():
    """Verify metrics under normal baseline conditions fall within realistic bounds."""
    sim = BranchSimulator(num_branches=50, seed=42)
    now = datetime.now(timezone.utc)

    # Active Probe
    probe = sim.generate_probe_metric("B001", now)
    assert 10.0 <= probe["latency_ms"] <= 90.0
    assert 0.5 <= probe["jitter_ms"] <= 20.0
    assert 0.0 <= probe["packet_loss_percent"] <= 1.0

    # Wi-Fi
    wifi = sim.generate_wifi_metric("B001", now)
    assert -70.0 <= wifi["wifi_rssi"] <= -35.0
    assert 0.0 <= wifi["wifi_retry_rate"] <= 6.0
    assert 10.0 <= wifi["channel_utilisation"] <= 55.0

    # Application
    app = sim.generate_application_metric("B001", now)
    assert 100.0 <= app["application_response_ms"] <= 600.0
    assert app["http_status"] == 200


def test_failure_injection_wan_degradation():
    """Verify WAN degradation elevates latency, jitter, packet loss while Wi-Fi stays normal."""
    sim = BranchSimulator(num_branches=50, seed=42)
    now = datetime.now(timezone.utc)
    wan_failure = FailureScenario(
        failure_type=FailureType.WAN_DEGRADATION,
        target_branch_id="B005",
        start_seconds=0,
        duration_seconds=120
    )

    probe = sim.generate_probe_metric("B005", now, failure=wan_failure)
    wifi = sim.generate_wifi_metric("B005", now, failure=wan_failure)

    assert probe["latency_ms"] >= 180.0
    assert probe["packet_loss_percent"] >= 5.0
    # Wi-Fi should remain healthy
    assert -70.0 <= wifi["wifi_rssi"] <= -35.0
    assert wifi["wifi_retry_rate"] < 10.0


def test_failure_injection_wifi_degradation():
    """Verify Wi-Fi degradation impacts RSSI, retry rate, channel util while probe stays normal."""
    sim = BranchSimulator(num_branches=50, seed=42)
    now = datetime.now(timezone.utc)
    wifi_failure = FailureScenario(
        failure_type=FailureType.WIFI_DEGRADATION,
        target_branch_id="B010",
        start_seconds=0,
        duration_seconds=120
    )

    probe = sim.generate_probe_metric("B010", now, failure=wifi_failure)
    wifi = sim.generate_wifi_metric("B010", now, failure=wifi_failure)

    assert wifi["wifi_rssi"] <= -75.0
    assert wifi["wifi_retry_rate"] >= 20.0
    assert wifi["channel_utilisation"] >= 70.0
    # Probe network metrics stay normal
    assert probe["latency_ms"] < 100.0
    assert probe["packet_loss_percent"] < 2.0


def test_failure_injection_application_degradation():
    """Verify Application degradation impacts app response & errors while WAN/Wi-Fi stay normal."""
    sim = BranchSimulator(num_branches=50, seed=42)
    now = datetime.now(timezone.utc)
    app_failure = FailureScenario(
        failure_type=FailureType.APPLICATION_DEGRADATION,
        target_branch_id="B015",
        start_seconds=0,
        duration_seconds=120
    )

    probe = sim.generate_probe_metric("B015", now, failure=app_failure)
    app = sim.generate_application_metric("B015", now, failure=app_failure)

    assert app["application_response_ms"] >= 2000.0
    # Network probe stays normal
    assert probe["latency_ms"] < 100.0


def test_user_report_generation():
    """Verify user report generation structure and pairing."""
    sim = BranchSimulator(num_branches=50, seed=42)
    now = datetime.now(timezone.utc)
    report_bundle = sim.generate_user_report("B007", now, severity="HIGH")

    assert "event" in report_bundle
    assert "report" in report_bundle
    assert report_bundle["event"]["branch_id"] == "B007"
    assert report_bundle["report"]["severity"] == "HIGH"
