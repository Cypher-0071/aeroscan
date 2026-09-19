"""Unit tests for instance loader, coordinate projection, and format parsers."""

from pathlib import Path

import pytest

from core.instance import (
    build_instance_context,
    latlon_to_cartesian_meters,
)


def test_latlon_to_cartesian_projection():
    """Verify equirectangular coordinate projection accuracy."""
    origin_lat, origin_lon = 37.7749, -122.4194
    # 0 offset
    x0, y0 = latlon_to_cartesian_meters(origin_lat, origin_lon, origin_lat, origin_lon)
    assert x0 == pytest.approx(0.0, abs=1e-3)
    assert y0 == pytest.approx(0.0, abs=1e-3)

    # 0.01 degree North (~1111 meters)
    x_north, y_north = latlon_to_cartesian_meters(origin_lat + 0.01, origin_lon, origin_lat, origin_lon)
    assert y_north == pytest.approx(1111.0, abs=25.0)


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


def test_parse_chao_instance_txt():
    """Verify parsing Chao benchmark text format."""
    path = Path("data/chao_instances/set_64_1.txt")
    if not path.exists():
        pytest.skip("data/chao_instances/set_64_1.txt not found")

    inst = build_instance_context(path, wind_speed_mps=2.0, wind_dir_deg=30.0)
    assert len(inst.targets) == 64
    assert len(inst.drones) == 3
    assert inst.time_matrix.shape == (64, 64)
    assert inst.targets[0].priority_score == 0.0  # Depot
    assert inst.targets[1].priority_score > 0.0   # Target


def test_non_contiguous_node_ids_and_lookups():
    """Verify InstanceContext properly maps arbitrary non-0-indexed node IDs to cost matrix indices."""
    import numpy as np

    from core.contracts import DroneSpec, InstanceContext, TargetNode
    from core.operators import evaluate_route_trajectory

    targets = [
        TargetNode(id=100, name="BaseCamp", x=0.0, y=0.0, elevation=0.0, priority_score=0.0, dwell_time=0.0),
        TargetNode(id=205, name="Victim-1", x=100.0, y=100.0, elevation=10.0, priority_score=50.0, dwell_time=30.0),
        TargetNode(id=309, name="Victim-2", x=200.0, y=200.0, elevation=10.0, priority_score=60.0, dwell_time=30.0),
    ]
    drone = DroneSpec(
        id="UAV-01",
        battery_joules=360000.0,
        max_flight_time=2400.0,
        launch_depot_id=100,
        recovery_depot_id=100,
    )
    time_mat = np.array([
        [0.0, 10.0, 20.0],
        [10.0, 0.0, 15.0],
        [20.0, 15.0, 0.0],
    ])
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
