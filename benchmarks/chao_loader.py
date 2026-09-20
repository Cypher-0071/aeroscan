"""Manifest-backed loader for Chao et al. (1996) Team Orienteering benchmarks.

Source of truth
---------------
Official instances and their Best Known Solutions (BKS) are read from
``data/chao_instances/manifest.json``. Nothing is derived, tuned, or fabricated:
an instance without manifest BKS metadata reports ``bks=None`` and benchmarks
report ``N/A`` instead of a synthetic near-optimal score.

Corpus availability
-------------------
The full 387-instance Chao corpus is **not** redistributed with this repository.
The manifest declares the expected corpus size and the loader reports the corpus
as incomplete rather than claiming coverage. Only the checked-in fixture
(``set_64_1.txt``) is present, and only for fast unit tests. Official runs require
placing the authorized instance files under ``data/chao_instances/`` and listing
them in the manifest.

Synthetic instances
-------------------
Geometric generators are retained solely as deterministic test fixtures. They are
always named ``synthetic_*`` and are never returned by the official enumeration
APIs, so they cannot be confused with Chao data.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from core.contracts import DroneSpec, InstanceContext, TargetNode
from core.instance import DEFAULT_CHAO_ADAPTER, ChaoAdapterConfig, build_instance_context
from core.physics import compute_cost_matrices

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS_DIR = REPO_ROOT / "data" / "chao_instances"
DEFAULT_MANIFEST_PATH = DEFAULT_CORPUS_DIR / "manifest.json"

SYNTHETIC_PREFIX = "synthetic_"

# Node counts for the four canonical Chao set families. Used only to size
# synthetic fixtures and to sanity-check manifest declarations.
CHAO_SET_NODE_COUNTS: dict[str, int] = {
    "set_64": 64,
    "set_66": 66,
    "set_100": 100,
    "set_102": 102,
}


@dataclass(frozen=True)
class ChaoInstanceMetadata:
    """One manifest entry describing an official or synthetic instance."""

    instance_id: str
    set_name: str
    path: Path
    node_count: int
    vehicle_count: int
    route_length_budget: float | None = None
    bks: float | None = None
    source: str = ""
    version: str = ""
    checksum: str | None = None
    synthetic: bool = False

    @property
    def available(self) -> bool:
        return self.path.exists()

    def is_official_bks_available(self) -> bool:
        return (not self.synthetic) and self.bks is not None and self.bks > 0


@dataclass(frozen=True)
class ChaoCorpusStatus:
    """Availability summary for the official corpus."""

    manifest_path: Path
    expected_instances: int
    declared_instances: int
    available_instances: int
    missing_files: tuple[str, ...]

    @property
    def corpus_complete(self) -> bool:
        return (
            self.missing_files == ()
            and self.declared_instances >= self.expected_instances
            and self.expected_instances > 0
        )

    def describe(self) -> str:
        if self.corpus_complete:
            return (
                f"Chao corpus complete: {self.available_instances}/"
                f"{self.expected_instances} official instances available."
            )
        return (
            f"Chao corpus UNAVAILABLE/INCOMPLETE: {self.available_instances} available, "
            f"{self.declared_instances} declared, {self.expected_instances} expected. "
            "Full-corpus BKS comparisons must not be claimed until the authorized "
            f"instance files are present under {self.manifest_path.parent}."
        )


class ChaoManifestError(ValueError):
    """Raised when the benchmark manifest is missing, malformed, or inconsistent."""


def load_manifest(manifest_path: str | Path = DEFAULT_MANIFEST_PATH) -> tuple[dict, list[ChaoInstanceMetadata]]:
    """Loads and validates the benchmark manifest.

    Returns the raw manifest document and the normalized instance entries.
    """
    path = Path(manifest_path)
    if not path.exists():
        raise ChaoManifestError(
            f"Benchmark manifest not found at {path}. Official Chao benchmarks cannot be "
            "discovered without a manifest."
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ChaoManifestError(f"{path}: invalid JSON at line {exc.lineno} column {exc.colno}") from exc
    if not isinstance(raw, dict):
        raise ChaoManifestError(f"{path}: manifest must be a JSON object")
    raw_instances = raw.get("instances", [])
    if not isinstance(raw_instances, list):
        raise ChaoManifestError(f"{path}: 'instances' must be a list")

    entries: list[ChaoInstanceMetadata] = []
    seen: set[str] = set()
    for idx, item in enumerate(raw_instances):
        if not isinstance(item, dict):
            raise ChaoManifestError(f"{path}: instances[{idx}] must be an object")
        instance_id = item.get("instance_id")
        if not instance_id:
            raise ChaoManifestError(f"{path}: instances[{idx}] is missing 'instance_id'")
        if instance_id in seen:
            raise ChaoManifestError(f"{path}: duplicate instance_id {instance_id!r}")
        seen.add(instance_id)
        rel_path = item.get("path")
        if not rel_path:
            raise ChaoManifestError(f"{path}: {instance_id} is missing 'path'")
        bks = item.get("bks")
        try:
            node_count = int(item.get("nodes", 0))
            vehicle_count = int(item.get("vehicles", 0))
            route_length_budget = (
                float(item["route_length_budget"]) if item.get("route_length_budget") is not None else None
            )
            bks_value = float(bks) if bks is not None else None
        except (TypeError, ValueError) as exc:
            raise ChaoManifestError(f"{path}: {instance_id} has a non-numeric field: {exc}") from exc
        entries.append(
            ChaoInstanceMetadata(
                instance_id=str(instance_id),
                set_name=str(item.get("set", "unknown")),
                path=path.parent / str(rel_path),
                node_count=node_count,
                vehicle_count=vehicle_count,
                route_length_budget=route_length_budget,
                bks=bks_value,
                source=str(item.get("source", "")),
                version=str(item.get("version", "")),
                checksum=item.get("checksum"),
                synthetic=bool(item.get("synthetic", False)),
            )
        )
    return raw, entries


def corpus_status(manifest_path: str | Path = DEFAULT_MANIFEST_PATH) -> ChaoCorpusStatus:
    """Reports how much of the official corpus is actually present on disk."""
    raw, entries = load_manifest(manifest_path)
    corpus = raw.get("corpus", {}) if isinstance(raw.get("corpus"), dict) else {}
    expected = int(corpus.get("expected_instances", 0))
    official = [entry for entry in entries if not entry.synthetic]
    missing = tuple(entry.instance_id for entry in official if not entry.available)
    return ChaoCorpusStatus(
        manifest_path=Path(manifest_path),
        expected_instances=expected,
        declared_instances=len(official),
        available_instances=sum(1 for entry in official if entry.available),
        missing_files=missing,
    )


def iter_instances(
    set_name: str | None = None,
    node_count: int | None = None,
    fleet_size: int | None = None,
    include_synthetic: bool = False,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
) -> list[ChaoInstanceMetadata]:
    """Enumerates manifest instances filtered by set, node count, and/or fleet size."""
    _raw, entries = load_manifest(manifest_path)
    selected: list[ChaoInstanceMetadata] = []
    for entry in entries:
        if entry.synthetic and not include_synthetic:
            continue
        if set_name is not None and entry.set_name != set_name:
            continue
        if node_count is not None and entry.node_count != node_count:
            continue
        if fleet_size is not None and entry.vehicle_count != fleet_size:
            continue
        selected.append(entry)
    return selected


def get_instance_metadata(
    instance_id: str, manifest_path: str | Path = DEFAULT_MANIFEST_PATH
) -> ChaoInstanceMetadata:
    """Looks up one manifest entry by stable instance ID."""
    _raw, entries = load_manifest(manifest_path)
    for entry in entries:
        if entry.instance_id == instance_id:
            return entry
    raise KeyError(f"Instance {instance_id!r} is not present in the benchmark manifest")


def get_official_bks(instance_id: str, manifest_path: str | Path = DEFAULT_MANIFEST_PATH) -> float | None:
    """Returns the authoritative BKS for an instance, or ``None`` when unavailable.

    Never falls back to a fabricated or derived score.
    """
    entry = get_instance_metadata(instance_id, manifest_path)
    if entry.synthetic:
        return None
    return entry.bks


def validate_instance_file(
    entry: ChaoInstanceMetadata, adapter: ChaoAdapterConfig = DEFAULT_CHAO_ADAPTER
) -> None:
    """Checks that a manifest entry matches the on-disk instance dimensions."""
    if not entry.available:
        raise FileNotFoundError(
            f"Instance file for {entry.instance_id!r} is missing at {entry.path}. "
            "Official corpus files are not redistributed with this repository."
        )
    if entry.path.suffix.lower() == ".txt":
        import hashlib

        if entry.checksum:
            digest = hashlib.sha256(entry.path.read_bytes()).hexdigest()
            if digest != entry.checksum:
                raise ChaoManifestError(
                    f"{entry.instance_id}: checksum mismatch (expected {entry.checksum}, got {digest})"
                )
        from core.instance import parse_chao_txt

        parsed = parse_chao_txt(entry.path, adapter=adapter)
        declared_nodes = parsed.metadata["declared_node_count"]
        declared_drones = parsed.metadata["declared_fleet_size"]
        if entry.node_count and declared_nodes != entry.node_count:
            raise ChaoManifestError(
                f"{entry.instance_id}: manifest declares {entry.node_count} nodes but file declares {declared_nodes}"
            )
        if entry.vehicle_count and declared_drones != entry.vehicle_count:
            raise ChaoManifestError(
                f"{entry.instance_id}: manifest declares {entry.vehicle_count} vehicles but file declares "
                f"{declared_drones}"
            )


def load_instance(
    instance_id: str,
    num_drones: int | None = None,
    wind_speed_mps: float | None = None,
    wind_dir_deg: float | None = None,
    adapter: ChaoAdapterConfig = DEFAULT_CHAO_ADAPTER,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
) -> InstanceContext:
    """Loads an official manifest instance by stable ID into an ``InstanceContext``."""
    entry = get_instance_metadata(instance_id, manifest_path)
    validate_instance_file(entry, adapter=adapter)
    context = build_instance_context(
        entry.path,
        wind_speed_mps=wind_speed_mps,
        wind_dir_deg=wind_dir_deg,
        num_drones=num_drones,
        adapter=adapter,
    )
    context.instance_name = entry.instance_id
    return context


def load_chao_instance(filepath: str | Path, adapter: ChaoAdapterConfig = DEFAULT_CHAO_ADAPTER) -> InstanceContext:
    """Loads a Chao benchmark instance directly from a file path (fixture or official)."""
    return build_instance_context(filepath, adapter=adapter)


# ---------------------------------------------------------------------------
# Synthetic fixtures (deterministic; never treated as official benchmarks)
# ---------------------------------------------------------------------------


def build_synthetic_nodes(set_name: str, total_nodes: int, seed: int = 12345) -> list[TargetNode]:
    """Builds a deterministic synthetic node set for a canonical Chao-topology fixture."""
    if total_nodes <= 1:
        raise ValueError(f"total_nodes must be greater than 1, got {total_nodes}")
    rng = np.random.default_rng(seed)

    nodes: list[TargetNode] = [
        TargetNode(id=0, name="Depot-0", x=0.0, y=0.0, elevation=0.0, priority_score=0.0, dwell_time=0.0)
    ]

    if "64" in set_name:
        cluster_centers = [(-400.0, -400.0), (400.0, -400.0), (-400.0, 400.0), (400.0, 400.0)]
        for i in range(total_nodes - 1):
            node_id = i + 1
            cx, cy = cluster_centers[i % len(cluster_centers)]
            nodes.append(
                TargetNode(
                    id=node_id,
                    name=f"ClusterTarget-{node_id}",
                    x=float(cx + rng.normal(0, 75.0)),
                    y=float(cy + rng.normal(0, 75.0)),
                    elevation=30.0,
                    priority_score=float(rng.choice([10, 15, 20, 25, 30, 40])),
                    dwell_time=30.0,
                )
            )
    elif "66" in set_name:
        for i in range(total_nodes - 1):
            node_id = i + 1
            theta = (2.0 * math.pi * i) / (total_nodes - 1)
            r = 600.0 * (0.6 + 0.4 * abs(math.sin(2.0 * theta)))
            nodes.append(
                TargetNode(
                    id=node_id,
                    name=f"DiamondTarget-{node_id}",
                    x=float(r * math.cos(theta) + rng.normal(0, 20.0)),
                    y=float(r * math.sin(theta) + rng.normal(0, 20.0)),
                    elevation=40.0,
                    priority_score=float(10 + (i % 6) * 5),
                    dwell_time=25.0,
                )
            )
    elif "100" in set_name:
        radii = [250.0, 500.0, 750.0]
        for i in range(total_nodes - 1):
            node_id = i + 1
            r = radii[i % len(radii)]
            theta = (2.0 * math.pi * (i // len(radii))) / ((total_nodes - 1) // len(radii) + 1)
            nodes.append(
                TargetNode(
                    id=node_id,
                    name=f"RingTarget-{node_id}",
                    x=float(r * math.cos(theta) + rng.normal(0, 15.0)),
                    y=float(r * math.sin(theta) + rng.normal(0, 15.0)),
                    elevation=50.0,
                    priority_score=float(15 + int(r / 50.0)),
                    dwell_time=30.0,
                )
            )
    else:
        for i in range(total_nodes - 1):
            node_id = i + 1
            nodes.append(
                TargetNode(
                    id=node_id,
                    name=f"RandomTarget-{node_id}",
                    x=float(rng.uniform(-800.0, 800.0)),
                    y=float(rng.uniform(-800.0, 800.0)),
                    elevation=45.0,
                    priority_score=float(rng.choice([10, 15, 20, 25, 30, 50])),
                    dwell_time=30.0,
                )
            )

    return nodes


def get_synthetic_instance(
    set_name: str,
    num_drones: int = 3,
    t_max: float = 2400.0,
    wind_speed_mps: float = 0.0,
    wind_dir_deg: float = 0.0,
    seed: int = 12345,
    adapter: ChaoAdapterConfig = DEFAULT_CHAO_ADAPTER,
) -> InstanceContext:
    """Constructs a deterministic *synthetic* fixture standing in for a Chao set.

    The returned ``instance_name`` is always prefixed with ``synthetic_`` and the
    context is never reported as an official benchmark result.
    """
    total_nodes = CHAO_SET_NODE_COUNTS.get(set_name)
    if total_nodes is None:
        valid = ", ".join(sorted(CHAO_SET_NODE_COUNTS))
        raise KeyError(f"Unknown Chao set {set_name!r}; expected one of: {valid}")
    if num_drones <= 0:
        raise ValueError(f"num_drones must be positive, got {num_drones}")

    nodes = build_synthetic_nodes(set_name, total_nodes, seed=seed)
    depot_id = nodes[0].id
    drones = [
        DroneSpec(
            id=f"UAV-{i + 1:02d}",
            battery_joules=adapter.battery_joules,
            safety_reserve_ratio=adapter.safety_reserve_ratio,
            max_flight_time=t_max,
            cruise_speed=adapter.cruise_speed_mps,
            launch_depot_id=depot_id,
            recovery_depot_id=depot_id,
        )
        for i in range(num_drones)
    ]

    coords = np.array([[n.x, n.y] for n in nodes], dtype=np.float64)
    time_mat, energy_mat = compute_cost_matrices(
        coords,
        wind_speed_mps=wind_speed_mps,
        wind_direction_deg=wind_dir_deg,
        cruise_speed_mps=adapter.cruise_speed_mps,
    )

    return InstanceContext(
        instance_name=f"{SYNTHETIC_PREFIX}{set_name}",
        targets=nodes,
        drones=drones,
        time_matrix=time_mat,
        energy_matrix=energy_mat,
        ambient_wind=(wind_speed_mps, math.radians(wind_dir_deg)),
        metadata={
            "source_format": "synthetic",
            "crs": "cartesian-meters",
            "synthetic": True,
            "set_name": set_name,
            "wind_speed_mps": wind_speed_mps,
            "wind_direction_deg": wind_dir_deg,
            "cruise_speed_mps": adapter.cruise_speed_mps,
        },
    )


def get_canonical_chao_instance(
    set_name: str,
    num_drones: int = 3,
    t_max: float = 2400.0,
    wind_speed_mps: float = 0.0,
    wind_dir_deg: float = 0.0,
) -> InstanceContext:
    """Backwards-compatible alias for :func:`get_synthetic_instance`.

    Kept so the dashboard keeps working; the result is explicitly synthetic and
    must not be used for official BKS claims.
    """
    return get_synthetic_instance(
        set_name,
        num_drones=num_drones,
        t_max=t_max,
        wind_speed_mps=wind_speed_mps,
        wind_dir_deg=wind_dir_deg,
    )
