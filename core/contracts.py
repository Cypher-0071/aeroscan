"""Data contracts and schemas for AeroScan-Optima."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np


@dataclass
class TargetNode:
    """Represents a target point of interest or depot location."""
    id: int                     # 0..N-1 for targets, N..N+2K-1 for depots
    name: str                   # Human-readable identifier
    x: float                    # Metric X coordinate (meters, UTM or Cartesian)
    y: float                    # Metric Y coordinate (meters, UTM or Cartesian)
    elevation: float            # Altitude in meters
    priority_score: float       # Search priority (0..100)
    dwell_time: float           # Sensor inspection dwell in seconds (e.g. 30.0s)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TargetNode:
        return cls(
            id=int(data["id"]),
            name=str(data.get("name", f"Node-{data['id']}")),
            x=float(data["x"]),
            y=float(data["y"]),
            elevation=float(data.get("elevation", 0.0)),
            priority_score=float(data.get("priority_score", 0.0)),
            dwell_time=float(data.get("dwell_time", data.get("dwell_time_seconds", 30.0))),
        )


@dataclass
class DroneSpec:
    """Represents specifications of an Uncrewed Aerial Vehicle in the fleet."""
    id: str                     # e.g., "UAV-01"
    battery_joules: float       # Total usable battery capacity (Joules)
    safety_reserve_ratio: float = 0.15  # Default 0.15 (15% reserve floor)
    max_flight_time: float = 2400.0     # Hard flight deadline in seconds (e.g. 2400s)
    cruise_speed: float = 14.5          # Airspeed in m/s (e.g. 14.5 m/s)
    launch_depot_id: int = 0            # Node ID of launch base
    recovery_depot_id: int = 0          # Node ID of landing base
    model: str = "Standard-UAV"

    @property
    def usable_battery_joules(self) -> float:
        """Effective battery energy allowed to consume (excluding 15% reserve)."""
        return self.battery_joules * (1.0 - self.safety_reserve_ratio)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DroneSpec:
        return cls(
            id=str(data["id"]),
            battery_joules=float(data["battery_joules"]),
            safety_reserve_ratio=float(data.get("safety_reserve_ratio", 0.15)),
            max_flight_time=float(data.get("max_flight_time", data.get("max_flight_time_seconds", 2400.0))),
            cruise_speed=float(data.get("cruise_speed", data.get("cruise_speed_mps", 14.5))),
            launch_depot_id=int(data.get("launch_depot_id", 0)),
            recovery_depot_id=int(data.get("recovery_depot_id", 0)),
            model=str(data.get("model", "Standard-UAV")),
        )


@dataclass
class InstanceContext:
    """Full mission scenario context including targets, fleet, and kinematic cost matrices."""
    instance_name: str
    targets: list[TargetNode]
    drones: list[DroneSpec]
    time_matrix: np.ndarray     # Shape: [TotalNodes, TotalNodes], time in seconds (asymmetric)
    energy_matrix: np.ndarray   # Shape: [TotalNodes, TotalNodes], energy in Joules (asymmetric)
    ambient_wind: tuple[float, float] = (0.0, 0.0)  # (speed_mps, direction_rad)

    @property
    def id_to_index(self) -> dict[int, int]:
        """Maps target/depot node IDs to row/column indices in cost matrices."""
        return {node.id: idx for idx, node in enumerate(self.targets)}

    def get_node(self, node_id: int) -> TargetNode | None:
        """O(1) lookup of TargetNode by node ID."""
        idx = self.id_to_index.get(node_id)
        return self.targets[idx] if idx is not None else None

    def get_transit_time(self, from_node_id: int, to_node_id: int) -> float:
        """Looks up transit time in seconds between two node IDs."""
        mapping = self.id_to_index
        i = mapping.get(from_node_id, from_node_id)
        j = mapping.get(to_node_id, to_node_id)
        return float(self.time_matrix[i, j])

    def get_transit_energy(self, from_node_id: int, to_node_id: int) -> float:
        """Looks up transit energy in Joules between two node IDs."""
        mapping = self.id_to_index
        i = mapping.get(from_node_id, from_node_id)
        j = mapping.get(to_node_id, to_node_id)
        return float(self.energy_matrix[i, j])

    @property
    def target_nodes(self) -> list[TargetNode]:
        """Returns only nodes with non-zero priority score or not designated solely as depots."""
        depot_ids = {d.launch_depot_id for d in self.drones} | {d.recovery_depot_id for d in self.drones}
        return [t for t in self.targets if t.id not in depot_ids and t.priority_score > 0]

    @property
    def total_nodes(self) -> int:
        return len(self.targets)


@dataclass
class WaypointVisit:
    """Chronological waypoint entry in a drone's flight trajectory."""
    node_id: int
    arrival_time: float         # Continuous seconds from mission start
    departure_time: float       # arrival_time + dwell_time
    energy_consumed: float      # Cumulative energy consumed up to this point (Joules)
    remaining_battery_percent: float = 100.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WaypointVisit:
        return cls(
            node_id=int(data["node_id"]),
            arrival_time=float(data["arrival_time"]),
            departure_time=float(data["departure_time"]),
            energy_consumed=float(data.get("energy_consumed", 0.0)),
            remaining_battery_percent=float(data.get("remaining_battery_percent", 100.0)),
        )


@dataclass
class CandidateRoute:
    """A feasible single-drone trajectory evaluated under physics constraints."""
    drone_id: str               # Eligible drone identifier
    target_ids: list[int]       # Visited target node IDs in sequence (excluding depots)
    waypoints: list[WaypointVisit] # Full trajectory including launch and recovery depots
    total_reward: float         # Sum of priority rewards of visited targets
    total_flight_time: float    # Return time to recovery depot (seconds)
    total_energy_joules: float  # Total energy burn (must be <= 0.85 * battery_joules)

    @property
    def final_reserve_percent(self) -> float:
        if not self.waypoints:
            return 100.0
        return self.waypoints[-1].remaining_battery_percent

    def to_dict(self) -> dict[str, Any]:
        return {
            "drone_id": self.drone_id,
            "target_ids": self.target_ids,
            "waypoints": [w.to_dict() for w in self.waypoints],
            "total_reward": self.total_reward,
            "total_flight_time": self.total_flight_time,
            "total_energy_joules": self.total_energy_joules,
            "final_reserve_percent": self.final_reserve_percent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CandidateRoute:
        return cls(
            drone_id=str(data["drone_id"]),
            target_ids=[int(x) for x in data.get("target_ids", [])],
            waypoints=[WaypointVisit.from_dict(w) for w in data.get("waypoints", [])],
            total_reward=float(data.get("total_reward", 0.0)),
            total_flight_time=float(data.get("total_flight_time", 0.0)),
            total_energy_joules=float(data.get("total_energy_joules", 0.0)),
        )


@dataclass
class RoutePool:
    """Pool of candidate feasible single-drone routes discovered by ALNS."""
    routes_by_drone: dict[str, list[CandidateRoute]] = field(default_factory=dict)

    @property
    def total_routes(self) -> int:
        return sum(len(routes) for routes in self.routes_by_drone.values())


@dataclass
class FleetSchedule:
    """Global optimal schedule produced by CP-SAT Master Problem along with validation and baselines."""
    status: str                 # "OPTIMAL", "FEASIBLE", or "INFEASIBLE"
    solve_time_seconds: float   # Execution latency in seconds
    cumulative_reward: float    # Sum of unique collected target rewards
    assigned_routes: list[CandidateRoute] # Selected routes (at most 1 per drone)
    unassigned_targets: list[int] # Target IDs not visited
    validation_passed: bool     # True if 0% battery violation and 0% subtours
    baseline_grasp_reward: float = 0.0 # Comparative GRASP baseline score
    baseline_ga_reward: float = 0.0    # Comparative Genetic Algorithm score
    reward_gain_percent: float = 0.0   # ((cumulative_reward - grasp_reward) / grasp_reward) * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "solve_time_seconds": self.solve_time_seconds,
            "cumulative_score": self.cumulative_reward,
            "cumulative_reward": self.cumulative_reward,
            "assigned_routes": [r.to_dict() for r in self.assigned_routes],
            "routes": [r.to_dict() for r in self.assigned_routes],
            "unassigned_targets": self.unassigned_targets,
            "validation_passed": self.validation_passed,
            "baseline_grasp_reward": self.baseline_grasp_reward,
            "baseline_ga_reward": self.baseline_ga_reward,
            "reward_gain_percent": self.reward_gain_percent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FleetSchedule:
        raw_routes = data.get("assigned_routes", data.get("routes", []))
        routes = [CandidateRoute.from_dict(r) for r in raw_routes]
        score = float(data.get("cumulative_reward", data.get("cumulative_score", 0.0)))
        return cls(
            status=str(data.get("status", "OPTIMAL")),
            solve_time_seconds=float(data.get("solve_time_seconds", 0.0)),
            cumulative_reward=score,
            assigned_routes=routes,
            unassigned_targets=[int(x) for x in data.get("unassigned_targets", [])],
            validation_passed=bool(data.get("validation_passed", True)),
            baseline_grasp_reward=float(data.get("baseline_grasp_reward", 0.0)),
            baseline_ga_reward=float(data.get("baseline_ga_reward", 0.0)),
            reward_gain_percent=float(data.get("reward_gain_percent", 0.0)),
        )
