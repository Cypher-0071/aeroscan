"""Reproducible, auditable benchmark harness for AeroScan-Optima.

Every reported number can be traced back to a row, and every row records where it
came from. Two properties are non-negotiable:

* **No fabricated BKS.** A row without authoritative manifest BKS metadata reports
  ``bks=None`` and a gap of ``N/A``. The runner never derives a reference score
  from the solver's own answer.
* **No hidden failures.** An unavailable or failing downstream solver produces a
  row with ``completed=False`` and an ``error`` string; it is never replaced by a
  synthetic result.

Two entry points:
* :func:`run_smoke_suite` - deterministic synthetic fixtures, fast, no corpus needed.
* :func:`run_benchmark_suite` - official manifest/corpus instances only.

The full suite reports whether it meets the PRD thresholds, and explicitly reports
them as *not evaluated* when there is nothing to measure instead of passing by default.
"""

from __future__ import annotations

import json
import math
import platform
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

import pandas as pd

from benchmarks.chao_loader import (
    DEFAULT_MANIFEST_PATH,
    SYNTHETIC_PREFIX,
    ChaoCorpusStatus,
    ChaoInstanceMetadata,
    corpus_status,
    get_synthetic_instance,
    iter_instances,
    load_instance,
)
from core.alns import explore_route_pool
from core.contracts import InstanceContext
from core.instance import DEFAULT_CHAO_ADAPTER, ChaoAdapterConfig
from core.set_packing import solve_fleet_schedule
from core.validator import audit_fleet_schedule

# PRD acceptance thresholds (see docs/team_prd_person3_physics_benchmarks.md).
PRD_MAX_AVERAGE_BKS_GAP_PCT = 0.15
PRD_MAX_AVERAGE_LATENCY_SEC = 2.5
PRD_MAX_BATTERY_VIOLATIONS = 0


@dataclass
class BenchmarkConfig:
    """Reproducible benchmark configuration. Two runs of the same config must match."""

    instance_ids: list[str] | None = None
    sets: list[str] | None = None
    fleet_sizes: list[int] | None = None
    alns_iterations: int = 200
    alns_time_limit_sec: float = 1.0
    cp_sat_time_limit_sec: float = 0.5
    random_seed: int = 42
    run_baselines: bool = False
    manifest_path: Path = DEFAULT_MANIFEST_PATH
    output_csv: Path | None = None
    output_json: Path | None = None
    # Chao-to-UAV adapter assumptions, recorded with every report so a benchmark
    # is reproducible from its data version and configuration alone.
    adapter: ChaoAdapterConfig = DEFAULT_CHAO_ADAPTER

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["adapter"] = asdict(self.adapter)
        data["manifest_path"] = str(self.manifest_path)
        data["output_csv"] = str(self.output_csv) if self.output_csv else None
        data["output_json"] = str(self.output_json) if self.output_json else None
        return data


@dataclass
class BenchmarkResult:
    """One auditable benchmark row."""

    instance_id: str
    source: str
    nodes: int
    fleet_size: int
    bks: float | None = None
    bks_source: str = ""
    bks_version: str = ""
    wind_speed_mps: float | None = None
    wind_direction_deg: float | None = None
    aeroscan_score: float | None = None
    grasp_score: float | None = None
    ga_score: float | None = None
    reward_gain_pct: float | None = None
    gap_to_bks_pct: float | None = None
    preprocessing_sec: float = 0.0
    alns_sec: float = 0.0
    master_sec: float = 0.0
    audit_sec: float = 0.0
    total_latency_sec: float = 0.0
    solver_latency_sec: float = 0.0
    route_count: int = 0
    battery_violations: int = 0
    violations: list[str] = field(default_factory=list)
    schedule_status: str = ""
    validation_status: str = "N/A"
    completed: bool = False
    error: str | None = None

    @property
    def bks_comparable(self) -> bool:
        return self.completed and self.bks is not None and self.gap_to_bks_pct is not None

    def to_dict(self) -> dict[str, Any]:
        """Flattens to a CSV-friendly row. Missing values are rendered as ``N/A``."""
        return {
            "Instance": self.instance_id,
            "Source": self.source,
            "Nodes": self.nodes,
            "Fleet Size": self.fleet_size,
            "BKS": self.bks if self.bks is not None else "N/A",
            "BKS Source": self.bks_source or "N/A",
            "BKS Version": self.bks_version or "N/A",
            "Wind (m/s)": _round_or_na(self.wind_speed_mps, 2),
            "Wind Dir (deg)": _round_or_na(self.wind_direction_deg, 1),
            "AeroScan Score": _round_or_na(self.aeroscan_score, 1),
            "GRASP Score": _round_or_na(self.grasp_score, 1),
            "GA Score": _round_or_na(self.ga_score, 1),
            "Gain vs GRASP (%)": _round_or_na(self.reward_gain_pct, 2),
            "Gap to BKS (%)": _round_or_na(self.gap_to_bks_pct, 3),
            "Preprocess (s)": round(self.preprocessing_sec, 4),
            "ALNS (s)": round(self.alns_sec, 4),
            "Master (s)": round(self.master_sec, 4),
            "Audit (s)": round(self.audit_sec, 4),
            "Total Latency (s)": round(self.total_latency_sec, 4),
            "Solver Latency (s)": round(self.solver_latency_sec, 4),
            "Routes": self.route_count,
            "Battery Violations": self.battery_violations,
            "Violations": "; ".join(self.violations),
            "Schedule Status": self.schedule_status or "N/A",
            "Valid": self.validation_status,
            "Completed": self.completed,
            "Error": self.error or "",
        }


def _round_or_na(value: float | None, digits: int) -> float | str:
    return round(value, digits) if value is not None else "N/A"


def environment_info() -> dict[str, Any]:
    """Records the interpreter and key solver/library versions for report provenance."""
    versions: dict[str, str | None] = {}
    for package in ("numpy", "pandas", "ortools", "scipy"):
        try:
            versions[package] = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:  # pragma: no cover - env dependent
            versions[package] = None
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": versions,
    }


def _wind_fields(instance: InstanceContext) -> tuple[float, float]:
    """Returns the instance wind as ``(speed_mps, direction_degrees)`` using the public convention."""
    speed, direction_rad = instance.ambient_wind
    return (float(speed), math.degrees(float(direction_rad)) % 360.0)


def _failed_row(
    instance: InstanceContext,
    instance_id: str,
    source: str,
    error: str,
    bks: float | None,
    bks_source: str = "",
    bks_version: str = "",
    preprocessing_sec: float = 0.0,
) -> BenchmarkResult:
    wind_speed, wind_dir = _wind_fields(instance)
    return BenchmarkResult(
        instance_id=instance_id,
        source=source,
        nodes=len(instance.targets),
        fleet_size=len(instance.drones),
        bks=bks,
        bks_source=bks_source,
        bks_version=bks_version,
        wind_speed_mps=wind_speed,
        wind_direction_deg=wind_dir,
        preprocessing_sec=preprocessing_sec,
        validation_status="N/A",
        completed=False,
        error=error,
    )


def run_single_benchmark(
    instance: InstanceContext,
    bks: float | None = None,
    alns_iterations: int = 300,
    time_limit_sec: float = 1.5,
    *,
    instance_id: str | None = None,
    bks_source: str = "",
    bks_version: str = "",
    cp_sat_time_limit_sec: float = 0.5,
    random_seed: int = 42,
    run_baselines: bool = True,
    source: str = "",
    preprocessing_sec: float = 0.0,
) -> BenchmarkResult:
    """Runs the full Person 1 + Person 2 pipeline on one instance and times each stage.

    ``bks`` is authoritative reference metadata, not a target to be manufactured.
    When it is ``None`` the row reports ``N/A`` for the gap and is excluded from
    BKS-comparable aggregates.
    """
    resolved_id = instance_id or instance.instance_name
    total_start = time.perf_counter()

    try:
        alns_start = time.perf_counter()
        route_pool = explore_route_pool(
            instance,
            max_iterations=alns_iterations,
            time_limit_sec=time_limit_sec,
            seed=random_seed,
        )
        alns_sec = time.perf_counter() - alns_start

        master_start = time.perf_counter()
        schedule = solve_fleet_schedule(
            instance,
            route_pool,
            run_baselines=run_baselines,
            time_limit_seconds=cp_sat_time_limit_sec,
        )
        master_sec = time.perf_counter() - master_start

        audit_start = time.perf_counter()
        audit = audit_fleet_schedule(schedule, instance)
        audit_sec = time.perf_counter() - audit_start
    except Exception as exc:  # noqa: BLE001 - failures must surface as reported rows
        return _failed_row(
            instance,
            resolved_id,
            source,
            f"{type(exc).__name__}: {exc}",
            bks,
            bks_source,
            bks_version,
            preprocessing_sec,
        )

    total_latency = time.perf_counter() - total_start
    violations = list(audit["violations"])
    battery_violations = sum(1 for v in violations if "Battery" in v)

    reference_bks = bks if (bks is not None and bks > 0) else None
    gap: float | None = None
    if reference_bks is not None:
        gap = max(0.0, (reference_bks - schedule.cumulative_reward) / reference_bks) * 100.0

    wind_speed, wind_dir = _wind_fields(instance)
    return BenchmarkResult(
        instance_id=resolved_id,
        source=source or ("synthetic" if resolved_id.startswith(SYNTHETIC_PREFIX) else "context"),
        nodes=len(instance.targets),
        fleet_size=len(instance.drones),
        bks=reference_bks,
        bks_source=bks_source,
        bks_version=bks_version,
        wind_speed_mps=wind_speed,
        wind_direction_deg=wind_dir,
        aeroscan_score=schedule.cumulative_reward,
        grasp_score=schedule.baseline_grasp_reward,
        ga_score=schedule.baseline_ga_reward,
        reward_gain_pct=schedule.reward_gain_percent,
        gap_to_bks_pct=gap,
        preprocessing_sec=preprocessing_sec,
        alns_sec=alns_sec,
        master_sec=master_sec,
        audit_sec=audit_sec,
        total_latency_sec=total_latency,
        solver_latency_sec=alns_sec + master_sec,
        route_count=len(schedule.assigned_routes),
        battery_violations=battery_violations,
        violations=violations,
        schedule_status=schedule.status,
        validation_status="PASS" if audit["valid"] else "FAIL",
        completed=True,
    )


def aggregate_report(results: list[BenchmarkResult]) -> dict[str, Any]:
    """Aggregates rows with explicit, documented denominators.

    The average gap uses only completed rows that carry an authoritative BKS;
    latency uses only completed rows; battery violations sum over completed rows.
    A threshold with an empty denominator is reported as ``None`` (not evaluated)
    rather than satisfied.
    """
    completed = [r for r in results if r.completed]
    failed = [r for r in results if not r.completed]
    bks_comparable = [r for r in completed if r.bks_comparable]
    valid_schedules = [r for r in completed if r.validation_status == "PASS"]

    average_gap: float | None = None
    if bks_comparable:
        average_gap = statistics.fmean(r.gap_to_bks_pct for r in bks_comparable)  # type: ignore[misc]

    average_latency: float | None = None
    if completed:
        average_latency = statistics.fmean(r.total_latency_sec for r in completed)

    total_battery_violations = sum(r.battery_violations for r in completed) if completed else None

    def threshold(value: float | None, target: float, denominator: int) -> dict[str, Any]:
        return {
            "value": value,
            "target": target,
            "denominator": denominator,
            "met": (value <= target) if (value is not None and denominator > 0) else None,
        }

    return {
        "rows_total": len(results),
        "rows_completed": len(completed),
        "rows_failed": len(failed),
        "bks_comparable_instances": len(bks_comparable),
        "valid_schedules": len(valid_schedules),
        "average_gap_to_bks_pct": threshold(
            average_gap, PRD_MAX_AVERAGE_BKS_GAP_PCT, len(bks_comparable)
        ),
        "average_latency_sec": threshold(
            average_latency, PRD_MAX_AVERAGE_LATENCY_SEC, len(completed)
        ),
        "battery_violations": {
            "value": total_battery_violations,
            "target": PRD_MAX_BATTERY_VIOLATIONS,
            "denominator": len(completed),
            "met": (
                total_battery_violations <= PRD_MAX_BATTERY_VIOLATIONS
                if total_battery_violations is not None
                else None
            ),
        },
        "failed_instances": [r.instance_id for r in failed],
    }


@dataclass
class BenchmarkReport:
    """A complete, self-describing benchmark run."""

    rows: list[BenchmarkResult]
    summary: dict[str, Any]
    config: dict[str, Any]
    corpus: ChaoCorpusStatus | None = None
    notes: list[str] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([row.to_dict() for row in self.rows])

    def write(
        self, csv_path: str | Path | None = None, json_path: str | Path | None = None
    ) -> None:
        """Writes a deterministic CSV and/or a JSON sidecar with config and summary."""
        if csv_path is not None:
            csv_out = Path(csv_path)
            csv_out.parent.mkdir(parents=True, exist_ok=True)
            self.to_dataframe().to_csv(csv_out, index=False)
        if json_path is not None:
            json_out = Path(json_path)
            json_out.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "config": self.config,
                "environment": environment_info(),
                "summary": self.summary,
                "notes": self.notes,
                "corpus": (
                    {
                        "manifest_path": str(self.corpus.manifest_path),
                        "expected_instances": self.corpus.expected_instances,
                        "declared_instances": self.corpus.declared_instances,
                        "available_instances": self.corpus.available_instances,
                        "corpus_complete": self.corpus.corpus_complete,
                        "missing_files": list(self.corpus.missing_files),
                    }
                    if self.corpus is not None
                    else None
                ),
                "rows": [row.to_dict() for row in self.rows],
            }
            json_out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _run_entries(
    entries: list[tuple[InstanceContext, ChaoInstanceMetadata | None]],
    config: BenchmarkConfig,
    notes: list[str],
    corpus: ChaoCorpusStatus | None = None,
) -> BenchmarkReport:
    results: list[BenchmarkResult] = []
    for instance, meta in entries:
        if meta is not None:
            bks = meta.bks if not meta.synthetic else None
            results.append(
                run_single_benchmark(
                    instance,
                    bks=bks,
                    alns_iterations=config.alns_iterations,
                    time_limit_sec=config.alns_time_limit_sec,
                    instance_id=meta.instance_id,
                    bks_source=meta.source,
                    bks_version=meta.version,
                    cp_sat_time_limit_sec=config.cp_sat_time_limit_sec,
                    random_seed=config.random_seed,
                    run_baselines=config.run_baselines,
                    source=str(meta.path),
                )
            )
        else:
            results.append(
                run_single_benchmark(
                    instance,
                    bks=None,
                    alns_iterations=config.alns_iterations,
                    time_limit_sec=config.alns_time_limit_sec,
                    cp_sat_time_limit_sec=config.cp_sat_time_limit_sec,
                    random_seed=config.random_seed,
                    run_baselines=config.run_baselines,
                    source="synthetic",
                )
            )

    report = BenchmarkReport(
        rows=results,
        summary=aggregate_report(results),
        config=config.to_dict(),
        corpus=corpus,
        notes=notes,
    )
    report.write(config.output_csv, config.output_json)
    return report


def run_benchmark_suite(config: BenchmarkConfig | None = None) -> BenchmarkReport:
    """Runs the *official* manifest-backed suite. Requires corpus files on disk.

    Instances whose files are missing are reported as failed rows (with an
    actionable error) rather than silently skipped, and a run with no available
    official instance never claims to have measured the PRD thresholds.
    """
    config = config or BenchmarkConfig()
    status = corpus_status(config.manifest_path)
    notes = [status.describe()]

    entries = iter_instances(
        node_count=None,
        include_synthetic=False,
        manifest_path=config.manifest_path,
    )
    if config.sets:
        entries = [e for e in entries if e.set_name in config.sets]
    if config.instance_ids:
        wanted = set(config.instance_ids)
        entries = [e for e in entries if e.instance_id in wanted]
    if config.fleet_sizes:
        entries = [e for e in entries if e.vehicle_count in config.fleet_sizes]

    if not entries:
        notes.append(
            "No official instances matched the configuration; no solver work was performed."
        )
        return _run_entries([], config, notes, corpus=status)

    loaded: list[tuple[InstanceContext, ChaoInstanceMetadata | None]] = []
    failed: list[BenchmarkResult] = []
    for meta in entries:
        try:
            # The manifest declares each instance's fleet size; ``fleet_sizes``
            # filters instances rather than silently rescaling their fleet.
            instance = load_instance(
                meta.instance_id,
                manifest_path=config.manifest_path,
                adapter=config.adapter,
            )
            loaded.append((instance, meta))
        except Exception as exc:  # noqa: BLE001 - missing corpus files are reported rows
            failed.append(
                BenchmarkResult(
                    instance_id=meta.instance_id,
                    source=str(meta.path),
                    nodes=meta.node_count,
                    fleet_size=meta.vehicle_count,
                    bks=meta.bks,
                    bks_source=meta.source,
                    bks_version=meta.version,
                    completed=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )

    report = _run_entries(loaded, config, notes, corpus=status)
    report.rows.extend(failed)
    report.summary = aggregate_report(report.rows)
    report.write(config.output_csv, config.output_json)
    return report


def run_smoke_suite(config: BenchmarkConfig | None = None) -> BenchmarkReport:
    """Runs the checked-in deterministic fixture suite (no corpus required).

    Synthetic instances are named ``synthetic_*`` and are never reported as
    official BKS comparisons.
    """
    config = config or BenchmarkConfig()
    sets = config.sets or ["set_64", "set_66"]
    fleet_sizes = config.fleet_sizes or [2, 3]

    entries = [
        (get_synthetic_instance(set_name, num_drones=k), None)
        for set_name in sets
        for k in fleet_sizes
    ]
    notes = [
        "Smoke suite uses deterministic synthetic fixtures; results are NOT official BKS comparisons.",
        "Synthetic rows carry no BKS, so the average BKS gap is reported as not evaluated.",
    ]
    return _run_entries(entries, config, notes)


def _build_arg_parser():
    import argparse

    parser = argparse.ArgumentParser(description="AeroScan-Optima benchmark harness")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run the official manifest corpus suite instead of the synthetic smoke suite.",
    )
    parser.add_argument("--alns-iterations", type=int, default=200)
    parser.add_argument("--alns-time-limit", type=float, default=1.0)
    parser.add_argument("--cp-sat-time-limit", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--fleet-sizes", type=int, nargs="*", default=None)
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--output-json", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    config = BenchmarkConfig(
        fleet_sizes=args.fleet_sizes,
        alns_iterations=args.alns_iterations,
        alns_time_limit_sec=args.alns_time_limit,
        cp_sat_time_limit_sec=args.cp_sat_time_limit,
        random_seed=args.seed,
        output_csv=args.output_csv,
        output_json=args.output_json,
    )
    report = run_benchmark_suite(config) if args.full else run_smoke_suite(config)

    print("AeroScan-Optima Benchmark Report")
    print("=" * 60)
    for note in report.notes:
        print(f"! {note}")
    print(report.to_dataframe().to_string(index=False))
    print("-" * 60)
    print(json.dumps(report.summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
