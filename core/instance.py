"""Mission instance ingestion, coordinate projection, and context builder."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from core.contracts import DroneSpec, InstanceContext, TargetNode
from core.physics import DroneAeroParams, compute_cost_matrices


def latlon_to_cartesian_meters(
    lat: float, lon: float, origin_lat: float, origin_lon: float
) -> tuple[float, float]:
    """
    Projects WGS-84 (lat, lon) coordinates into local Cartesian (x, y) meters
    relative to an origin point using equirectangular projection.
    """
    r_earth = 6371000.0  # Earth radius in meters
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    lat0_rad = math.radians(origin_lat)
    lon0_rad = math.radians(origin_lon)

    x = (lon_rad - lon0_rad) * math.cos(0.5 * (lat_rad + lat0_rad)) * r_earth
    y = (lat_rad - lat0_rad) * r_earth
    return (float(x), float(y))


def parse_chao_txt(filepath: str | Path) -> tuple[str, list[TargetNode], int, float]:
    """
    Parses a Chao et al. (1996) standard benchmark instance file.

    Format:
    Line 1: N K Tmax (or similar header)
    Subsequent lines: node_id x y score (or similar standard format)
    """
    path = Path(filepath)
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    header = lines[0].split()
    # Typically: N K Tmax or similar
    _num_nodes = int(header[0])
    num_drones = int(header[1]) if len(header) > 1 else 3
    t_max = float(header[2]) if len(header) > 2 else 2400.0

    nodes: list[TargetNode] = []
    for line in lines[1:]:
        tokens = line.split()
        if len(tokens) < 4:
            continue
        node_id = int(tokens[0])
        x = float(tokens[1])
        y = float(tokens[2])
        score = float(tokens[3])
        dwell = 30.0 if score > 0 else 0.0
        name = f"Depot-{node_id}" if score == 0 else f"Target-{node_id}"
        nodes.append(
            TargetNode(
                id=node_id,
                name=name,
                x=x,
                y=y,
                elevation=50.0 if score > 0 else 0.0,
                priority_score=score,
                dwell_time=dwell,
            )
        )

    return path.stem, nodes, num_drones, t_max


def parse_json_mission(filepath: str | Path) -> tuple[str, list[TargetNode], list[DroneSpec], tuple[float, float]]:
    """
    Parses a standard or custom JSON/GeoJSON mission file.
    """
    path = Path(filepath)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    instance_name = data.get("name", data.get("instance_name", path.stem))
    ambient_wind_data = data.get("ambient_wind", {})
    wind_speed = float(ambient_wind_data.get("speed_mps", 0.0))
    wind_dir = float(ambient_wind_data.get("direction_degrees", 0.0))

    # Parse targets
    raw_targets = data.get("targets", [])
    if not raw_targets and "features" in data:
        # GeoJSON support
        raw_targets = []
        origin_coords: tuple[float, float] | None = None
        for feat in data["features"]:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [0.0, 0.0])
            lon, lat = float(coords[0]), float(coords[1])
            if origin_coords is None:
                origin_coords = (lat, lon)
            x, y = latlon_to_cartesian_meters(lat, lon, origin_coords[0], origin_coords[1])
            raw_targets.append({
                "id": props.get("id", len(raw_targets)),
                "name": props.get("name", f"Target-{len(raw_targets)}"),
                "x": x,
                "y": y,
                "elevation": props.get("elevation", 50.0),
                "priority_score": props.get("priority_score", props.get("score", 10.0)),
                "dwell_time": props.get("dwell_time", 30.0),
            })

    targets: list[TargetNode] = [TargetNode.from_dict(t) for t in raw_targets]

    # Parse drones
    raw_drones = data.get("drones", data.get("fleet", {}).get("drones", []))
    drones: list[DroneSpec] = []
    if raw_drones:
        for d in raw_drones:
            drones.append(DroneSpec.from_dict(d))
    else:
        # Default fleet: 3 identical industrial drones
        depot_id = targets[0].id if targets else 0
        for i in range(3):
            drones.append(
                DroneSpec(
                    id=f"UAV-0{i+1}",
                    battery_joules=360000.0,  # 100 Wh
                    safety_reserve_ratio=0.15,
                    max_flight_time=2400.0,
                    cruise_speed=14.5,
                    launch_depot_id=depot_id,
                    recovery_depot_id=depot_id,
                    model="Matrice-350-RTK",
                )
            )

    return instance_name, targets, drones, (wind_speed, wind_dir)


def build_instance_context(
    filepath: str | Path,
    wind_speed_mps: float = 0.0,
    wind_dir_deg: float = 0.0,
    num_drones: int | None = None,
    aero_params: DroneAeroParams = DroneAeroParams(),
) -> InstanceContext:
    """
    Parses mission instance file, computes aerodynamic cost matrices with wind drift,
    and returns a fully resolved InstanceContext.
    """
    path = Path(filepath)
    suffix = path.suffix.lower()

    if suffix == ".json" or suffix == ".geojson":
        name, targets, drones, wind = parse_json_mission(path)
        if wind_speed_mps != 0.0 or wind_dir_deg != 0.0:
            wind = (wind_speed_mps, wind_dir_deg)
    elif suffix == ".txt":
        name, targets, k, t_max = parse_chao_txt(path)
        actual_k = num_drones if num_drones is not None else k
        depot_id = targets[0].id if targets else 0
        drones = [
            DroneSpec(
                id=f"UAV-0{i+1}",
                battery_joules=360000.0,
                safety_reserve_ratio=0.15,
                max_flight_time=t_max,
                cruise_speed=14.5,
                launch_depot_id=depot_id,
                recovery_depot_id=depot_id,
            )
            for i in range(actual_k)
        ]
        wind = (wind_speed_mps, wind_dir_deg)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")

    if num_drones is not None and len(drones) != num_drones:
        # Re-scale drone fleet if requested
        base_drone = drones[0]
        drones = [
            DroneSpec(
                id=f"UAV-0{i+1}",
                battery_joules=base_drone.battery_joules,
                safety_reserve_ratio=base_drone.safety_reserve_ratio,
                max_flight_time=base_drone.max_flight_time,
                cruise_speed=base_drone.cruise_speed,
                launch_depot_id=base_drone.launch_depot_id,
                recovery_depot_id=base_drone.recovery_depot_id,
            )
            for i in range(num_drones)
        ]

    # Precompute time and energy matrices
    coords = np.array([[t.x, t.y] for t in targets], dtype=np.float64)
    cruise_speed = drones[0].cruise_speed if drones else 14.5
    time_mat, energy_mat = compute_cost_matrices(
        coords,
        wind_speed_mps=wind[0],
        wind_direction_deg=wind[1],
        cruise_speed_mps=cruise_speed,
        params=aero_params,
    )

    # Convert wind direction in degrees to radians for storage
    ambient_wind_tuple = (wind[0], math.radians(wind[1]))

    return InstanceContext(
        instance_name=name,
        targets=targets,
        drones=drones,
        time_matrix=time_mat,
        energy_matrix=energy_mat,
        ambient_wind=ambient_wind_tuple,
    )
