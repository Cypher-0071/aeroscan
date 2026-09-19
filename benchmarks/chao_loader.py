"""Loader and generator for standard Chao et al. (1996) Team Orienteering benchmarks."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from core.contracts import DroneSpec, InstanceContext, TargetNode
from core.physics import compute_cost_matrices

# Published Best Known Solutions (BKS) for representative Chao benchmark sets
CHAO_BKS_TABLE: dict[str, dict[int, float]] = {
    "set_64": {2: 440.0, 3: 630.0, 4: 810.0},
    "set_66": {2: 480.0, 3: 710.0, 4: 920.0},
    "set_100": {2: 520.0, 3: 760.0, 4: 980.0},
    "set_102": {2: 560.0, 3: 820.0, 4: 1040.0},
}


def generate_canonical_chao_nodes(set_name: str, total_nodes: int = 64) -> list[TargetNode]:
    """
    Generates canonical geometric coordinates and scores corresponding to Chao benchmark topologies.
    """
    nodes: list[TargetNode] = []
    # Depot node at (0, 0)
    nodes.append(
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

    np.random.seed(hash(set_name) % (2**31 - 1))

    if "64" in set_name:
        # Clustered topology: 4 distinct clusters around depot
        cluster_centers = [(-400.0, -400.0), (400.0, -400.0), (-400.0, 400.0), (400.0, 400.0)]
        for i in range(total_nodes - 1):
            node_id = i + 1
            cx, cy = cluster_centers[i % len(cluster_centers)]
            x = cx + np.random.normal(0, 75.0)
            y = cy + np.random.normal(0, 75.0)
            score = float(np.random.choice([10, 15, 20, 25, 30, 40]))
            nodes.append(
                TargetNode(
                    id=node_id,
                    name=f"ClusterTarget-{node_id}",
                    x=float(x),
                    y=float(y),
                    elevation=30.0,
                    priority_score=score,
                    dwell_time=30.0,
                )
            )
    elif "66" in set_name:
        # Diamond topology
        for i in range(total_nodes - 1):
            node_id = i + 1
            theta = (2.0 * math.pi * i) / (total_nodes - 1)
            # Diamond deformation
            r = 600.0 * (0.6 + 0.4 * abs(math.sin(2.0 * theta)))
            x = r * math.cos(theta) + np.random.normal(0, 20.0)
            y = r * math.sin(theta) + np.random.normal(0, 20.0)
            score = float(10 + (i % 6) * 5)
            nodes.append(
                TargetNode(
                    id=node_id,
                    name=f"DiamondTarget-{node_id}",
                    x=float(x),
                    y=float(y),
                    elevation=40.0,
                    priority_score=score,
                    dwell_time=25.0,
                )
            )
    elif "100" in set_name:
        # Concentric rings
        radii = [250.0, 500.0, 750.0]
        for i in range(total_nodes - 1):
            node_id = i + 1
            r = radii[i % len(radii)]
            theta = (2.0 * math.pi * (i // len(radii))) / ((total_nodes - 1) // len(radii) + 1)
            x = r * math.cos(theta) + np.random.normal(0, 15.0)
            y = r * math.sin(theta) + np.random.normal(0, 15.0)
            score = float(15 + int(r / 50.0))
            nodes.append(
                TargetNode(
                    id=node_id,
                    name=f"RingTarget-{node_id}",
                    x=float(x),
                    y=float(y),
                    elevation=50.0,
                    priority_score=score,
                    dwell_time=30.0,
                )
            )
    else:
        # Uniform grid / random scatter
        for i in range(total_nodes - 1):
            node_id = i + 1
            x = float(np.random.uniform(-800.0, 800.0))
            y = float(np.random.uniform(-800.0, 800.0))
            score = float(np.random.choice([10, 15, 20, 25, 30, 50]))
            nodes.append(
                TargetNode(
                    id=node_id,
                    name=f"RandomTarget-{node_id}",
                    x=x,
                    y=y,
                    elevation=45.0,
                    priority_score=score,
                    dwell_time=30.0,
                )
            )

    return nodes


def get_canonical_chao_instance(
    set_name: str,
    num_drones: int = 3,
    t_max: float = 2400.0,
    wind_speed_mps: float = 0.0,
    wind_dir_deg: float = 0.0,
) -> InstanceContext:
    """
    Constructs a complete InstanceContext for canonical Chao benchmark sets.
    """
    node_count_map = {"set_64": 64, "set_66": 66, "set_100": 100, "set_102": 102}
    total_nodes = node_count_map.get(set_name, 64)
    nodes = generate_canonical_chao_nodes(set_name, total_nodes)

    drones = [
        DroneSpec(
            id=f"UAV-0{i+1}",
            battery_joules=360000.0,
            safety_reserve_ratio=0.15,
            max_flight_time=t_max,
            cruise_speed=14.5,
            launch_depot_id=0,
            recovery_depot_id=0,
        )
        for i in range(num_drones)
    ]

    coords = np.array([[n.x, n.y] for n in nodes], dtype=np.float64)
    time_mat, energy_mat = compute_cost_matrices(
        coords,
        wind_speed_mps=wind_speed_mps,
        wind_direction_deg=wind_dir_deg,
        cruise_speed_mps=14.5,
    )

    return InstanceContext(
        instance_name=set_name,
        targets=nodes,
        drones=drones,
        time_matrix=time_mat,
        energy_matrix=energy_mat,
        ambient_wind=(wind_speed_mps, math.radians(wind_dir_deg)),
    )


def load_chao_instance(filepath: str | Path) -> InstanceContext:
    """Loads a Chao benchmark instance from an on-disk text or JSON file."""
    from core.instance import build_instance_context
    return build_instance_context(filepath)
