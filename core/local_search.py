"""Local search optimization with 2-opt de-crossing and immediate slack-filling."""

from __future__ import annotations

from core.contracts import CandidateRoute, DroneSpec, InstanceContext
from core.operators import evaluate_route_trajectory


def two_opt_de_crossing(
    target_ids: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
) -> tuple[list[int], float]:
    """
    Applies 2-opt geometric de-crossing to a sequence of targets.
    Returns:
        (improved_target_ids, time_saved_seconds)
    """
    best_route = list(target_ids)
    best_eval = evaluate_route_trajectory(best_route, drone, instance)
    if best_eval is None or len(best_route) < 2:
        return best_route, 0.0

    initial_time = best_eval.total_flight_time
    improved = True

    while improved:
        improved = False
        n = len(best_route)
        for i in range(n - 1):
            for j in range(i + 1, n):
                # Reverse segment [i..j]
                candidate = best_route[:i] + best_route[i : j + 1][::-1] + best_route[j + 1 :]
                cand_eval = evaluate_route_trajectory(candidate, drone, instance)
                if cand_eval is not None and (
                    cand_eval.total_flight_time < best_eval.total_flight_time - 1e-3
                    or (abs(cand_eval.total_flight_time - best_eval.total_flight_time) <= 1e-3 and cand_eval.total_energy_joules < best_eval.total_energy_joules - 1.0)
                ):
                    best_route = candidate
                    best_eval = cand_eval
                    improved = True
                    break
            if improved:
                break

    time_saved = max(0.0, initial_time - best_eval.total_flight_time)
    return best_route, time_saved


def fill_temporal_slack(
    current_route: list[int],
    unassigned_pool: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
) -> list[int]:
    """
    Immediate Slack-Filling Engine:
    Scans the unassigned target pool to greedily insert additional high-value
    targets into newly created temporal/energy slack without violating feasibility.
    """
    route = list(current_route)
    node_map = {n.id: n for n in instance.targets}
    candidates = sorted(
        [tid for tid in unassigned_pool if tid not in route],
        key=lambda x: node_map[x].priority_score if x in node_map else 0.0,
        reverse=True,
    )

    for cand_id in candidates:
        best_slot: int | None = None
        best_eval: CandidateRoute | None = None

        for slot in range(len(route) + 1):
            test_route = route[:slot] + [cand_id] + route[slot:]
            cand_eval = evaluate_route_trajectory(test_route, drone, instance)
            if cand_eval is not None:
                if best_eval is None or cand_eval.total_energy_joules < best_eval.total_energy_joules:
                    best_eval = cand_eval
                    best_slot = slot

        if best_slot is not None:
            route.insert(best_slot, cand_id)

    return route


def run_local_search_pipeline(
    target_ids: list[int],
    unassigned_pool: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
) -> list[int]:
    """
    Executes full local search:
    1. 2-Opt smoothing to de-cross flight legs and unlock time/energy slack.
    2. Immediate slack-filling to capture additional targets in newly created slack.
    """
    smoothed_route, time_saved = two_opt_de_crossing(target_ids, drone, instance)
    if time_saved > 0.0 or len(smoothed_route) < len(instance.target_nodes):
        filled_route = fill_temporal_slack(smoothed_route, unassigned_pool, drone, instance)
        # Apply one more light 2-opt pass after slack filling
        final_route, _ = two_opt_de_crossing(filled_route, drone, instance)
        return final_route
    return smoothed_route
