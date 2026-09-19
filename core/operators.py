"""Adaptive Large Neighborhood Search (ALNS) Destroy and Repair Operators.

Contains:
- 4 Destroy Operators: Shaw Spatio-Temporal, Worst-Cost Detour, Radial Angular Cone, Contiguous String.
- 3 Repair Operators: Greedy Insertion, Regret-2 Insertion, Corrected Big-M Regret-3 Insertion.
- Trajectory evaluation utilities for feasibility, dwell, and energy checks.
- Fast vector/matrix evaluator context for high-throughput heuristic iterations.
"""

from __future__ import annotations

import math
import random

import numpy as np

from core.contracts import CandidateRoute, DroneSpec, InstanceContext, WaypointVisit
from core.physics import compute_dwell_energy


class EvaluatorContext:
    """Fast cache and O(1) delta evaluator for a specific (drone, instance) pair."""

    def __init__(self, drone: DroneSpec, instance: InstanceContext) -> None:
        self.drone = drone
        self.instance = instance
        self.time_mat = instance.time_matrix
        self.energy_mat = instance.energy_matrix
        self.id_to_idx = instance.id_to_index
        self.launch_id = drone.launch_depot_id
        self.recovery_id = drone.recovery_depot_id
        self.launch_idx = self.id_to_idx.get(self.launch_id, self.launch_id)
        self.recovery_idx = self.id_to_idx.get(self.recovery_id, self.recovery_id)
        self.usable_battery = drone.usable_battery_joules
        self.max_time = drone.max_flight_time

        self.node_map = {n.id: n for n in instance.targets}
        self.dwell_times = {n.id: n.dwell_time for n in instance.targets}
        self.dwell_energies = {
            n.id: compute_dwell_energy(n.dwell_time) if n.dwell_time > 0 else 0.0
            for n in instance.targets
        }
        self.priority_scores = {n.id: n.priority_score for n in instance.targets}

        # Flat array caches for direct O(1) indexing (zero dict hashing in inner loops)
        max_id = max((n.id for n in instance.targets), default=0)
        max_idx = max(self.id_to_idx.values(), default=0)
        size = max(max_id, max_idx) + 1

        self.idx_arr = np.zeros(size, dtype=np.int32)
        self.dwell_e_arr = np.zeros(size, dtype=np.float64)
        self.dwell_t_arr = np.zeros(size, dtype=np.float64)
        self.reward_arr = np.zeros(size, dtype=np.float64)

        for n in instance.targets:
            nid = n.id
            idx = self.id_to_idx.get(nid, nid)
            self.idx_arr[nid] = idx
            self.dwell_e_arr[nid] = self.dwell_energies[nid]
            self.dwell_t_arr[nid] = self.dwell_times[nid]
            self.reward_arr[nid] = self.priority_scores[nid]

        # Normalization constants for Shaw relatedness operator
        coords = np.array([[n.x, n.y] for n in instance.targets], dtype=np.float64)
        if len(coords) > 1:
            diffs = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
            self.max_d = max(float(np.max(np.sqrt(np.sum(diffs**2, axis=-1)))), 1.0)
        else:
            self.max_d = 1.0

        self.max_score = max(
            (n.priority_score for n in instance.targets if n.priority_score > 0), default=1.0
        )

    def compute_delta(self, pred_id: int, cand_id: int, succ_id: int) -> tuple[float, float]:
        """
        Computes (delta_energy, delta_time) for inserting cand_id between pred_id and succ_id.
        O(1) execution with zero allocations.
        """
        p = (
            self.idx_arr[pred_id]
            if pred_id < len(self.idx_arr)
            else self.id_to_idx.get(pred_id, pred_id)
        )
        c = (
            self.idx_arr[cand_id]
            if cand_id < len(self.idx_arr)
            else self.id_to_idx.get(cand_id, cand_id)
        )
        s = (
            self.idx_arr[succ_id]
            if succ_id < len(self.idx_arr)
            else self.id_to_idx.get(succ_id, succ_id)
        )

        delta_energy = float(
            self.energy_mat[p, c]
            + self.energy_mat[c, s]
            - self.energy_mat[p, s]
            + (
                self.dwell_e_arr[cand_id]
                if cand_id < len(self.dwell_e_arr)
                else self.dwell_energies.get(cand_id, 0.0)
            )
        )
        delta_time = float(
            self.time_mat[p, c]
            + self.time_mat[c, s]
            - self.time_mat[p, s]
            + (
                self.dwell_t_arr[cand_id]
                if cand_id < len(self.dwell_t_arr)
                else self.dwell_times.get(cand_id, 0.0)
            )
        )
        return delta_energy, delta_time

    def compute_route_totals(self, route: list[int]) -> tuple[float, float, float]:
        """
        Returns (total_energy, total_time, total_reward) for the complete sequence
        launch -> route -> recovery.
        """
        if not route:
            t = float(self.time_mat[self.launch_idx, self.recovery_idx])
            e = float(self.energy_mat[self.launch_idx, self.recovery_idx])
            return e, t, 0.0

        seq_indices = (
            [self.launch_idx]
            + [
                self.idx_arr[tid] if tid < len(self.idx_arr) else self.id_to_idx[tid]
                for tid in route
            ]
            + [self.recovery_idx]
        )
        total_energy = 0.0
        total_time = 0.0
        total_reward = 0.0

        for i in range(len(seq_indices) - 1):
            u = seq_indices[i]
            v = seq_indices[i + 1]
            total_energy += self.energy_mat[u, v]
            total_time += self.time_mat[u, v]

        for tid in route:
            if tid < len(self.dwell_e_arr):
                total_energy += self.dwell_e_arr[tid]
                total_time += self.dwell_t_arr[tid]
                total_reward += self.reward_arr[tid]
            else:
                total_energy += self.dwell_energies.get(tid, 0.0)
                total_time += self.dwell_times.get(tid, 0.0)
                total_reward += self.priority_scores.get(tid, 0.0)

        return float(total_energy), float(total_time), float(total_reward)


def evaluate_route_trajectory(
    target_ids: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
    evaluator: EvaluatorContext | None = None,
) -> CandidateRoute | None:
    """
    Evaluates a candidate target sequence for a drone from launch to recovery depot.
    Computes continuous arrival/departure times, dwell durations, and cumulative energy.
    Returns CandidateRoute if feasible under both time deadline and 15% battery reserve.
    Returns None if infeasible or duplicate targets are detected.
    """
    if len(target_ids) != len(set(target_ids)):
        return None

    if evaluator is None:
        evaluator = EvaluatorContext(drone, instance)

    node_map = evaluator.node_map
    launch_id = drone.launch_depot_id
    recovery_id = drone.recovery_depot_id

    # Complete sequence of node IDs: launch -> targets -> recovery
    full_sequence = [launch_id] + list(target_ids) + [recovery_id]
    seq_indices = [
        evaluator.idx_arr[nid]
        if nid < len(evaluator.idx_arr)
        else evaluator.id_to_idx.get(nid, nid)
        for nid in full_sequence
    ]

    current_time = 0.0
    current_energy = 0.0
    total_reward = 0.0
    waypoints: list[WaypointVisit] = []

    # First waypoint: Launch depot
    waypoints.append(
        WaypointVisit(
            node_id=launch_id,
            arrival_time=0.0,
            departure_time=0.0,
            energy_consumed=0.0,
            remaining_battery_percent=100.0,
        )
    )

    for idx in range(len(full_sequence) - 1):
        u = seq_indices[idx]
        v = seq_indices[idx + 1]
        to_id = full_sequence[idx + 1]

        transit_time = float(evaluator.time_mat[u, v])
        transit_energy = float(evaluator.energy_mat[u, v])

        arr_time = current_time + transit_time
        if to_id != recovery_id:
            if to_id < len(evaluator.dwell_t_arr):
                dwell_time = float(evaluator.dwell_t_arr[to_id])
                dwell_energy = float(evaluator.dwell_e_arr[to_id])
                total_reward += float(evaluator.reward_arr[to_id])
            else:
                tn = node_map.get(to_id)
                dwell_time = tn.dwell_time if tn else 0.0
                dwell_energy = compute_dwell_energy(dwell_time) if dwell_time > 0 else 0.0
                if tn:
                    total_reward += tn.priority_score
        else:
            dwell_time = 0.0
            dwell_energy = 0.0

        dep_time = arr_time + dwell_time
        node_energy = current_energy + transit_energy + dwell_energy

        current_time = dep_time
        current_energy = node_energy

        remaining_battery_joules = max(0.0, drone.battery_joules - current_energy)
        rem_pct = (remaining_battery_joules / drone.battery_joules) * 100.0

        waypoints.append(
            WaypointVisit(
                node_id=to_id,
                arrival_time=arr_time,
                departure_time=dep_time,
                energy_consumed=current_energy,
                remaining_battery_percent=rem_pct,
            )
        )

    # Check hard feasibility:
    # 1. Total energy burn <= 0.85 * battery_joules (must preserve >= 15% reserve)
    # 2. Total return flight time <= drone.max_flight_time
    max_allowed_energy = drone.usable_battery_joules
    if current_energy > max_allowed_energy + 1e-4 or current_time > drone.max_flight_time + 1e-4:
        return None

    return CandidateRoute(
        drone_id=drone.id,
        target_ids=list(target_ids),
        waypoints=waypoints,
        total_reward=total_reward,
        total_flight_time=current_time,
        total_energy_joules=current_energy,
    )


# ---------------------------------------------------------------------------
# Destroy Operators
# ---------------------------------------------------------------------------


def destroy_shaw_relatedness(
    target_ids: list[int],
    q: int,
    drone: DroneSpec,
    instance: InstanceContext,
    phi1: float = 0.5,
    phi2: float = 0.3,
    phi3: float = 0.2,
    p_determinism: float = 3.0,
    evaluator: EvaluatorContext | None = None,
) -> tuple[list[int], list[int]]:
    """
    Shaw Spatio-Temporal Relatedness Destroy.
    R(i, j) = phi1 * (d_ij / max_d) + phi2 * (|t_arr_i - t_arr_j| / max_t) + phi3 * (|R_i - R_j| / max_R)
    Removes seed target i, then iteratively removes targets with minimum R(i, j).
    """
    if q <= 0:
        return list(target_ids), []
    if len(target_ids) <= q:
        return [], list(target_ids)

    if evaluator is None:
        evaluator = EvaluatorContext(drone, instance)

    node_map = evaluator.node_map

    # Precalculate exact arrival times along current route sequence
    arr_times: dict[int, float] = {}
    curr_t = 0.0
    prev_idx = evaluator.launch_idx
    for tid in target_ids:
        tid_idx = (
            evaluator.idx_arr[tid]
            if tid < len(evaluator.idx_arr)
            else evaluator.id_to_idx.get(tid, tid)
        )
        curr_t += float(evaluator.time_mat[prev_idx, tid_idx])
        arr_times[tid] = curr_t
        curr_t += float(
            evaluator.dwell_t_arr[tid]
            if tid < len(evaluator.dwell_t_arr)
            else evaluator.dwell_times.get(tid, 0.0)
        )
        prev_idx = tid_idx

    max_d = evaluator.max_d
    max_t = max(drone.max_flight_time, curr_t, 1.0)
    max_score = evaluator.max_score

    # Initial seed target selected uniformly at random
    seed_idx = random.randrange(len(target_ids))
    seed_target = target_ids[seed_idx]
    removed: list[int] = [seed_target]
    remaining: list[int] = [tid for tid in target_ids if tid != seed_target]

    while len(removed) < q and remaining:
        ref_id = random.choice(removed)
        ref_node = node_map[ref_id]
        t_ref = arr_times.get(ref_id, 0.0)

        relatedness_scores: list[tuple[float, int]] = []
        for cand_id in remaining:
            cand_node = node_map[cand_id]
            dist = math.hypot(ref_node.x - cand_node.x, ref_node.y - cand_node.y)
            dist_term = dist / max_d

            t_cand = arr_times.get(cand_id, 0.0)
            time_term = abs(t_ref - t_cand) / max_t

            score_term = abs(ref_node.priority_score - cand_node.priority_score) / max_score

            rel = phi1 * dist_term + phi2 * time_term + phi3 * score_term
            relatedness_scores.append((rel, cand_id))

        relatedness_scores.sort(key=lambda x: x[0])
        # Randomized selection bias r^p favoring most related (minimum R)
        idx = int(len(relatedness_scores) * (random.random() ** p_determinism))
        chosen_id = relatedness_scores[min(idx, len(relatedness_scores) - 1)][1]
        removed.append(chosen_id)
        remaining.remove(chosen_id)

    # Keep remaining in their original relative sequence
    removed_set = set(removed)
    remaining_ordered = [tid for tid in target_ids if tid not in removed_set]
    return remaining_ordered, removed


def destroy_worst_cost_efficiency(
    target_ids: list[int],
    q: int,
    drone: DroneSpec,
    instance: InstanceContext,
    p_determinism: float = 3.0,
    evaluator: EvaluatorContext | None = None,
) -> tuple[list[int], list[int]]:
    """
    Worst-Cost Efficiency Detour Destroy.
    Target efficiency: eta_i = R_i / Delta_Energy_i
    where Delta_Energy_i = E_{p, i} + E_{i, s} - E_{p, s} + E_dwell_i.
    Removes q worst-performing detours with randomized bias.
    """
    if q <= 0:
        return list(target_ids), []
    if len(target_ids) <= q:
        return [], list(target_ids)

    if evaluator is None:
        evaluator = EvaluatorContext(drone, instance)

    full_seq = [drone.launch_depot_id] + target_ids + [drone.recovery_depot_id]
    seq_idx = [
        evaluator.idx_arr[nid]
        if nid < len(evaluator.idx_arr)
        else evaluator.id_to_idx.get(nid, nid)
        for nid in full_seq
    ]

    efficiency_list: list[tuple[float, int]] = []
    for i, tid in enumerate(target_ids):
        p = seq_idx[i]
        c = seq_idx[i + 1]
        s = seq_idx[i + 2]
        dwell_e = (
            evaluator.dwell_e_arr[tid]
            if tid < len(evaluator.dwell_e_arr)
            else evaluator.dwell_energies.get(tid, 0.0)
        )
        delta_energy = (
            evaluator.energy_mat[p, c]
            + evaluator.energy_mat[c, s]
            - evaluator.energy_mat[p, s]
            + dwell_e
        )
        reward = (
            evaluator.reward_arr[tid]
            if tid < len(evaluator.reward_arr)
            else evaluator.priority_scores.get(tid, 0.0)
        )
        eta = reward / max(delta_energy, 1e-3)
        efficiency_list.append((eta, tid))

    efficiency_list.sort(key=lambda x: x[0])  # Ascending: worst efficiency first

    removed: list[int] = []
    pool = list(efficiency_list)
    while len(removed) < q and pool:
        idx = int(len(pool) * (random.random() ** p_determinism))
        chosen_id = pool.pop(min(idx, len(pool) - 1))[1]
        removed.append(chosen_id)

    removed_set = set(removed)
    remaining = [tid for tid in target_ids if tid not in removed_set]
    return remaining, removed


def destroy_radial_cone(
    target_ids: list[int],
    q: int,
    drone: DroneSpec,
    instance: InstanceContext,
    evaluator: EvaluatorContext | None = None,
) -> tuple[list[int], list[int]]:
    """
    Radial Angular Cone Destroy.
    theta_i = atan2(y_i - y_depot, x_i - x_depot).
    Removes all targets within angular cone [theta_0 - Delta theta, theta_0 + Delta theta].
    """
    if q <= 0:
        return list(target_ids), []
    if len(target_ids) <= q:
        return [], list(target_ids)

    if evaluator is None:
        evaluator = EvaluatorContext(drone, instance)

    node_map = evaluator.node_map
    depot = node_map.get(drone.launch_depot_id, instance.targets[0])

    angles: list[tuple[float, int]] = []
    for tid in target_ids:
        node = node_map[tid]
        theta = math.atan2(node.y - depot.y, node.x - depot.x)
        angles.append((theta, tid))

    # Center cone on a randomly chosen target from the route
    seed_tid = random.choice(target_ids)
    seed_node = node_map[seed_tid]
    center_theta = math.atan2(seed_node.y - depot.y, seed_node.x - depot.x)

    def angular_dist(th: float) -> float:
        d = abs(th - center_theta)
        return min(d, 2.0 * math.pi - d)

    angles.sort(key=lambda x: angular_dist(x[0]))
    removed = [tid for _, tid in angles[:q]]
    removed_set = set(removed)
    remaining = [tid for tid in target_ids if tid not in removed_set]
    return remaining, removed


def destroy_contiguous_string(
    target_ids: list[int],
    q: int,
    drone: DroneSpec,
    instance: InstanceContext,
    evaluator: EvaluatorContext | None = None,
) -> tuple[list[int], list[int]]:
    """
    Contiguous String Destroy.
    Ejects a continuous chain of adjacent targets along the route.
    """
    if q <= 0:
        return list(target_ids), []
    n = len(target_ids)
    if n <= q:
        return [], list(target_ids)

    length = min(q, n)
    start = random.randint(0, n - length)
    removed = target_ids[start : start + length]
    remaining = target_ids[:start] + target_ids[start + length :]
    return remaining, removed


# ---------------------------------------------------------------------------
# Repair Operators
# ---------------------------------------------------------------------------


def repair_greedy_insertion(
    current_route: list[int],
    unassigned_pool: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
    evaluator: EvaluatorContext | None = None,
) -> list[int]:
    """
    Greedy Insertion: Evaluates every unassigned target across every insertion slot (i, i+1),
    greedily inserting the target yielding maximum Delta R / Delta Energy without violating
    battery reserve or flight deadline.
    """
    if evaluator is None:
        evaluator = EvaluatorContext(drone, instance)

    route = list(current_route)
    pool = set(unassigned_pool) - set(route)
    if not pool:
        return route

    energy_mat = evaluator.energy_mat
    time_mat = evaluator.time_mat
    idx_arr = evaluator.idx_arr
    launch_idx = evaluator.launch_idx
    recovery_idx = evaluator.recovery_idx
    usable_bat = evaluator.usable_battery + 1e-4
    max_time = evaluator.max_time + 1e-4
    dwell_e_arr = evaluator.dwell_e_arr
    dwell_t_arr = evaluator.dwell_t_arr
    reward_arr = evaluator.reward_arr

    curr_energy, curr_time, _ = evaluator.compute_route_totals(route)

    while pool:
        n = len(route)
        route_indices = [
            idx_arr[tid] if tid < len(idx_arr) else evaluator.id_to_idx.get(tid, tid)
            for tid in route
        ]
        slot_p = [launch_idx if s == 0 else route_indices[s - 1] for s in range(n + 1)]
        slot_s = [recovery_idx if s == n else route_indices[s] for s in range(n + 1)]
        base_slot_e = [energy_mat[slot_p[s], slot_s[s]] for s in range(n + 1)]
        base_slot_t = [time_mat[slot_p[s], slot_s[s]] for s in range(n + 1)]

        best_cand: int | None = None
        best_slot: int = -1
        best_ratio: float = -1.0
        best_de: float = 0.0
        best_dt: float = 0.0

        for cand_id in pool:
            c = (
                idx_arr[cand_id]
                if cand_id < len(idx_arr)
                else evaluator.id_to_idx.get(cand_id, cand_id)
            )
            reward = (
                reward_arr[cand_id]
                if cand_id < len(reward_arr)
                else evaluator.priority_scores.get(cand_id, 0.0)
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

            for s in range(n + 1):
                p = slot_p[s]
                succ = slot_s[s]
                delta_e = energy_mat[p, c] + energy_mat[c, succ] - base_slot_e[s] + d_e
                delta_t = time_mat[p, c] + time_mat[c, succ] - base_slot_t[s] + d_t

                if curr_energy + delta_e <= usable_bat and curr_time + delta_t <= max_time:
                    ratio = reward / max(delta_e, 1.0)
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_cand = cand_id
                        best_slot = s
                        best_de = delta_e
                        best_dt = delta_t

        if best_cand is not None:
            route.insert(best_slot, best_cand)
            curr_energy += best_de
            curr_time += best_dt
            pool.remove(best_cand)
        else:
            break

    return route


def repair_regret2_insertion(
    current_route: list[int],
    unassigned_pool: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
    big_m: float = 1e6,
    evaluator: EvaluatorContext | None = None,
) -> list[int]:
    """
    Regret-2 Insertion: Computes difference between best insertion cost c1(u) and
    second-best insertion cost c2(u). Target with highest regret is inserted first.
    """
    if evaluator is None:
        evaluator = EvaluatorContext(drone, instance)

    route = list(current_route)
    pool = set(unassigned_pool) - set(route)
    if not pool:
        return route

    energy_mat = evaluator.energy_mat
    time_mat = evaluator.time_mat
    idx_arr = evaluator.idx_arr
    launch_idx = evaluator.launch_idx
    recovery_idx = evaluator.recovery_idx
    usable_bat = evaluator.usable_battery + 1e-4
    max_time = evaluator.max_time + 1e-4
    dwell_e_arr = evaluator.dwell_e_arr
    dwell_t_arr = evaluator.dwell_t_arr
    reward_arr = evaluator.reward_arr

    curr_energy, curr_time, _ = evaluator.compute_route_totals(route)

    while pool:
        n = len(route)
        route_indices = [
            idx_arr[tid] if tid < len(idx_arr) else evaluator.id_to_idx.get(tid, tid)
            for tid in route
        ]
        slot_p = [launch_idx if s == 0 else route_indices[s - 1] for s in range(n + 1)]
        slot_s = [recovery_idx if s == n else route_indices[s] for s in range(n + 1)]
        base_slot_e = [energy_mat[slot_p[s], slot_s[s]] for s in range(n + 1)]
        base_slot_t = [time_mat[slot_p[s], slot_s[s]] for s in range(n + 1)]

        max_regret = -1.0
        chosen_cand: int | None = None
        chosen_slot: int = -1
        chosen_de: float = 0.0
        chosen_dt: float = 0.0

        for cand_id in pool:
            c = (
                idx_arr[cand_id]
                if cand_id < len(idx_arr)
                else evaluator.id_to_idx.get(cand_id, cand_id)
            )
            reward = (
                reward_arr[cand_id]
                if cand_id < len(reward_arr)
                else evaluator.priority_scores.get(cand_id, 0.0)
            )
            inv_reward = 1.0 / max(reward, 1.0)
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

            c1 = float("inf")
            c2 = float("inf")
            s1 = -1
            de1 = 0.0
            dt1 = 0.0

            for s in range(n + 1):
                p = slot_p[s]
                succ = slot_s[s]
                delta_e = energy_mat[p, c] + energy_mat[c, succ] - base_slot_e[s] + d_e
                delta_t = time_mat[p, c] + time_mat[c, succ] - base_slot_t[s] + d_t

                if curr_energy + delta_e <= usable_bat and curr_time + delta_t <= max_time:
                    cost = delta_e * inv_reward
                    if cost < c1:
                        c2 = c1
                        c1 = cost
                        s1 = s
                        de1 = delta_e
                        dt1 = delta_t
                    elif cost < c2:
                        c2 = cost

            if s1 == -1:
                continue

            c2_pen = c2 if c2 != float("inf") else c1 + big_m
            regret = c2_pen - c1

            if regret > max_regret:
                max_regret = regret
                chosen_cand = cand_id
                chosen_slot = s1
                chosen_de = de1
                chosen_dt = dt1

        if chosen_cand is not None:
            route.insert(chosen_slot, chosen_cand)
            curr_energy += chosen_de
            curr_time += chosen_dt
            pool.remove(chosen_cand)
        else:
            break

    return route


def repair_big_m_regret3_insertion(
    current_route: list[int],
    unassigned_pool: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
    big_m: float = 1e6,
    evaluator: EvaluatorContext | None = None,
) -> list[int]:
    """
    Corrected Big-M Regret-3 Insertion.
    Evaluates top 3 insertion positions. Missing feasible positions are penalized with M = 10^6:
    Regret_3(u) = sum_{r=2}^3 (c_r(u) - c_1(u))
    Guarantees time-critical targets nearing deadline expiration are scheduled before slots close.
    """
    if evaluator is None:
        evaluator = EvaluatorContext(drone, instance)

    route = list(current_route)
    pool = set(unassigned_pool) - set(route)
    if not pool:
        return route

    energy_mat = evaluator.energy_mat
    time_mat = evaluator.time_mat
    idx_arr = evaluator.idx_arr
    launch_idx = evaluator.launch_idx
    recovery_idx = evaluator.recovery_idx
    usable_bat = evaluator.usable_battery + 1e-4
    max_time = evaluator.max_time + 1e-4
    dwell_e_arr = evaluator.dwell_e_arr
    dwell_t_arr = evaluator.dwell_t_arr
    reward_arr = evaluator.reward_arr

    curr_energy, curr_time, _ = evaluator.compute_route_totals(route)

    while pool:
        n = len(route)
        route_indices = [
            idx_arr[tid] if tid < len(idx_arr) else evaluator.id_to_idx.get(tid, tid)
            for tid in route
        ]
        slot_p = [launch_idx if s == 0 else route_indices[s - 1] for s in range(n + 1)]
        slot_s = [recovery_idx if s == n else route_indices[s] for s in range(n + 1)]
        base_slot_e = [energy_mat[slot_p[s], slot_s[s]] for s in range(n + 1)]
        base_slot_t = [time_mat[slot_p[s], slot_s[s]] for s in range(n + 1)]

        max_regret = -1.0
        chosen_cand: int | None = None
        chosen_slot: int = -1
        chosen_de: float = 0.0
        chosen_dt: float = 0.0

        for cand_id in pool:
            c = (
                idx_arr[cand_id]
                if cand_id < len(idx_arr)
                else evaluator.id_to_idx.get(cand_id, cand_id)
            )
            reward = (
                reward_arr[cand_id]
                if cand_id < len(reward_arr)
                else evaluator.priority_scores.get(cand_id, 0.0)
            )
            inv_reward = 1.0 / max(reward, 1.0)
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

            c1 = float("inf")
            c2 = float("inf")
            c3 = float("inf")
            s1 = -1
            de1 = 0.0
            dt1 = 0.0

            for s in range(n + 1):
                p = slot_p[s]
                succ = slot_s[s]
                delta_e = energy_mat[p, c] + energy_mat[c, succ] - base_slot_e[s] + d_e
                delta_t = time_mat[p, c] + time_mat[c, succ] - base_slot_t[s] + d_t

                if curr_energy + delta_e <= usable_bat and curr_time + delta_t <= max_time:
                    cost = delta_e * inv_reward
                    if cost < c1:
                        c3 = c2
                        c2 = c1
                        c1 = cost
                        s1 = s
                        de1 = delta_e
                        dt1 = delta_t
                    elif cost < c2:
                        c3 = c2
                        c2 = cost
                    elif cost < c3:
                        c3 = cost

            if s1 == -1:
                continue

            c2_pen = c2 if c2 != float("inf") else c1 + big_m
            c3_pen = c3 if c3 != float("inf") else c1 + big_m
            regret3 = (c2_pen - c1) + (c3_pen - c1)

            if regret3 > max_regret:
                max_regret = regret3
                chosen_cand = cand_id
                chosen_slot = s1
                chosen_de = de1
                chosen_dt = dt1

        if chosen_cand is not None:
            route.insert(chosen_slot, chosen_cand)
            curr_energy += chosen_de
            curr_time += chosen_dt
            pool.remove(chosen_cand)
        else:
            break

    return route
