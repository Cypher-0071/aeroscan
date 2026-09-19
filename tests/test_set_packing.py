"""Unit tests for Tier-2 CP-SAT Set Packing master problem solver."""

import pytest

from core.set_packing import solve_fleet_schedule, solve_set_packing
from tests.mock_instance import create_mock_instance
from tests.mock_routes import create_mock_route_pool


@pytest.fixture
def mock_inst():
    return create_mock_instance(num_targets=20, num_drones=3)


@pytest.fixture
def mock_pool(mock_inst):
    return create_mock_route_pool(mock_inst, routes_per_drone=12)


def test_set_packing_feasibility(mock_inst, mock_pool):
    """Verify that CP-SAT solver finds optimal assignment without overlapping targets."""
    status, assigned_routes, unassigned_tids, latency, total_reward = solve_set_packing(
        mock_inst, mock_pool, time_limit_seconds=0.5
    )

    assert status in ("OPTIMAL", "FEASIBLE")
    assert latency < 0.5  # Sub-second latency guarantee
    assert len(assigned_routes) <= len(mock_inst.drones)

    # Verify target deconfliction (zero overlap across drones)
    visited_all = []
    for route in assigned_routes:
        visited_all.extend(route.target_ids)
    assert len(visited_all) == len(set(visited_all)), "CP-SAT must produce non-overlapping target assignments"


def test_solve_fleet_schedule_end_to_end(mock_inst, mock_pool):
    """Verify solve_fleet_schedule runs baselines and audits constraints."""
    schedule = solve_fleet_schedule(mock_inst, mock_pool, run_baselines=True)

    assert schedule.status in ("OPTIMAL", "FEASIBLE")
    assert schedule.validation_passed is True
    assert schedule.cumulative_reward >= 0.0
    assert schedule.baseline_grasp_reward >= 0.0
