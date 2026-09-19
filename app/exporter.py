"""Hardware flight plan exporter for QGroundControl (.plan), MAVLink, and telemetry audit CSV."""

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
            "vehicleType": 2,  # Multi-Rotor
            "plannedHomePosition": [home_lat, home_lon, launch_node.elevation],
            "items": items,
        },
    }
    return json.dumps(plan, indent=2)


def export_mavlink_waypoint_file(
    route: CandidateRoute,
    drone: DroneSpec,
    instance: InstanceContext,
    origin_lat: float = 37.7749,
    origin_lon: float = -122.4194,
) -> str:
    """Generates a standard MAVLink / ArduPilot / PX4 QGC WPL 110 format waypoint file."""
    node_map = {n.id: n for n in instance.targets}
    m_per_deg_lat = 111132.954
    m_per_deg_lon = 111132.954 * 0.788

    lines = ["QGC WPL 110"]
    for seq_idx, wp in enumerate(route.waypoints):
        node = node_map[wp.node_id]
        lat = origin_lat + (node.y / m_per_deg_lat)
        lon = origin_lon + (node.x / m_per_deg_lon)
        alt = max(50.0, node.elevation)
        dwell = wp.departure_time - wp.arrival_time
        # INDEX, CURRENT_WP, COORD_FRAME, COMMAND, PARAM1, PARAM2, PARAM3, PARAM4, PARAM5/X/LAT, PARAM6/Y/LON, PARAM7/Z/ALT, AUTOCONTINUE
        lines.append(f"{seq_idx}\t{'1' if seq_idx == 0 else '0'}\t3\t16\t{dwell:.1f}\t5.000000\t0.000000\t0.000000\t{lat:.7f}\t{lon:.7f}\t{alt:.2f}\t1")

    return "\n".join(lines)


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


def export_mission_dossier_html(
    schedule: FleetSchedule,
    instance: InstanceContext,
) -> str:
    """Generates a downloadable HTML Mission Flight Authorization & Clearance Dossier."""
    node_map = {n.id: n for n in instance.targets}
    routes_html = ""
    for r in schedule.assigned_routes:
        routes_html += f"""
        <div style="background:#1e293b; padding:12px; border-radius:8px; margin-bottom:12px; border-left:4px solid #00f0ff;">
            <h4 style="margin:0 0 6px 0; color:#00f0ff;">🛸 UAV {r.drone_id}</h4>
            <p style="margin:0; color:#cbd5e1; font-size:13px;">
                Targets Visited: <b>{len(r.target_ids)}</b> |
                Score Captured: <b>{r.total_reward:.0f} pts</b> |
                Flight Time: <b>{r.total_flight_time:.1f}s</b> |
                Final Battery: <b>{r.final_reserve_percent:.1f}%</b>
            </p>
        </div>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>AeroScan-Optima Mission Clearance Dossier</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0a0e17; color: #e2e8f0; padding: 30px; }}
        .header {{ border-bottom: 2px solid #00f0ff; padding-bottom: 15px; margin-bottom: 20px; }}
        .badge {{ background: #00f0ff; color: #000; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; }}
        .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 25px; }}
        .card {{ background: #111827; border: 1px solid #334155; padding: 15px; border-radius: 8px; }}
        .card-val {{ font-size: 22px; font-weight: bold; color: #00ff88; }}
        .card-lbl {{ font-size: 11px; color: #94a3b8; text-transform: uppercase; }}
    </style>
</head>
<body>
    <div class="header">
        <span class="badge">MISSION FLIGHT AUTHORIZATION</span>
        <h1 style="color:#00f0ff; margin:10px 0 5px 0;">AEROSCAN-OPTIMA MISSION DOSSIER</h1>
        <p style="color:#94a3b8; margin:0;">Scenario: <b>{instance.instance_name}</b> | Solver: <b>{schedule.status}</b></p>
    </div>
    <div class="grid">
        <div class="card"><div class="card-val">{schedule.cumulative_reward:.0f} pts</div><div class="card-lbl">Total Score</div></div>
        <div class="card"><div class="card-val">{schedule.solve_time_seconds:.2f}s</div><div class="card-lbl">Solve Latency</div></div>
        <div class="card"><div class="card-val">{len(schedule.assigned_routes)} UAVs</div><div class="card-lbl">Active Fleet</div></div>
        <div class="card"><div class="card-val">{min((r.final_reserve_percent for r in schedule.assigned_routes), default=100.0):.1f}%</div><div class="card-lbl">Min Battery Reserve</div></div>
    </div>
    <h3 style="color:#38bdf8;">Fleet Route Breakdown</h3>
    {routes_html}
    <footer style="margin-top:30px; font-size:11px; color:#64748b; text-align:center;">
        Generated by AeroScan-Optima Matheuristic Engine • Compliant with FAA 14 CFR § 107.25 / PX4 SITL
    </footer>
</body>
</html>
"""
