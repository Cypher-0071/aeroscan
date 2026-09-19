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

        self.dwell_times = {n.id: n.dwell_time for n in instance.targets}
        self.dwell_energies = {
            n.id: compute_dwell_energy(n.dwell_time) if n.dwell_time > 0 else 0.0
            for n in instance.targets
        }
        self.priority_scores = {n.id: n.priority_score for n in instance.targets}

    def compute_delta(self, pred_id: int, cand_id: int, succ_id: int) -> tuple[float, float]:
        """
        Computes (delta_energy, delta_time) for inserting cand_id between pred_id and succ_id.
        O(1) execution with zero allocations.
        """
        p = self.id_to_idx.get(pred_id, pred_id)
        c = self.id_to_idx.get(cand_id, cand_id)
        s = self.id_to_idx.get(succ_id, succ_id)

        delta_energy = float(
            self.energy_mat[p, c]
            + self.energy_mat[c, s]
            - self.energy_mat[p, s]
            + self.dwell_energies.get(cand_id, 0.0)
        )
        delta_time = float(
            self.time_mat[p, c]
            + self.time_mat[c, s]
            - self.time_mat[p, s]
            + self.dwell_times.get(cand_id, 0.0)
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

        total_energy = 0.0
        total_time = 0.0
        total_reward = 0.0

        seq_indices = (
            [self.launch_idx] + [self.id_to_idx[tid] for tid in route] + [self.recovery_idx]
        )
        for i in range(len(seq_indices) - 1):
            u = seq_indices[i]
            v = seq_indices[i + 1]
            total_energy += float(self.energy_mat[u, v])
            total_time += float(self.time_mat[u, v])

        for tid in route:
            total_energy += self.dwell_energies.get(tid, 0.0)
            total_time += self.dwell_times.get(tid, 0.0)
            total_reward += self.priority_scores.get(tid, 0.0)

        return total_energy, total_time, total_reward


def evaluate_route_trajectory(
    target_ids: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
) -> CandidateRoute | None:
    """
    Evaluates a candidate target sequence for a drone from launch to recovery depot.
    Computes continuous arrival/departure times, dwell durations, and cumulative energy.
    Returns CandidateRoute if feasible under both time deadline and 15% battery reserve.
    Returns None if infeasible or duplicate targets are detected.
    """
    if len(target_ids) != len(set(target_ids)):
        return None

    node_map = {n.id: n for n in instance.targets}
    launch_id = drone.launch_depot_id
    recovery_id = drone.recovery_depot_id

    # Complete sequence of node IDs: launch -> targets -> recovery
    full_sequence = [launch_id] + list(target_ids) + [recovery_id]

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
        from_id = full_sequence[idx]
        to_id = full_sequence[idx + 1]

        # Transit time and energy from precomputed matrices (node ID safe)
        transit_time = instance.get_transit_time(from_id, to_id)
        transit_energy = instance.get_transit_energy(from_id, to_id)

        arr_time = current_time + transit_time
        target_node = node_map.get(to_id)
        dwell_time = target_node.dwell_time if (target_node and to_id != recovery_id) else 0.0
        dwell_energy = (
            compute_dwell_energy(dwell_time) if (dwell_time > 0 and to_id != recovery_id) else 0.0
        )

        dep_time = arr_time + dwell_time
        node_energy = current_energy + transit_energy + dwell_energy

        current_time = dep_time
        current_energy = node_energy

        if to_id != recovery_id and target_node:
            total_reward += target_node.priority_score

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

    node_map = {n.id: n for n in instance.targets}

    # Precalculate exact arrival times along current route sequence
    arr_times: dict[int, float] = {}
    curr_t = 0.0
    prev_id = drone.launch_depot_id
    for tid in target_ids:
        curr_t += instance.get_transit_time(prev_id, tid)
        arr_times[tid] = curr_t
        node = node_map.get(tid)
        if node:
            curr_t += node.dwell_time
        prev_id = tid

    # Maximum distance, flight time, and score normalizers
    coords = np.array([[n.x, n.y] for n in instance.targets], dtype=np.float64)
    if len(coords) > 1:
        diffs = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
        max_d = max(float(np.max(np.sqrt(np.sum(diffs**2, axis=-1)))), 1.0)
    else:
        max_d = 1.0

    max_t = max(drone.max_flight_time, curr_t, 1.0)
    max_score = max(
        (n.priority_score for n in instance.targets if n.priority_score > 0), default=1.0
    )

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

    node_map = {n.id: n for n in instance.targets}
    full_seq = [drone.launch_depot_id] + target_ids + [drone.recovery_depot_id]

    efficiency_list: list[tuple[float, int]] = []
    for i, tid in enumerate(target_ids):
        pred = full_seq[i]
        succ = full_seq[i + 2]
        dwell_e = compute_dwell_energy(node_map[tid].dwell_time) if tid in node_map else 0.0
        delta_energy = (
            instance.get_transit_energy(pred, tid)
            + instance.get_transit_energy(tid, succ)
            - instance.get_transit_energy(pred, succ)
            + dwell_e
        )
        reward = node_map[tid].priority_score if tid in node_map else 0.0
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

    depot = next(
        (n for n in instance.targets if n.id == drone.launch_depot_id), instance.targets[0]
    )
    node_map = {n.id: n for n in instance.targets}

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
) -> list[int]:
    """
    Greedy Insertion: Evaluates every unassigned target across every insertion slot (i, i+1),
    greedily inserting the target yielding maximum Delta R / Delta Energy without violating
    battery reserve or flight deadline.
    """
    evaluator = EvaluatorContext(drone, instance)
    route = list(current_route)
    pool = set(unassigned_pool) - set(route)
    if not pool:
        return route

    curr_energy, curr_time, _ = evaluator.compute_route_totals(route)

    while pool:
        best_candidate: int | None = None
        best_slot: int = -1
        best_ratio: float = -1.0
        best_delta_e: float = 0.0
        best_delta_t: float = 0.0

        n = len(route)
        for cand_id in list(pool):
            reward = evaluator.priority_scores.get(cand_id, 0.0)
            for slot in range(n + 1):
                pred_id = evaluator.launch_id if slot == 0 else route[slot - 1]
                succ_id = evaluator.recovery_id if slot == n else route[slot]

                delta_e, delta_t = evaluator.compute_delta(pred_id, cand_id, succ_id)
                new_e = curr_energy + delta_e
                new_t = curr_time + delta_t

                if new_e <= evaluator.usable_battery + 1e-4 and new_t <= evaluator.max_time + 1e-4:
                    ratio = reward / max(delta_e, 1.0)
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_candidate = cand_id
                        best_slot = slot
                        best_delta_e = delta_e
                        best_delta_t = delta_t

        if best_candidate is not None:
            route.insert(best_slot, best_candidate)
            curr_energy += best_delta_e
            curr_time += best_delta_t
            pool.remove(best_candidate)
        else:
            break

    return route


def repair_regret2_insertion(
    current_route: list[int],
    unassigned_pool: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
    big_m: float = 1e6,
) -> list[int]:
    """
    Regret-2 Insertion: Computes difference between best insertion cost c1(u) and
    second-best insertion cost c2(u). Target with highest regret is inserted first.
    """
    evaluator = EvaluatorContext(drone, instance)
    route = list(current_route)
    pool = set(unassigned_pool) - set(route)
    if not pool:
        return route

    curr_energy, curr_time, _ = evaluator.compute_route_totals(route)

    while pool:
        max_regret = -1.0
        chosen_candidate: int | None = None
        chosen_slot: int = -1
        chosen_delta_e: float = 0.0
        chosen_delta_t: float = 0.0

        n = len(route)
        for cand_id in list(pool):
            reward = evaluator.priority_scores.get(cand_id, 0.0)
            costs: list[tuple[float, int, float, float]] = []  # (cost, slot, delta_e, delta_t)

            for slot in range(n + 1):
                pred_id = evaluator.launch_id if slot == 0 else route[slot - 1]
                succ_id = evaluator.recovery_id if slot == n else route[slot]

                delta_e, delta_t = evaluator.compute_delta(pred_id, cand_id, succ_id)
                new_e = curr_energy + delta_e
                new_t = curr_time + delta_t

                if new_e <= evaluator.usable_battery + 1e-4 and new_t <= evaluator.max_time + 1e-4:
                    cost = delta_e / max(reward, 1.0)
                    costs.append((cost, slot, delta_e, delta_t))

            if not costs:
                continue

            costs.sort(key=lambda x: x[0])
            c1, s1, de1, dt1 = costs[0]
            c2 = costs[1][0] if len(costs) > 1 else c1 + big_m
            regret = c2 - c1

            if regret > max_regret:
                max_regret = regret
                chosen_candidate = cand_id
                chosen_slot = s1
                chosen_delta_e = de1
                chosen_delta_t = dt1

        if chosen_candidate is not None:
            route.insert(chosen_slot, chosen_candidate)
            curr_energy += chosen_delta_e
            curr_time += chosen_delta_t
            pool.remove(chosen_candidate)
        else:
            break

    return route


def repair_big_m_regret3_insertion(
    current_route: list[int],
    unassigned_pool: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
    big_m: float = 1e6,
) -> list[int]:
    """
    Corrected Big-M Regret-3 Insertion.
    Evaluates top 3 insertion positions. Missing feasible positions are penalized with M = 10^6:
    Regret_3(u) = sum_{r=2}^3 (c_r(u) - c_1(u))
    Guarantees time-critical targets nearing deadline expiration are scheduled before slots close.
    """
    evaluator = EvaluatorContext(drone, instance)
    route = list(current_route)
    pool = set(unassigned_pool) - set(route)
    if not pool:
        return route

    curr_energy, curr_time, _ = evaluator.compute_route_totals(route)

    while pool:
        max_regret = -1.0
        chosen_candidate: int | None = None
        chosen_slot: int = -1
        chosen_delta_e: float = 0.0
        chosen_delta_t: float = 0.0

        n = len(route)
        for cand_id in list(pool):
            reward = evaluator.priority_scores.get(cand_id, 0.0)
            costs: list[tuple[float, int, float, float]] = []

            for slot in range(n + 1):
                pred_id = evaluator.launch_id if slot == 0 else route[slot - 1]
                succ_id = evaluator.recovery_id if slot == n else route[slot]

                delta_e, delta_t = evaluator.compute_delta(pred_id, cand_id, succ_id)
                new_e = curr_energy + delta_e
                new_t = curr_time + delta_t

                if new_e <= evaluator.usable_battery + 1e-4 and new_t <= evaluator.max_time + 1e-4:
                    cost = delta_e / max(reward, 1.0)
                    costs.append((cost, slot, delta_e, delta_t))

            if not costs:
                continue

            costs.sort(key=lambda x: x[0])
            c1, s1, de1, dt1 = costs[0]
            c2 = costs[1][0] if len(costs) > 1 else c1 + big_m
            c3 = costs[2][0] if len(costs) > 2 else c1 + big_m
            regret3 = (c2 - c1) + (c3 - c1)

            if regret3 > max_regret:
                max_regret = regret3
                chosen_candidate = cand_id
                chosen_slot = s1
                chosen_delta_e = de1
                chosen_delta_t = dt1

        if chosen_candidate is not None:
            route.insert(chosen_slot, chosen_candidate)
            curr_energy += chosen_delta_e
            curr_time += chosen_delta_t
            pool.remove(chosen_candidate)
        else:
            break

    return route
