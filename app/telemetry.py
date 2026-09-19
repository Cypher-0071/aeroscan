"""Telemetry simulator and dynamic state interpolator for AeroScan-Optima."""

from __future__ import annotations

from typing import Any

import pandas as pd

from core.contracts import CandidateRoute, DroneSpec, FleetSchedule, InstanceContext


def interpolate_drone_state(
    route: CandidateRoute,
    t_sec: float,
    instance: InstanceContext,
    drone: DroneSpec,
) -> dict[str, Any]:
    """
    Interpolates a drone's precise 3D kinematic position, flight status, and battery SoC
    at an arbitrary mission timestamp t_sec.
    """
    node_map = {n.id: n for n in instance.targets}
    waypoints = route.waypoints

    if not waypoints:
        launch = node_map.get(drone.launch_depot_id, instance.targets[0])
        return {
            "drone_id": drone.id,
            "x": launch.x,
            "y": launch.y,
            "z": launch.elevation,
            "status": "GROUND_STANDBY",
            "current_node_id": launch.id,
            "battery_percent": 100.0,
            "speed_mps": 0.0,
        }

    # Before mission departure
    if t_sec <= waypoints[0].departure_time:
        wp0 = waypoints[0]
        node0 = node_map[wp0.node_id]
        return {
            "drone_id": drone.id,
            "x": node0.x,
            "y": node0.y,
            "z": node0.elevation,
            "status": "LAUNCH_DEPOT",
            "current_node_id": node0.id,
            "battery_percent": 100.0,
            "speed_mps": 0.0,
        }

    # After mission recovery
    last_wp = waypoints[-1]
    if t_sec >= last_wp.arrival_time:
        last_node = node_map[last_wp.node_id]
        return {
            "drone_id": drone.id,
            "x": last_node.x,
            "y": last_node.y,
            "z": last_node.elevation,
            "status": "MISSION_COMPLETE",
            "current_node_id": last_node.id,
            "battery_percent": last_wp.remaining_battery_percent,
            "speed_mps": 0.0,
        }

    # Find active segment
    for i in range(len(waypoints) - 1):
        wp_curr = waypoints[i]
        wp_next = waypoints[i + 1]
        node_curr = node_map[wp_curr.node_id]
        node_next = node_map[wp_next.node_id]

        # Case 1: Hovering over target for sensor dwell
        if wp_curr.arrival_time <= t_sec <= wp_curr.departure_time:
            bat_pct = wp_curr.remaining_battery_percent  # Dwell battery
            return {
                "drone_id": drone.id,
                "x": node_curr.x,
                "y": node_curr.y,
                "z": node_curr.elevation + 15.0,  # 15m inspection altitude
                "status": f"HOVER_INSPECTION ({node_curr.name})",
                "current_node_id": node_curr.id,
                "battery_percent": bat_pct,
                "speed_mps": 0.0,
            }

        # Case 2: In forward transit between wp_curr and wp_next
        if wp_curr.departure_time < t_sec < wp_next.arrival_time:
            transit_dur = wp_next.arrival_time - wp_curr.departure_time
            frac = (t_sec - wp_curr.departure_time) / max(transit_dur, 1e-4)

            x = node_curr.x + frac * (node_next.x - node_curr.x)
            y = node_curr.y + frac * (node_next.y - node_curr.y)
            cruise_alt = 60.0  # Cruise altitude
            z = cruise_alt

            bat_pct = wp_curr.remaining_battery_percent + frac * (
                wp_next.remaining_battery_percent - wp_curr.remaining_battery_percent
            )

            return {
                "drone_id": drone.id,
                "x": float(x),
                "y": float(y),
                "z": float(z),
                "status": f"CRUISE -> {node_next.name}",
                "current_node_id": node_next.id,
                "battery_percent": float(bat_pct),
                "speed_mps": drone.cruise_speed,
            }

    # Fallback to final waypoint
    last_node = node_map[last_wp.node_id]
    return {
        "drone_id": drone.id,
        "x": last_node.x,
        "y": last_node.y,
        "z": last_node.elevation,
        "status": "MISSION_COMPLETE",
        "current_node_id": last_node.id,
        "battery_percent": last_wp.remaining_battery_percent,
        "speed_mps": 0.0,
    }


def get_fleet_telemetry_at_time(
    schedule: FleetSchedule,
    t_sec: float,
    instance: InstanceContext,
) -> tuple[list[dict[str, Any]], set[int]]:
    """
    Computes real-time telemetry positions for all drones in the fleet and identifies targets
    visited and secured up to timestamp t_sec.
    """
    route_map = {r.drone_id: r for r in schedule.assigned_routes}
    telemetry_list: list[dict[str, Any]] = []
    secured_targets: set[int] = set()

    for drone in instance.drones:
        route = route_map.get(drone.id)
        if route is not None:
            state = interpolate_drone_state(route, t_sec, instance, drone)
            for wp in route.waypoints:
                if wp.departure_time <= t_sec:
                    # Target inspection completed
                    if wp.node_id not in (drone.launch_depot_id, drone.recovery_depot_id):
                        secured_targets.add(wp.node_id)
        else:
            dummy_route = CandidateRoute(
                drone_id=drone.id,
                target_ids=[],
                waypoints=[],
                total_reward=0.0,
                total_flight_time=0.0,
                total_energy_joules=0.0,
            )
            state = interpolate_drone_state(dummy_route, t_sec, instance, drone)
        telemetry_list.append(state)

    return telemetry_list, secured_targets


def compute_battery_curves(
    schedule: FleetSchedule,
    instance: InstanceContext,
    num_points: int = 150,
) -> pd.DataFrame:
    """Generates a tidy DataFrame of Battery SoC % over time for all drones in the fleet."""
    route_map = {r.drone_id: r for r in schedule.assigned_routes}
    max_time = max(
        (r.total_flight_time for r in schedule.assigned_routes),
        default=600.0,
    )
    if max_time <= 0:
        max_time = 600.0

    times = [i * (max_time / max(num_points - 1, 1)) for i in range(num_points)]
    records: list[dict[str, Any]] = []

    for t in times:
        row: dict[str, Any] = {"Time_sec": t, "Time_min": round(t / 60.0, 2)}
        for drone in instance.drones:
            route = route_map.get(drone.id)
            if route is not None:
                state = interpolate_drone_state(route, t, instance, drone)
            else:
                dummy_route = CandidateRoute(
                    drone_id=drone.id,
                    target_ids=[],
                    waypoints=[],
                    total_reward=0.0,
                    total_flight_time=0.0,
                    total_energy_joules=0.0,
                )
                state = interpolate_drone_state(dummy_route, t, instance, drone)
            row[f"{drone.id} SoC (%)"] = round(state["battery_percent"], 2)
        records.append(row)

    return pd.DataFrame(records)
