"""Explainable rule-based fault localisation engine."""
import json
from typing import List, Dict, Any, Tuple


class LocalisationEngine:
    """
    Evaluates multi-source telemetry evidence within an incident window
    and localises the probable fault domain with full explainability.
    """

    # Domain Anomaly Thresholds
    WAN_LATENCY_THRESHOLD_MS = 140.0
    WAN_PACKET_LOSS_THRESHOLD = 3.0
    WAN_JITTER_THRESHOLD_MS = 20.0
    WAN_DNS_THRESHOLD_MS = 120.0

    WIFI_RSSI_THRESHOLD_DBM = -75.0
    WIFI_RETRY_THRESHOLD_PCT = 15.0
    WIFI_CHANNEL_UTIL_THRESHOLD_PCT = 70.0

    APP_RESPONSE_THRESHOLD_MS = 1400.0
    APP_TRANSACTION_THRESHOLD_MS = 2000.0

    def localise(self, events: List[Dict[str, Any]], user_report_count: int = 0) -> Dict[str, Any]:
        """
        Analyze a cluster of incident events across active probe, Wi-Fi, and application sources.
        Returns:
            Dict containing:
                - probable_cause: str
                - confidence: float
                - severity: str
                - evidence: Dict[str, Any]
        """
        if not events:
            return {
                "probable_cause": "Insufficient evidence",
                "confidence": 0.0,
                "severity": "LOW",
                "evidence": {"reason": "No telemetry events captured in incident window"}
            }

        # Extract metric aggregates
        latencies = [e["latency_ms"] for e in events if e.get("latency_ms") is not None]
        packet_losses = [e["packet_loss_percent"] for e in events if e.get("packet_loss_percent") is not None]
        jitters = [e["jitter_ms"] for e in events if e.get("jitter_ms") is not None]
        dns_times = [e["dns_response_ms"] for e in events if e.get("dns_response_ms") is not None]

        rssis = [e["wifi_rssi"] for e in events if e.get("wifi_rssi") is not None]
        retries = [e["wifi_retry_rate"] for e in events if e.get("wifi_retry_rate") is not None]
        channel_utils = [e["channel_utilisation"] for e in events if e.get("channel_utilisation") is not None]

        app_responses = [e["application_response_ms"] for e in events if e.get("application_response_ms") is not None]
        tx_durations = [e["transaction_duration_ms"] for e in events if e.get("transaction_duration_ms") is not None]
        http_errors = [e["http_status"] for e in events if e.get("http_status") is not None and e.get("http_status") >= 500]

        # Computed Aggregates
        peak_lat = max(latencies) if latencies else 0.0
        avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
        peak_loss = max(packet_losses) if packet_losses else 0.0
        avg_loss = sum(packet_losses) / len(packet_losses) if packet_losses else 0.0

        min_rssi = min(rssis) if rssis else -50.0
        peak_retry = max(retries) if retries else 0.0
        peak_channel = max(channel_utils) if channel_utils else 0.0

        peak_app = max(app_responses) if app_responses else 0.0
        avg_app = sum(app_responses) / len(app_responses) if app_responses else 0.0
        http_error_count = len(http_errors)

        # Signal Flags
        wan_abnormal = (
            peak_lat >= self.WAN_LATENCY_THRESHOLD_MS or
            peak_loss >= self.WAN_PACKET_LOSS_THRESHOLD or
            (jitters and max(jitters) >= self.WAN_JITTER_THRESHOLD_MS) or
            (dns_times and max(dns_times) >= self.WAN_DNS_THRESHOLD_MS)
        )

        wifi_abnormal = (
            (rssis and min_rssi <= self.WIFI_RSSI_THRESHOLD_DBM) or
            (retries and peak_retry >= self.WIFI_RETRY_THRESHOLD_PCT) or
            (channel_utils and peak_channel >= self.WIFI_CHANNEL_UTIL_THRESHOLD_PCT)
        )

        app_abnormal = (
            peak_app >= self.APP_RESPONSE_THRESHOLD_MS or
            http_error_count > 0 or
            (tx_durations and max(tx_durations) >= self.APP_TRANSACTION_THRESHOLD_MS)
        )

        # Trace rationale
        reasons = []
        if wan_abnormal:
            reasons.append(f"WAN latency peaked at {peak_lat:.1f}ms, packet loss reached {peak_loss:.1f}%")
        if wifi_abnormal:
            reasons.append(f"Wi-Fi RSSI degraded to {min_rssi:.1f}dBm, retry rate surged to {peak_retry:.1f}%, channel util reached {peak_channel:.1f}%")
        if app_abnormal:
            reasons.append(f"Application response peaked at {peak_app:.1f}ms with {http_error_count} HTTP 5xx errors")

        # Decision Tree Logic
        # Case 1: WAN is abnormal, Wi-Fi is healthy
        if wan_abnormal and not wifi_abnormal:
            # Notice: High WAN latency naturally inflates end-to-end application response times (RTT overhead).
            # Unless there are explicit internal application 5xx errors without WAN cause, this is WAN degradation.
            if http_error_count > 2 and peak_lat < 250.0:
                probable_cause = "Multiple contributing signals"
                confidence = 0.88
            else:
                probable_cause = "WAN degradation"
                confidence = 0.96 if peak_loss > 5.0 or peak_lat > 220.0 else 0.85

        # Case 2: Wi-Fi is abnormal, WAN probe is healthy
        elif wifi_abnormal and not wan_abnormal:
            probable_cause = "Wi-Fi degradation"
            confidence = 0.95 if (peak_retry > 25.0 or min_rssi < -80.0) else 0.86

        # Case 3: Application is abnormal, WAN and Wi-Fi are both healthy
        elif app_abnormal and not wan_abnormal and not wifi_abnormal:
            probable_cause = "Application degradation"
            confidence = 0.94 if (http_error_count > 0 or peak_app > 2200.0) else 0.82

        # Case 4: Multiple independent components abnormal
        elif (wan_abnormal and wifi_abnormal) or (wifi_abnormal and app_abnormal and http_error_count > 0):
            probable_cause = "Multiple contributing signals"
            confidence = 0.92

        # Case 5: Neither has strong signals
        else:
            if user_report_count > 0:
                probable_cause = "Insufficient evidence"
                confidence = 0.50
                reasons.append("User reports filed but recorded telemetry remained within normal thresholds")
            else:
                probable_cause = "Normal / Transient noise"
                confidence = 0.70
                reasons.append("No sustained threshold violations across any monitored domain")

        # Determine severity
        severity = "LOW"
        if peak_loss >= 15.0 or peak_lat >= 350.0 or http_error_count >= 3 or peak_retry >= 40.0:
            severity = "CRITICAL"
        elif peak_loss >= 5.0 or peak_lat >= 200.0 or peak_app >= 2500.0 or peak_retry >= 20.0 or user_report_count >= 2:
            severity = "HIGH"
        elif wan_abnormal or wifi_abnormal or app_abnormal:
            severity = "MEDIUM"

        evidence_payload = {
            "probable_cause": probable_cause,
            "confidence": confidence,
            "severity": severity,
            "supporting_metrics": {
                "peak_latency_ms": round(peak_lat, 2),
                "avg_latency_ms": round(avg_lat, 2),
                "peak_packet_loss_percent": round(peak_loss, 2),
                "avg_packet_loss_percent": round(avg_loss, 2),
                "min_wifi_rssi_dbm": round(min_rssi, 2),
                "peak_wifi_retry_percent": round(peak_retry, 2),
                "peak_wifi_channel_util_percent": round(peak_channel, 2),
                "peak_application_response_ms": round(peak_app, 2),
                "avg_application_response_ms": round(avg_app, 2),
                "http_error_count": http_error_count,
                "user_report_count": user_report_count
            },
            "domain_states": {
                "wan_abnormal": wan_abnormal,
                "wifi_abnormal": wifi_abnormal,
                "application_abnormal": app_abnormal
            },
            "reasoning": "; ".join(reasons)
        }

        return {
            "probable_cause": probable_cause,
            "confidence": confidence,
            "severity": severity,
            "evidence": evidence_payload
        }
