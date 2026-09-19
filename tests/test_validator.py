"""Unit tests for independent constraint validator and violation detector."""

import pytest

from core.contracts import CandidateRoute, FleetSchedule, WaypointVisit
from core.validator import ScheduleValidationError, audit_fleet_schedule, validate_fleet_schedule
from tests.mock_instance import create_mock_instance


@pytest.fixture
def mock_inst():
    return create_mock_instance(num_targets=20, num_drones=3)


def test_validator_passes_on_valid_schedule(mock_inst):
    """Verify validator passes on a clean, valid schedule."""
    drone = mock_inst.drones[0]
    valid_route = CandidateRoute(
        drone_id=drone.id,
        target_ids=[1, 2],
        waypoints=[
            WaypointVisit(node_id=0, arrival_time=0.0, departure_time=0.0, energy_consumed=0.0, remaining_battery_percent=100.0),
            WaypointVisit(node_id=1, arrival_time=50.0, departure_time=80.0, energy_consumed=20000.0, remaining_battery_percent=94.4),
            WaypointVisit(node_id=2, arrival_time=120.0, departure_time=150.0, energy_consumed=40000.0, remaining_battery_percent=88.8),
            WaypointVisit(node_id=0, arrival_time=200.0, departure_time=200.0, energy_consumed=60000.0, remaining_battery_percent=83.3),
        ],
        total_reward=50.0,
        total_flight_time=200.0,
        total_energy_joules=60000.0,
    )
    schedule = FleetSchedule(
        status="OPTIMAL",
        solve_time_seconds=0.1,
        cumulative_reward=50.0,
        assigned_routes=[valid_route],
        unassigned_targets=[3, 4],
        validation_passed=True,
    )

    audit = audit_fleet_schedule(schedule, mock_inst)
    assert audit["valid"] is True
    assert len(audit["violations"]) == 0
    assert validate_fleet_schedule(schedule, mock_inst) is True


def test_validator_detects_battery_violation(mock_inst):
    """Verify validator raises error if energy consumed exceeds 85% of battery."""
    drone = mock_inst.drones[0]
    # Consumes 95% of battery (exceeds 85% ceiling)
    excessive_energy = drone.battery_joules * 0.95
    bad_route = CandidateRoute(
        drone_id=drone.id,
        target_ids=[1],
        waypoints=[
            WaypointVisit(node_id=0, arrival_time=0.0, departure_time=0.0, energy_consumed=0.0, remaining_battery_percent=100.0),
            WaypointVisit(node_id=1, arrival_time=100.0, departure_time=130.0, energy_consumed=excessive_energy, remaining_battery_percent=5.0),
            WaypointVisit(node_id=0, arrival_time=200.0, departure_time=200.0, energy_consumed=excessive_energy, remaining_battery_percent=5.0),
        ],
        total_reward=25.0,
        total_flight_time=200.0,
        total_energy_joules=excessive_energy,
    )
    bad_schedule = FleetSchedule(
        status="FEASIBLE",
        solve_time_seconds=0.1,
        cumulative_reward=25.0,
        assigned_routes=[bad_route],
        unassigned_targets=[],
        validation_passed=True,
    )

    audit = audit_fleet_schedule(bad_schedule, mock_inst)
    assert audit["valid"] is False
    assert any("Battery reserve violation" in v for v in audit["violations"])

    with pytest.raises(ScheduleValidationError):
        validate_fleet_schedule(bad_schedule, mock_inst)


def test_validator_detects_target_duplication(mock_inst):
    """Verify validator catches target cannibalization / duplication across multiple drones."""
    d1 = mock_inst.drones[0]
    d2 = mock_inst.drones[1]
    # Both drones visit target 1
    r1 = CandidateRoute(
        drone_id=d1.id,
        target_ids=[1, 2],
        waypoints=[
            WaypointVisit(node_id=0, arrival_time=0.0, departure_time=0.0, energy_consumed=0.0),
            WaypointVisit(node_id=1, arrival_time=50.0, departure_time=80.0, energy_consumed=10000.0),
            WaypointVisit(node_id=2, arrival_time=120.0, departure_time=150.0, energy_consumed=20000.0),
            WaypointVisit(node_id=0, arrival_time=200.0, departure_time=200.0, energy_consumed=30000.0),
        ],
        total_reward=50.0,
        total_flight_time=200.0,
        total_energy_joules=30000.0,
    )
    r2 = CandidateRoute(
        drone_id=d2.id,
        target_ids=[1, 3],  # Target 1 duplicate
        waypoints=[
            WaypointVisit(node_id=0, arrival_time=0.0, departure_time=0.0, energy_consumed=0.0),
            WaypointVisit(node_id=1, arrival_time=50.0, departure_time=80.0, energy_consumed=10000.0),
            WaypointVisit(node_id=3, arrival_time=120.0, departure_time=150.0, energy_consumed=20000.0),
            WaypointVisit(node_id=0, arrival_time=200.0, departure_time=200.0, energy_consumed=30000.0),
        ],
        total_reward=60.0,
        total_flight_time=200.0,
        total_energy_joules=30000.0,
    )
    dup_schedule = FleetSchedule(
        status="FEASIBLE",
        solve_time_seconds=0.1,
        cumulative_reward=110.0,
        assigned_routes=[r1, r2],
        unassigned_targets=[],
        validation_passed=True,
    )

    audit = audit_fleet_schedule(dup_schedule, mock_inst)
    assert audit["valid"] is False
    assert any("duplication" in v for v in audit["violations"])


def test_validator_detects_deadline_violation(mock_inst):
    """Verify validator flags flight times exceeding T_max."""
    drone = mock_inst.drones[0]
    bad_route = CandidateRoute(
        drone_id=drone.id,
        target_ids=[1],
        waypoints=[
            WaypointVisit(node_id=0, arrival_time=0.0, departure_time=0.0, energy_consumed=0.0),
            WaypointVisit(node_id=1, arrival_time=1000.0, departure_time=1030.0, energy_consumed=10000.0),
            WaypointVisit(node_id=0, arrival_time=drone.max_flight_time + 100.0, departure_time=drone.max_flight_time + 100.0, energy_consumed=20000.0),
        ],
        total_reward=25.0,
        total_flight_time=drone.max_flight_time + 100.0,
        total_energy_joules=20000.0,
    )
    bad_schedule = FleetSchedule(
        status="FEASIBLE",
        solve_time_seconds=0.1,
        cumulative_reward=25.0,
        assigned_routes=[bad_route],
        unassigned_targets=[],
        validation_passed=True,
    )
    audit = audit_fleet_schedule(bad_schedule, mock_inst)
    assert audit["valid"] is False
    assert any("Deadline violation" in v for v in audit["violations"])


def test_validator_detects_depot_mismatch(mock_inst):
    """Verify validator flags routes starting or ending at the wrong depot."""
    drone = mock_inst.drones[0]
    bad_route = CandidateRoute(
        drone_id=drone.id,
        target_ids=[1],
        waypoints=[
            WaypointVisit(node_id=5, arrival_time=0.0, departure_time=0.0, energy_consumed=0.0),  # Not launch depot
            WaypointVisit(node_id=1, arrival_time=50.0, departure_time=80.0, energy_consumed=10000.0),
            WaypointVisit(node_id=0, arrival_time=120.0, departure_time=120.0, energy_consumed=20000.0),
        ],
        total_reward=25.0,
        total_flight_time=120.0,
        total_energy_joules=20000.0,
    )
    bad_schedule = FleetSchedule(
        status="FEASIBLE",
        solve_time_seconds=0.1,
        cumulative_reward=25.0,
        assigned_routes=[bad_route],
        unassigned_targets=[],
        validation_passed=True,
    )
    audit = audit_fleet_schedule(bad_schedule, mock_inst)
    assert audit["valid"] is False
    assert any("Depot flow mismatch" in v for v in audit["violations"])


def test_validator_detects_non_monotonic_timeline(mock_inst):
    """Verify validator flags non-monotonic timestamps or decreasing energy consumption."""
    drone = mock_inst.drones[0]
    bad_route = CandidateRoute(
        drone_id=drone.id,
        target_ids=[1, 2],
        waypoints=[
            WaypointVisit(node_id=0, arrival_time=0.0, departure_time=0.0, energy_consumed=0.0),
            WaypointVisit(node_id=1, arrival_time=100.0, departure_time=130.0, energy_consumed=20000.0),
            WaypointVisit(node_id=2, arrival_time=90.0, departure_time=120.0, energy_consumed=15000.0),  # Decreasing time and energy
            WaypointVisit(node_id=0, arrival_time=200.0, departure_time=200.0, energy_consumed=30000.0),
        ],
        total_reward=50.0,
        total_flight_time=200.0,
        total_energy_joules=30000.0,
    )
    bad_schedule = FleetSchedule(
        status="FEASIBLE",
        solve_time_seconds=0.1,
        cumulative_reward=50.0,
        assigned_routes=[bad_route],
        unassigned_targets=[],
        validation_passed=True,
    )
    audit = audit_fleet_schedule(bad_schedule, mock_inst)
    assert audit["valid"] is False
    assert any("Non-monotonic" in v for v in audit["violations"])
