"""Unit tests for instance loader, coordinate projection, and format parsers."""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from core.instance import (
    build_instance_context,
    enforce_matrix_invariants,
    latlon_to_cartesian_meters,
    parse_chao_txt,
    parse_instance_file,
    sidecar_path_for,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _write_mission(tmp_path: Path, payload: dict, name: str = "mission.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _minimal_mission() -> dict:
    return {
        "name": "tmp_mission",
        "drones": [
            {
                "id": "UAV-01",
                "battery_joules": 360000.0,
                "max_flight_time_seconds": 2400.0,
                "cruise_speed_mps": 14.5,
                "launch_depot_id": 0,
                "recovery_depot_id": 0,
            }
        ],
        "targets": [
            {"id": 0, "x": 0.0, "y": 0.0, "priority_score": 0.0, "dwell_time": 0.0},
            {"id": 1, "x": 100.0, "y": 0.0, "priority_score": 10.0, "dwell_time": 30.0},
        ],
    }


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


def test_latlon_to_cartesian_projection():
    """Verify equirectangular coordinate projection accuracy."""
    origin_lat, origin_lon = 37.7749, -122.4194
    # 0 offset
    x0, y0 = latlon_to_cartesian_meters(origin_lat, origin_lon, origin_lat, origin_lon)
    assert x0 == pytest.approx(0.0, abs=1e-3)
    assert y0 == pytest.approx(0.0, abs=1e-3)

    # 0.01 degree North (~1111 meters)
    x_north, y_north = latlon_to_cartesian_meters(
        origin_lat + 0.01, origin_lon, origin_lat, origin_lon
    )
    assert x_north == pytest.approx(0.0, abs=1e-6)
    assert y_north == pytest.approx(1111.0, abs=25.0)

    # 0.01 degree East (~882 meters at this latitude), with no northward offset
    x_east, y_east = latlon_to_cartesian_meters(
        origin_lat, origin_lon + 0.01, origin_lat, origin_lon
    )
    assert x_east == pytest.approx(879.0, abs=25.0)
    assert y_east == pytest.approx(0.0, abs=1e-6)
    assert x_east > 0.0


# ---------------------------------------------------------------------------
# JSON / GeoJSON
# ---------------------------------------------------------------------------


def test_parse_sample_mission_json():
    """Verify parsing the real-world Mountain SAR sample mission."""
    path = Path("data/sample_mission.json")
    if not path.exists():
        pytest.skip("data/sample_mission.json not found")

    inst = build_instance_context(path)
    assert inst.instance_name == "SAR_Cascade_Mountain_05"
    assert len(inst.targets) == 20
    assert len(inst.drones) == 3
    assert inst.time_matrix.shape == (20, 20)
    assert inst.energy_matrix.shape == (20, 20)
    assert inst.drones[0].battery_joules == 360000.0
    # File wind is used when no override is supplied.
    assert inst.ambient_wind[0] == pytest.approx(4.5)
    assert inst.ambient_wind[1] == pytest.approx(math.radians(55.0))
    assert inst.time_matrix[0, 1] != inst.time_matrix[1, 0]


def test_cartesian_mission_with_arbitrary_ids():
    """Cartesian fixture keeps declaration order and non-contiguous IDs."""
    inst = build_instance_context(FIXTURES / "cartesian_mission.json")
    assert inst.instance_name == "fixture_cartesian_mission"
    assert [t.id for t in inst.targets] == [100, 205, 309, 410]
    assert inst.id_to_index[100] == 0
    assert inst.id_to_index[410] == 3
    assert inst.get_transit_time(100, 205) == pytest.approx(500.0 / 20.5, rel=1e-6)
    assert inst.get_transit_time(205, 100) == pytest.approx(500.0 / 8.5, rel=1e-6)
    # Zero-valued scores/dwell times are preserved exactly.
    assert inst.get_node(100).priority_score == 0.0
    assert inst.get_node(309).dwell_time == 0.0


def test_geojson_wgs84_projection_fixture():
    """GeoJSON features are projected with a single origin and directional offsets."""
    inst = build_instance_context(FIXTURES / "wgs84_mission.geojson")
    assert inst.instance_name == "fixture_wgs84_mission"
    assert [t.id for t in inst.targets] == [0, 1, 2]
    depot, north, east = inst.targets
    assert (depot.x, depot.y) == pytest.approx((0.0, 0.0), abs=1e-6)
    assert north.y == pytest.approx(111.2, abs=1.0)
    assert north.x == pytest.approx(0.0, abs=1e-6)
    assert east.x == pytest.approx(879.0, abs=2.0)
    assert east.y == pytest.approx(0.0, abs=1.0)
    assert len(inst.drones) == 1


def test_geojson_direction_from_degrees_is_converted():
    """A meteorological 'from' bearing is converted to the moving-towards convention."""
    inst = build_instance_context(FIXTURES / "wgs84_mission.geojson")
    speed, direction_rad = inst.ambient_wind
    assert speed == pytest.approx(3.0)
    assert direction_rad == pytest.approx(math.radians(270.0))  # 90 from -> 270 towards


def test_geojson_rejects_non_point_geometry(tmp_path):
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[0.0, 0.0], [1.0, 1.0]]},
                "properties": {"id": 0},
            }
        ],
    }
    path = _write_mission(tmp_path, payload, "bad.geojson")
    with pytest.raises(ValueError, match="Point"):
        build_instance_context(path)


def test_malformed_json_reports_location(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text('{"targets": [ }', encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON at line"):
        build_instance_context(path)


def test_duplicate_target_ids_rejected(tmp_path):
    payload = _minimal_mission()
    payload["targets"][1]["id"] = 0
    path = _write_mission(tmp_path, payload)
    with pytest.raises(ValueError, match="duplicate node id"):
        build_instance_context(path)


def test_target_missing_coordinates_rejected(tmp_path):
    payload = _minimal_mission()
    del payload["targets"][1]["x"]
    del payload["targets"][1]["y"]
    path = _write_mission(tmp_path, payload)
    with pytest.raises(ValueError, match="x/y"):
        build_instance_context(path)


def test_target_mixing_coordinate_systems_rejected(tmp_path):
    payload = _minimal_mission()
    payload["targets"][1]["longitude"] = -122.4
    payload["targets"][1]["latitude"] = 37.7
    path = _write_mission(tmp_path, payload)
    with pytest.raises(ValueError, match="both x/y and longitude/latitude"):
        build_instance_context(path)


def test_ambiguous_wind_direction_rejected(tmp_path):
    payload = _minimal_mission()
    payload["ambient_wind"] = {
        "speed_mps": 2.0,
        "direction_degrees": 30.0,
        "direction_from_degrees": 10.0,
    }
    path = _write_mission(tmp_path, payload)
    with pytest.raises(ValueError, match="direction_degrees"):
        build_instance_context(path)


# ---------------------------------------------------------------------------
# Fleet validation
# ---------------------------------------------------------------------------


def test_missing_fleet_is_actionable(tmp_path):
    payload = _minimal_mission()
    del payload["drones"]
    path = _write_mission(tmp_path, payload)
    with pytest.raises(ValueError, match="no fleet defined"):
        build_instance_context(path)


def test_unknown_depot_id_rejected(tmp_path):
    payload = _minimal_mission()
    payload["drones"][0]["launch_depot_id"] = 99
    path = _write_mission(tmp_path, payload)
    with pytest.raises(ValueError, match="launch_depot_id 99 not found"):
        build_instance_context(path)


@pytest.mark.parametrize(
    "override, match",
    [
        ({"battery_joules": 0.0}, "battery_joules must be positive"),
        ({"max_flight_time_seconds": -1.0}, "max_flight_time must be positive"),
        ({"cruise_speed_mps": 0.0}, "cruise_speed must be positive"),
        ({"safety_reserve_ratio": 1.5}, "safety_reserve_ratio"),
    ],
)
def test_bad_drone_specs_rejected(tmp_path, override, match):
    payload = _minimal_mission()
    payload["drones"][0].update(override)
    path = _write_mission(tmp_path, payload)
    with pytest.raises(ValueError, match=match):
        build_instance_context(path)


def test_duplicate_drone_ids_rejected(tmp_path):
    payload = _minimal_mission()
    payload["drones"].append(dict(payload["drones"][0]))
    path = _write_mission(tmp_path, payload)
    with pytest.raises(ValueError, match="duplicate drone id"):
        build_instance_context(path)


def test_num_drones_override_rescales_fleet(tmp_path):
    path = _write_mission(tmp_path, _minimal_mission())
    inst = build_instance_context(path, num_drones=4)
    assert len(inst.drones) == 4
    assert [d.id for d in inst.drones] == ["UAV-01", "UAV-02", "UAV-03", "UAV-04"]
    assert all(d.battery_joules == 360000.0 for d in inst.drones)


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def test_csv_mission_with_sidecar():
    inst = build_instance_context(FIXTURES / "targets.csv")
    assert inst.instance_name == "fixture_csv_mission"
    assert len(inst.targets) == 4
    assert len(inst.drones) == 1
    assert [t.id for t in inst.targets] == [0, 1, 2, 3]
    assert inst.get_node(1).priority_score == pytest.approx(75.0)
    # A zero priority score is retained exactly, not dropped or defaulted.
    assert inst.get_node(3).priority_score == 0.0
    assert inst.get_node(1).dwell_time == pytest.approx(30.0)
    assert inst.ambient_wind[0] == pytest.approx(2.5)


def test_csv_without_sidecar_reports_missing_fleet(tmp_path):
    csv_path = tmp_path / "orphan.csv"
    csv_path.write_text(
        "id,name,x,y,priority_score\n0,Depot,0.0,0.0,0.0\n1,T1,10.0,10.0,5.0\n", encoding="utf-8"
    )
    assert sidecar_path_for(csv_path).name == "orphan.meta.json"
    with pytest.raises(ValueError, match="no fleet defined"):
        build_instance_context(csv_path)


def test_csv_requires_coordinate_columns(tmp_path):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("id,name,priority_score\n0,Depot,0.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="x/y"):
        build_instance_context(csv_path)


def test_csv_reports_row_for_bad_number(tmp_path):
    csv_path = tmp_path / "badnum.csv"
    csv_path.write_text(
        "id,x,y,priority_score\n0,0.0,0.0,0.0\n1,not-a-number,10.0,5.0\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="row 3"):
        parse_instance_file(csv_path)


# ---------------------------------------------------------------------------
# Wind override semantics
# ---------------------------------------------------------------------------


def test_file_wind_used_when_not_overridden():
    inst = build_instance_context(FIXTURES / "cartesian_mission.json")
    assert inst.ambient_wind[0] == pytest.approx(6.0)
    assert inst.time_matrix[0, 1] < inst.time_matrix[1, 0]


def test_explicit_zero_wind_overrides_file_wind():
    """0.0 is an intentional override, not a missing value."""
    inst = build_instance_context(
        FIXTURES / "cartesian_mission.json", wind_speed_mps=0.0, wind_dir_deg=0.0
    )
    assert inst.ambient_wind == (0.0, 0.0)
    assert np.allclose(inst.time_matrix, inst.time_matrix.T)
    assert np.allclose(inst.energy_matrix, inst.energy_matrix.T)


def test_partial_wind_override_defaults_other_component():
    inst = build_instance_context(FIXTURES / "cartesian_mission.json", wind_speed_mps=0.0)
    assert inst.ambient_wind == (0.0, 0.0)


def test_direction_override_is_applied():
    inst = build_instance_context(
        FIXTURES / "cartesian_mission.json", wind_speed_mps=6.0, wind_dir_deg=180.0
    )
    assert inst.ambient_wind == pytest.approx((6.0, math.pi))
    # Now the +x leg is a headwind instead of a tailwind.
    assert inst.time_matrix[0, 1] > inst.time_matrix[1, 0]


# ---------------------------------------------------------------------------
# Chao text format
# ---------------------------------------------------------------------------


def test_parse_tiny_chao_fixture():
    parsed = parse_chao_txt(FIXTURES / "tiny_chao.txt")
    assert parsed.metadata["declared_node_count"] == 5
    assert parsed.metadata["declared_fleet_size"] == 2
    assert parsed.metadata["route_length_budget"] == pytest.approx(600.0)
    assert parsed.metadata["depot_id"] == 0
    assert len(parsed.drones) == 2
    assert all(d.max_flight_time == pytest.approx(600.0) for d in parsed.drones)

    inst = build_instance_context(FIXTURES / "tiny_chao.txt")
    assert len(inst.targets) == 5
    assert inst.targets[0].priority_score == 0.0
    assert inst.get_node(4).priority_score == pytest.approx(40.0)


def test_parse_chao_instance_txt():
    """Verify parsing the checked-in Chao benchmark text fixture."""
    path = Path("data/chao_instances/set_64_1.txt")
    if not path.exists():
        pytest.skip("data/chao_instances/set_64_1.txt not found")

    inst = build_instance_context(path, wind_speed_mps=2.0, wind_dir_deg=30.0)
    assert len(inst.targets) == 64
    assert len(inst.drones) == 3
    assert inst.time_matrix.shape == (64, 64)
    assert inst.targets[0].priority_score == 0.0  # Depot
    assert inst.targets[1].priority_score > 0.0  # Target


def test_chao_declared_count_mismatch(tmp_path):
    path = tmp_path / "mismatch.txt"
    path.write_text("5 2 600.0\n0 0.0 0.0 0.0\n1 1.0 1.0 5.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="declared 5 nodes but found 2"):
        parse_chao_txt(path)


def test_chao_duplicate_ids_rejected(tmp_path):
    path = tmp_path / "dup.txt"
    path.write_text("3 1 600.0\n0 0.0 0.0 0.0\n1 1.0 1.0 5.0\n1 2.0 2.0 6.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate node id"):
        parse_chao_txt(path)


def test_chao_multiple_depots_rejected(tmp_path):
    path = tmp_path / "twodepots.txt"
    path.write_text("3 1 600.0\n0 0.0 0.0 0.0\n1 1.0 1.0 0.0\n2 2.0 2.0 6.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one depot"):
        parse_chao_txt(path)


def test_chao_no_depot_rejected(tmp_path):
    path = tmp_path / "nodepot.txt"
    path.write_text("2 1 600.0\n1 1.0 1.0 5.0\n2 2.0 2.0 6.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one depot"):
        parse_chao_txt(path)


def test_chao_bad_header_rejected(tmp_path):
    path = tmp_path / "badheader.txt"
    path.write_text("N K Tmax\n0 0.0 0.0 0.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        parse_chao_txt(path)


def test_chao_short_node_record_rejected(tmp_path):
    path = tmp_path / "short.txt"
    path.write_text("2 1 600.0\n0 0.0 0.0\n1 1.0 1.0 5.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="node record"):
        parse_chao_txt(path)


# ---------------------------------------------------------------------------
# Dispatcher and matrix invariants
# ---------------------------------------------------------------------------


def test_unknown_suffix_lists_supported_types(tmp_path):
    path = tmp_path / "mission.yaml"
    path.write_text("targets: []", encoding="utf-8")
    with pytest.raises(ValueError, match=r"\.json, \.geojson, \.csv, \.txt"):
        build_instance_context(path)


def test_missing_file_reports_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_instance_context(tmp_path / "nope.json")


def test_context_matrix_invariants():
    inst = build_instance_context(FIXTURES / "cartesian_mission.json")
    enforce_matrix_invariants(inst.time_matrix, inst.energy_matrix, len(inst.targets))
    assert inst.time_matrix.dtype == np.float64
    assert inst.energy_matrix.flags["C_CONTIGUOUS"]
    assert np.all(np.diag(inst.time_matrix) == 0.0)


def test_enforce_matrix_invariants_rejects_bad_shapes():
    good = np.zeros((2, 2), dtype=np.float64)
    with pytest.raises(ValueError, match="shape"):
        enforce_matrix_invariants(np.zeros((3, 3)), np.zeros((3, 3)), 2)
    with pytest.raises(ValueError, match="float64"):
        enforce_matrix_invariants(np.zeros((2, 2), dtype=np.float32), good, 2)
    with pytest.raises(ValueError, match="C-contiguous"):
        enforce_matrix_invariants(np.asfortranarray(good), good, 2)
    with pytest.raises(ValueError, match="diagonal"):
        enforce_matrix_invariants(np.ones((2, 2)), good, 2)
    with pytest.raises(ValueError, match="disagree on unreachable"):
        bad_energy = good.copy()
        bad_energy[0, 1] = np.inf
        enforce_matrix_invariants(good, bad_energy, 2)


def test_non_contiguous_node_ids_and_lookups():
    """Verify InstanceContext properly maps arbitrary non-0-indexed node IDs to cost matrix indices."""
    from core.contracts import DroneSpec, InstanceContext, TargetNode
    from core.operators import evaluate_route_trajectory

    targets = [
        TargetNode(
            id=100, name="BaseCamp", x=0.0, y=0.0, elevation=0.0, priority_score=0.0, dwell_time=0.0
        ),
        TargetNode(
            id=205,
            name="Victim-1",
            x=100.0,
            y=100.0,
            elevation=10.0,
            priority_score=50.0,
            dwell_time=30.0,
        ),
        TargetNode(
            id=309,
            name="Victim-2",
            x=200.0,
            y=200.0,
            elevation=10.0,
            priority_score=60.0,
            dwell_time=30.0,
        ),
    ]
    drone = DroneSpec(
        id="UAV-01",
        battery_joules=360000.0,
        max_flight_time=2400.0,
        launch_depot_id=100,
        recovery_depot_id=100,
    )
    time_mat = np.array(
        [
            [0.0, 10.0, 20.0],
            [10.0, 0.0, 15.0],
            [20.0, 15.0, 0.0],
        ]
    )
    energy_mat = time_mat * 150.0

    inst = InstanceContext(
        instance_name="arbitrary_ids",
        targets=targets,
        drones=[drone],
        time_matrix=time_mat,
        energy_matrix=energy_mat,
    )

    # 1. Fast O(1) node lookup
    assert inst.get_node(100) == targets[0]
    assert inst.get_node(205) == targets[1]
    assert inst.get_node(999) is None

    # 2. Safe transit time & energy lookup
    assert inst.get_transit_time(100, 205) == 10.0
    assert inst.get_transit_time(205, 309) == 15.0
    assert inst.get_transit_energy(100, 309) == 3000.0

    # 3. Feasible evaluation of trajectory with non-contiguous IDs
    route = evaluate_route_trajectory([205, 309], drone, inst)
    assert route is not None
    assert route.target_ids == [205, 309]
    assert len(route.waypoints) == 4
    assert route.waypoints[0].node_id == 100
    assert route.waypoints[-1].node_id == 100
