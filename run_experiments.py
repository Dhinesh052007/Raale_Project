"""Standalone CLI runner for the 100-incident experimental evaluation suite."""
import os
os.environ["DISABLE_SQLALCHEMY_CEXT"] = "1"

import sys
import json
from src.models.db import SessionLocal, init_db
from src.experiments.benchmark import ExperimentRunner


def main():
    print("=" * 70)
    print("EXPERIENCE RECORDER — 100-INCIDENT RIGOROUS EXPERIMENT RUNNER")
    print("=" * 70)
    print("Initializing database and branch infrastructure...")
    init_db()
    db = SessionLocal()

    try:
        runner = ExperimentRunner(db=db, seed=42)
        print("Executing benchmark suite: 100 Injected Incidents + 50 Control Scenarios...")
        print("  - WAN Degradation: 30 scenarios")
        print("  - Wi-Fi Degradation: 30 scenarios")
        print("  - Application Degradation: 25 scenarios")
        print("  - Multiple Contributing Signals: 15 scenarios")
        print("  - Intermittent Duration Variation: 40s - 240s")
        print("  - Injected Resilience Edge Cases: 25% duplicate & delayed events")
        print("Running...")

        results = runner.run_benchmark(num_incidents=100, num_normal_controls=50)

        er = results["metrics"]["experience_recorder"]
        base = results["metrics"]["baseline_monitor"]

        print("\n" + "=" * 70)
        print("BENCHMARK EVALUATION RESULTS (100 SCENARIOS)")
        print("=" * 70)
        print(f"{'Metric':<30} | {'Baseline System':<16} | {'Experience Recorder':<16}")
        print("-" * 70)
        print(f"{'Detection Rate (%)':<30} | {base['detection_rate_pct']:<16.2f} | {er['detection_rate_pct']:<16.2f}")
        print(f"{'Miss Rate (%)':<30} | {base['miss_rate_pct']:<16.2f} | {er['miss_rate_pct']:<16.2f}")
        print(f"{'Localisation Accuracy (%)':<30} | {base['localisation_accuracy_pct']:<16.2f} | {er['localisation_accuracy_pct']:<16.2f}")
        print(f"{'False Positive Rate (%)':<30} | {base['false_positive_rate_pct']:<16.2f} | {er['false_positive_rate_pct']:<16.2f}")
        print("-" * 70)
        print(f"Total Detected / Injected:   Baseline: {base['detected_incidents']}/100  |  Experience Recorder: {er['detected_incidents']}/100")
        print(f"Correct Localisation:        Baseline: {base['correctly_localised']}/{base['detected_incidents']}  |  Experience Recorder: {er['correctly_localised']}/{er['detected_incidents']}")
        print(f"False Positives on Controls: Baseline: {base['false_positives']}/50  |  Experience Recorder: {er['false_positives']}/50")
        print("=" * 70)

        err_summary = results["error_analysis_summary"]
        print(f"\nAutomated Error Analysis ({err_summary['total_errors']} cases):")
        for cat, cnt in err_summary["error_categories"].items():
            print(f"  • {cat}: {cnt}")

        output_path = os.path.join("data", "experiment_results.json")
        print(f"\nBenchmark artifacts preserved at: {output_path}")
        print("=" * 70)
    finally:
        db.close()


if __name__ == "__main__":
    main()
