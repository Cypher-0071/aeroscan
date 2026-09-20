"""
AeroScan — Aerospace Swarm Mission Operations REST API
Exposes the core matheuristic optimization engine, real-time telemetry simulator,
battery depletion models, and autopilot exporters to the React frontend.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import numpy as np

from app.exporter import (
    export_mavlink_waypoint_file,
    export_mission_telemetry_csv,
    export_qgroundcontrol_plan,
)
from app.telemetry import (
    compute_battery_curves,
    get_fleet_telemetry_at_time,
    interpolate_drone_state,
)
from baselines.grasp import solve_grasp_baseline
from benchmarks.chao_loader import get_canonical_chao_instance
from core.alns import explore_route_pool
from core.contracts import CandidateRoute, FleetSchedule, InstanceContext
from core.instance import build_instance_context
from core.set_packing import solve_fleet_schedule

app = Flask(__name__, static_folder=str(_PROJECT_ROOT / "web" / "dist"), static_url_path="")
CORS(app)


class NumpyEncoder(json.JSONEncoder):
    """Custom encoder for NumPy scalar types and arrays."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def serialize_instance(instance: InstanceContext) -> dict[str, Any]:
    """Converts InstanceContext to a JSON-serializable dictionary."""
    depot_ids = {d.launch_depot_id for d in instance.drones} | {
        d.recovery_depot_id for d in instance.drones
    }
    return {
        "instance_name": instance.instance_name,
        "total_nodes": instance.total_nodes,
        "depot_ids": sorted(list(depot_ids)),
        "ambient_wind": {
            "speed_mps": float(instance.ambient_wind[0]),
            "direction_rad": float(instance.ambient_wind[1]),
            "direction_deg": round(math.degrees(instance.ambient_wind[1])) % 360,
        },
        "metadata": instance.metadata,
        "drones": [d.to_dict() for d in instance.drones],
        "targets": [t.to_dict() for t in instance.targets],
        "target_nodes": [t.to_dict() for t in instance.target_nodes],
    }


def load_instance(
    scenario_name: str, num_drones: int = 3, wind_speed: float = 3.5, wind_dir: float = 45.0
) -> InstanceContext:
    """Loads an InstanceContext by scenario key."""
    if "Mountain" in scenario_name or scenario_name == "sample":
        sample_path = _PROJECT_ROOT / "data" / "sample_mission.json"
        if sample_path.exists():
            return build_instance_context(
                sample_path,
                wind_speed_mps=wind_speed,
                wind_dir_deg=wind_dir,
                num_drones=num_drones,
            )

    set_key = "set_64"
    if "66" in scenario_name:
        set_key = "set_66"
    elif "100" in scenario_name:
        set_key = "set_100"
    elif "102" in scenario_name:
        set_key = "set_102"

    return get_canonical_chao_instance(
        set_key,
        num_drones=num_drones,
        wind_speed_mps=wind_speed,
        wind_dir_deg=wind_dir,
    )


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "aeroscan-api", "version": "1.0.0"})


@app.route("/api/scenarios", methods=["GET"])
def get_scenarios():
    scenarios = [
        {"id": "set_64", "name": "Chao Set 64 (Clustered SAR)", "type": "Chao TOP"},
        {"id": "set_66", "name": "Chao Set 66 (Diamond Perimeter)", "type": "Chao TOP"},
        {"id": "set_100", "name": "Chao Set 100 (Concentric Grid)", "type": "Chao TOP"},
        {"id": "set_102", "name": "Chao Set 102 (Uniform Scatter)", "type": "Chao TOP"},
        {"id": "sample_sar", "name": "Sample Mountain SAR", "type": "GeoJSON/Cartesian"},
    ]
    return jsonify({"scenarios": scenarios})


@app.route("/api/solve", methods=["POST"])
def solve():
    """
    Executes the two-tier matheuristic optimization pipeline:
    Tier 1: ALNS route pool generation
    Tier 2: CP-SAT Set Packing solver
    Also computes the GRASP baseline for performance gain comparison.
    """
    data = request.get_json() or {}
    scenario_name = data.get("scenario", "Chao Set 64 (Clustered SAR)")
    fleet_size = int(data.get("fleet_size", 3))
    wind_speed = float(data.get("wind_speed", 3.5))
    wind_dir = float(data.get("wind_dir", 45.0))
    max_iterations = int(data.get("max_iterations", 250))
    time_limit_sec = float(data.get("time_limit_sec", 1.2))

    # Ingest and project instance
    instance = load_instance(scenario_name, fleet_size, wind_speed, wind_dir)

    # Solve Tier 1 (ALNS) & Tier 2 (CP-SAT)
    pool = explore_route_pool(instance, max_iterations=max_iterations, time_limit_sec=time_limit_sec)
    schedule = solve_fleet_schedule(instance, pool, run_baselines=True)

    # Baseline comparison
    grasp_schedule = solve_grasp_baseline(instance)

    # Compute initial telemetry state at t = 0
    init_telem, secured = get_fleet_telemetry_at_time(schedule, 0.0, instance)

    max_mission_time = max(
        (r.total_flight_time for r in schedule.assigned_routes),
        default=600.0,
    )
    if max_mission_time <= 0:
        max_mission_time = 600.0

    response_payload = {
        "success": True,
        "instance": serialize_instance(instance),
        "schedule": schedule.to_dict(),
        "grasp_schedule": grasp_schedule.to_dict(),
        "max_mission_time": float(max_mission_time),
        "telemetry_init": init_telem,
        "secured_targets_init": list(secured),
    }
    return app.response_class(
        json.dumps(response_payload, cls=NumpyEncoder),
        mimetype="application/json",
    )


@app.route("/api/mock", methods=["GET"])
def get_mock():
    """Loads a precomputed mock mission fixture or solves for requested fleet size."""
    fleet_size = request.args.get("fleet_size", 3, type=int)
    instance = load_instance("set_64", fleet_size, 3.5, 45.0)

    mock_path = _PROJECT_ROOT / "tests" / "mock_schedule.json"
    if fleet_size == 2 and mock_path.exists():
        with open(mock_path, "r", encoding="utf-8") as f:
            mock_data = json.load(f)
        schedule = FleetSchedule.from_dict(mock_data)
    else:
        pool = explore_route_pool(instance, max_iterations=120, time_limit_sec=0.5, seed=42)
        schedule = solve_fleet_schedule(instance, pool, run_baselines=True)

    grasp_schedule = solve_grasp_baseline(instance)
    init_telem, secured = get_fleet_telemetry_at_time(schedule, 0.0, instance)
    max_time = max((r.total_flight_time for r in schedule.assigned_routes), default=1285.4)

    return app.response_class(
        json.dumps(
            {
                "success": True,
                "instance": serialize_instance(instance),
                "schedule": schedule.to_dict(),
                "grasp_schedule": grasp_schedule.to_dict(),
                "max_mission_time": float(max_time),
                "telemetry_init": init_telem,
                "secured_targets_init": list(secured),
            },
            cls=NumpyEncoder,
        ),
        mimetype="application/json",
    )


@app.route("/api/telemetry", methods=["POST"])
def get_telemetry():
    """
    Computes real-time 10Hz kinematics and target state for arbitrary timestamp t_sec.
    """
    data = request.get_json() or {}
    t_sec = float(data.get("t_sec", 0.0))
    schedule_data = data.get("schedule")
    instance_data = data.get("instance")

    if not schedule_data or not instance_data:
        return jsonify({"error": "Missing schedule or instance payload"}), 400

    schedule = FleetSchedule.from_dict(schedule_data)
    # Reconstitute minimal instance context for interpolation
    scenario_name = instance_data.get("instance_name", "set_64")
    drones_cnt = len(instance_data.get("drones", []))
    wind = instance_data.get("ambient_wind", {})
    w_spd = float(wind.get("speed_mps", 0.0))
    w_dir = float(wind.get("direction_deg", 0.0))

    instance = load_instance(scenario_name, drones_cnt, w_spd, w_dir)
    telemetry_list, secured_targets = get_fleet_telemetry_at_time(schedule, t_sec, instance)

    return app.response_class(
        json.dumps(
            {
                "t_sec": t_sec,
                "telemetry": telemetry_list,
                "secured_targets": list(secured_targets),
            },
            cls=NumpyEncoder,
        ),
        mimetype="application/json",
    )


@app.route("/api/battery-curves", methods=["POST"])
def get_battery_curves():
    """Computes battery SoC depletion curves over the mission duration."""
    data = request.get_json() or {}
    schedule_data = data.get("schedule")
    instance_data = data.get("instance")
    num_points = int(data.get("num_points", 120))

    if not schedule_data or not instance_data:
        return jsonify({"error": "Missing schedule or instance payload"}), 400

    schedule = FleetSchedule.from_dict(schedule_data)
    scenario_name = instance_data.get("instance_name", "set_64")
    drones_cnt = len(instance_data.get("drones", []))
    wind = instance_data.get("ambient_wind", {})
    w_spd = float(wind.get("speed_mps", 0.0))
    w_dir = float(wind.get("direction_deg", 0.0))

    instance = load_instance(scenario_name, drones_cnt, w_spd, w_dir)
    df = compute_battery_curves(schedule, instance, num_points=num_points)

    records = df.to_dict(orient="records")
    return app.response_class(
        json.dumps({"curves": records}, cls=NumpyEncoder),
        mimetype="application/json",
    )


@app.route("/api/export", methods=["POST"])
def export_hardware_plan():
    """Generates QGroundControl plan, MAVLink waypoints, or Swarm Telemetry CSV."""
    data = request.get_json() or {}
    export_type = data.get("type", "qgc")  # "qgc", "mavlink", "csv"
    drone_id = data.get("drone_id", "UAV-01")
    schedule_data = data.get("schedule")
    instance_data = data.get("instance")

    if not schedule_data or not instance_data:
        return jsonify({"error": "Missing schedule or instance payload"}), 400

    schedule = FleetSchedule.from_dict(schedule_data)
    scenario_name = instance_data.get("instance_name", "set_64")
    drones_cnt = len(instance_data.get("drones", []))
    wind = instance_data.get("ambient_wind", {})
    w_spd = float(wind.get("speed_mps", 0.0))
    w_dir = float(wind.get("direction_deg", 0.0))

    instance = load_instance(scenario_name, drones_cnt, w_spd, w_dir)

    selected_route = next(
        (r for r in schedule.assigned_routes if r.drone_id == drone_id),
        schedule.assigned_routes[0] if schedule.assigned_routes else None,
    )
    selected_drone = next(
        (d for d in instance.drones if d.id == drone_id),
        instance.drones[0] if instance.drones else None,
    )

    if export_type == "csv":
        csv_content = export_mission_telemetry_csv(schedule, instance)
        return jsonify({
            "filename": "aeroscan_swarm_telemetry_audit.csv",
            "content": csv_content,
            "mime": "text/csv",
        })

    if not selected_route or not selected_drone:
        return jsonify({"error": f"No route found for {drone_id}"}), 404

    if export_type == "mavlink":
        mavlink_content = export_mavlink_waypoint_file(selected_route, selected_drone, instance)
        return jsonify({
            "filename": f"aeroscan_{drone_id}_mavlink.waypoints",
            "content": mavlink_content,
            "mime": "text/plain",
        })

    # Default: QGroundControl plan
    qgc_json = export_qgroundcontrol_plan(selected_route, selected_drone, instance)
    return jsonify({
        "filename": f"aeroscan_{drone_id}_mission.plan",
        "content": qgc_json,
        "mime": "application/json",
    })


# Serve static React build files in production
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path: str):
    dist_dir = _PROJECT_ROOT / "web" / "dist"
    if path != "" and (dist_dir / path).exists():
        return send_from_directory(str(dist_dir), path)
    if (dist_dir / "index.html").exists():
        return send_from_directory(str(dist_dir), "index.html")
    return jsonify({
        "message": "AeroScan API server running. React frontend is not yet built in web/dist.",
        "endpoints": ["/api/health", "/api/scenarios", "/api/solve", "/api/telemetry", "/api/battery-curves", "/api/export", "/api/mock"],
    })


if __name__ == "__main__":
    port = 5001
    print(f"[*] Starting AeroScan Mission Operations API on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
