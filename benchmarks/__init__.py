"""Benchmark suite and automated harness for AeroScan-Optima."""

from benchmarks.benchmark_runner import (
    BenchmarkConfig,
    aggregate_report,
    run_benchmark_suite,
    run_single_benchmark,
    run_smoke_suite,
)
from benchmarks.chao_loader import (
    ChaoInstanceMetadata,
    corpus_status,
    get_canonical_chao_instance,
    get_instance_metadata,
    get_official_bks,
    get_synthetic_instance,
    iter_instances,
    load_chao_instance,
    load_instance,
    load_manifest,
)

__all__ = [
    "BenchmarkConfig",
    "ChaoInstanceMetadata",
    "aggregate_report",
    "corpus_status",
    "get_canonical_chao_instance",
    "get_instance_metadata",
    "get_official_bks",
    "get_synthetic_instance",
    "iter_instances",
    "load_chao_instance",
    "load_instance",
    "load_manifest",
    "run_benchmark_suite",
    "run_single_benchmark",
    "run_smoke_suite",
]
