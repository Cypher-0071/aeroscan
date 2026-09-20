"""Tier-2 Exact 0-1 Set Packing Master Problem Solver using Google OR-Tools CP-SAT."""

from __future__ import annotations

import logging
import time

from ortools.sat.python import cp_model

from core.contracts import CandidateRoute, FleetSchedule, InstanceContext, RoutePool

logger = logging.getLogger(__name__)


def solve_set_packing(
    instance: InstanceContext,
    route_pool: RoutePool,
    time_limit_seconds: float = 0.5,
) -> tuple[str, list[CandidateRoute], list[int], float, float]:
    """
    Solves the 0-1 Set Packing Master Problem over candidate routes in route_pool.

    Returns:
        (status_str, assigned_routes, unassigned_target_ids, solve_latency_sec, total_reward)
    """
    t0 = time.perf_counter()
    model = cp_model.CpModel()

    # Decision variables: z[(drone_id, route_idx)] in {0, 1}
    z_vars: dict[tuple[str, int], cp_model.IntVar] = {}
    for drone_id, routes in route_pool.routes_by_drone.items():
        for r_idx in range(len(routes)):
            z_vars[(drone_id, r_idx)] = model.NewBoolVar(f"z_{drone_id}_{r_idx}")

    # Constraint 1: Drone assignment limit (at most 1 route per drone)
    for drone_id, routes in route_pool.routes_by_drone.items():
        drone_vars = [z_vars[(drone_id, r_idx)] for r_idx in range(len(routes))]
        if drone_vars:
            model.Add(sum(drone_vars) <= 1)

    # Constraint 2: Target uniqueness (each target visited at most once across the fleet)
    all_target_ids = [t.id for t in instance.target_nodes]
    target_to_vars: dict[int, list[cp_model.IntVar]] = {}
    for drone_id, routes in route_pool.routes_by_drone.items():
        for r_idx, route in enumerate(routes):
            var = z_vars[(drone_id, r_idx)]
            for tid in route.target_ids:
                target_to_vars.setdefault(tid, []).append(var)

    for tid, vars_list in target_to_vars.items():
        if len(vars_list) > 1:
            model.Add(sum(vars_list) <= 1)

    # Objective: Maximize total collected reward
    # Scale float rewards to integers for CP-SAT
    scale_factor = 1000
    obj_terms = []
    for drone_id, routes in route_pool.routes_by_drone.items():
        for r_idx, route in enumerate(routes):
            scaled_reward = int(round(route.total_reward * scale_factor))
            obj_terms.append(scaled_reward * z_vars[(drone_id, r_idx)])

    if obj_terms:
        model.Maximize(sum(obj_terms))

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_workers = 4
    cp_status = solver.Solve(model)
    solve_latency = time.perf_counter() - t0

    if solve_latency > 0.25:
        logger.warning(
            "CP-SAT solver latency %.3fs exceeded 0.25s target budget (limit=%.2fs)",
            solve_latency,
            time_limit_seconds,
        )

    status_map = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
        cp_model.UNKNOWN: "UNKNOWN",
    }
    status_str = status_map.get(cp_status, "UNKNOWN")

    assigned_routes: list[CandidateRoute] = []
    visited_targets: set[int] = set()
    total_reward = 0.0

    if cp_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for drone_id, routes in route_pool.routes_by_drone.items():
            for r_idx, route in enumerate(routes):
                if solver.Value(z_vars[(drone_id, r_idx)]) == 1:
                    assigned_routes.append(route)
                    visited_targets.update(route.target_ids)
                    total_reward += route.total_reward

    unassigned_targets = [tid for tid in all_target_ids if tid not in visited_targets]

    return (status_str, assigned_routes, unassigned_targets, solve_latency, total_reward)


def solve_fleet_schedule(
    instance: InstanceContext,
    route_pool: RoutePool,
    run_baselines: bool = True,
    time_limit_seconds: float = 0.5,
) -> FleetSchedule:
    """
    Main entrypoint for Tier-2 Master Optimization:
    1. Solves the 0-1 Set Packing problem using CP-SAT.
    2. Runs comparative GRASP and Genetic Algorithm baselines.
    3. Audits all constraints through the independent validator.
    4. Computes reward gain percentages.
    """
    from baselines.genetic import solve_genetic_algorithm
    from baselines.grasp import solve_grasp_baseline
    from core.validator import audit_fleet_schedule

    status_str, assigned_routes, unassigned_targets, solve_sec, total_reward = solve_set_packing(
        instance=instance,
        route_pool=route_pool,
        time_limit_seconds=time_limit_seconds,
    )

    grasp_reward = 0.0
    ga_reward = 0.0
    if run_baselines:
        try:
            grasp_sched = solve_grasp_baseline(instance, alpha=0.3, seed=42)
            grasp_reward = grasp_sched.cumulative_reward
        except Exception:
            grasp_reward = 0.0

        try:
            ga_sched = solve_genetic_algorithm(
                instance,
                population_size=20,
                generations=15,
                seed=42,
            )
            ga_reward = ga_sched.cumulative_reward
        except Exception:
            ga_reward = 0.0

    gain_pct = 0.0
    if grasp_reward > 0:
        gain_pct = ((total_reward - grasp_reward) / grasp_reward) * 100.0
    elif total_reward > 0 and grasp_reward == 0.0:
        gain_pct = 100.0

    temp_sched = FleetSchedule(
        status=status_str,
        solve_time_seconds=solve_sec,
        cumulative_reward=total_reward,
        assigned_routes=assigned_routes,
        unassigned_targets=unassigned_targets,
        validation_passed=True,
        baseline_grasp_reward=grasp_reward,
        baseline_ga_reward=ga_reward,
        reward_gain_percent=gain_pct,
    )

    audit = audit_fleet_schedule(temp_sched, instance)
    temp_sched.validation_passed = audit["valid"] and (status_str in ("OPTIMAL", "FEASIBLE"))

    return temp_sched

