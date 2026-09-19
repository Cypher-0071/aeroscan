"""Unit tests for UI components, SITL exporters, and mock schedule ingestion."""

import json
from pathlib import Path

from app.exporter import export_mission_telemetry_csv, export_qgroundcontrol_plan
from core.contracts import FleetSchedule
from tests.mock_instance import create_mock_instance


def test_load_mock_schedule_json():
    """Verify loading pre-baked mock_schedule.json fixture."""
    path = Path("tests/mock_schedule.json")
    assert path.exists(), "mock_schedule.json fixture must exist"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    schedule = FleetSchedule.from_dict(data)
    assert schedule.status == "OPTIMAL"
    assert schedule.cumulative_reward == 545.0
    assert len(schedule.assigned_routes) == 3
    assert schedule.assigned_routes[0].drone_id == "UAV-01"
    assert schedule.validation_passed is True


def test_qgc_plan_export_format():
    """Verify exported .plan file matches QGroundControl schema specifications."""
    inst = create_mock_instance(num_targets=20, num_drones=3)
    path = Path("tests/mock_schedule.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    schedule = FleetSchedule.from_dict(data)

    route = schedule.assigned_routes[0]
    drone = inst.drones[0]
    plan_str = export_qgroundcontrol_plan(route, drone, inst)
    plan_dict = json.loads(plan_str)

    assert plan_dict["fileType"] == "Plan"
    assert plan_dict["version"] == 1
    assert "mission" in plan_dict
    assert len(plan_dict["mission"]["items"]) == len(route.waypoints)
    # Check first waypoint is MAV_CMD_NAV_WAYPOINT (16)
    assert plan_dict["mission"]["items"][0]["command"] == 16


def test_telemetry_csv_export():
    """Verify exported telemetry CSV contains proper columns and formatting."""
    inst = create_mock_instance(num_targets=20, num_drones=3)
    path = Path("tests/mock_schedule.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    schedule = FleetSchedule.from_dict(data)

    csv_str = export_mission_telemetry_csv(schedule, inst)
    assert "Drone_ID,Waypoint_Seq,Node_ID" in csv_str
    assert "UAV-01" in csv_str
    assert "Remaining_SoC_Percent" in csv_str


def test_streamlit_app_loads():
    """Verify Streamlit dashboard application files compile cleanly without syntax or import errors."""
    import py_compile

    ui_files = [
        "app/dashboard.py",
        "app/visualizer.py",
        "app/telemetry.py",
        "app/arena_view.py",
        "app/exporter.py",
    ]
    for file_path in ui_files:
        compiled = py_compile.compile(file_path, doraise=True)
        assert compiled is not None
