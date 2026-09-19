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
) -> list[int]:
    """
    Constructs an initial feasible route using a Randomized Restricted Candidate List (RCL).
    """
    route: list[int] = []
    available = set(t.id for t in instance.target_nodes)
    node_map = {n.id: n for n in instance.targets}

    while available:
        base_eval = evaluate_route_trajectory(route, drone, instance)
        base_energy = base_eval.total_energy_joules if base_eval else 0.0

        candidates: list[tuple[float, int, int]] = []  # (gain_ratio, target_id, slot)
        for tid in list(available):
            node = node_map.get(tid)
            if not node:
                continue
            for slot in range(len(route) + 1):
                test_seq = route[:slot] + [tid] + route[slot:]
                eval_res = evaluate_route_trajectory(test_seq, drone, instance)
                if eval_res is not None:
                    delta_energy = max(1.0, eval_res.total_energy_joules - base_energy)
                    gain_ratio = node.priority_score / delta_energy
                    candidates.append((gain_ratio, tid, slot))

        if not candidates:
            break

        candidates.sort(key=lambda x: x[0], reverse=True)
        max_c = candidates[0][0]
        min_c = candidates[-1][0]
        cutoff = max_c - alpha * (max_c - min_c)

        rcl = [c for c in candidates if c[0] >= cutoff]
        chosen = random.choice(rcl)
        _, chosen_tid, chosen_slot = chosen
        route.insert(chosen_slot, chosen_tid)
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

    def _select_operator(self, weights: np.ndarray) -> int:
        probs = weights / np.sum(weights)
        return int(np.random.choice(len(weights), p=probs))

    def explore_for_drone(
        self,
        drone: DroneSpec,
        max_iterations: int = 400,
        time_limit_sec: float = 0.5,
    ) -> list[CandidateRoute]:
        """Runs ALNS on a single drone and collects a pool of distinct feasible CandidateRoute objects."""
        start_t = time.perf_counter()
        discovered_routes: dict[tuple[int, ...], CandidateRoute] = {}
        all_target_ids = [t.id for t in self.instance.target_nodes]

        # 1. Seed construction
        seed_targets = construct_greedy_seed_route(drone, self.instance, alpha=0.2)
        seed_targets = run_local_search_pipeline(seed_targets, all_target_ids, drone, self.instance)
        seed_eval = evaluate_route_trajectory(seed_targets, drone, self.instance)

        if seed_eval is not None:
            discovered_routes[tuple(seed_targets)] = seed_eval
            best_reward = seed_eval.total_reward
            current_route = list(seed_targets)
            current_reward = seed_eval.total_reward
        else:
            best_reward = 0.0
            current_route = []
            current_reward = 0.0

        num_d = len(self.destroy_ops)
        num_r = len(self.repair_ops)
        w_d = np.ones(num_d, dtype=np.float64)
        w_r = np.ones(num_r, dtype=np.float64)
        scores_d = np.zeros(num_d, dtype=np.float64)
        scores_r = np.zeros(num_r, dtype=np.float64)
        counts_d = np.zeros(num_d, dtype=np.int32)
        counts_r = np.zeros(num_r, dtype=np.int32)

        temp = self.start_temp

        for iteration in range(1, max_iterations + 1):
            if time.perf_counter() - start_t >= time_limit_sec:
                break

            # Choose operators
            d_idx = self._select_operator(w_d)
            r_idx = self._select_operator(w_r)
            counts_d[d_idx] += 1
            counts_r[r_idx] += 1

            # Determine removal size q
            n_curr = len(current_route)
            if n_curr > 2:
                max_q = max(2, int(0.35 * n_curr))
                q = random.randint(2, max_q)
            else:
                q = 1

            # Destroy step
            destroy_fn = self.destroy_ops[d_idx]
            rem_route, removed = destroy_fn(current_route, q, drone, self.instance)

            # Repair step
            repair_fn = self.repair_ops[r_idx]
            unassigned = list(set(all_target_ids) - set(rem_route))
            new_route = repair_fn(rem_route, unassigned, drone, self.instance)

            # Local search & immediate slack-filling
            new_route = run_local_search_pipeline(new_route, all_target_ids, drone, self.instance)

            eval_res = evaluate_route_trajectory(new_route, drone, self.instance)
            if eval_res is not None:
                route_key = tuple(new_route)
                if route_key not in discovered_routes:
                    discovered_routes[route_key] = eval_res

                new_reward = eval_res.total_reward
                delta = new_reward - current_reward

                if new_reward > best_reward:
                    scores_d[d_idx] += self.sigma1
                    scores_r[r_idx] += self.sigma1
                    best_reward = new_reward
                    current_route = list(new_route)
                    current_reward = new_reward
                elif delta >= 0:
                    scores_d[d_idx] += self.sigma2
                    scores_r[r_idx] += self.sigma2
                    current_route = list(new_route)
                    current_reward = new_reward
                else:
                    # Simulated Annealing acceptance
                    accept_prob = math.exp(delta / max(temp, 1e-4))
                    if random.random() < accept_prob:
                        scores_d[d_idx] += self.sigma3
                        scores_r[r_idx] += self.sigma3
                        current_route = list(new_route)
                        current_reward = new_reward

            temp = max(1e-2, temp * self.cooling_rate)

            # Update weights dynamically every delta_segment iterations
            if iteration % self.delta_segment == 0:
                for idx in range(num_d):
                    if counts_d[idx] > 0:
                        w_d[idx] = self.reaction_factor * w_d[idx] + (1 - self.reaction_factor) * (
                            scores_d[idx] / counts_d[idx]
                        )
                for idx in range(num_r):
                    if counts_r[idx] > 0:
                        w_r[idx] = self.reaction_factor * w_r[idx] + (1 - self.reaction_factor) * (
                            scores_r[idx] / counts_r[idx]
                        )
                w_d = np.maximum(w_d, 0.1)
                w_r = np.maximum(w_r, 0.1)
                scores_d.fill(0.0)
                scores_r.fill(0.0)
                counts_d.fill(0)
                counts_r.fill(0)

        # Always include an empty (depot loitering) route as a valid candidate
        empty_route = evaluate_route_trajectory([], drone, self.instance)
        if empty_route is not None:
            discovered_routes[()] = empty_route

        return list(discovered_routes.values())


def explore_route_pool(
    instance: InstanceContext,
    max_iterations: int = 400,
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
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    engine = ALNSEngine(instance)
    pool = RoutePool()

    num_drones = len(instance.drones)
    per_drone_time = max(0.2, (time_limit_sec / max(num_drones, 1)))

    for drone in instance.drones:
        routes = engine.explore_for_drone(
            drone=drone,
            max_iterations=max_iterations,
            time_limit_sec=per_drone_time,
        )
        pool.routes_by_drone[drone.id] = routes

    return pool
