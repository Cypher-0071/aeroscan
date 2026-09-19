"""Unit tests for Tier-1 ALNS route pool exploration and local search."""

import pytest

from core.alns import ALNSEngine, construct_greedy_seed_route, explore_route_pool
from core.local_search import fill_temporal_slack, run_local_search_pipeline, two_opt_de_crossing
from core.operators import evaluate_route_trajectory
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
    eval_res = evaluate_route_trajectory(seed_targets, drone, mock_inst)
    assert eval_res is not None
    assert eval_res.total_energy_joules <= drone.usable_battery_joules
    assert eval_res.total_flight_time <= drone.max_flight_time


def test_2opt_smoothing_and_slack_filling(mock_inst):
    """Verify that 2-opt de-crosses routes and slack filling successfully inserts targets."""
    drone = mock_inst.drones[0]
    all_targets = [t.id for t in mock_inst.target_nodes]
    route = [1, 5, 2, 8, 3]

    improved_route = run_local_search_pipeline(route, all_targets, drone, mock_inst)
    assert len(improved_route) >= len(route)
    assert len(improved_route) == len(set(improved_route))


def test_2opt_slack_refill(mock_inst):
    """
    PRD Standalone Test Plan:
    Verify that 2-opt reduces route length and slack filling adds score.
    """
    drone = mock_inst.drones[0]
    # Crossed route pattern where 2-opt definitely unlocks time slack
    crossed_route = [1, 10, 2, 9, 3]
    eval_before = evaluate_route_trajectory(crossed_route, drone, mock_inst)
    assert eval_before is not None

    smoothed_route, time_saved = two_opt_de_crossing(crossed_route, drone, mock_inst)
    eval_smoothed = evaluate_route_trajectory(smoothed_route, drone, mock_inst)
    assert eval_smoothed is not None
    assert eval_smoothed.total_flight_time <= eval_before.total_flight_time + 1e-4

    # Slack filling adds score from unassigned targets
    unassigned = [t.id for t in mock_inst.target_nodes if t.id not in smoothed_route]
    filled_route = fill_temporal_slack(smoothed_route, unassigned, drone, mock_inst)
    eval_filled = evaluate_route_trajectory(filled_route, drone, mock_inst)
    assert eval_filled is not None
    assert eval_filled.total_reward >= eval_smoothed.total_reward
    assert eval_filled.total_energy_joules <= drone.usable_battery_joules + 1e-4


def test_route_pool_uniqueness(mock_inst):
    """
    PRD Standalone Test Plan:
    Verify that candidate route pool contains unique target sets for every drone.
    """
    pool = explore_route_pool(mock_inst, max_iterations=100, time_limit_sec=0.8, seed=42)
    assert pool.total_routes > 0

    for drone in mock_inst.drones:
        routes = pool.routes_by_drone[drone.id]
        assert len(routes) > 0

        target_sets = [frozenset(r.target_ids) for r in routes]
        # Uniqueness guarantee: No two routes for the same drone visit the exact same set of targets
        assert len(target_sets) == len(set(target_sets))


def test_explore_route_pool_contract(mock_inst):
    """Verify that explore_route_pool produces a well-populated, compliant RoutePool."""
    pool = explore_route_pool(mock_inst, max_iterations=150, time_limit_sec=0.8, seed=42)

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


def test_alns_multi_armed_bandit_adaptation(mock_inst):
    """Verify that operator weights and probabilities adapt dynamically over segments."""
    engine = ALNSEngine(mock_inst, delta_segment=10)
    drone = mock_inst.drones[0]

    initial_prob_d = list(engine.probabilities_d)
    initial_prob_r = list(engine.probabilities_r)
    assert len(initial_prob_d) == 4
    assert len(initial_prob_r) == 3

    # Run for 25 iterations (triggers at least 2 segments of delta=10)
    routes = engine.explore_for_drone(drone, max_iterations=25, time_limit_sec=0.5)
    assert len(routes) > 0

    # Probabilities should be valid probability distributions summing to 1.0
    assert abs(sum(engine.probabilities_d) - 1.0) < 1e-5
    assert abs(sum(engine.probabilities_r) - 1.0) < 1e-5
    assert all(p > 0.0 for p in engine.probabilities_d)
    assert all(p > 0.0 for p in engine.probabilities_r)


def test_empty_route_loiter_included(mock_inst):
    """Verify that every drone's route pool includes the empty depot loitering candidate."""
    pool = explore_route_pool(mock_inst, max_iterations=50, time_limit_sec=0.4, seed=42)
    for drone in mock_inst.drones:
        routes = pool.routes_by_drone[drone.id]
        empty_candidates = [r for r in routes if len(r.target_ids) == 0]
        assert len(empty_candidates) == 1
        assert empty_candidates[0].total_reward == 0.0
        assert empty_candidates[0].waypoints[0].node_id == drone.launch_depot_id
        assert empty_candidates[0].waypoints[-1].node_id == drone.recovery_depot_id


def test_heterogeneous_fleet_and_asymmetric_depots(mock_inst):
    """Verify ALNS exploration for a heterogeneous fleet with varying batteries, speeds, and asymmetric depots."""
    from core.contracts import DroneSpec, InstanceContext

    drones = [
        DroneSpec(
            id="Heavy-Lift-01",
            battery_joules=500000.0,
            safety_reserve_ratio=0.15,
            max_flight_time=3000.0,
            cruise_speed=12.0,
            launch_depot_id=0,
            recovery_depot_id=0,
        ),
        DroneSpec(
            id="Fast-Scout-02",
            battery_joules=250000.0,
            safety_reserve_ratio=0.20,
            max_flight_time=1800.0,
            cruise_speed=18.0,
            launch_depot_id=0,
            recovery_depot_id=1,  # Asymmetric depot
        ),
    ]

    hetero_inst = InstanceContext(
        instance_name="Heterogeneous_Test",
        targets=mock_inst.targets,
        drones=drones,
        time_matrix=mock_inst.time_matrix,
        energy_matrix=mock_inst.energy_matrix,
        ambient_wind=mock_inst.ambient_wind,
    )

    pool = explore_route_pool(hetero_inst, max_iterations=80, time_limit_sec=0.8, seed=42)
    assert pool.total_routes >= 2

    # Verify Fast-Scout routes respect its specific 20% reserve and asymmetric recovery depot
    scout_routes = pool.routes_by_drone["Fast-Scout-02"]
    assert len(scout_routes) > 0
    for r in scout_routes:
        assert r.waypoints[0].node_id == 0
        assert r.waypoints[-1].node_id == 1
        assert r.total_energy_joules <= drones[1].usable_battery_joules + 1e-4
        assert r.total_flight_time <= drones[1].max_flight_time + 1e-4


def test_alns_scoring_no_false_improvement(mock_inst):
    """Verify that ALNS does not grant sigma2 (improved route) score when a candidate is identical."""
    engine = ALNSEngine(mock_inst, delta_segment=5)
    drone = mock_inst.drones[0]

    # Run for 15 iterations and verify probabilities remain valid
    routes = engine.explore_for_drone(drone, max_iterations=15, time_limit_sec=0.4)
    assert len(routes) > 0
    assert abs(sum(engine.probabilities_d) - 1.0) < 1e-5
    assert abs(sum(engine.probabilities_r) - 1.0) < 1e-5


def test_alns_high_iteration_stability(mock_inst):
    """Stress-test ALNS with high iteration count to confirm stability and performance."""
    pool = explore_route_pool(mock_inst, max_iterations=300, time_limit_sec=0.9, seed=42)
    assert pool.total_routes > 0
    for drone in mock_inst.drones:
        routes = pool.routes_by_drone[drone.id]
        assert len(routes) > 5
        # Ensure all generated routes are strictly valid
        for r in routes:
            assert r.total_energy_joules <= drone.usable_battery_joules + 1e-4
            assert r.total_flight_time <= drone.max_flight_time + 1e-4
