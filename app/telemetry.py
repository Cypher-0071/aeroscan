"""Telemetry simulator and dynamic state interpolator for AeroScan-Optima."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from core.contracts import CandidateRoute, DroneSpec, FleetSchedule, InstanceContext
from core.physics import calculate_cruise_power, resolve_groundspeed, wind_to_vector


def calculate_heading_deg(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculates compass heading angle in degrees (0° = North, 90° = East)."""
    dx = x2 - x1
    dy = y2 - y1
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return 0.0
    heading = (90.0 - math.degrees(math.atan2(dy, dx))) % 360.0
    return round(heading, 1)


def interpolate_drone_state(
    route: CandidateRoute,
    t_sec: float,
    instance: InstanceContext,
    drone: DroneSpec,
) -> dict[str, Any]:
    """
    Interpolates a drone's precise 3D kinematic position, flight status, heading,
    groundspeed, and battery SoC at an arbitrary mission timestamp t_sec.
    """
    node_map = {n.id: n for n in instance.targets}
    waypoints = route.waypoints
    wind_spd, wind_dir_rad = instance.ambient_wind

    # Baseline nominal power calculation from drone battery & flight endurance
    nominal_power = getattr(drone, "battery_joules", 360000.0) / max(
        getattr(drone, "max_flight_time", 2400.0), 1.0
    )

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
            "ground_speed_mps": 0.0,
            "air_speed_mps": 0.0,
            "heading_deg": 0.0,
            "power_watts": 0.0,
            "flight_phase": "STANDBY",
            "target_name": launch.name,
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
            "ground_speed_mps": 0.0,
            "air_speed_mps": 0.0,
            "heading_deg": 0.0,
            "power_watts": 15.0,  # Avionics standby draw
            "flight_phase": "PRE-FLIGHT",
            "target_name": node0.name,
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
            "ground_speed_mps": 0.0,
            "air_speed_mps": 0.0,
            "heading_deg": 0.0,
            "power_watts": 0.0,
            "flight_phase": "RECOVERED",
            "target_name": last_node.name,
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
            hdg = calculate_heading_deg(node_curr.x, node_curr.y, node_next.x, node_next.y)
            return {
                "drone_id": drone.id,
                "x": node_curr.x,
                "y": node_curr.y,
                "z": node_curr.elevation + 15.0,  # 15m inspection altitude
                "status": f"HOVER_INSPECTION ({node_curr.name})",
                "current_node_id": node_curr.id,
                "battery_percent": bat_pct,
                "speed_mps": 0.0,
                "ground_speed_mps": 0.0,
                "air_speed_mps": wind_spd,
                "heading_deg": hdg,
                "power_watts": round(nominal_power * 1.15, 1),
                "flight_phase": "HOVER_SCAN",
                "target_name": node_curr.name,
            }

        # Case 2: In forward transit between wp_curr and wp_next
        if wp_curr.departure_time < t_sec < wp_next.arrival_time:
            transit_dur = wp_next.arrival_time - wp_curr.departure_time
            frac = (t_sec - wp_curr.departure_time) / max(transit_dur, 1e-4)

            x = node_curr.x + frac * (node_next.x - node_curr.x)
            y = node_curr.y + frac * (node_next.y - node_curr.y)
            cruise_alt = max(60.0, max(node_curr.elevation, node_next.elevation) + 25.0)
            z = cruise_alt

            bat_pct = wp_curr.remaining_battery_percent + frac * (
                wp_next.remaining_battery_percent - wp_curr.remaining_battery_percent
            )

            hdg = calculate_heading_deg(node_curr.x, node_curr.y, node_next.x, node_next.y)

            dx = node_next.x - node_curr.x
            dy = node_next.y - node_curr.y
            wind_deg = math.degrees(wind_dir_rad)
            wind_vec = wind_to_vector(wind_spd, wind_deg)
            vg, _ = resolve_groundspeed((dx, dy), wind_vec, drone.cruise_speed)
            if not math.isfinite(vg) or vg <= 0:
                vg = drone.cruise_speed

            dist = math.hypot(dx, dy)
            u_x, u_y = (dx / dist, dy / dist) if dist > 1e-6 else (1.0, 0.0)
            w_x, w_y = wind_vec
            wind_along_track = w_x * u_x + w_y * u_y  # positive = tailwind, negative = headwind
            crosswind = abs(-w_x * u_y + w_y * u_x)

            cruise_power = calculate_cruise_power(drone.cruise_speed)
            power_adj = max(
                80.0,
                min(
                    380.0,
                    cruise_power * (1.0 - 0.35 * (wind_along_track / max(drone.cruise_speed, 1.0))),
                ),
            )

            wind_desc = (
                f"Tailwind (+{wind_along_track:.1f} m/s)"
                if wind_along_track > 0.6
                else (
                    f"Headwind ({wind_along_track:.1f} m/s)"
                    if wind_along_track < -0.6
                    else f"Crosswind ({crosswind:.1f} m/s)"
                )
            )

            return {
                "drone_id": drone.id,
                "x": float(x),
                "y": float(y),
                "z": float(z),
                "status": f"CRUISE -> {node_next.name} [{wind_desc}]",
                "current_node_id": node_next.id,
                "battery_percent": float(bat_pct),
                "speed_mps": drone.cruise_speed,
                "ground_speed_mps": round(float(vg), 1),
                "air_speed_mps": drone.cruise_speed,
                "heading_deg": hdg,
                "power_watts": round(float(power_adj), 1),
                "wind_along_mps": round(float(wind_along_track), 1),
                "crosswind_mps": round(float(crosswind), 1),
                "wind_effect": (
                    "Tailwind"
                    if wind_along_track > 0.6
                    else ("Headwind" if wind_along_track < -0.6 else "Crosswind")
                ),
                "flight_phase": "TRANSIT_CRUISE",
                "target_name": node_next.name,
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
        "ground_speed_mps": 0.0,
        "air_speed_mps": 0.0,
        "heading_deg": 0.0,
        "power_watts": 0.0,
        "flight_phase": "RECOVERED",
        "target_name": last_node.name,
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
            row[f"{drone.id} Power (W)"] = round(state.get("power_watts", 0.0), 1)
        records.append(row)

    return pd.DataFrame(records)
