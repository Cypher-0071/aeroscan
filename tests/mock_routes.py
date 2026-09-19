"""Mock RoutePool fixture for Day 0 CP-SAT Set Packing solver testing."""

from __future__ import annotations

import random

from core.contracts import CandidateRoute, InstanceContext, RoutePool
from core.operators import evaluate_route_trajectory


def create_mock_route_pool(instance: InstanceContext, routes_per_drone: int = 15) -> RoutePool:
    """Generates a synthetic RoutePool containing diverse feasible candidate routes."""
    random.seed(42)
    pool = RoutePool()
    target_ids = [t.id for t in instance.target_nodes]

    for drone in instance.drones:
        drone_routes: list[CandidateRoute] = []

        # Empty route
        empty_res = evaluate_route_trajectory([], drone, instance)
        if empty_res is not None:
            drone_routes.append(empty_res)

        attempts = 0
        while len(drone_routes) < routes_per_drone and attempts < 200:
            attempts += 1
            length = random.randint(3, 7)
            sampled = random.sample(target_ids, min(length, len(target_ids)))
            res = evaluate_route_trajectory(sampled, drone, instance)
            if res is not None:
                # Check duplicate target sets
                if not any(set(r.target_ids) == set(res.target_ids) for r in drone_routes):
                    drone_routes.append(res)

        pool.routes_by_drone[drone.id] = drone_routes

    return pool
