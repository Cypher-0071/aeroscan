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

    print(f"\n[CP-SAT] Latency: {latency:.4f}s | Status: {status} | Reward: {total_reward} | Routes: {len(assigned_routes)}")
    assert status in ("OPTIMAL", "FEASIBLE")
    assert latency < 0.5  # Sub-second latency guarantee
    assert len(assigned_routes) <= len(mock_inst.drones)

    # Verify target deconfliction (zero overlap across drones)
    visited_all = []
    for route in assigned_routes:
        visited_all.extend(route.target_ids)
    assert len(visited_all) == len(set(visited_all)), "CP-SAT must produce non-overlapping target assignments"

    # Edge case 1: Empty RoutePool
    from core.contracts import CandidateRoute, RoutePool
    empty_pool = RoutePool()
    st_e, as_e, un_e, lat_e, rew_e = solve_set_packing(mock_inst, empty_pool)
    assert st_e in ("OPTIMAL", "FEASIBLE")
    assert len(as_e) == 0
    assert rew_e == 0.0

    # Edge case 2: Single drone
    single_inst = create_mock_instance(num_targets=10, num_drones=1)
    single_pool = create_mock_route_pool(single_inst, routes_per_drone=5)
    st_s, as_s, _, lat_s, rew_s = solve_set_packing(single_inst, single_pool)
    assert st_s in ("OPTIMAL", "FEASIBLE")
    assert len(as_s) <= 1

    # Edge case 3: Duplicate candidate routes in pool
    dup_pool = RoutePool(
        routes_by_drone={
            "UAV-01": [
                CandidateRoute("UAV-01", [1, 2], [], 40.0, 100.0, 5000.0),
                CandidateRoute("UAV-01", [1, 2], [], 40.0, 100.0, 5000.0),
            ],
            "UAV-02": [
                CandidateRoute("UAV-02", [1, 2], [], 40.0, 100.0, 5000.0),
            ],
        }
    )
    st_d, as_d, _, _, rew_d = solve_set_packing(mock_inst, dup_pool)
    assert st_d in ("OPTIMAL", "FEASIBLE")
    assert len(as_d) == 1
    assert rew_d == 40.0

    # Edge case 4: Zero-reward routes
    zero_pool = RoutePool(
        routes_by_drone={
            "UAV-01": [CandidateRoute("UAV-01", [1], [], 0.0, 100.0, 5000.0)]
        }
    )
    st_z, as_z, _, _, rew_z = solve_set_packing(mock_inst, zero_pool)
    assert st_z in ("OPTIMAL", "FEASIBLE")
    assert rew_z == 0.0


def test_solve_fleet_schedule_end_to_end(mock_inst, mock_pool):
    """Verify solve_fleet_schedule runs baselines and audits constraints."""
    schedule = solve_fleet_schedule(mock_inst, mock_pool, run_baselines=True)

    print(
        f"\n[FleetSchedule] Status: {schedule.status} | Solve: {schedule.solve_time_seconds:.4f}s | "
        f"Reward: {schedule.cumulative_reward} | GRASP: {schedule.baseline_grasp_reward} | "
        f"GA: {schedule.baseline_ga_reward} | Gain: {schedule.reward_gain_percent:.2f}% | "
        f"Validated: {schedule.validation_passed}"
    )

    assert schedule.status in ("OPTIMAL", "FEASIBLE")
    assert schedule.validation_passed is True
    assert schedule.cumulative_reward >= 0.0
    assert schedule.baseline_grasp_reward >= 0.0
    assert schedule.solve_time_seconds < 0.5

    # Edge case: Empty pool must not crash solve_fleet_schedule
    from core.contracts import RoutePool
    empty_sched = solve_fleet_schedule(mock_inst, RoutePool(), run_baselines=False)
    assert empty_sched.status in ("OPTIMAL", "FEASIBLE")
    assert empty_sched.cumulative_reward == 0.0
    assert len(empty_sched.assigned_routes) == 0
    assert empty_sched.validation_passed is True
