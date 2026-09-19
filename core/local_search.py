"""Local search optimization with 2-opt de-crossing and immediate slack-filling."""

from __future__ import annotations

from core.contracts import DroneSpec, InstanceContext
from core.operators import EvaluatorContext


def two_opt_de_crossing(
    target_ids: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
    evaluator: EvaluatorContext | None = None,
) -> tuple[list[int], float]:
    """
    Applies 2-opt geometric de-crossing to a sequence of targets.
    Reverses segment [i..j] if flight time is reduced and energy is feasible.
    Uses O(1) incremental asymmetric matrix updates for high throughput.

    Returns:
        (improved_target_ids, time_saved_seconds)
    """
    best_route = list(target_ids)
    n = len(best_route)
    if n < 2:
        return best_route, 0.0

    if evaluator is None:
        evaluator = EvaluatorContext(drone, instance)

    usable_bat = evaluator.usable_battery + 1e-4
    max_time = evaluator.max_time + 1e-4
    base_e, base_t, _ = evaluator.compute_route_totals(best_route)

    if base_e > usable_bat or base_t > max_time:
        return best_route, 0.0

    initial_time = base_t
    time_mat = evaluator.time_mat
    energy_mat = evaluator.energy_mat
    idx_arr = evaluator.idx_arr
    launch_idx = evaluator.launch_idx
    recovery_idx = evaluator.recovery_idx

    improved = True
    while improved:
        improved = False
        n = len(best_route)
        route_indices = [
            idx_arr[tid] if tid < len(idx_arr) else evaluator.id_to_idx.get(tid, tid)
            for tid in best_route
        ]

        for i in range(n - 1):
            p_idx = launch_idx if i == 0 else route_indices[i - 1]
            ti_idx = route_indices[i]

            internal_dt = 0.0
            internal_de = 0.0

            for j in range(i + 1, n):
                tj_idx = route_indices[j]
                tj_prev_idx = route_indices[j - 1]

                # Internal segment edges reversed: (k, k-1) instead of (k-1, k)
                internal_dt += time_mat[tj_idx, tj_prev_idx] - time_mat[tj_prev_idx, tj_idx]
                internal_de += energy_mat[tj_idx, tj_prev_idx] - energy_mat[tj_prev_idx, tj_idx]

                s_idx = recovery_idx if j == n - 1 else route_indices[j + 1]

                cand_t = (
                    base_t
                    + (
                        time_mat[p_idx, tj_idx]
                        + time_mat[ti_idx, s_idx]
                        - time_mat[p_idx, ti_idx]
                        - time_mat[tj_idx, s_idx]
                    )
                    + internal_dt
                )

                cand_e = (
                    base_e
                    + (
                        energy_mat[p_idx, tj_idx]
                        + energy_mat[ti_idx, s_idx]
                        - energy_mat[p_idx, ti_idx]
                        - energy_mat[tj_idx, s_idx]
                    )
                    + internal_de
                )

                if cand_e <= usable_bat and cand_t <= max_time:
                    if cand_t < base_t - 1e-3 or (
                        abs(cand_t - base_t) <= 1e-3 and cand_e < base_e - 1.0
                    ):
                        best_route = (
                            best_route[:i] + best_route[i : j + 1][::-1] + best_route[j + 1 :]
                        )
                        base_t = cand_t
                        base_e = cand_e
                        improved = True
                        break
            if improved:
                break

    time_saved = max(0.0, initial_time - base_t)
    return best_route, time_saved


def fill_temporal_slack(
    current_route: list[int],
    unassigned_pool: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
    evaluator: EvaluatorContext | None = None,
) -> list[int]:
    """
    Immediate Slack-Filling Engine:
    Scans the unassigned target pool to greedily insert additional high-value
    targets into newly created temporal/energy slack without violating feasibility.
    """
    if evaluator is None:
        evaluator = EvaluatorContext(drone, instance)

    route = list(current_route)
    pool = [tid for tid in unassigned_pool if tid not in set(route)]
    if not pool:
        return route

    curr_energy, curr_time, _ = evaluator.compute_route_totals(route)
    candidates = sorted(
        pool,
        key=lambda x: (
            evaluator.reward_arr[x]
            if x < len(evaluator.reward_arr)
            else evaluator.priority_scores.get(x, 0.0)
        ),
        reverse=True,
    )

    energy_mat = evaluator.energy_mat
    time_mat = evaluator.time_mat
    idx_arr = evaluator.idx_arr
    launch_idx = evaluator.launch_idx
    recovery_idx = evaluator.recovery_idx
    usable_bat = evaluator.usable_battery + 1e-4
    max_time = evaluator.max_time + 1e-4
    dwell_e_arr = evaluator.dwell_e_arr
    dwell_t_arr = evaluator.dwell_t_arr

    for cand_id in candidates:
        n = len(route)
        route_indices = [
            idx_arr[tid] if tid < len(idx_arr) else evaluator.id_to_idx.get(tid, tid)
            for tid in route
        ]
        c = (
            idx_arr[cand_id]
            if cand_id < len(idx_arr)
            else evaluator.id_to_idx.get(cand_id, cand_id)
        )
        d_e = (
            dwell_e_arr[cand_id]
            if cand_id < len(dwell_e_arr)
            else evaluator.dwell_energies.get(cand_id, 0.0)
        )
        d_t = (
            dwell_t_arr[cand_id]
            if cand_id < len(dwell_t_arr)
            else evaluator.dwell_times.get(cand_id, 0.0)
        )

        best_slot: int | None = None
        best_delta_e: float = float("inf")
        best_delta_t: float = 0.0

        for slot in range(n + 1):
            p = launch_idx if slot == 0 else route_indices[slot - 1]
            s = recovery_idx if slot == n else route_indices[slot]

            delta_e = energy_mat[p, c] + energy_mat[c, s] - energy_mat[p, s] + d_e
            delta_t = time_mat[p, c] + time_mat[c, s] - time_mat[p, s] + d_t

            if curr_energy + delta_e <= usable_bat and curr_time + delta_t <= max_time:
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
    evaluator: EvaluatorContext | None = None,
) -> list[int]:
    """
    Executes full local search:
    1. 2-Opt smoothing to de-cross flight legs and unlock time/energy slack.
    2. Immediate slack-filling to capture additional targets in newly created slack (if time_saved > 0).
    3. Final light 2-opt smoothing pass if new targets were added.
    """
    if evaluator is None:
        evaluator = EvaluatorContext(drone, instance)

    smoothed_route, time_saved = two_opt_de_crossing(
        target_ids, drone, instance, evaluator=evaluator
    )
    if time_saved > 1e-4:
        filled_route = fill_temporal_slack(
            smoothed_route, unassigned_pool, drone, instance, evaluator=evaluator
        )
        if len(filled_route) > len(smoothed_route):
            final_route, _ = two_opt_de_crossing(filled_route, drone, instance, evaluator=evaluator)
            return final_route
        return filled_route
    return smoothed_route
