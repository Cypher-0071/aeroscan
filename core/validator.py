"""Independent constraint validator for battery reserves, flight deadlines, and fleet deconfliction."""

from __future__ import annotations

from typing import Any

from core.contracts import DroneSpec, FleetSchedule, InstanceContext


class ScheduleValidationError(ValueError, AssertionError):
    """Raised when a mission schedule violates physical or operational constraints."""


def audit_fleet_schedule(
    schedule: FleetSchedule,
    instance: InstanceContext,
) -> dict[str, Any]:
    """
    Performs comprehensive audit of a FleetSchedule against all physical, operational,
    and safety constraints.

    Checks:
    1. Battery Reserve >= 15.0% State-of-Charge for all drones (E_total <= 0.85 * B_k).
    2. Flight Deadline <= T_max for all drones.
    3. Proper depot launch and recovery flow.
    4. Exact zero target duplication across assigned drones.
    5. Continuous waypoint timelines and monotonic energy consumption.

    Returns:
        Dict containing audit status, details, and list of violations (if any).
    """
    violations: list[str] = []
    drone_map: dict[str, DroneSpec] = {d.id: d for d in instance.drones}
    visited_all_targets: set[int] = set()

    for route in schedule.assigned_routes:
        drone = drone_map.get(route.drone_id)
        if drone is None:
            violations.append(f"Unknown drone_id '{route.drone_id}' in assigned routes.")
            continue

        # 1. Battery Reserve Check (E_total <= 0.85 * B_k <=> Remaining SoC >= 15.0%)
        max_allowed_energy = drone.usable_battery_joules
        if route.total_energy_joules > max_allowed_energy + 1e-4:
            rem_pct = (
                (drone.battery_joules - route.total_energy_joules) / drone.battery_joules
            ) * 100.0
            violations.append(
                f"Fatal: Battery safety margin breached: Battery reserve violation on {drone.id}: "
                f"consumed {route.total_energy_joules:.1f} J (max allowed {max_allowed_energy:.1f} J). "
                f"Remaining SoC: {rem_pct:.2f}% (< 15.0% floor)."
            )

        # 2. Flight Deadline Check (t_arrival <= T_max)
        if route.total_flight_time > drone.max_flight_time + 1e-4:
            violations.append(
                f"Deadline violation on {drone.id}: flight time {route.total_flight_time:.1f} s "
                f"exceeds T_max {drone.max_flight_time:.1f} s."
            )
        if route.waypoints and route.waypoints[-1].arrival_time > drone.max_flight_time + 1e-4:
            violations.append(
                f"Deadline violation on {drone.id}: final waypoint arrival time {route.waypoints[-1].arrival_time:.1f} s "
                f"exceeds T_max {drone.max_flight_time:.1f} s."
            )

        # 3. Depot Decoupling Flow Check
        if not route.waypoints:
            violations.append(f"Empty waypoints list for assigned drone {drone.id}.")
        else:
            launch_wp = route.waypoints[0]
            recovery_wp = route.waypoints[-1]
            if launch_wp.node_id != drone.launch_depot_id:
                violations.append(
                    f"Depot flow mismatch on {drone.id}: first waypoint {launch_wp.node_id} "
                    f"!= launch depot {drone.launch_depot_id}."
                )
            if recovery_wp.node_id != drone.recovery_depot_id:
                violations.append(
                    f"Depot flow mismatch on {drone.id}: final waypoint {recovery_wp.node_id} "
                    f"!= recovery depot {drone.recovery_depot_id}."
                )

        # 4. Target Sequence & Waypoint Monotonicity
        prev_arr = 0.0
        prev_energy = 0.0
        for idx, wp in enumerate(route.waypoints):
            if wp.arrival_time < prev_arr - 1e-4:
                violations.append(f"Non-monotonic arrival time at waypoint {idx} on {drone.id}.")
            if wp.departure_time < wp.arrival_time - 1e-4:
                violations.append(f"Non-monotonic departure time at waypoint {idx} on {drone.id}.")
            if wp.energy_consumed < prev_energy - 1e-4:
                violations.append(f"Non-monotonic energy at waypoint {idx} on {drone.id}.")
            if wp.energy_consumed > max_allowed_energy + 1e-4:
                violations.append(
                    f"Fatal: Battery safety margin breached: Battery reserve violation at waypoint {idx} on {drone.id}: "
                    f"consumed {wp.energy_consumed:.1f} J exceeds usable ceiling {max_allowed_energy:.1f} J."
                )
            prev_arr = wp.departure_time
            prev_energy = wp.energy_consumed

        # 5. Target Deconfliction Check (Internal & Cross-Drone)
        route_targets = set(route.target_ids)
        if len(route.target_ids) != len(route_targets):
            violations.append(
                f"Internal target duplication on {drone.id}: route contains repeated target IDs."
            )

        overlap = visited_all_targets.intersection(route_targets)
        if overlap:
            violations.append(
                f"Target cannibalization / duplication detected: targets {sorted(overlap)} visited by multiple drones."
            )
        visited_all_targets.update(route_targets)

    passed = len(violations) == 0
    return {
        "valid": passed,
        "violations": violations,
        "total_routes_checked": len(schedule.assigned_routes),
        "total_targets_visited": len(visited_all_targets),
        "cumulative_reward": schedule.cumulative_reward,
    }


def validate_fleet_schedule(schedule: FleetSchedule, instance: InstanceContext) -> bool:
    """
    Validates a fleet schedule and raises ScheduleValidationError if any constraint is breached.
    """
    audit = audit_fleet_schedule(schedule, instance)
    if not audit["valid"]:
        error_msg = "Constraint validation failed with violations:\n" + "\n".join(
            audit["violations"]
        )
        raise ScheduleValidationError(error_msg)
    return True
