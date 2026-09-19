"""Unit tests for real-time telemetry simulator and kinematic interpolation."""

import pytest

from app.telemetry import (
    compute_battery_curves,
    interpolate_drone_state,
)
from core.contracts import CandidateRoute, FleetSchedule, WaypointVisit
from tests.mock_instance import create_mock_instance


@pytest.fixture
def mock_inst():
    return create_mock_instance(num_targets=20, num_drones=3)


def test_telemetry_interpolation_transit(mock_inst):
    """Verify linear coordinate interpolation when drone is in forward cruise."""
    drone = mock_inst.drones[0]
    route = CandidateRoute(
        drone_id=drone.id,
        target_ids=[1],
        waypoints=[
            WaypointVisit(node_id=0, arrival_time=0.0, departure_time=0.0, energy_consumed=0.0, remaining_battery_percent=100.0),
            WaypointVisit(node_id=1, arrival_time=100.0, departure_time=130.0, energy_consumed=20000.0, remaining_battery_percent=94.0),
            WaypointVisit(node_id=0, arrival_time=230.0, departure_time=230.0, energy_consumed=40000.0, remaining_battery_percent=88.0),
        ],
        total_reward=25.0,
        total_flight_time=230.0,
        total_energy_joules=40000.0,
    )

    node0 = mock_inst.targets[0]
    node1 = mock_inst.targets[1]

    # At t = 50s (midpoint of leg 0 -> 1)
    state = interpolate_drone_state(route, 50.0, mock_inst, drone)
    assert state["x"] == pytest.approx(0.5 * (node0.x + node1.x), abs=1.0)
    assert state["y"] == pytest.approx(0.5 * (node0.y + node1.y), abs=1.0)
    assert "CRUISE" in state["status"]
    assert state["speed_mps"] == drone.cruise_speed
    assert state["battery_percent"] == pytest.approx(97.0, abs=0.5)


def test_telemetry_interpolation_hover(mock_inst):
    """Verify hovering inspection state and 0 m/s groundspeed during dwell time."""
    drone = mock_inst.drones[0]
    route = CandidateRoute(
        drone_id=drone.id,
        target_ids=[1],
        waypoints=[
            WaypointVisit(node_id=0, arrival_time=0.0, departure_time=0.0, energy_consumed=0.0, remaining_battery_percent=100.0),
            WaypointVisit(node_id=1, arrival_time=100.0, departure_time=130.0, energy_consumed=20000.0, remaining_battery_percent=94.0),
            WaypointVisit(node_id=0, arrival_time=230.0, departure_time=230.0, energy_consumed=40000.0, remaining_battery_percent=88.0),
        ],
        total_reward=25.0,
        total_flight_time=230.0,
        total_energy_joules=40000.0,
    )

    # At t = 115s (inside dwell window [100, 130])
    state = interpolate_drone_state(route, 115.0, mock_inst, drone)
    node1 = mock_inst.targets[1]
    assert state["x"] == pytest.approx(node1.x, abs=1e-3)
    assert state["y"] == pytest.approx(node1.y, abs=1e-3)
    assert "HOVER_INSPECTION" in state["status"]
    assert state["speed_mps"] == 0.0


def test_battery_curves_computation(mock_inst):
    """Verify compute_battery_curves returns non-empty dataframe with monotonic decline."""
    drone = mock_inst.drones[0]
    route = CandidateRoute(
        drone_id=drone.id,
        target_ids=[1],
        waypoints=[
            WaypointVisit(node_id=0, arrival_time=0.0, departure_time=0.0, energy_consumed=0.0, remaining_battery_percent=100.0),
            WaypointVisit(node_id=1, arrival_time=100.0, departure_time=130.0, energy_consumed=20000.0, remaining_battery_percent=94.0),
            WaypointVisit(node_id=0, arrival_time=230.0, departure_time=230.0, energy_consumed=40000.0, remaining_battery_percent=88.0),
        ],
        total_reward=25.0,
        total_flight_time=230.0,
        total_energy_joules=40000.0,
    )
    sched = FleetSchedule(
        status="OPTIMAL",
        solve_time_seconds=0.1,
        cumulative_reward=25.0,
        assigned_routes=[route],
        unassigned_targets=[],
        validation_passed=True,
    )
    df = compute_battery_curves(sched, mock_inst, num_points=25)
    assert len(df) == 25
    assert f"{drone.id} SoC (%)" in df.columns
    # Check that battery declines monotonically
    soc_vals = df[f"{drone.id} SoC (%)"].values
    assert soc_vals[0] >= soc_vals[-1]
