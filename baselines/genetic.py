"""Genetic Algorithm (GA) Baseline for Multi-Drone Orienteering."""

from __future__ import annotations

import random
import time

from core.contracts import CandidateRoute, FleetSchedule, InstanceContext, WaypointVisit
from core.operators import evaluate_route_trajectory


def order_crossover(p1: list[int], p2: list[int]) -> list[int]:
    """Applies standard Order Crossover (OX) to two permutations."""
    if len(p1) < 2:
        return list(p1)
    a, b = sorted(random.sample(range(len(p1)), 2))
    child = [-1] * len(p1)
    child[a : b + 1] = p1[a : b + 1]
    filled = set(child[a : b + 1])

    p2_remaining = [x for x in p2 if x not in filled]
    p2_idx = 0
    for i in range(len(child)):
        if child[i] == -1:
            child[i] = p2_remaining[p2_idx]
            p2_idx += 1
    return child


def evaluate_chromosome(
    perm: list[int],
    instance: InstanceContext,
) -> tuple[float, list[CandidateRoute]]:
    """
    Decodes a target permutation by greedily assigning targets to drones in fleet order.
    Returns (fitness_reward, assigned_routes).
    """
    assigned_routes: list[CandidateRoute] = []
    total_reward = 0.0
    remaining_targets = list(perm)

    for drone in instance.drones:
        drone_targets: list[int] = []
        for tid in list(remaining_targets):
            test_seq = drone_targets + [tid]
            eval_res = evaluate_route_trajectory(test_seq, drone, instance)
            if eval_res is not None:
                drone_targets.append(tid)
                remaining_targets.remove(tid)

        final_eval = evaluate_route_trajectory(drone_targets, drone, instance)
        if final_eval is not None:
            assigned_routes.append(final_eval)
            total_reward += final_eval.total_reward
        else:
            empty_eval = evaluate_route_trajectory([], drone, instance)
            if empty_eval is not None:
                assigned_routes.append(empty_eval)
            else:
                assigned_routes.append(
                    CandidateRoute(
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
                )

    return total_reward, assigned_routes


def solve_genetic_algorithm(
    instance: InstanceContext,
    population_size: int = 20,
    generations: int = 20,
    crossover_rate: float = 0.8,
    mutation_rate: float = 0.2,
    seed: int | None = 42,
) -> FleetSchedule:
    """
    Executes standard Genetic Algorithm baseline.
    """
    if seed is not None:
        random.seed(seed)

    t0 = time.perf_counter()
    all_target_ids = [t.id for t in instance.target_nodes]
    if not all_target_ids:
        return FleetSchedule(
            status="OPTIMAL",
            solve_time_seconds=0.01,
            cumulative_reward=0.0,
            assigned_routes=[],
            unassigned_targets=[],
            validation_passed=True,
        )

    # Initial population: random permutations
    population: list[list[int]] = []
    for _ in range(population_size):
        p = list(all_target_ids)
        random.shuffle(p)
        population.append(p)

    best_fitness = -1.0
    best_routes: list[CandidateRoute] = []

    for gen in range(generations):
        # Evaluate fitness
        scored_pop = []
        for ind in population:
            fitness, routes = evaluate_chromosome(ind, instance)
            scored_pop.append((fitness, ind, routes))
            if fitness > best_fitness:
                best_fitness = fitness
                best_routes = routes

        # Tournament selection
        scored_pop.sort(key=lambda x: x[0], reverse=True)
        new_pop: list[list[int]] = [scored_pop[0][1]]  # Elitism

        while len(new_pop) < population_size:
            # Select 2 parents via tournament
            t1 = random.sample(scored_pop, 3)
            p1 = max(t1, key=lambda x: x[0])[1]
            t2 = random.sample(scored_pop, 3)
            p2 = max(t2, key=lambda x: x[0])[1]

            # Crossover
            if random.random() < crossover_rate and len(p1) > 1:
                child = order_crossover(p1, p2)
            else:
                child = list(p1)

            # Mutation: swap
            if random.random() < mutation_rate and len(child) > 1:
                i, j = random.sample(range(len(child)), 2)
                child[i], child[j] = child[j], child[i]

            new_pop.append(child)

        population = new_pop

    latency = time.perf_counter() - t0
    visited_ids = set()
    for r in best_routes:
        visited_ids.update(r.target_ids)
    unassigned = [tid for tid in all_target_ids if tid not in visited_ids]

    return FleetSchedule(
        status="FEASIBLE",
        solve_time_seconds=latency,
        cumulative_reward=best_fitness,
        assigned_routes=best_routes,
        unassigned_targets=unassigned,
        validation_passed=True,
        baseline_ga_reward=best_fitness,
    )
