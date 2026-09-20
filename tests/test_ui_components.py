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


def test_tactical_map_underlay_generation():
    """Verify build_mission_map_figure incorporates tactical map image underlay."""
    from app.visualizer import build_mission_map_figure, get_tactical_map_data_uri

    uri = get_tactical_map_data_uri()
    assert uri is not None, "Tactical map asset must be present and encoded as base64 data URI"
    assert uri.startswith("data:image/jpeg;base64,")

    inst = create_mock_instance(num_targets=20, num_drones=3)
    path = Path("tests/mock_schedule.json")
    with open(path, "r", encoding="utf-8") as f:
        schedule = FleetSchedule.from_dict(json.load(f))

    fig = build_mission_map_figure(inst, schedule, use_tactical_map=True)
    assert fig.layout.images is not None
    # 1 underlay map + 1 drone SVG icon per fleet UAV (all rendered above the map)
    underlays = [im for im in fig.layout.images if im.layer == "below"]
    assert len(underlays) == 1, "exactly one tactical map underlay expected"
    assert underlays[0].sizing == "stretch"
    drone_icons = [im for im in fig.layout.images if im.layer == "above"]
    assert len(drone_icons) == len(inst.drones), (
        "one drone SVG icon per fleet UAV expected"
    )


def test_drone_svg_icon_geometry_and_rotation():
    """Verify the quadcopter icon builder emits a valid rotated SVG data URI."""
    import base64

    from app.visualizer import create_drone_quadcopter_icon

    uri, w, h = create_drone_quadcopter_icon(0.0, 0.0, heading_deg=90.0)
    assert uri.startswith("data:image/svg+xml;base64,")
    assert w == h and w > 0

    payload = base64.b64decode(uri.split(",", 1)[1]).decode("utf-8")
    assert "rotate(90" in payload, "icon must be pre-rotated by compass heading"
    assert "ellipse" in payload, "quadcopter silhouette must include rotor ellipses"


def test_uavs_render_drone_svg_icons_on_map():
    """Verify every fleet UAV renders exactly one heading-rotated drone SVG icon."""
    import base64

    from app.visualizer import build_mission_map_figure

    inst = create_mock_instance(num_targets=20, num_drones=3)
    path = Path("tests/mock_schedule.json")
    with open(path, "r", encoding="utf-8") as f:
        schedule = FleetSchedule.from_dict(json.load(f))

    for t in (0.0, 300.0, 1200.0):
        fig = build_mission_map_figure(inst, schedule, current_time_sec=t)
        svg_icons = [
            img.source
            for img in fig.layout.images
            if img.source.startswith("data:image/svg+xml;base64,")
        ]
        assert len(svg_icons) == 3, (
            f"expected one quadcopter SVG icon per UAV at t={t}, got {len(svg_icons)}"
        )
        rotations = [
            base64.b64decode(s.split(",", 1)[1]).decode("utf-8") for s in svg_icons
        ]
        assert all("rotate(" in p for p in rotations), (
            "icons must carry live heading rotation"
        )

