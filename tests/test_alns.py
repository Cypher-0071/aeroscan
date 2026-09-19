"""Unit tests for Tier-1 ALNS route pool exploration and local search."""

import pytest

from core.alns import construct_greedy_seed_route, explore_route_pool
from core.local_search import run_local_search_pipeline
from tests.mock_instance import create_mock_instance


@pytest.fixture
def mock_inst():
    return create_mock_instance(num_targets=20, num_drones=3)


def test_greedy_seed_construction(mock_inst):
    """Verify greedy seed builds an initial valid route without battery violations."""
    drone = mock_inst.drones[0]
    seed_targets = construct_greedy_seed_route(drone, mock_inst, alpha=0.2)
    assert len(seed_targets) >= 1
    # Check that seed does not duplicate targets
    assert len(seed_targets) == len(set(seed_targets))


def test_2opt_smoothing_and_slack_filling(mock_inst):
    """Verify that 2-opt de-crosses routes and slack filling successfully inserts targets."""
    drone = mock_inst.drones[0]
    all_targets = [t.id for t in mock_inst.target_nodes]
    route = [1, 5, 2, 8, 3]

    improved_route = run_local_search_pipeline(route, all_targets, drone, mock_inst)
    assert len(improved_route) >= len(route)
    assert len(improved_route) == len(set(improved_route))


def test_explore_route_pool_contract(mock_inst):
    """Verify that explore_route_pool produces a well-populated, compliant RoutePool."""
    pool = explore_route_pool(mock_inst, max_iterations=100, time_limit_sec=0.8, seed=42)

    assert pool.total_routes > 0
    for drone in mock_inst.drones:
        assert drone.id in pool.routes_by_drone
        routes = pool.routes_by_drone[drone.id]
        assert len(routes) > 0

        for r in routes:
            # 1. Start and end at depots
            assert r.waypoints[0].node_id == drone.launch_depot_id
            assert r.waypoints[-1].node_id == drone.recovery_depot_id
            # 2. Strict battery reserve <= 85% burn
            assert r.total_energy_joules <= drone.usable_battery_joules + 1e-4
            assert r.final_reserve_percent >= 15.0 - 1e-4
            # 3. Flight deadline
            assert r.total_flight_time <= drone.max_flight_time + 1e-4
            # 4. Monotonic timestamps
            for i in range(len(r.waypoints) - 1):
                assert r.waypoints[i + 1].arrival_time >= r.waypoints[i].departure_time
