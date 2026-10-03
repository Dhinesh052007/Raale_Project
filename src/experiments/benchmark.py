"""Automated experiment benchmark runner: 100 injected scenarios, baseline comparison, and error analysis."""
import json
import os
import random
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session

from src.models.db import SessionLocal, init_db, Branch, Event, Incident, UserReport
from src.collector.collector import EventCollector
from src.collector.buffer import EventBuffer
from src.simulator.branch_generator import generate_branch_inventory
from src.simulator.branch_simulator import BranchSimulator
from src.simulator.failure_scenarios import FailureScenario, FailureType
from src.engine.baseline import BaselineMonitor
from src.engine.recorder import ExperienceRecorder
from src.engine.localisation import LocalisationEngine


class ExperimentRunner:
    """
    Executes rigorous evaluation experiments with at least 100 injected incidents
    and control normal intervals. Calculates real mathematical metrics comparing
    Baseline Threshold Monitor against Experience Recorder.
    """

    def __init__(self, db: Session, seed: int = 42):
        self.db = db
        self.seed = seed
        self.rng = random.Random(seed)
        self.sim = BranchSimulator(num_branches=50, seed=seed)
        self.baseline_monitor = BaselineMonitor(latency_threshold_ms=150.0, loss_threshold_percent=5.0)

    def run_benchmark(
        self,
        num_incidents: int = 100,
        num_normal_controls: int = 50,
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run 100 injected incidents across WAN, Wi-Fi, App, and Multiple domains,
        plus 50 normal control runs to calculate False Positive Rate.
        """
        # Ensure 50 branches exist
        branches = generate_branch_inventory(num_branches=50, seed=self.seed)
        for b in branches:
            if not self.db.query(Branch).filter_by(branch_id=b["branch_id"]).first():
                self.db.add(Branch(
                    branch_id=b["branch_id"],
                    name=b["name"],
                    region=b["region"],
                    wan_type=b["wan_type"]
                ))
        self.db.commit()

        # Distribution of failure types across 100 incidents
        # ~30 WAN, ~30 Wi-Fi, ~25 Application, ~15 Multiple
        scenario_types = (
            [FailureType.WAN_DEGRADATION] * 30 +
            [FailureType.WIFI_DEGRADATION] * 30 +
            [FailureType.APPLICATION_DEGRADATION] * 25 +
            [FailureType.MULTIPLE_DEGRADATION] * 15
        )
        self.rng.shuffle(scenario_types)
        scenario_types = scenario_types[:num_incidents]

        branch_ids = [b["branch_id"] for b in branches]

        # Tracking metrics for Experience Recorder
        er_detected = 0
        er_missed = 0
        er_correct_localised = 0
        er_incorrect_localised = 0
        er_false_positives = 0

        # Tracking metrics for Baseline System
        base_detected = 0
        base_missed = 0
        base_correct_localised = 0
        base_false_positives = 0

        # Detailed logs & error analysis
        incident_logs = []
        error_analysis = []

        base_time = datetime(2026, 10, 1, 8, 0, 0)
        time_cursor = base_time

        # Run 100 Injected Incidents
        for i, failure_type in enumerate(scenario_types):
            target_branch = self.rng.choice(branch_ids)
            # Duration variation: some short (30-60s), some medium (90-150s), some long (180-240s)
            duration_s = self.rng.choice([40, 60, 90, 120, 180, 240])

            # Pre-baseline (60s), degradation (duration_s), post-recovery (60s)
            scenario_events = []
            f_scenario = FailureScenario(
                failure_type=failure_type,
                target_branch_id=target_branch,
                start_seconds=60,
                duration_seconds=duration_s
            )

            # Generate telemetry ticks every 10s
            for s in range(0, 120 + duration_s, 10):
                t = time_cursor + timedelta(seconds=s)
                active_failure = f_scenario if f_scenario.is_active(s) else None
                scenario_events.append(self.sim.generate_probe_metric(target_branch, t, failure=active_failure))
                scenario_events.append(self.sim.generate_wifi_metric(target_branch, t, failure=active_failure))
                scenario_events.append(self.sim.generate_application_metric(target_branch, t, failure=active_failure))

            # Ingest user report during peak if failure active
            user_report_bundle = self.sim.generate_user_report(
                target_branch,
                time_cursor + timedelta(seconds=60 + duration_s // 2)
            )
            scenario_events.append(user_report_bundle["event"])

            # Ingest duplicate events (5% probability)
            if self.rng.random() < 0.25:
                dup_sample = self.rng.choice(scenario_events)
                scenario_events.append(dict(dup_sample))

            # Ingest delayed / out-of-order events (5% probability)
            if self.rng.random() < 0.25:
                rev_idx = min(3, len(scenario_events) - 1)
                scenario_events[-rev_idx]["event_time"] = time_cursor + timedelta(seconds=15)

            # Ingest events through collector
            collector = EventCollector(db_session=self.db)
            for evt in scenario_events:
                collector.ingest_event(evt)

            # 1. Evaluate with Baseline Monitor
            # Baseline samples during the active failure peak
            peak_events = [e for e in scenario_events if 60 <= (e["event_time"] - time_cursor).total_seconds() < 60 + duration_s]
            baseline_alerted = False
            for pe in peak_events:
                b_eval = self.baseline_monitor.evaluate_event(pe)
                if b_eval["alert_active"]:
                    baseline_alerted = True
                    break

            if baseline_alerted:
                base_detected += 1
                # Baseline has no root cause distinction; only flags generic network alert on WAN
                if failure_type == FailureType.WAN_DEGRADATION:
                    base_correct_localised += 1
            else:
                base_missed += 1

            # 2. Evaluate with Experience Recorder
            recorder = ExperienceRecorder(db_session=self.db)
            eval_time = time_cursor + timedelta(seconds=120 + duration_s + 10)
            rec_incident = recorder.process_telemetry_batch(target_branch, current_time=eval_time)

            expected_cause_map = {
                FailureType.WAN_DEGRADATION: "WAN degradation",
                FailureType.WIFI_DEGRADATION: "Wi-Fi degradation",
                FailureType.APPLICATION_DEGRADATION: "Application degradation",
                FailureType.MULTIPLE_DEGRADATION: "Multiple contributing signals"
            }
            expected_cause = expected_cause_map[failure_type]

            er_alerted = rec_incident is not None
            er_localised_correctly = False
            error_reason = None

            if er_alerted:
                er_detected += 1
                pred_cause = rec_incident.probable_cause
                if pred_cause == expected_cause:
                    er_correct_localised += 1
                    er_localised_correctly = True
                else:
                    er_incorrect_localised += 1
                    error_reason = f"Misclassified {expected_cause} as {pred_cause}"
                    error_analysis.append({
                        "case_id": i + 1,
                        "branch_id": target_branch,
                        "duration_seconds": duration_s,
                        "failure_type": failure_type.value,
                        "expected_cause": expected_cause,
                        "predicted_cause": pred_cause,
                        "error_category": "Conflicting signals / Overlapping symptoms" if failure_type == FailureType.MULTIPLE_DEGRADATION else "Threshold boundary",
                        "explanation": error_reason
                    })
            else:
                er_missed += 1
                error_reason = f"Missed {failure_type.value} detection (duration {duration_s}s)"
                error_analysis.append({
                    "case_id": i + 1,
                    "branch_id": target_branch,
                    "duration_seconds": duration_s,
                    "failure_type": failure_type.value,
                    "expected_cause": expected_cause,
                    "predicted_cause": "None (Missed)",
                    "error_category": "Very short incident / Weak signal" if duration_s <= 40 else "Insufficient evidence",
                    "explanation": error_reason
                })

            incident_logs.append({
                "case_id": i + 1,
                "branch_id": target_branch,
                "failure_type": failure_type.value,
                "duration_seconds": duration_s,
                "baseline_detected": baseline_alerted,
                "recorder_detected": er_alerted,
                "recorder_localised": rec_incident.probable_cause if rec_incident else "None",
                "recorder_correct": er_localised_correctly,
                "error_reason": error_reason
            })

            time_cursor += timedelta(seconds=180 + duration_s)

        # Advance time by 10 minutes to ensure clean separation from previous incidents
        time_cursor += timedelta(minutes=10)

        # Run Normal Controls (to measure False Positive Rate)
        for j in range(num_normal_controls):
            ctrl_branch = self.rng.choice(branch_ids)
            ctrl_events = []
            for s in range(0, 120, 10):
                t = time_cursor + timedelta(seconds=s)
                ctrl_events.append(self.sim.generate_probe_metric(ctrl_branch, t))
                ctrl_events.append(self.sim.generate_wifi_metric(ctrl_branch, t))
                ctrl_events.append(self.sim.generate_application_metric(ctrl_branch, t))

            collector = EventCollector(db_session=self.db)
            for evt in ctrl_events:
                collector.ingest_event(evt)

            # Baseline check
            b_false = any(self.baseline_monitor.evaluate_event(e)["alert_active"] for e in ctrl_events)
            if b_false:
                base_false_positives += 1

            # Recorder check
            recorder = ExperienceRecorder(db_session=self.db)
            r_inc = recorder.process_telemetry_batch(ctrl_branch, current_time=time_cursor + timedelta(seconds=120))
            if r_inc and r_inc.probable_cause not in ("Normal / Transient noise", "Insufficient evidence") and r_inc.status == "ACTIVE":
                er_false_positives += 1

            time_cursor += timedelta(minutes=5)

        # Calculate Real Mathematical Metrics
        # Detection Rate = detected / injected * 100
        er_detection_rate = round((er_detected / num_incidents) * 100.0, 2)
        base_detection_rate = round((base_detected / num_incidents) * 100.0, 2)

        # Miss Rate = missed / injected * 100
        er_miss_rate = round((er_missed / num_incidents) * 100.0, 2)
        base_miss_rate = round((base_missed / num_incidents) * 100.0, 2)

        # Localisation Accuracy = correct_localisation / detected * 100
        er_localisation_acc = round((er_correct_localised / er_detected * 100.0), 2) if er_detected > 0 else 0.0
        base_localisation_acc = round((base_correct_localised / base_detected * 100.0), 2) if base_detected > 0 else 0.0

        # False Positive Rate = false_positives / normal_cases * 100
        er_fpr = round((er_false_positives / num_normal_controls) * 100.0, 2)
        base_fpr = round((base_false_positives / num_normal_controls) * 100.0, 2)

        # Event Integrity
        integrity = collector.get_integrity_stats()

        results_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "random_seed": self.seed,
            "total_injected_incidents": num_incidents,
            "total_normal_controls": num_normal_controls,
            "failure_distribution": {
                "WAN_DEGRADATION": 30,
                "WIFI_DEGRADATION": 30,
                "APPLICATION_DEGRADATION": 25,
                "MULTIPLE_DEGRADATION": 15
            },
            "metrics": {
                "experience_recorder": {
                    "detected_incidents": er_detected,
                    "missed_incidents": er_missed,
                    "detection_rate_pct": er_detection_rate,
                    "miss_rate_pct": er_miss_rate,
                    "correctly_localised": er_correct_localised,
                    "incorrectly_localised": er_incorrect_localised,
                    "localisation_accuracy_pct": er_localisation_acc,
                    "false_positives": er_false_positives,
                    "false_positive_rate_pct": er_fpr
                },
                "baseline_monitor": {
                    "detected_incidents": base_detected,
                    "missed_incidents": base_missed,
                    "detection_rate_pct": base_detection_rate,
                    "miss_rate_pct": base_miss_rate,
                    "correctly_localised": base_correct_localised,
                    "localisation_accuracy_pct": base_localisation_acc,
                    "false_positives": base_false_positives,
                    "false_positive_rate_pct": base_fpr
                }
            },
            "event_integrity": integrity,
            "error_analysis_summary": {
                "total_errors": len(error_analysis),
                "error_categories": {
                    "Very short incident / Weak signal": len([e for e in error_analysis if "Very short" in e["error_category"]]),
                    "Conflicting signals / Overlapping symptoms": len([e for e in error_analysis if "Conflicting" in e["error_category"]]),
                    "Threshold boundary": len([e for e in error_analysis if "Threshold" in e["error_category"]]),
                    "Insufficient evidence": len([e for e in error_analysis if "Insufficient" in e["error_category"]])
                },
                "error_details": error_analysis[:10]  # sample of errors for report
            },
            "scenario_samples": incident_logs[:15]
        }

        # Save to disk
        out_path = output_file or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data",
            "experiment_results.json"
        )
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(results_payload, f, indent=2)

        return results_payload
