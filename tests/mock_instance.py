"""Mock InstanceContext fixture for Day 0 independent testing."""

from __future__ import annotations

import math

import numpy as np

from core.contracts import DroneSpec, InstanceContext, TargetNode
from core.physics import compute_cost_matrices


def create_mock_instance(
    num_targets: int = 20,
    num_drones: int = 3,
    wind_speed: float = 3.0,
    wind_dir_deg: float = 45.0,
) -> InstanceContext:
    """
    Creates a reproducible 20-target mock InstanceContext with 3 drones and wind.
    """
    np.random.seed(42)
    targets: list[TargetNode] = []

    # Launch / Recovery depot at (0, 0)
    targets.append(
        TargetNode(
            id=0,
            name="Depot-0",
            x=0.0,
            y=0.0,
            elevation=0.0,
            priority_score=0.0,
            dwell_time=0.0,
        )
    )

    # 20 targets scattered around depot within 800m
    for i in range(1, num_targets + 1):
        angle = (2.0 * math.pi * i) / num_targets
        dist = float(np.random.uniform(200.0, 750.0))
        x = dist * math.cos(angle)
        y = dist * math.sin(angle)
        score = float(np.random.choice([15, 20, 25, 30, 40, 50, 75]))
        dwell = float(np.random.choice([20.0, 30.0, 45.0]))
        targets.append(
            TargetNode(
                id=i,
                name=f"Target-{i}",
                x=x,
                y=y,
                elevation=float(np.random.uniform(20.0, 80.0)),
                priority_score=score,
                dwell_time=dwell,
            )
        )

    drones = [
        DroneSpec(
            id=f"UAV-0{i+1}",
            battery_joules=360000.0,  # 100 Wh
            safety_reserve_ratio=0.15,
            max_flight_time=2400.0,
            cruise_speed=14.5,
            launch_depot_id=0,
            recovery_depot_id=0,
            model="Matrice-350-RTK",
        )
        for i in range(num_drones)
    ]

    coords = np.array([[t.x, t.y] for t in targets], dtype=np.float64)
    time_mat, energy_mat = compute_cost_matrices(
        coords,
        wind_speed_mps=wind_speed,
        wind_direction_deg=wind_dir_deg,
        cruise_speed_mps=14.5,
    )

    return InstanceContext(
        instance_name="Synthetic_Mock_20_Targets",
        targets=targets,
        drones=drones,
        time_matrix=time_mat,
        energy_matrix=energy_mat,
        ambient_wind=(wind_speed, math.radians(wind_dir_deg)),
    )
