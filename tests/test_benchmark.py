"""Unit tests for experiment benchmark suite and metrics computation."""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.models.db import Base, init_db
from src.experiments.benchmark import ExperimentRunner


@pytest.fixture
def db_session():
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    init_db(test_engine)
    TestingSession = sessionmaker(bind=test_engine)
    session = TestingSession()
    yield session
    session.close()


def test_experiment_benchmark_execution_and_metrics(db_session, tmp_path):
    """Verify running a benchmark scenario calculates accurate mathematical metrics."""
    out_file = str(tmp_path / "test_exp_results.json")
    runner = ExperimentRunner(db=db_session, seed=101)

    # Run mini benchmark with 12 incidents and 6 normal controls
    results = runner.run_benchmark(num_incidents=12, num_normal_controls=6, output_file=out_file)

    assert os.path.exists(out_file)
    assert results["total_injected_incidents"] == 12
    assert results["total_normal_controls"] == 6

    # Verify metrics structure
    er_metrics = results["metrics"]["experience_recorder"]
    base_metrics = results["metrics"]["baseline_monitor"]

    # Mathematical consistency checks
    assert er_metrics["detected_incidents"] + er_metrics["missed_incidents"] == 12
    assert round(er_metrics["detection_rate_pct"] + er_metrics["miss_rate_pct"], 1) == 100.0

    # Localisation accuracy formula verification
    if er_metrics["detected_incidents"] > 0:
        expected_loc_acc = round((er_metrics["correctly_localised"] / er_metrics["detected_incidents"]) * 100.0, 2)
        assert er_metrics["localisation_accuracy_pct"] == expected_loc_acc

    # Experience Recorder should significantly outperform Baseline in multi-domain localisation
    assert er_metrics["localisation_accuracy_pct"] > base_metrics["localisation_accuracy_pct"]

    # Verify error analysis summary structure
    assert "error_analysis_summary" in results
    assert "error_categories" in results["error_analysis_summary"]
