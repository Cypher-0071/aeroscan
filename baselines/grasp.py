"""Organizer GRASP Baseline: Sequential Greedy Randomized Adaptive Search Procedure.

Simulates the standard sequential heuristic used in existing literature:
Drone 1 greedily plans its route from the unassigned target pool.
Targets visited by Drone 1 are removed. Drone 2 then plans sequentially,
exhibiting severe route cannibalization and performance degradation.
"""

from __future__ import annotations

import random
import time

from core.contracts import CandidateRoute, DroneSpec, FleetSchedule, InstanceContext
from core.operators import evaluate_route_trajectory


def solve_grasp_single_drone(
    drone: DroneSpec,
    available_targets: set[int],
    instance: InstanceContext,
    alpha: float = 0.3,
) -> tuple[CandidateRoute, set[int]]:
    """
    Greedily builds a single drone route using a randomized restricted candidate list (RCL).
    """
    current_route: list[int] = []
    pool = set(available_targets)

    node_map = {n.id: n for n in instance.targets}

    while pool:
        base_eval = evaluate_route_trajectory(current_route, drone, instance)
        base_energy = base_eval.total_energy_joules if base_eval else 0.0

        candidates: list[tuple[float, int, int]] = []  # (efficiency, target_id, slot)
        for tid in list(pool):
            node = node_map.get(tid)
            if not node:
                continue
            for slot in range(len(current_route) + 1):
                test_seq = current_route[:slot] + [tid] + current_route[slot:]
                eval_res = evaluate_route_trajectory(test_seq, drone, instance)
                if eval_res is not None:
                    delta_energy = max(1.0, eval_res.total_energy_joules - base_energy)
                    efficiency = node.priority_score / delta_energy
                    candidates.append((efficiency, tid, slot))

        if not candidates:
            break

        candidates.sort(key=lambda x: x[0], reverse=True)
        max_eff = candidates[0][0]
        min_eff = candidates[-1][0]
        threshold = max_eff - alpha * (max_eff - min_eff)

        rcl = [c for c in candidates if c[0] >= threshold]
        chosen_eff, chosen_tid, chosen_slot = random.choice(rcl)

        current_route.insert(chosen_slot, chosen_tid)
        pool.remove(chosen_tid)

    eval_final = evaluate_route_trajectory(current_route, drone, instance)
    if eval_final is None:
        eval_final = evaluate_route_trajectory([], drone, instance)
    if eval_final is None:
        eval_final = CandidateRoute(
            drone_id=drone.id,
            target_ids=[],
            waypoints=[],
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
