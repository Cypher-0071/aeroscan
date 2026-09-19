"""Unit tests for Chao benchmark loader and automated harness."""


from benchmarks.benchmark_runner import run_single_benchmark
from benchmarks.chao_loader import get_canonical_chao_instance


def test_chao_canonical_loader():
    """Verify loading canonical Chao benchmark instance sets."""
    inst_64 = get_canonical_chao_instance("set_64", num_drones=3)
    assert len(inst_64.targets) == 64
    assert len(inst_64.drones) == 3
    assert inst_64.targets[0].priority_score == 0.0  # Depot

    inst_66 = get_canonical_chao_instance("set_66", num_drones=2)
    assert len(inst_66.targets) == 66
    assert len(inst_66.drones) == 2


def test_run_single_benchmark_execution():
    """Verify end-to-end execution of a single benchmark run."""
    inst = get_canonical_chao_instance("set_64", num_drones=2)
    res = run_single_benchmark(inst, bks=440.0, alns_iterations=80, time_limit_sec=0.5)

    assert res.nodes == 64
    assert res.fleet_size == 2
    assert res.aeroscan_score > 0.0
    assert res.battery_violations == 0
    assert res.validation_status == "PASS"
