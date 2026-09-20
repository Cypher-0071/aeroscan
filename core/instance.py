"""Mission instance ingestion, coordinate projection, and context builder.

Parsing and context construction are deliberately separated:

* the ``parse_*`` helpers return a :class:`ParsedInstance` of normalized records
  without touching aerodynamics, so parser behavior is testable in isolation;
* :func:`build_instance_context` is the only place that calls the physics engine,
  enforces the matrix invariants, and constructs an ``InstanceContext``.

Public input conventions
------------------------
* Metric Cartesian coordinates (``x``/``y``) are **meters** and are used as-is.
* Geographic coordinates (``longitude``/``latitude`` or GeoJSON ``[lon, lat]``)
  are WGS-84 degrees and are projected once per mission into local meters with
  :func:`latlon_to_cartesian_meters` (equirectangular, dependency free). The
  chosen CRS and projection origin are recorded in the instance metadata.
* Wind is supplied as ``(speed_mps, direction_deg)`` where ``direction_deg`` uses
  the module-level convention in :mod:`core.physics`: the direction the air mass
  moves **towards**, ``0`` = ``+x``/East, increasing counter-clockwise. A
  meteorological "blowing from" bearing can be supplied instead as
  ``direction_from_degrees`` and is converted at ingestion.
* Wind override semantics: ``wind_speed_mps=None`` and ``wind_dir_deg=None`` mean
  *use the wind declared in the file*. Supplying a value - including ``0.0`` -
  explicitly overrides the file wind.

Supported inputs
----------------
``.json`` (mission JSON), ``.geojson`` (Point ``FeatureCollection``), ``.csv``
(target table, with a companion ``<stem>.meta.json`` mission sidecar for fleet and
wind metadata), and ``.txt`` (Chao TOP benchmark format).
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from core.contracts import DroneSpec, InstanceContext, TargetNode
from core.physics import DroneAeroParams, compute_cost_matrices

SUPPORTED_SUFFIXES: tuple[str, ...] = (".json", ".geojson", ".csv", ".txt")

# Default dwelling assigned to a CSV/benchmark target that does not declare one.
CSV_DEFAULT_DWELL_TIME_SECONDS = 30.0


# ---------------------------------------------------------------------------
# Normalized records
# ---------------------------------------------------------------------------


@dataclass
class ParsedInstance:
    """Normalized parse result: raw records plus provenance metadata."""

    name: str
    targets: list[TargetNode]
    drones: list[DroneSpec] = field(default_factory=list)
    wind_speed_mps: float | None = None
    wind_direction_deg: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChaoAdapterConfig:
    """Explicit adapter assumptions used to map a Chao TOP instance onto UAV physics.

    Chao instances encode pure distance/route-length TOP problems; these values
    are the documented, configurable bridge to the UAV energy/time model.
    """

    target_dwell_time_seconds: float = 30.0
    depot_dwell_time_seconds: float = 0.0
    target_elevation_m: float = 50.0
    depot_elevation_m: float = 0.0
    battery_joules: float = 360000.0
    safety_reserve_ratio: float = 0.15
    cruise_speed_mps: float = 14.5


DEFAULT_CHAO_ADAPTER = ChaoAdapterConfig()


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


def latlon_to_cartesian_meters(
    lat: float, lon: float, origin_lat: float, origin_lon: float
) -> tuple[float, float]:
    """Projects WGS-84 ``(lat, lon)`` into local Cartesian ``(x, y)`` meters.

    Uses a dependency-free equirectangular projection around ``origin``: ``x`` is
    east of the origin and ``y`` is north of the origin. Accurate over compact SAR
    extents; not a substitute for a projected CRS over continental scales.
    """
    r_earth = 6371000.0  # Earth radius in meters
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    lat0_rad = math.radians(origin_lat)
    lon0_rad = math.radians(origin_lon)

    x = (lon_rad - lon0_rad) * math.cos(0.5 * (lat_rad + lat0_rad)) * r_earth
    y = (lat_rad - lat0_rad) * r_earth
    return (float(x), float(y))


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _fail(source: str, message: str) -> ValueError:
    return ValueError(f"{source}: {message}")


def _require_mapping(value: Any, source: str, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail(source, f"{label} must be a JSON object, got {type(value).__name__}")
    return value


def _as_float(value: Any, source: str, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise _fail(source, f"{label} must be a number, got {value!r}") from exc


def _validate_unique_target_ids(targets: list[TargetNode], source: str) -> None:
    seen: set[int] = set()
    for node in targets:
        if node.id in seen:
            raise _fail(source, f"duplicate node id {node.id}")
        seen.add(node.id)


def validate_fleet(drones: list[DroneSpec], targets: list[TargetNode], source: str) -> None:
    """Validates unique drone IDs, positive per-drone limits, and existing depots."""
    if not drones:
        raise _fail(source, "fleet is empty; at least one drone specification is required")

    valid_ids = {node.id for node in targets}
    seen: set[str] = set()
    for drone in drones:
        if drone.id in seen:
            raise _fail(source, f"duplicate drone id {drone.id!r}")
        seen.add(drone.id)
        if drone.battery_joules <= 0:
            raise _fail(source, f"drone {drone.id!r} battery_joules must be positive")
        if drone.max_flight_time <= 0:
            raise _fail(source, f"drone {drone.id!r} max_flight_time must be positive")
        if drone.cruise_speed <= 0:
            raise _fail(source, f"drone {drone.id!r} cruise_speed must be positive")
        if not 0.0 <= drone.safety_reserve_ratio < 1.0:
            raise _fail(source, f"drone {drone.id!r} safety_reserve_ratio must be in [0, 1)")
        if drone.launch_depot_id not in valid_ids:
            raise _fail(source, f"drone {drone.id!r} launch_depot_id {drone.launch_depot_id} not found")
        if drone.recovery_depot_id not in valid_ids:
            raise _fail(
                source, f"drone {drone.id!r} recovery_depot_id {drone.recovery_depot_id} not found"
            )


def _resolve_wind_direction(ambient: dict[str, Any], source: str) -> float:
    """Resolves a Cartesian moving-towards direction, converting meteorological bearings."""
    has_towards = "direction_degrees" in ambient
    has_from = "direction_from_degrees" in ambient
    if has_towards and has_from:
        raise _fail(source, "ambient_wind cannot set both direction_degrees and direction_from_degrees")
    if has_from:
        from_deg = _as_float(ambient["direction_from_degrees"], source, "ambient_wind.direction_from_degrees")
        return (from_deg + 180.0) % 360.0
    if has_towards:
        return _as_float(ambient["direction_degrees"], source, "ambient_wind.direction_degrees")
    return 0.0


def _parse_wind(data: dict[str, Any], source: str) -> tuple[float | None, float | None]:
    ambient = data.get("ambient_wind")
    if ambient is None:
        speed = data.get("wind_speed_mps")
        direction = data.get("wind_direction_degrees")
        if speed is None and direction is None:
            return (None, None)
        return (_as_float(speed if speed is not None else 0.0, source, "wind_speed_mps"), _as_float(
            direction if direction is not None else 0.0, source, "wind_direction_degrees"
        ))
    ambient = _require_mapping(ambient, source, "ambient_wind")
    speed = _as_float(ambient.get("speed_mps", 0.0), source, "ambient_wind.speed_mps")
    if speed < 0:
        raise _fail(source, f"ambient_wind.speed_mps must be non-negative, got {speed}")
    return (speed, _resolve_wind_direction(ambient, source))


def _parse_drones(data: dict[str, Any], source: str) -> list[DroneSpec]:
    raw_fleet = data.get("drones")
    if raw_fleet is None:
        fleet = data.get("fleet")
        if isinstance(fleet, dict):
            raw_fleet = fleet.get("drones")
        elif fleet is not None:
            raise _fail(source, "'fleet' must be an object containing a 'drones' list")
    if raw_fleet is None:
        return []
    if not isinstance(raw_fleet, list):
        raise _fail(source, "'drones' must be a list")
    drones: list[DroneSpec] = []
    for idx, raw in enumerate(raw_fleet):
        record = _require_mapping(raw, source, f"drones[{idx}]")
        if "id" not in record:
            raise _fail(source, f"drones[{idx}] is missing required field 'id'")
        try:
            drones.append(DroneSpec.from_dict(record))
        except (KeyError, TypeError, ValueError) as exc:
            raise _fail(source, f"drones[{idx}]: {exc}") from exc
    return drones


# ---------------------------------------------------------------------------
# JSON / GeoJSON parsing
# ---------------------------------------------------------------------------


def _coordinate_kind(record: dict[str, Any], source: str, index: int) -> str:
    """Classifies a target record as Cartesian ("xy") or geographic ("latlon")."""
    has_xy = "x" in record and "y" in record
    has_partial_xy = ("x" in record or "y" in record) and not has_xy
    lon = record.get("longitude", record.get("lon"))
    lat = record.get("latitude", record.get("lat"))
    has_latlon = lon is not None and lat is not None
    if has_xy and has_latlon:
        raise _fail(source, f"targets[{index}] sets both x/y and longitude/latitude")
    if has_latlon and ("x" in record or "y" in record):
        raise _fail(source, f"targets[{index}] sets both x/y and longitude/latitude")
    if has_partial_xy:
        raise _fail(source, f"targets[{index}] must provide both x and y (meters), not just one")
    if not has_xy and not has_latlon:
        raise _fail(source, f"targets[{index}] must provide either x/y (meters) or longitude/latitude")
    return "latlon" if has_latlon else "xy"


def _target_from_record(
    record: dict[str, Any],
    source: str,
    index: int,
    projection: dict[str, Any] | None,
) -> TargetNode:
    if "id" not in record:
        raise _fail(source, f"targets[{index}] is missing required field 'id'")

    kind = _coordinate_kind(record, source, index)
    if kind == "latlon":
        lon = record.get("longitude", record.get("lon"))
        lat = record.get("latitude", record.get("lat"))
        lon_f = _as_float(lon, source, f"targets[{index}].longitude")
        lat_f = _as_float(lat, source, f"targets[{index}].latitude")
        if projection is None:
            raise _fail(source, f"targets[{index}] uses geographic coordinates without a mission origin")
        x, y = latlon_to_cartesian_meters(lat_f, lon_f, projection["origin_lat"], projection["origin_lon"])
        projection.setdefault("crs", "wgs84-equirectangular")
    else:
        x = _as_float(record["x"], source, f"targets[{index}].x")
        y = _as_float(record["y"], source, f"targets[{index}].y")

    default_dwell = _as_float(
        record.get("dwell_time", record.get("dwell_time_seconds", CSV_DEFAULT_DWELL_TIME_SECONDS)),
        source,
        f"targets[{index}].dwell_time",
    )
    raw_id = record["id"]
    try:
        id_float = float(raw_id)
    except (TypeError, ValueError) as exc:
        raise _fail(source, f"targets[{index}].id must be an integer, got {raw_id!r}") from exc
    if not id_float.is_integer():
        raise _fail(source, f"targets[{index}].id must be an integer, got {raw_id!r}")
    return TargetNode(
        id=int(id_float),
        name=str(record.get("name", f"Node-{record['id']}")),
        x=x,
        y=y,
        elevation=_as_float(record.get("elevation", 0.0), source, f"targets[{index}].elevation"),
        priority_score=_as_float(
            record.get("priority_score", record.get("score", 0.0)), source, f"targets[{index}].priority_score"
        ),
        dwell_time=default_dwell,
    )


def _parse_geojson(data: dict[str, Any], source: str, name: str) -> ParsedInstance:
    features = data.get("features")
    if not isinstance(features, list):
        raise _fail(source, "GeoJSON FeatureCollection must contain a 'features' list")
    if not features:
        raise _fail(source, "GeoJSON FeatureCollection contains no features")

    projection: dict[str, Any] = {}
    raw_records: list[dict[str, Any]] = []
    for idx, feature in enumerate(features):
        feat = _require_mapping(feature, source, f"features[{idx}]")
        geom = _require_mapping(feat.get("geometry", {}), source, f"features[{idx}].geometry")
        geom_type = geom.get("type")
        if geom_type != "Point":
            raise _fail(source, f"features[{idx}] geometry type must be 'Point', got {geom_type!r}")
        coords = geom.get("coordinates")
        if not isinstance(coords, (list, tuple)) or len(coords) != 2:
            raise _fail(
                source,
                f"features[{idx}] Point coordinates must be [longitude, latitude]; "
                "elevation comes from feature properties (default 0.0), not a third coordinate",
            )
        props = feat.get("properties") or {}
        props = _require_mapping(props, source, f"features[{idx}].properties")

        record = dict(props)
        record.setdefault("id", idx)
        record["longitude"] = coords[0]
        record["latitude"] = coords[1]
        if "x" in record or "y" in record:
            raise _fail(source, f"features[{idx}] cannot mix projected x/y with geographic coordinates")
        raw_records.append(record)

    # One origin/CRS per mission: the first feature defines the local frame unless
    # the mission explicitly declares an origin.
    declared_origin = data.get("origin")
    if isinstance(declared_origin, dict):
        projection["origin_lat"] = _as_float(declared_origin.get("latitude"), source, "origin.latitude")
        projection["origin_lon"] = _as_float(declared_origin.get("longitude"), source, "origin.longitude")
    else:
        projection["origin_lat"] = _as_float(raw_records[0]["latitude"], source, "features[0].latitude")
        projection["origin_lon"] = _as_float(raw_records[0]["longitude"], source, "features[0].longitude")
    projection["crs"] = "wgs84-equirectangular"

    targets = [
        _target_from_record(record, source, idx, projection) for idx, record in enumerate(raw_records)
    ]
    drones = _parse_drones(data, source)
    wind_speed, wind_dir = _parse_wind(data, source)
    return ParsedInstance(
        name=str(data.get("name", name)),
        targets=targets,
        drones=drones,
        wind_speed_mps=wind_speed,
        wind_direction_deg=wind_dir,
        metadata={
            "source_format": "geojson",
            "crs": projection["crs"],
            "projection_origin": (projection["origin_lat"], projection["origin_lon"]),
        },
    )


def _parse_mission_json(data: dict[str, Any], source: str, name: str) -> ParsedInstance:
    raw_targets = data.get("targets")
    if raw_targets is None:
        raise _fail(source, "mission JSON must contain a 'targets' list")
    if not isinstance(raw_targets, list):
        raise _fail(source, "'targets' must be a list")
    if not raw_targets:
        raise _fail(source, "'targets' must not be empty")

    records = [_require_mapping(raw, source, f"targets[{idx}]") for idx, raw in enumerate(raw_targets)]
    kinds = [_coordinate_kind(record, source, idx) for idx, record in enumerate(records)]

    projection: dict[str, Any] | None = None
    if "latlon" in kinds:
        declared_origin = data.get("origin")
        origin_lat: float | None = None
        origin_lon: float | None = None
        if isinstance(declared_origin, dict):
            origin_lat = _as_float(declared_origin.get("latitude"), source, "origin.latitude")
            origin_lon = _as_float(declared_origin.get("longitude"), source, "origin.longitude")
        else:
            for idx, record in enumerate(records):
                if kinds[idx] != "latlon":
                    continue
                origin_lat = _as_float(
                    record.get("latitude", record.get("lat")), source, f"targets[{idx}].latitude"
                )
                origin_lon = _as_float(
                    record.get("longitude", record.get("lon")), source, f"targets[{idx}].longitude"
                )
                break
        if origin_lat is None or origin_lon is None:
            raise _fail(source, "geographic targets require an origin (or one latitude/longitude target)")
        projection = {"crs": "wgs84-equirectangular", "origin_lat": origin_lat, "origin_lon": origin_lon}

    targets: list[TargetNode] = []
    for idx, record in enumerate(records):
        targets.append(_target_from_record(record, source, idx, projection))

    drones = _parse_drones(data, source)
    wind_speed, wind_dir = _parse_wind(data, source)
    metadata: dict[str, Any] = {"source_format": "json"}
    if projection is not None:
        metadata["crs"] = projection["crs"]
        metadata["projection_origin"] = (projection["origin_lat"], projection["origin_lon"])
    else:
        metadata["crs"] = "cartesian-meters"
    return ParsedInstance(
        name=str(data.get("name", data.get("instance_name", name))),
        targets=targets,
        drones=drones,
        wind_speed_mps=wind_speed,
        wind_direction_deg=wind_dir,
        metadata=metadata,
    )


def parse_json_mission(filepath: str | Path) -> ParsedInstance:
    """Parses a mission JSON or GeoJSON ``FeatureCollection`` file."""
    path = Path(filepath)
    source = str(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise _fail(source, f"invalid JSON at line {exc.lineno} column {exc.colno}: {exc.msg}") from exc
    data = _require_mapping(raw, source, "top-level document")

    is_geojson = data.get("type") == "FeatureCollection" or "features" in data
    if is_geojson:
        return _parse_geojson(data, source, path.stem)
    return _parse_mission_json(data, source, path.stem)


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


def parse_csv_targets(filepath: str | Path, sidecar: dict[str, Any] | None = None) -> ParsedInstance:
    """Parses a target table CSV plus optional mission sidecar metadata.

    Required columns: ``id``, ``priority_score`` and either ``x``/``y`` (meters) or
    ``longitude``/``latitude`` (WGS-84). Optional columns: ``name``, ``elevation``,
    ``dwell_time`` (or ``dwell_time_seconds``).

    Fleet and wind metadata are supplied through a companion mission JSON sidecar
    (:func:`sidecar_path_for`); a bare CSV cannot safely describe a fleet, so a
    missing sidecar that also has no drones is reported rather than invented.
    """
    path = Path(filepath)
    source = str(path)
    text = path.read_text(encoding="utf-8")
    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None:
        raise _fail(source, "CSV file is empty")
    headers = [h.strip() for h in reader.fieldnames if h is not None]
    lower_headers = {h.lower(): h for h in headers}

    def col(name: str) -> str | None:
        return lower_headers.get(name)

    if col("id") is None:
        raise _fail(source, "CSV must contain an 'id' column")
    if col("priority_score") is None and col("score") is None:
        raise _fail(source, "CSV must contain a 'priority_score' column")
    has_xy = col("x") is not None and col("y") is not None
    has_latlon = (col("longitude") is not None or col("lon") is not None) and (
        col("latitude") is not None or col("lat") is not None
    )
    if not has_xy and not has_latlon:
        raise _fail(source, "CSV must provide either x/y (meters) or longitude/latitude columns")

    records: list[dict[str, Any]] = []
    for row_idx, row in enumerate(reader, start=2):
        if row is None or all((v is None or str(v).strip() == "") for v in row.values()):
            continue
        record: dict[str, Any] = {"__row__": row_idx}
        record["id"] = _as_float(row.get(col("id")), source, f"row {row_idx} 'id'")
        record["priority_score"] = _as_float(
            row.get(col("priority_score") or col("score")), source, f"row {row_idx} 'priority_score'"
        )
        if has_xy:
            record["x"] = _as_float(row.get(col("x")), source, f"row {row_idx} 'x'")
            record["y"] = _as_float(row.get(col("y")), source, f"row {row_idx} 'y'")
        else:
            record["longitude"] = _as_float(
                row.get(col("longitude") or col("lon")), source, f"row {row_idx} 'longitude'"
            )
            record["latitude"] = _as_float(
                row.get(col("latitude") or col("lat")), source, f"row {row_idx} 'latitude'"
            )
        if col("name") is not None and row.get(col("name")):
            record["name"] = row[col("name")]
        if col("elevation") is not None and row.get(col("elevation")):
            record["elevation"] = _as_float(row.get(col("elevation")), source, f"row {row_idx} 'elevation'")
        dwell_col = col("dwell_time") or col("dwell_time_seconds")
        if dwell_col is not None and row.get(dwell_col):
            record["dwell_time"] = _as_float(row.get(dwell_col), source, f"row {row_idx} 'dwell_time'")
        records.append(record)

    if not records:
        raise _fail(source, "CSV contains no target rows")

    projection: dict[str, Any] | None = None
    if not has_xy:
        origin = sidecar.get("origin") if sidecar else None
        if isinstance(origin, dict):
            origin_lat = _as_float(origin.get("latitude"), source, "origin.latitude")
            origin_lon = _as_float(origin.get("longitude"), source, "origin.longitude")
        else:
            origin_lat = float(records[0]["latitude"])
            origin_lon = float(records[0]["longitude"])
        projection = {"crs": "wgs84-equirectangular", "origin_lat": origin_lat, "origin_lon": origin_lon}

    targets: list[TargetNode] = []
    for idx, record in enumerate(records):
        row_idx = record.pop("__row__")
        try:
            targets.append(_target_from_record(record, source, row_idx, projection))
        except ValueError as exc:
            raise _fail(source, f"row {row_idx}: {exc}") from exc

    metadata: dict[str, Any] = {"source_format": "csv"}
    if projection is not None:
        metadata["crs"] = projection["crs"]
        metadata["projection_origin"] = (projection["origin_lat"], projection["origin_lon"])
    else:
        metadata["crs"] = "cartesian-meters"

    name = str(sidecar.get("name", path.stem)) if sidecar else path.stem
    drones = _parse_drones(sidecar, source) if sidecar else []
    wind_speed, wind_dir = _parse_wind(sidecar, source) if sidecar else (None, None)
    return ParsedInstance(
        name=name,
        targets=targets,
        drones=drones,
        wind_speed_mps=wind_speed,
        wind_direction_deg=wind_dir,
        metadata=metadata,
    )


def sidecar_path_for(filepath: str | Path) -> Path:
    """Returns the conventional companion mission JSON path for a CSV target table."""
    path = Path(filepath)
    return path.with_name(f"{path.stem}.meta.json")


# ---------------------------------------------------------------------------
# Chao TOP text parsing
# ---------------------------------------------------------------------------


def parse_chao_txt(
    filepath: str | Path, adapter: ChaoAdapterConfig = DEFAULT_CHAO_ADAPTER
) -> ParsedInstance:
    """Parses a Chao et al. (1996) TOP benchmark text instance.

    Layout::

        N K Tmax
        id x y score
        ... (exactly N node records)

    Node ``0`` (``score == 0``) is the single depot. Adapter assumptions (dwell
    time, elevation, battery, cruise speed) are explicit in
    :class:`ChaoAdapterConfig` rather than hard-coded parser behavior. The source
    route-length budget and fleet size are preserved in the instance metadata.
    """
    path = Path(filepath)
    source = str(path)
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise _fail(source, "file is empty")

    header = lines[0].split()
    if len(header) < 3:
        raise _fail(source, f"header must be 'N K Tmax', got {lines[0]!r}")
    try:
        declared_nodes = int(header[0])
        declared_drones = int(header[1])
        t_max = float(header[2])
    except ValueError as exc:
        raise _fail(source, f"header fields must be numeric: {lines[0]!r}") from exc
    if declared_nodes <= 0:
        raise _fail(source, f"declared node count must be positive, got {declared_nodes}")
    if declared_drones <= 0:
        raise _fail(source, f"declared fleet size must be positive, got {declared_drones}")
    if t_max <= 0:
        raise _fail(source, f"declared route-length budget must be positive, got {t_max}")

    node_lines = lines[1:]
    if len(node_lines) != declared_nodes:
        raise _fail(
            source,
            f"declared {declared_nodes} nodes but found {len(node_lines)} node records",
        )

    nodes: list[TargetNode] = []
    for offset, line in enumerate(node_lines):
        tokens = line.split()
        if len(tokens) < 4:
            raise _fail(source, f"node record {offset + 1} must have 'id x y score', got {line!r}")
        try:
            node_id = int(tokens[0])
            x = float(tokens[1])
            y = float(tokens[2])
            score = float(tokens[3])
        except ValueError as exc:
            raise _fail(source, f"node record {offset + 1} has a non-numeric field: {line!r}") from exc
        is_depot = score == 0.0
        nodes.append(
            TargetNode(
                id=node_id,
                name=f"Depot-{node_id}" if is_depot else f"Target-{node_id}",
                x=x,
                y=y,
                elevation=adapter.depot_elevation_m if is_depot else adapter.target_elevation_m,
                priority_score=score,
                dwell_time=adapter.depot_dwell_time_seconds if is_depot else adapter.target_dwell_time_seconds,
            )
        )

    _validate_unique_target_ids(nodes, source)
    nodes.sort(key=lambda node: node.id)

    depots = [node for node in nodes if node.priority_score == 0.0]
    if len(depots) != 1:
        raise _fail(
            source,
            f"expected exactly one depot (a node with score 0), found {len(depots)}",
        )
    depot_id = depots[0].id

    drones = [
        DroneSpec(
            id=f"UAV-0{i + 1}",
            battery_joules=adapter.battery_joules,
            safety_reserve_ratio=adapter.safety_reserve_ratio,
            max_flight_time=t_max,
            cruise_speed=adapter.cruise_speed_mps,
            launch_depot_id=depot_id,
            recovery_depot_id=depot_id,
        )
        for i in range(declared_drones)
    ]

    return ParsedInstance(
        name=path.stem,
        targets=nodes,
        drones=drones,
        wind_speed_mps=None,
        wind_direction_deg=None,
        metadata={
            "source_format": "chao_txt",
            "crs": "cartesian-meters",
            "declared_node_count": declared_nodes,
            "declared_fleet_size": declared_drones,
            "route_length_budget": t_max,
            "depot_id": depot_id,
            "adapter": {
                "target_dwell_time_seconds": adapter.target_dwell_time_seconds,
                "target_elevation_m": adapter.target_elevation_m,
                "battery_joules": adapter.battery_joules,
                "safety_reserve_ratio": adapter.safety_reserve_ratio,
                "cruise_speed_mps": adapter.cruise_speed_mps,
            },
        },
    )


# ---------------------------------------------------------------------------
# Dispatch and context building
# ---------------------------------------------------------------------------


def parse_instance_file(filepath: str | Path, adapter: ChaoAdapterConfig = DEFAULT_CHAO_ADAPTER) -> ParsedInstance:
    """Dispatches to the parser matching the file suffix.

    Raises ``ValueError`` listing supported suffixes for unknown formats.
    """
    path = Path(filepath)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"Unsupported file format {suffix!r} for {path}; supported types: "
            + ", ".join(SUPPORTED_SUFFIXES)
        )
    if not path.exists():
        raise FileNotFoundError(f"Instance file not found: {path}")

    if suffix in (".json", ".geojson"):
        return parse_json_mission(path)
    if suffix == ".txt":
        return parse_chao_txt(path, adapter=adapter)

    sidecar_path = sidecar_path_for(path)
    sidecar: dict[str, Any] | None = None
    if sidecar_path.exists():
        try:
            raw = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise _fail(str(sidecar_path), f"invalid JSON at line {exc.lineno} column {exc.colno}") from exc
        sidecar = _require_mapping(raw, str(sidecar_path), "top-level document")
    return parse_csv_targets(path, sidecar)


def _rescale_fleet(drones: list[DroneSpec], num_drones: int, source: str) -> list[DroneSpec]:
    """Clones the first drone spec ``num_drones`` times, preserving its physical parameters."""
    if num_drones <= 0:
        raise _fail(source, f"num_drones must be positive, got {num_drones}")
    base = drones[0]
    return [
        DroneSpec(
            id=f"UAV-{i + 1:02d}",
            battery_joules=base.battery_joules,
            safety_reserve_ratio=base.safety_reserve_ratio,
            max_flight_time=base.max_flight_time,
            cruise_speed=base.cruise_speed,
            launch_depot_id=base.launch_depot_id,
            recovery_depot_id=base.recovery_depot_id,
            model=base.model,
        )
        for i in range(num_drones)
    ]


def enforce_matrix_invariants(
    time_matrix: np.ndarray,
    energy_matrix: np.ndarray,
    node_count: int,
    source: str = "<matrices>",
) -> None:
    """Raises ``ValueError`` if the cost matrices break the Person 3 contract."""
    for label, matrix in (("time_matrix", time_matrix), ("energy_matrix", energy_matrix)):
        if matrix.shape != (node_count, node_count):
            raise _fail(source, f"{label} shape {matrix.shape} does not match {node_count} nodes")
        if matrix.dtype != np.float64:
            raise _fail(source, f"{label} dtype must be float64, got {matrix.dtype}")
        if not matrix.flags["C_CONTIGUOUS"]:
            raise _fail(source, f"{label} must be C-contiguous")
        if not np.all(np.isfinite(np.diag(matrix))):
            raise _fail(source, f"{label} diagonal must be finite")
        if not np.all(np.diag(matrix) == 0.0):
            raise _fail(source, f"{label} diagonal must be zero")
    reachable = np.isfinite(time_matrix)
    if not np.array_equal(reachable, np.isfinite(energy_matrix)):
        raise _fail(source, "time_matrix and energy_matrix disagree on unreachable arcs")


def build_instance_context(
    filepath: str | Path,
    wind_speed_mps: float | None = None,
    wind_dir_deg: float | None = None,
    num_drones: int | None = None,
    aero_params: DroneAeroParams | None = None,
    adapter: ChaoAdapterConfig = DEFAULT_CHAO_ADAPTER,
) -> InstanceContext:
    """Parses an instance file, computes wind-corrected cost matrices, and returns a context.

    Wind override semantics: ``None`` (the default) uses the wind declared in the
    file; supplying either value - including ``0.0`` - overrides it. If only one
    component is supplied, the other defaults to ``0.0``.

    Cost matrices describe transit at a single cruise airspeed
    (``drones[0].cruise_speed``). Heterogeneous fleets are permitted by
    :func:`validate_fleet`, but per-drone matrices are not built; callers with
    heterogeneous ``cruise_speed`` values must not treat the shared matrices as
    exact for drones other than ``drones[0]``. The airspeed used is recorded in
    ``InstanceContext.metadata["cruise_speed_mps"]``.

    CRS/projection provenance from parsing (``crs``, ``projection_origin``) is
    propagated into ``InstanceContext.metadata``.
    """
    path = Path(filepath)
    source = str(path)
    parsed = parse_instance_file(path, adapter=adapter)

    if wind_speed_mps is None and wind_dir_deg is None:
        wind_speed = parsed.wind_speed_mps if parsed.wind_speed_mps is not None else 0.0
        wind_dir = parsed.wind_direction_deg if parsed.wind_direction_deg is not None else 0.0
    else:
        wind_speed = float(wind_speed_mps) if wind_speed_mps is not None else 0.0
        wind_dir = float(wind_dir_deg) if wind_dir_deg is not None else 0.0
    if wind_speed < 0:
        raise _fail(source, f"wind_speed_mps must be non-negative, got {wind_speed}")

    if not parsed.targets:
        raise _fail(source, "instance contains no targets")
    _validate_unique_target_ids(parsed.targets, source)

    drones = parsed.drones
    if num_drones is not None:
        if not drones:
            raise _fail(source, "num_drones override requires a parsed fleet or Chao fleet size")
        if len(drones) != num_drones:
            drones = _rescale_fleet(drones, num_drones, source)
    if not drones:
        raise _fail(
            source,
            "no fleet defined; provide a 'drones' list in the mission file or a companion "
            f"'{sidecar_path_for(path).name}' sidecar for a CSV",
        )
    validate_fleet(drones, parsed.targets, source)

    coords = np.array([[t.x, t.y] for t in parsed.targets], dtype=np.float64)
    cruise_speed = drones[0].cruise_speed
    time_mat, energy_mat = compute_cost_matrices(
        coords,
        wind_speed_mps=wind_speed,
        wind_direction_deg=wind_dir,
        cruise_speed_mps=cruise_speed,
        params=aero_params,
    )
    enforce_matrix_invariants(time_mat, energy_mat, len(parsed.targets), source)

    parsed.metadata["wind_speed_mps"] = wind_speed
    parsed.metadata["wind_direction_deg"] = wind_dir
    parsed.metadata["cruise_speed_mps"] = cruise_speed

    return InstanceContext(
        instance_name=parsed.name,
        targets=parsed.targets,
        drones=drones,
        time_matrix=time_mat,
        energy_matrix=energy_mat,
        ambient_wind=(wind_speed, math.radians(wind_dir)),
        metadata=dict(parsed.metadata),
    )
