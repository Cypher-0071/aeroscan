"""Adaptive Large Neighborhood Search (ALNS) Destroy and Repair Operators.

Contains:
- 4 Destroy Operators: Shaw Spatio-Temporal, Worst-Cost Detour, Radial Angular Cone, Contiguous String.
- 3 Repair Operators: Greedy Insertion, Regret-2 Insertion, Corrected Big-M Regret-3 Insertion.
- Trajectory evaluation utilities for feasibility, dwell, and energy checks.
"""

from __future__ import annotations

import math
import random

import numpy as np

from core.contracts import CandidateRoute, DroneSpec, InstanceContext, WaypointVisit
from core.physics import compute_dwell_energy


def evaluate_route_trajectory(
    target_ids: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
) -> CandidateRoute | None:
    """
    Evaluates a candidate target sequence for a drone from launch to recovery depot.
    Computes continuous arrival/departure times, dwell durations, and cumulative energy.
    Returns CandidateRoute if feasible under both time deadline and 15% battery reserve.
    Returns None if infeasible.
    """
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
        dwell_energy = compute_dwell_energy(dwell_time) if (dwell_time > 0 and to_id != recovery_id) else 0.0

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
    if current_energy > max_allowed_energy or current_time > drone.max_flight_time:
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
    R(i, j) = phi1 * (dist_ij / max_dist) + phi2 * (|t_arr_i - t_arr_j| / max_t) + phi3 * (|R_i - R_j| / max_R)
    """
    if len(target_ids) <= q:
        return [], list(target_ids)

    node_map = {n.id: n for n in instance.targets}
    # Initial seed target selected uniformly at random
    seed_idx = random.randrange(len(target_ids))
    seed_target = target_ids[seed_idx]
    removed: list[int] = [seed_target]
    remaining: list[int] = [tid for tid in target_ids if tid != seed_target]

    max_dist = max(float(np.max(instance.time_matrix)), 1.0)
    max_score = max((n.priority_score for n in instance.targets if n.priority_score > 0), default=1.0)

    while len(removed) < q and remaining:
        ref_id = random.choice(removed)
        ref_node = node_map[ref_id]

        relatedness_scores: list[tuple[float, int]] = []
        for cand_id in remaining:
            cand_node = node_map[cand_id]
            dist_term = instance.get_transit_time(ref_id, cand_id) / max_dist
            score_term = abs(ref_node.priority_score - cand_node.priority_score) / max_score
            # Temporal proximity approximation
            rel = phi1 * dist_term + (phi2 + phi3) * score_term
            relatedness_scores.append((rel, cand_id))

        relatedness_scores.sort(key=lambda x: x[0])
        # Randomized selection bias r^p
        idx = int(len(relatedness_scores) * (random.random() ** p_determinism))
        chosen_id = relatedness_scores[min(idx, len(relatedness_scores) - 1)][1]
        removed.append(chosen_id)
        remaining.remove(chosen_id)

    return remaining, removed


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
    Removes q targets with worst energy efficiency.
    """
    if len(target_ids) <= q:
        return [], list(target_ids)

    node_map = {n.id: n for n in instance.targets}
    full_seq = [drone.launch_depot_id] + target_ids + [drone.recovery_depot_id]

    efficiency_list: list[tuple[float, int]] = []
    for i, tid in enumerate(target_ids):
        pred = full_seq[i]
        succ = full_seq[i + 2]
        delta_energy = (
            instance.get_transit_energy(pred, tid)
            + instance.get_transit_energy(tid, succ)
            - instance.get_transit_energy(pred, succ)
            + compute_dwell_energy(node_map[tid].dwell_time)
        )
        reward = node_map[tid].priority_score
        eta = reward / max(delta_energy, 1.0)
        efficiency_list.append((eta, tid))

    efficiency_list.sort(key=lambda x: x[0])  # Ascending: worst efficiency first

    removed: list[int] = []
    remaining = list(target_ids)
    while len(removed) < q and efficiency_list:
        idx = int(len(efficiency_list) * (random.random() ** p_determinism))
        chosen_id = efficiency_list.pop(min(idx, len(efficiency_list) - 1))[1]
        removed.append(chosen_id)
        remaining.remove(chosen_id)

    return remaining, removed


def destroy_radial_cone(
    target_ids: list[int],
    q: int,
    drone: DroneSpec,
    instance: InstanceContext,
) -> tuple[list[int], list[int]]:
    """
    Radial Angular Cone Destroy.
    Calculates polar angle relative to launch depot and removes targets within an angular sector.
    """
    if len(target_ids) <= q:
        return [], list(target_ids)

    depot = next((n for n in instance.targets if n.id == drone.launch_depot_id), instance.targets[0])
    node_map = {n.id: n for n in instance.targets}

    angles: list[tuple[float, int]] = []
    for tid in target_ids:
        node = node_map[tid]
        theta = math.atan2(node.y - depot.y, node.x - depot.x)
        angles.append((theta, tid))

    # Pick a random center angle
    center_theta = random.uniform(-math.pi, math.pi)

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
    Ejects a continuous chain of L targets along the route.
    """
    n = len(target_ids)
    if n <= q:
        return [], list(target_ids)

    length = max(2, min(q, n))
    start = random.randint(0, n - length)
    removed = target_ids[start : start + length]
    remaining = target_ids[:start] + target_ids[start + length :]
    return remaining, removed


# ---------------------------------------------------------------------------
# Repair Operators
# ---------------------------------------------------------------------------

def calculate_insertion_delta(
    cand_id: int,
    slot_idx: int,
    current_route: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
) -> tuple[float, float, float] | None:
    """
    Evaluates inserting cand_id at position slot_idx in current_route.
    Returns (delta_energy, delta_time, delta_reward) if feasible, else None.
    """
    new_route = current_route[:slot_idx] + [cand_id] + current_route[slot_idx:]
    eval_res = evaluate_route_trajectory(new_route, drone, instance)
    if eval_res is None:
        return None

    node = next(n for n in instance.targets if n.id == cand_id)
    return (eval_res.total_energy_joules, eval_res.total_flight_time, node.priority_score)


def repair_greedy_insertion(
    current_route: list[int],
    unassigned_pool: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
) -> list[int]:
    """
    Greedy Insertion: Evaluates every unassigned target across every slot,
    greedily inserting candidate yielding maximum Delta Reward / Delta Energy.
    """
    route = list(current_route)
    pool = set(unassigned_pool) - set(route)
    node_map = {n.id: n for n in instance.targets}

    while pool:
        base_eval = evaluate_route_trajectory(route, drone, instance)
        base_energy = base_eval.total_energy_joules if base_eval else 0.0

        best_candidate: int | None = None
        best_slot: int = -1
        best_ratio: float = -1.0

        for cand_id in list(pool):
            node = node_map.get(cand_id)
            if not node:
                continue
            for slot in range(len(route) + 1):
                test_route = route[:slot] + [cand_id] + route[slot:]
                res = evaluate_route_trajectory(test_route, drone, instance)
                if res is not None:
                    delta_energy = max(1.0, res.total_energy_joules - base_energy)
                    ratio = node.priority_score / delta_energy
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_candidate = cand_id
                        best_slot = slot

        if best_candidate is not None:
            route.insert(best_slot, best_candidate)
            pool.remove(best_candidate)
        else:
            break

    return route


def repair_regret2_insertion(
    current_route: list[int],
    unassigned_pool: list[int],
    drone: DroneSpec,
    instance: InstanceContext,
) -> list[int]:
    """
    Regret-2 Insertion: Computes difference between best and second-best insertion cost.
    Target with highest regret is inserted first.
    """
    route = list(current_route)
    pool = set(unassigned_pool) - set(route)
    node_map = {n.id: n for n in instance.targets}

    while pool:
        base_eval = evaluate_route_trajectory(route, drone, instance)
        base_energy = base_eval.total_energy_joules if base_eval else 0.0

        max_regret = -1.0
        chosen_candidate: int | None = None
        chosen_slot: int = -1

        for cand_id in list(pool):
            node = node_map.get(cand_id)
            if not node:
                continue
            costs: list[tuple[float, int]] = []
            for slot in range(len(route) + 1):
                test_route = route[:slot] + [cand_id] + route[slot:]
                res = evaluate_route_trajectory(test_route, drone, instance)
                if res is not None:
                    delta_energy = max(1.0, res.total_energy_joules - base_energy)
                    cost = delta_energy / max(node.priority_score, 1.0)
                    costs.append((cost, slot))

            if not costs:
                continue

            costs.sort(key=lambda x: x[0])
            c1, s1 = costs[0]
            c2 = costs[1][0] if len(costs) > 1 else c1 + 1000.0
            regret = c2 - c1

            if regret > max_regret:
                max_regret = regret
                chosen_candidate = cand_id
                chosen_slot = s1

        if chosen_candidate is not None:
            route.insert(chosen_slot, chosen_candidate)
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
    Evaluates top 3 insertion positions. Missing feasible positions are penalized with M.
    Regret3 = sum_{r=2}^3 (c_r - c_1)
    """
    route = list(current_route)
    pool = set(unassigned_pool) - set(route)
    node_map = {n.id: n for n in instance.targets}

    while pool:
        base_eval = evaluate_route_trajectory(route, drone, instance)
        base_energy = base_eval.total_energy_joules if base_eval else 0.0

        max_regret = -1.0
        chosen_candidate: int | None = None
        chosen_slot: int = -1

        for cand_id in list(pool):
            node = node_map.get(cand_id)
            if not node:
                continue
            costs: list[tuple[float, int]] = []
            for slot in range(len(route) + 1):
                test_route = route[:slot] + [cand_id] + route[slot:]
                res = evaluate_route_trajectory(test_route, drone, instance)
                if res is not None:
                    delta_energy = max(1.0, res.total_energy_joules - base_energy)
                    cost = delta_energy / max(node.priority_score, 1.0)
                    costs.append((cost, slot))

            if not costs:
                continue

            costs.sort(key=lambda x: x[0])
            c1, s1 = costs[0]
            c2 = costs[1][0] if len(costs) > 1 else c1 + big_m
            c3 = costs[2][0] if len(costs) > 2 else c1 + big_m
            regret3 = (c2 - c1) + (c3 - c1)

            if regret3 > max_regret:
                max_regret = regret3
                chosen_candidate = cand_id
                chosen_slot = s1

        if chosen_candidate is not None:
            route.insert(chosen_slot, chosen_candidate)
            pool.remove(chosen_candidate)
        else:
            break

    return route
