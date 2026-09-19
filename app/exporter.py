"""Hardware flight plan exporter for QGroundControl (.plan) and telemetry audit CSV."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from core.contracts import CandidateRoute, DroneSpec, FleetSchedule, InstanceContext


def export_qgroundcontrol_plan(
    route: CandidateRoute,
    drone: DroneSpec,
    instance: InstanceContext,
    origin_lat: float = 37.7749,
    origin_lon: float = -122.4194,
) -> str:
    """
    Serializes a drone's scheduled trajectory into QGroundControl .plan JSON format (version 1).
    Translates local Cartesian (x, y) coordinates into simulated WGS-84 coordinates.
    """
    node_map = {n.id: n for n in instance.targets}
    items: list[dict[str, Any]] = []

    # Earth projection factor
    m_per_deg_lat = 111132.954
    m_per_deg_lon = 111132.954 * 0.788  # Approximate cos(lat)

    for seq_idx, wp in enumerate(route.waypoints):
        node = node_map[wp.node_id]
        lat = origin_lat + (node.y / m_per_deg_lat)
        lon = origin_lon + (node.x / m_per_deg_lon)
        alt = node.elevation if node.elevation > 0 else 50.0
        dwell = wp.departure_time - wp.arrival_time

        # MAV_CMD_NAV_WAYPOINT = 16
        # Params: [hold_time, accept_radius, pass_radius, yaw, lat, lon, alt]
        item = {
            "autoContinue": True,
            "command": 16,
            "doJumpId": seq_idx + 1,
            "frame": 3,  # MAV_FRAME_GLOBAL_RELATIVE_ALT
            "params": [dwell, 5.0, 0.0, None, lat, lon, alt],
            "type": "SimpleItem",
        }
        items.append(item)

    launch_node = node_map[drone.launch_depot_id]
    home_lat = origin_lat + (launch_node.y / m_per_deg_lat)
    home_lon = origin_lon + (launch_node.x / m_per_deg_lon)

    plan = {
        "fileType": "Plan",
        "version": 1,
        "groundStation": "AeroScan-Optima SITL Controller",
        "mission": {
            "cruiseSpeed": drone.cruise_speed,
            "hoverSpeed": 5.0,
            "firmwareType": 12,  # PX4 Autopilot
            "vehicleType": 2,    # Multi-Rotor
            "plannedHomePosition": [home_lat, home_lon, launch_node.elevation],
            "items": items,
        },
    }
    return json.dumps(plan, indent=2)


def export_mission_telemetry_csv(
    schedule: FleetSchedule,
    instance: InstanceContext,
) -> str:
    """Generates an audit CSV report containing waypoint logs across all assigned drones."""
    node_map = {n.id: n for n in instance.targets}
    rows: list[dict[str, Any]] = []

    for route in schedule.assigned_routes:
        for seq_idx, wp in enumerate(route.waypoints):
            node = node_map[wp.node_id]
            dwell = wp.departure_time - wp.arrival_time
            rows.append({
                "Drone_ID": route.drone_id,
                "Waypoint_Seq": seq_idx,
                "Node_ID": wp.node_id,
                "Node_Name": node.name,
                "Priority_Score": node.priority_score if seq_idx not in (0, len(route.waypoints) - 1) else 0.0,
                "Arrival_Time_sec": round(wp.arrival_time, 2),
                "Departure_Time_sec": round(wp.departure_time, 2),
                "Dwell_Time_sec": round(dwell, 2),
                "Energy_Burn_Joules": round(wp.energy_consumed, 1),
                "Remaining_SoC_Percent": round(wp.remaining_battery_percent, 2),
            })

    df = pd.DataFrame(rows)
    return df.to_csv(index=False)
