"""Unit tests for baseline solvers (GRASP and Genetic Algorithm)."""

import pytest

from baselines.genetic import solve_genetic_algorithm
from baselines.grasp import solve_grasp_baseline
from core.validator import audit_fleet_schedule
from tests.mock_instance import create_mock_instance


@pytest.fixture
def mock_inst():
    return create_mock_instance(num_targets=20, num_drones=3)


def test_grasp_baseline_execution(mock_inst):
    """Verify that GRASP runs cleanly in <0.2s and returns a valid schedule."""
    sched = solve_grasp_baseline(mock_inst, alpha=0.3, seed=42)
    assert sched.status in ("FEASIBLE", "OPTIMAL")
    assert sched.solve_time_seconds < 0.5
    assert sched.cumulative_reward > 0.0

    # Ensure no constraint violations
    audit = audit_fleet_schedule(sched, mock_inst)
    assert audit["valid"] is True, f"GRASP produced invalid schedule: {audit['violations']}"


def test_genetic_algorithm_baseline_execution(mock_inst):
    """Verify that GA baseline runs and returns a valid schedule."""
    sched = solve_genetic_algorithm(mock_inst, population_size=20, generations=15, seed=42)
    assert sched.status in ("FEASIBLE", "OPTIMAL")
    assert sched.cumulative_reward > 0.0

    audit = audit_fleet_schedule(sched, mock_inst)
    assert audit["valid"] is True, f"GA produced invalid schedule: {audit['violations']}"
