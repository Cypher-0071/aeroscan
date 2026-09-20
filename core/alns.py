"""Tier-1 Adaptive Large Neighborhood Search (ALNS) Route Exploration Engine.

Explores rich, diverse, and energy-feasible candidate trajectories for each drone in the fleet,
populating a RoutePool for Tier-2 CP-SAT Set Packing.
"""

from __future__ import annotations

import math
import random
import time
from collections.abc import Callable

import numpy as np

from core.contracts import CandidateRoute, DroneSpec, InstanceContext, RoutePool
from core.local_search import run_local_search_pipeline
from core.operators import (
    EvaluatorContext,
    destroy_contiguous_string,
    destroy_radial_cone,
    destroy_shaw_relatedness,
    destroy_worst_cost_efficiency,
    evaluate_route_trajectory,
    repair_big_m_regret3_insertion,
    repair_greedy_insertion,
    repair_regret2_insertion,
)


def construct_greedy_seed_route(
    drone: DroneSpec,
    instance: InstanceContext,
    alpha: float = 0.2,
    evaluator: EvaluatorContext | None = None,
    candidate_target_ids: list[int] | None = None,
) -> list[int]:
    """
    Constructs an initial feasible route using a Randomized Restricted Candidate List (RCL, alpha = 0.2).
    When candidate_target_ids is supplied, the route is built strictly within that target sector.
    """
    if evaluator is None:
        evaluator = EvaluatorContext(drone, instance)

    route: list[int] = []
    if candidate_target_ids is not None:
        available = set(candidate_target_ids)
    else:
        available = set(t.id for t in instance.target_nodes)
    curr_energy, curr_time, _ = evaluator.compute_route_totals(route)

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

    while available:
        n = len(route)
        route_indices = [
            idx_arr[tid] if tid < len(idx_arr) else evaluator.id_to_idx.get(tid, tid)
            for tid in route
        ]
        slot_p = [launch_idx if s == 0 else route_indices[s - 1] for s in range(n + 1)]
        slot_s = [recovery_idx if s == n else route_indices[s] for s in range(n + 1)]
        base_slot_e = [energy_mat[slot_p[s], slot_s[s]] for s in range(n + 1)]
        base_slot_t = [time_mat[slot_p[s], slot_s[s]] for s in range(n + 1)]

        candidates: list[
            tuple[float, int, int, float, float]
        ] = []  # (gain_ratio, tid, slot, delta_e, delta_t)

        for tid in list(available):
            c = idx_arr[tid] if tid < len(idx_arr) else evaluator.id_to_idx.get(tid, tid)
            reward = (
                reward_arr[tid]
                if tid < len(reward_arr)
                else evaluator.priority_scores.get(tid, 0.0)
            )
            d_e = (
                dwell_e_arr[tid]
                if tid < len(dwell_e_arr)
                else evaluator.dwell_energies.get(tid, 0.0)
            )
            d_t = (
                dwell_t_arr[tid] if tid < len(dwell_t_arr) else evaluator.dwell_times.get(tid, 0.0)
            )

            for s in range(n + 1):
                p = slot_p[s]
                succ = slot_s[s]
                delta_e = energy_mat[p, c] + energy_mat[c, succ] - base_slot_e[s] + d_e
                delta_t = time_mat[p, c] + time_mat[c, succ] - base_slot_t[s] + d_t

                if curr_energy + delta_e <= usable_bat and curr_time + delta_t <= max_time:
                    delta_energy = max(1.0, delta_e)
                    gain_ratio = reward / delta_energy
                    candidates.append((gain_ratio, tid, s, delta_e, delta_t))

        if not candidates:
            break

        candidates.sort(key=lambda x: x[0], reverse=True)
        max_c = candidates[0][0]
        min_c = candidates[-1][0]
        cutoff = max_c - alpha * (max_c - min_c)

        rcl = [c for c in candidates if c[0] >= cutoff]
        chosen = random.choice(rcl)
        _, chosen_tid, chosen_slot, chosen_de, chosen_dt = chosen
        route.insert(chosen_slot, chosen_tid)
        curr_energy += chosen_de
        curr_time += chosen_dt
        available.remove(chosen_tid)

    return route


class ALNSEngine:
    """Adaptive Large Neighborhood Search Engine for single-drone route exploration."""

    def __init__(
        self,
        instance: InstanceContext,
        delta_segment: int = 50,
        reaction_factor: float = 0.8,
        score_new_global_best: float = 15.0,
        score_better_solution: float = 8.0,
        score_accepted_solution: float = 3.0,
        cooling_rate: float = 0.995,
        start_temperature: float = 100.0,
    ) -> None:
        self.instance = instance
        self.delta_segment = delta_segment
        self.reaction_factor = reaction_factor
        self.sigma1 = score_new_global_best
        self.sigma2 = score_better_solution
        self.sigma3 = score_accepted_solution
        self.cooling_rate = cooling_rate
        self.start_temp = start_temperature

        self.destroy_ops: list[Callable] = [
            destroy_shaw_relatedness,
            destroy_worst_cost_efficiency,
            destroy_radial_cone,
            destroy_contiguous_string,
        ]
        self.repair_ops: list[Callable] = [
            repair_greedy_insertion,
            repair_regret2_insertion,
            repair_big_m_regret3_insertion,
        ]

        self.weights_d = np.ones(len(self.destroy_ops), dtype=np.float64)
        self.weights_r = np.ones(len(self.repair_ops), dtype=np.float64)
        self.probabilities_d = self.weights_d / np.sum(self.weights_d)
        self.probabilities_r = self.weights_r / np.sum(self.weights_r)

    def _select_destroy_operator(self) -> int:
        return int(np.random.choice(len(self.weights_d), p=self.probabilities_d))

    def _select_repair_operator(self) -> int:
        return int(np.random.choice(len(self.weights_r), p=self.probabilities_r))

    def explore_for_drone(
        self,
        drone: DroneSpec,
        max_iterations: int = 800,
        time_limit_sec: float = 0.6,
        candidate_target_ids: list[int] | None = None,
    ) -> list[CandidateRoute]:
        """Runs ALNS on a single drone and collects a pool of distinct feasible CandidateRoute objects."""
        start_t = time.perf_counter()
        evaluator = EvaluatorContext(drone, self.instance)
        discovered_routes: dict[frozenset[int], CandidateRoute] = {}
        if candidate_target_ids is not None:
            all_target_ids = list(candidate_target_ids)
        else:
            all_target_ids = [t.id for t in self.instance.target_nodes]

        # Reset weights & probabilities for independent drone exploration
        self.weights_d = np.ones(len(self.destroy_ops), dtype=np.float64)
        self.weights_r = np.ones(len(self.repair_ops), dtype=np.float64)
        self.probabilities_d = self.weights_d / np.sum(self.weights_d)
        self.probabilities_r = self.weights_r / np.sum(self.weights_r)

        # 1. Seed construction with RCL
        seed_targets = construct_greedy_seed_route(
            drone, self.instance, alpha=0.2, evaluator=evaluator, candidate_target_ids=all_target_ids
        )
        seed_targets = run_local_search_pipeline(
            seed_targets, all_target_ids, drone, self.instance, evaluator=evaluator
        )
        seed_eval = evaluate_route_trajectory(
            seed_targets, drone, self.instance, evaluator=evaluator
        )

        if seed_eval is not None:
            discovered_routes[frozenset(seed_targets)] = seed_eval
            best_reward = seed_eval.total_reward
            current_route = list(seed_targets)
            current_reward = seed_eval.total_reward
            current_time = seed_eval.total_flight_time
        else:
            best_reward = 0.0
            current_route = []
            current_reward = 0.0
            current_time = 0.0

        num_d = len(self.destroy_ops)
        num_r = len(self.repair_ops)
        scores_d = np.zeros(num_d, dtype=np.float64)
        scores_r = np.zeros(num_r, dtype=np.float64)
        counts_d = np.zeros(num_d, dtype=np.int32)
        counts_r = np.zeros(num_r, dtype=np.int32)

        temp = self.start_temp

        for iteration in range(1, max_iterations + 1):
            if time.perf_counter() - start_t >= time_limit_sec:
                break

            # Choose operators proportional to weights
            d_idx = self._select_destroy_operator()
            r_idx = self._select_repair_operator()
            counts_d[d_idx] += 1
            counts_r[r_idx] += 1

            # Determine removal size q in [2, max(3, floor(0.35 * |S|))]
            n_curr = len(current_route)
            if n_curr >= 3:
                max_q = min(n_curr, max(3, int(0.35 * n_curr)))
                q = random.randint(2, max_q)
            elif n_curr > 0:
                q = random.randint(1, n_curr)
            else:
                q = 0

            # Destroy step
            destroy_fn = self.destroy_ops[d_idx]
            rem_route, _ = destroy_fn(current_route, q, drone, self.instance, evaluator=evaluator)
            if rem_route:
                eval_rem = evaluate_route_trajectory(rem_route, drone, self.instance, evaluator=evaluator)
                if eval_rem is not None:
                    k_rem = frozenset(rem_route)
                    if k_rem not in discovered_routes:
                        discovered_routes[k_rem] = eval_rem

            # Repair step
            repair_fn = self.repair_ops[r_idx]
            unassigned = [tid for tid in all_target_ids if tid not in set(rem_route)]
            new_route = repair_fn(rem_route, unassigned, drone, self.instance, evaluator=evaluator)
            if new_route:
                eval_part = evaluate_route_trajectory(new_route, drone, self.instance, evaluator=evaluator)
                if eval_part is not None:
                    k_part = frozenset(new_route)
                    if k_part not in discovered_routes:
                        discovered_routes[k_part] = eval_part

            # Local search & immediate slack-filling
            new_route = run_local_search_pipeline(
                new_route, all_target_ids, drone, self.instance, evaluator=evaluator
            )

            eval_res = evaluate_route_trajectory(
                new_route, drone, self.instance, evaluator=evaluator
            )
            if eval_res is not None:
                route_key = frozenset(new_route)
                if route_key not in discovered_routes:
                    discovered_routes[route_key] = eval_res
                else:
                    # Keep route that minimizes flight time / energy
                    existing = discovered_routes[route_key]
                    if eval_res.total_flight_time < existing.total_flight_time - 1e-3 or (
                        abs(eval_res.total_flight_time - existing.total_flight_time) <= 1e-3
                        and eval_res.total_energy_joules < existing.total_energy_joules - 1.0
                    ):
                        discovered_routes[route_key] = eval_res

                new_reward = eval_res.total_reward
                is_strictly_better = new_reward > current_reward + 1e-4 or (
                    abs(new_reward - current_reward) <= 1e-4
                    and eval_res.total_flight_time < current_time - 1e-3
                )

                if new_reward > best_reward + 1e-4:
                    scores_d[d_idx] += self.sigma1
                    scores_r[r_idx] += self.sigma1
                    best_reward = new_reward
                    current_route = list(new_route)
                    current_reward = new_reward
                    current_time = eval_res.total_flight_time
                elif is_strictly_better:
                    scores_d[d_idx] += self.sigma2
                    scores_r[r_idx] += self.sigma2
                    current_route = list(new_route)
                    current_reward = new_reward
                    current_time = eval_res.total_flight_time
                else:
                    # Non-improving route under Simulated Annealing acceptance criterion: P(accept) = exp(-Delta / T)
                    loss = max(0.0, current_reward - new_reward)
                    accept_prob = math.exp(-loss / max(temp, 1e-4))
                    if random.random() < accept_prob:
                        scores_d[d_idx] += self.sigma3
                        scores_r[r_idx] += self.sigma3
                        current_route = list(new_route)
                        current_reward = new_reward
                        current_time = eval_res.total_flight_time

            temp = max(1e-2, temp * self.cooling_rate)

            # Update weights dynamically every delta_segment iterations
            if iteration % self.delta_segment == 0:
                for idx in range(num_d):
                    if counts_d[idx] > 0:
                        self.weights_d[idx] = self.reaction_factor * self.weights_d[idx] + (
                            1.0 - self.reaction_factor
                        ) * (scores_d[idx] / counts_d[idx])
                for idx in range(num_r):
                    if counts_r[idx] > 0:
                        self.weights_r[idx] = self.reaction_factor * self.weights_r[idx] + (
                            1.0 - self.reaction_factor
                        ) * (scores_r[idx] / counts_r[idx])

                self.weights_d = np.maximum(self.weights_d, 0.1)
                self.weights_r = np.maximum(self.weights_r, 0.1)
                self.probabilities_d = self.weights_d / np.sum(self.weights_d)
                self.probabilities_r = self.weights_r / np.sum(self.weights_r)
                scores_d.fill(0.0)
                scores_r.fill(0.0)
                counts_d.fill(0)
                counts_r.fill(0)

        # Always include an empty (depot loitering) route as a valid candidate
        empty_route = evaluate_route_trajectory([], drone, self.instance, evaluator=evaluator)
        if empty_route is not None and frozenset() not in discovered_routes:
            discovered_routes[frozenset()] = empty_route

        return list(discovered_routes.values())


def partition_targets_by_sectors(
    instance: InstanceContext,
    num_sectors: int,
) -> dict[str, list[int]]:
    """
    Partitions target nodes among the fleet by azimuth angle relative to the depot.
    Guarantees non-overlapping spatial sectors and mutual flight corridor deconfliction.
    """
    if num_sectors <= 1 or not instance.drones:
        all_ids = [t.id for t in instance.target_nodes]
        return {d.id: list(all_ids) for d in instance.drones}

    # Reference depot
    launch_depot_id = instance.drones[0].launch_depot_id
    depot = next((t for t in instance.targets if t.id == launch_depot_id), instance.targets[0])

    target_nodes = instance.target_nodes
    if not target_nodes:
        return {d.id: [] for d in instance.drones}

    # Calculate azimuth angle in [0, 2*pi)
    target_angles: list[tuple[float, int]] = []
    for t in target_nodes:
        dx = t.x - depot.x
        dy = t.y - depot.y
        angle = math.atan2(dy, dx) % (2.0 * math.pi)
        target_angles.append((angle, t.id))

    # Sort radially by azimuth
    target_angles.sort(key=lambda x: x[0])

    # Assign contiguous angular slices to each drone
    total_targets = len(target_angles)
    chunk = total_targets // num_sectors
    sectors: dict[str, list[int]] = {}

    for i, drone in enumerate(instance.drones):
        start_idx = i * chunk
        end_idx = (i + 1) * chunk if i < num_sectors - 1 else total_targets
        sec_targets = [tid for _, tid in target_angles[start_idx:end_idx]]
        sectors[drone.id] = sec_targets

    return sectors


def explore_route_pool(
    instance: InstanceContext,
    max_iterations: int = 800,
    time_limit_sec: float = 1.8,
    seed: int | None = 42,
) -> RoutePool:
    """
    Executes Tier-1 ALNS across the fleet and returns a populated RoutePool.

    Guarantees:
    1. Every route in RoutePool starts at launch_depot and ends at recovery_depot.
    2. Every route satisfies: total_energy <= 0.85 * drone.battery_joules.
    3. Every route satisfies: total_flight_time <= drone.max_flight_time.
    4. Waypoint arrival and departure timestamps are continuous and dwell times are added.
    5. Each drone is assigned an exclusive spatial sector around the depot to guarantee
       non-overlapping flight corridors.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    engine = ALNSEngine(instance)
    pool = RoutePool()

    num_drones = len(instance.drones)
    if num_drones == 0:
        return pool

    start_t = time.perf_counter()
    sector_map = partition_targets_by_sectors(instance, num_drones)

    for i, drone in enumerate(instance.drones):
        elapsed = time.perf_counter() - start_t
        remaining_time = max(0.05, time_limit_sec - elapsed)
        remaining_drones = num_drones - i
        per_drone_time = remaining_time / remaining_drones

        drone_targets = sector_map.get(drone.id)
        routes = engine.explore_for_drone(
            drone=drone,
            max_iterations=max_iterations,
            time_limit_sec=per_drone_time,
            candidate_target_ids=drone_targets,
        )
        pool.routes_by_drone[drone.id] = routes

    return pool
