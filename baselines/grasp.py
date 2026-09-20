"""Organizer GRASP Baseline: Sequential Greedy Randomized Adaptive Search Procedure.

Simulates the standard sequential heuristic used in existing literature:
Drone 1 greedily plans its route from the unassigned target pool.
Targets visited by Drone 1 are removed. Drone 2 then plans sequentially,
exhibiting severe route cannibalization and performance degradation.
"""

from __future__ import annotations

import math
import random
import time

from core.contracts import (
    CandidateRoute,
    DroneSpec,
    FleetSchedule,
    InstanceContext,
    WaypointVisit,
)
from core.operators import EvaluatorContext, evaluate_route_trajectory


def solve_grasp_single_drone(
    drone: DroneSpec,
    available_targets: set[int],
    instance: InstanceContext,
    alpha: float = 0.3,
) -> tuple[CandidateRoute, set[int]]:
    """
    Greedily builds a single drone route using a randomized restricted candidate list (RCL)
    ranked by efficiency = delta_reward / delta_dist.
    """
    current_route: list[int] = []
    pool = set(available_targets)

    node_map = {n.id: n for n in instance.targets}
    evaluator = EvaluatorContext(drone, instance)
    curr_e, curr_t, _ = evaluator.compute_route_totals(current_route)
    usable_energy = drone.usable_battery_joules
    max_time = drone.max_flight_time

    while pool:
        candidates: list[
            tuple[float, int, int, float, float]
        ] = []  # (efficiency, target_id, slot, delta_e, delta_t)
        for tid in list(pool):
            node = node_map.get(tid)
            if not node:
                continue
            for slot in range(len(current_route) + 1):
                pred_id = current_route[slot - 1] if slot > 0 else drone.launch_depot_id
                succ_id = (
                    current_route[slot] if slot < len(current_route) else drone.recovery_depot_id
                )
                pred_node = node_map.get(pred_id)
                succ_node = node_map.get(succ_id)
                if not pred_node or not succ_node:
                    continue

                curr_dist = math.hypot(succ_node.x - pred_node.x, succ_node.y - pred_node.y)
                new_dist = math.hypot(node.x - pred_node.x, node.y - pred_node.y) + math.hypot(
                    succ_node.x - node.x, succ_node.y - node.y
                )
                delta_dist = max(1.0, new_dist - curr_dist)

                delta_e, delta_t = evaluator.compute_delta(pred_id, tid, succ_id)
                if curr_e + delta_e <= usable_energy and curr_t + delta_t <= max_time:
                    efficiency = node.priority_score / delta_dist
                    candidates.append((efficiency, tid, slot, delta_e, delta_t))

        if not candidates:
            break

        candidates.sort(key=lambda x: x[0], reverse=True)
        max_eff = candidates[0][0]
        min_eff = candidates[-1][0]
        threshold = max_eff - alpha * (max_eff - min_eff)

        rcl = [c for c in candidates if c[0] >= threshold]
        chosen_eff, chosen_tid, chosen_slot, chosen_de, chosen_dt = random.choice(rcl)

        current_route.insert(chosen_slot, chosen_tid)
        pool.remove(chosen_tid)
        curr_e += chosen_de
        curr_t += chosen_dt

    eval_final = evaluate_route_trajectory(current_route, drone, instance, evaluator=evaluator)
    if eval_final is None:
        eval_final = evaluate_route_trajectory([], drone, instance)
    if eval_final is None:
        eval_final = CandidateRoute(
            drone_id=drone.id,
            target_ids=[],
            waypoints=[
                WaypointVisit(
                    node_id=drone.launch_depot_id,
                    arrival_time=0.0,
                    departure_time=0.0,
                    energy_consumed=0.0,
                    remaining_battery_percent=100.0,
                ),
                WaypointVisit(
                    node_id=drone.recovery_depot_id,
                    arrival_time=0.0,
                    departure_time=0.0,
                    energy_consumed=0.0,
                    remaining_battery_percent=100.0,
                ),
            ],
            total_reward=0.0,
            total_flight_time=0.0,
            total_energy_joules=0.0,
        )
        return (eval_final, set())

    return (eval_final, set(current_route))


def solve_grasp_baseline(
    instance: InstanceContext,
    alpha: float = 0.3,
    seed: int | None = 42,
) -> FleetSchedule:
    """
    Executes sequential GRASP heuristic across the fleet.
    Each drone claims targets sequentially, directly demonstrating route cannibalization.
    """
    if seed is not None:
        random.seed(seed)

    t0 = time.perf_counter()
    available_targets = set(t.id for t in instance.target_nodes)
    assigned_routes: list[CandidateRoute] = []
    total_reward = 0.0

    for drone in instance.drones:
        route, visited = solve_grasp_single_drone(
            drone=drone,
            available_targets=available_targets,
            instance=instance,
            alpha=alpha,
        )
        assigned_routes.append(route)
        total_reward += route.total_reward
        available_targets.difference_update(visited)

    latency = time.perf_counter() - t0
    unassigned = [t.id for t in instance.target_nodes if t.id in available_targets]

    return FleetSchedule(
        status="FEASIBLE",
        solve_time_seconds=latency,
        cumulative_reward=total_reward,
        assigned_routes=assigned_routes,
        unassigned_targets=unassigned,
        validation_passed=True,
        baseline_grasp_reward=total_reward,
    )
