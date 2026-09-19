"""Local search optimization with 2-opt de-crossing and immediate slack-filling."""

from __future__ import annotations

from core.contracts import DroneSpec, InstanceContext
from core.operators import EvaluatorContext


def two_opt_de_crossing(
    target_ids: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
) -> tuple[list[int], float]:
    """
    Applies 2-opt geometric de-crossing to a sequence of targets.
    Reverses segment [i..j] if flight time is reduced and energy is reduced/feasible.

    Returns:
        (improved_target_ids, time_saved_seconds)
    """
    best_route = list(target_ids)
    evaluator = EvaluatorContext(drone, instance)
    initial_energy, initial_time, _ = evaluator.compute_route_totals(best_route)

    if (
        len(best_route) < 2
        or initial_energy > evaluator.usable_battery + 1e-4
        or initial_time > evaluator.max_time + 1e-4
    ):
        return best_route, 0.0

    best_time = initial_time
    best_energy = initial_energy
    improved = True

    while improved:
        improved = False
        n = len(best_route)
        for i in range(n - 1):
            for j in range(i + 1, n):
                # Reverse segment [i..j]
                candidate = best_route[:i] + best_route[i : j + 1][::-1] + best_route[j + 1 :]
                cand_energy, cand_time, _ = evaluator.compute_route_totals(candidate)

                if (
                    cand_energy <= evaluator.usable_battery + 1e-4
                    and cand_time <= evaluator.max_time + 1e-4
                ):
                    if cand_time < best_time - 1e-3 or (
                        abs(cand_time - best_time) <= 1e-3 and cand_energy < best_energy - 1.0
                    ):
                        best_route = candidate
                        best_time = cand_time
                        best_energy = cand_energy
                        improved = True
                        break
            if improved:
                break

    time_saved = max(0.0, initial_time - best_time)
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
    evaluator = EvaluatorContext(drone, instance)
    route = list(current_route)
    curr_energy, curr_time, _ = evaluator.compute_route_totals(route)

    pool = [tid for tid in unassigned_pool if tid not in set(route)]
    candidates = sorted(
        pool,
        key=lambda x: evaluator.priority_scores.get(x, 0.0),
        reverse=True,
    )

    for cand_id in candidates:
        best_slot: int | None = None
        best_delta_e: float = float("inf")
        best_delta_t: float = 0.0

        n = len(route)
        for slot in range(n + 1):
            pred_id = evaluator.launch_id if slot == 0 else route[slot - 1]
            succ_id = evaluator.recovery_id if slot == n else route[slot]

            delta_e, delta_t = evaluator.compute_delta(pred_id, cand_id, succ_id)
            new_e = curr_energy + delta_e
            new_t = curr_time + delta_t

            if new_e <= evaluator.usable_battery + 1e-4 and new_t <= evaluator.max_time + 1e-4:
                if delta_e < best_delta_e:
                    best_delta_e = delta_e
                    best_delta_t = delta_t
                    best_slot = slot

        if best_slot is not None:
            route.insert(best_slot, cand_id)
            curr_energy += best_delta_e
            curr_time += best_delta_t

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
    3. Final light 2-opt smoothing pass.
    """
    smoothed_route, time_saved = two_opt_de_crossing(target_ids, drone, instance)
    if time_saved > 0.0 or len(smoothed_route) < len(instance.target_nodes):
        filled_route = fill_temporal_slack(smoothed_route, unassigned_pool, drone, instance)
        final_route, _ = two_opt_de_crossing(filled_route, drone, instance)
        return final_route
    return smoothed_route
