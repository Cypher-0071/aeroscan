"""Unit tests for ALNS destroy and repair operators and trajectory evaluation."""

import pytest

from core.contracts import DroneSpec
from core.operators import (
    destroy_contiguous_string,
    destroy_radial_cone,
    destroy_shaw_relatedness,
    destroy_worst_cost_efficiency,
    evaluate_route_trajectory,
    repair_big_m_regret3_insertion,
    repair_greedy_insertion,
    repair_regret2_insertion,
)
from tests.mock_instance import create_mock_instance


@pytest.fixture
def mock_inst():
    return create_mock_instance(num_targets=20, num_drones=3)


def test_evaluate_route_trajectory_feasibility(mock_inst):
    """Verify trajectory evaluation generates correct waypoints and respects battery."""
    drone = mock_inst.drones[0]
    # Small route with 3 targets
    targets = [1, 2, 3]
    route = evaluate_route_trajectory(targets, drone, mock_inst)
    assert route is not None
    assert route.drone_id == drone.id
    assert route.target_ids == targets
    assert len(route.waypoints) == 5  # launch + 3 targets + recovery
    assert route.total_energy_joules <= drone.usable_battery_joules
    assert route.total_flight_time <= drone.max_flight_time
    assert route.waypoints[0].remaining_battery_percent == 100.0
    assert route.waypoints[-1].remaining_battery_percent >= 15.0


def test_evaluate_route_trajectory_empty_route(mock_inst):
    """Verify trajectory evaluation for an empty route (depot loiter)."""
    drone = mock_inst.drones[0]
    route = evaluate_route_trajectory([], drone, mock_inst)
    assert route is not None
    assert route.target_ids == []
    assert len(route.waypoints) == 2  # launch + recovery
    assert route.total_reward == 0.0
    assert route.total_energy_joules <= drone.usable_battery_joules
    assert route.waypoints[0].node_id == drone.launch_depot_id
    assert route.waypoints[-1].node_id == drone.recovery_depot_id


def test_evaluate_route_trajectory_duplicate_targets(mock_inst):
    """Verify that route trajectory with duplicate target visits is rejected."""
    drone = mock_inst.drones[0]
    duplicate_route = [1, 2, 1]
    assert evaluate_route_trajectory(duplicate_route, drone, mock_inst) is None


def test_evaluate_route_trajectory_battery_violation(mock_inst):
    """Verify that route requiring more energy than usable battery returns None."""
    # Create drone with near-zero battery
    tiny_drone = DroneSpec(
        id="Tiny-01",
        battery_joules=100.0,
        safety_reserve_ratio=0.15,
        max_flight_time=2400.0,
        cruise_speed=14.5,
        launch_depot_id=0,
        recovery_depot_id=0,
    )
    res = evaluate_route_trajectory([1, 2, 3], tiny_drone, mock_inst)
    assert res is None


def test_destroy_operators(mock_inst):
    """Verify all 4 destroy operators remove the expected number of targets."""
    drone = mock_inst.drones[0]
    initial_route = [1, 2, 3, 4, 5, 6, 7, 8]
    q = 3

    # 1. Shaw Relatedness
    rem_shaw, removed_shaw = destroy_shaw_relatedness(initial_route, q, drone, mock_inst)
    assert len(removed_shaw) == q
    assert len(rem_shaw) == len(initial_route) - q
    assert set(rem_shaw + removed_shaw) == set(initial_route)

    # 2. Worst-Cost Efficiency
    rem_wc, removed_wc = destroy_worst_cost_efficiency(initial_route, q, drone, mock_inst)
    assert len(removed_wc) == q
    assert len(rem_wc) == len(initial_route) - q
    assert set(rem_wc + removed_wc) == set(initial_route)

    # 3. Radial Cone
    rem_rc, removed_rc = destroy_radial_cone(initial_route, q, drone, mock_inst)
    assert len(removed_rc) == q
    assert len(rem_rc) == len(initial_route) - q
    assert set(rem_rc + removed_rc) == set(initial_route)

    # 4. Contiguous String
    rem_cs, removed_cs = destroy_contiguous_string(initial_route, q, drone, mock_inst)
    assert len(removed_cs) == q
    assert len(rem_cs) == len(initial_route) - q
    assert set(rem_cs + removed_cs) == set(initial_route)


def test_destroy_operators_edge_cases(mock_inst):
    """Verify boundary conditions for destroy operators: q=1, q=0, and q >= len(route)."""
    drone = mock_inst.drones[0]
    initial_route = [1, 2, 3, 4]

    # Case q = 1
    for destroy_fn in [
        destroy_shaw_relatedness,
        destroy_worst_cost_efficiency,
        destroy_radial_cone,
        destroy_contiguous_string,
    ]:
        rem, removed = destroy_fn(initial_route, 1, drone, mock_inst)
        assert len(removed) == 1
        assert len(rem) == 3
        assert set(rem + removed) == set(initial_route)

    # Case q >= len(route)
    for destroy_fn in [
        destroy_shaw_relatedness,
        destroy_worst_cost_efficiency,
        destroy_radial_cone,
        destroy_contiguous_string,
    ]:
        rem, removed = destroy_fn(initial_route, 10, drone, mock_inst)
        assert len(removed) == len(initial_route)
        assert len(rem) == 0

    # Case q = 0
    for destroy_fn in [
        destroy_shaw_relatedness,
        destroy_worst_cost_efficiency,
        destroy_radial_cone,
        destroy_contiguous_string,
    ]:
        rem, removed = destroy_fn(initial_route, 0, drone, mock_inst)
        assert len(removed) == 0
        assert rem == initial_route


def test_repair_operators(mock_inst):
    """
    PRD Standalone Test Plan: Verify that repaired routes never exceed 0.85 * Battery.
    """
    drone = mock_inst.drones[0]
    base_route = [1, 2]
    all_targets = [t.id for t in mock_inst.target_nodes]

    # Test Greedy
    repaired_greedy = repair_greedy_insertion(base_route, all_targets, drone, mock_inst)
    eval_greedy = evaluate_route_trajectory(repaired_greedy, drone, mock_inst)
    assert eval_greedy is not None
    assert eval_greedy.total_energy_joules <= drone.usable_battery_joules + 1e-4
    assert eval_greedy.final_reserve_percent >= 15.0 - 1e-4
    assert eval_greedy.total_flight_time <= drone.max_flight_time + 1e-4
    assert len(repaired_greedy) == len(set(repaired_greedy))

    # Test Regret-2
    repaired_r2 = repair_regret2_insertion(base_route, all_targets, drone, mock_inst)
    eval_r2 = evaluate_route_trajectory(repaired_r2, drone, mock_inst)
    assert eval_r2 is not None
    assert eval_r2.total_energy_joules <= drone.usable_battery_joules + 1e-4
    assert eval_r2.final_reserve_percent >= 15.0 - 1e-4
    assert eval_r2.total_flight_time <= drone.max_flight_time + 1e-4
    assert len(repaired_r2) == len(set(repaired_r2))

    # Test Big-M Regret-3
    repaired_r3 = repair_big_m_regret3_insertion(base_route, all_targets, drone, mock_inst)
    eval_r3 = evaluate_route_trajectory(repaired_r3, drone, mock_inst)
    assert eval_r3 is not None
    assert eval_r3.total_energy_joules <= drone.usable_battery_joules + 1e-4
    assert eval_r3.final_reserve_percent >= 15.0 - 1e-4
    assert eval_r3.total_flight_time <= drone.max_flight_time + 1e-4
    assert len(repaired_r3) == len(set(repaired_r3))


def test_repair_operators_preserve_battery_reserve(mock_inst):
    """Backward compatible alias for test_repair_operators."""
    test_repair_operators(mock_inst)


def test_asymmetric_depots_operator_evaluation(mock_inst):
    """Verify trajectory evaluation when launch depot != recovery depot."""
    asym_drone = DroneSpec(
        id="Asym-01",
        battery_joules=360000.0,
        safety_reserve_ratio=0.15,
        max_flight_time=2400.0,
        cruise_speed=14.5,
        launch_depot_id=0,
        recovery_depot_id=1,  # Different recovery node
    )
    targets = [2, 3, 4]
    route = evaluate_route_trajectory(targets, asym_drone, mock_inst)
    assert route is not None
    assert route.waypoints[0].node_id == 0
    assert route.waypoints[-1].node_id == 1
    # Check that recovery depot does not add inspection dwell time
    node_rec = mock_inst.get_node(1)
    assert node_rec is not None and node_rec.dwell_time > 0.0
    last_wp = route.waypoints[-1]
    assert last_wp.departure_time == last_wp.arrival_time  # 0 dwell at recovery


def test_evaluator_context_cache_integrity(mock_inst):
    """Verify EvaluatorContext fast vector caches match original instance properties."""
    from core.operators import EvaluatorContext

    drone = mock_inst.drones[0]
    ctx = EvaluatorContext(drone, mock_inst)

    assert ctx.launch_id == drone.launch_depot_id
    assert ctx.recovery_id == drone.recovery_depot_id
    assert ctx.max_d > 0.0
    assert ctx.max_score > 0.0

    for n in mock_inst.targets:
        assert ctx.idx_arr[n.id] == ctx.id_to_idx[n.id]
        assert abs(ctx.dwell_e_arr[n.id] - ctx.dwell_energies[n.id]) < 1e-6
        assert abs(ctx.dwell_t_arr[n.id] - n.dwell_time) < 1e-6
        assert abs(ctx.reward_arr[n.id] - n.priority_score) < 1e-6


def test_evaluator_context_compute_delta_matches_route_totals(mock_inst):
    """Verify that compute_delta produces exact route energy and time transitions."""
    from core.operators import EvaluatorContext

    drone = mock_inst.drones[0]
    ctx = EvaluatorContext(drone, mock_inst)

    route = [1, 2, 3]
    base_e, base_t, _ = ctx.compute_route_totals(route)

    cand = 4
    # Insert candidate at slot 1 (between 1 and 2)
    pred_id = route[0]
    succ_id = route[1]
    de, dt = ctx.compute_delta(pred_id, cand, succ_id)

    new_route = [1, 4, 2, 3]
    new_e, new_t, _ = ctx.compute_route_totals(new_route)

    assert abs((base_e + de) - new_e) < 1e-5
    assert abs((base_t + dt) - new_t) < 1e-5
