"""Unit tests for the manifest-backed Chao loader and the benchmark harness."""

import json
from pathlib import Path

import pytest

import benchmarks.benchmark_runner as runner
from benchmarks.benchmark_runner import (
    BenchmarkConfig,
    BenchmarkResult,
    aggregate_report,
    run_benchmark_suite,
    run_single_benchmark,
    run_smoke_suite,
)
from benchmarks.chao_loader import (
    ChaoManifestError,
    corpus_status,
    get_instance_metadata,
    get_official_bks,
    get_synthetic_instance,
    iter_instances,
    load_chao_instance,
    load_instance,
    load_manifest,
    validate_instance_file,
)
from core.contracts import FleetSchedule, RoutePool

FIXTURES = Path(__file__).parent / "fixtures"
TINY_CHAO = FIXTURES / "tiny_chao.txt"


# ---------------------------------------------------------------------------
# Pipeline stub: keeps runner tests cheap and independent of the optimizers
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_pipeline(monkeypatch):
    state = {"reward": 100.0, "violations": [], "status": "OPTIMAL"}

    def fake_explore(instance, max_iterations=400, time_limit_sec=1.8, seed=42):
        return RoutePool()

    def fake_solve(instance, route_pool, run_baselines=True, time_limit_seconds=0.5):
        return FleetSchedule(
            status=state["status"],
            solve_time_seconds=0.01,
            cumulative_reward=state["reward"],
            assigned_routes=[],
            unassigned_targets=[],
            validation_passed=True,
            baseline_grasp_reward=state["reward"] * 0.8,
            baseline_ga_reward=state["reward"] * 0.9,
            reward_gain_percent=25.0,
        )

    def fake_audit(schedule, instance):
        return {
            "valid": not state["violations"],
            "violations": list(state["violations"]),
            "total_routes_checked": 0,
            "total_targets_visited": 0,
            "cumulative_reward": schedule.cumulative_reward,
        }

    monkeypatch.setattr(runner, "explore_route_pool", fake_explore)
    monkeypatch.setattr(runner, "solve_fleet_schedule", fake_solve)
    monkeypatch.setattr(runner, "audit_fleet_schedule", fake_audit)
    return state


def _write_manifest(tmp_path: Path, instances: list[dict], expected: int = 387) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"corpus": {"expected_instances": expected}, "instances": instances}),
        encoding="utf-8",
    )
    return path


def _tiny_entry(**overrides) -> dict:
    entry = {
        "instance_id": "tiny_1",
        "set": "set_tiny",
        "path": str(TINY_CHAO),
        "nodes": 5,
        "vehicles": 2,
        "route_length_budget": 600.0,
        "bks": None,
        "source": "test fixture",
        "version": "fixture",
    }
    entry.update(overrides)
    return entry


# ---------------------------------------------------------------------------
# Manifest and corpus status
# ---------------------------------------------------------------------------


def test_manifest_is_valid_and_ids_are_unique():
    _raw, entries = load_manifest()
    ids = [entry.instance_id for entry in entries]
    assert len(ids) == len(set(ids))
    assert "set_64_1" in ids
    entry = get_instance_metadata("set_64_1")
    assert entry.node_count == 64
    assert entry.vehicle_count == 3
    assert entry.path.name == "set_64_1.txt"
    assert entry.available


def test_corpus_status_does_not_claim_full_coverage():
    status = corpus_status()
    assert status.expected_instances == 387
    assert status.corpus_complete is False
    assert "UNAVAILABLE" in status.describe() or "INCOMPLETE" in status.describe()
    assert status.available_instances <= status.declared_instances


def test_get_instance_metadata_unknown_id_raises():
    with pytest.raises(KeyError):
        get_instance_metadata("does_not_exist")


def test_official_bks_is_never_fabricated():
    """A fixture without authoritative BKS metadata reports None, not a derived score."""
    assert get_official_bks("set_64_1") is None


def test_iter_instances_filters_by_set_nodes_and_fleet():
    assert [e.instance_id for e in iter_instances(set_name="set_64")] == ["set_64_1"]
    assert [e.instance_id for e in iter_instances(node_count=64)] == ["set_64_1"]
    assert iter_instances(fleet_size=999) == []
    # Synthetic entries are excluded from official enumeration by default.
    assert all(not entry.synthetic for entry in iter_instances())


def test_missing_corpus_file_is_reported(tmp_path):
    manifest = _write_manifest(tmp_path, [_tiny_entry(path="not_present.txt")])
    entry = get_instance_metadata("tiny_1", manifest)
    with pytest.raises(FileNotFoundError, match="not redistributed"):
        validate_instance_file(entry)


def test_checksum_mismatch_is_detected(tmp_path):
    manifest = _write_manifest(tmp_path, [_tiny_entry(checksum="0" * 64)])
    entry = get_instance_metadata("tiny_1", manifest)
    with pytest.raises(ChaoManifestError, match="checksum mismatch"):
        validate_instance_file(entry)


def test_declared_dimension_mismatch_is_detected(tmp_path):
    manifest = _write_manifest(tmp_path, [_tiny_entry(nodes=99)])
    entry = get_instance_metadata("tiny_1", manifest)
    with pytest.raises(ChaoManifestError, match="declares 99 nodes"):
        validate_instance_file(entry)


def test_duplicate_manifest_ids_rejected(tmp_path):
    manifest = _write_manifest(tmp_path, [_tiny_entry(), _tiny_entry()])
    with pytest.raises(ChaoManifestError, match="duplicate instance_id"):
        load_manifest(manifest)


def test_malformed_manifest_rejected(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ChaoManifestError, match="invalid JSON"):
        load_manifest(path)
    with pytest.raises(ChaoManifestError, match="not found"):
        load_manifest(tmp_path / "absent.json")


def test_load_instance_by_stable_id():
    inst = load_instance("set_64_1")
    assert inst.instance_name == "set_64_1"
    assert len(inst.targets) == 64


def test_synthetic_fixtures_are_deterministic_and_labelled():
    first = get_synthetic_instance("set_66", num_drones=2)
    second = get_synthetic_instance("set_66", num_drones=2)
    assert first.instance_name.startswith("synthetic_")
    assert [n.x for n in first.targets] == [n.x for n in second.targets]
    assert (first.time_matrix == second.time_matrix).all()
    # A different seed must produce a different fixture.
    other = get_synthetic_instance("set_66", num_drones=2, seed=999)
    assert [n.x for n in other.targets] != [n.x for n in first.targets]
    with pytest.raises(KeyError):
        get_synthetic_instance("set_unknown")


# ---------------------------------------------------------------------------
# run_single_benchmark
# ---------------------------------------------------------------------------


def test_run_single_benchmark_without_bks_reports_na(stub_pipeline):
    inst = get_synthetic_instance("set_64", num_drones=2)
    result = run_single_benchmark(inst, bks=None, alns_iterations=10, time_limit_sec=0.01)

    assert result.completed is True
    assert result.bks is None
    assert result.gap_to_bks_pct is None
    assert result.to_dict()["Gap to BKS (%)"] == "N/A"
    assert result.to_dict()["BKS"] == "N/A"
    assert result.bks_comparable is False
    assert result.validation_status == "PASS"
    assert result.solver_latency_sec <= result.total_latency_sec


def test_run_single_benchmark_gap_uses_authoritative_bks(stub_pipeline):
    stub_pipeline["reward"] = 100.0
    inst = get_synthetic_instance("set_64", num_drones=2)
    result = run_single_benchmark(inst, bks=125.0, bks_source="paper", bks_version="v1")

    assert result.gap_to_bks_pct == pytest.approx(20.0)
    assert result.bks_source == "paper"
    assert result.bks_version == "v1"
    assert result.bks_comparable is True


def test_run_single_benchmark_records_failures_instead_of_hiding_them(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("solver unavailable")

    monkeypatch.setattr(runner, "explore_route_pool", boom)
    inst = get_synthetic_instance("set_64", num_drones=2)
    result = run_single_benchmark(inst, bks=100.0)

    assert result.completed is False
    assert result.aeroscan_score is None
    assert result.gap_to_bks_pct is None
    assert result.validation_status == "N/A"
    assert "solver unavailable" in result.error


def test_run_single_benchmark_counts_battery_violations(stub_pipeline):
    stub_pipeline["violations"] = ["Battery reserve violation on UAV-01", "Deadline violation on UAV-02"]
    inst = get_synthetic_instance("set_64", num_drones=2)
    result = run_single_benchmark(inst)

    assert result.validation_status == "FAIL"
    assert result.battery_violations == 1
    assert len(result.violations) == 2


# ---------------------------------------------------------------------------
# Aggregation denominators
# ---------------------------------------------------------------------------


def _row(instance_id: str, *, completed=True, bks=None, gap=None, latency=1.0, violations=0) -> BenchmarkResult:
    return BenchmarkResult(
        instance_id=instance_id,
        source="test",
        nodes=5,
        fleet_size=1,
        bks=bks,
        gap_to_bks_pct=gap,
        total_latency_sec=latency,
        battery_violations=violations,
        validation_status="PASS" if completed else "N/A",
        completed=completed,
        error=None if completed else "boom",
    )


def test_aggregate_uses_documented_denominators():
    rows = [
        _row("a", bks=120.0, gap=1.0, latency=1.0),
        _row("b", bks=None, gap=None, latency=3.0),
        _row("c", completed=False),
    ]
    summary = aggregate_report(rows)

    assert summary["rows_total"] == 3
    assert summary["rows_completed"] == 2
    assert summary["rows_failed"] == 1
    assert summary["bks_comparable_instances"] == 1
    assert summary["average_gap_to_bks_pct"]["value"] == pytest.approx(1.0)
    assert summary["average_gap_to_bks_pct"]["denominator"] == 1
    assert summary["average_latency_sec"]["value"] == pytest.approx(2.0)
    assert summary["average_latency_sec"]["denominator"] == 2
    assert summary["failed_instances"] == ["c"]


def test_aggregate_thresholds_are_not_evaluated_without_a_denominator():
    summary = aggregate_report([])
    assert summary["average_gap_to_bks_pct"]["met"] is None
    assert summary["average_latency_sec"]["met"] is None
    assert summary["battery_violations"]["met"] is None


def test_aggregate_flags_threshold_failures():
    rows = [_row("a", bks=100.0, gap=5.0, latency=4.0, violations=2)]
    summary = aggregate_report(rows)
    assert summary["average_gap_to_bks_pct"]["met"] is False
    assert summary["average_latency_sec"]["met"] is False
    assert summary["battery_violations"]["met"] is False


# ---------------------------------------------------------------------------
# Suites and report output
# ---------------------------------------------------------------------------


def test_smoke_suite_labels_synthetic_results_and_writes_reports(tmp_path, stub_pipeline):
    csv_path = tmp_path / "smoke.csv"
    json_path = tmp_path / "smoke.json"
    config = BenchmarkConfig(
        sets=["set_64"], fleet_sizes=[2], output_csv=csv_path, output_json=json_path
    )
    report = run_smoke_suite(config)

    assert len(report.rows) == 1
    assert report.rows[0].instance_id.startswith("synthetic_")
    assert report.rows[0].bks is None
    assert report.summary["bks_comparable_instances"] == 0
    assert any("NOT official BKS comparisons" in note for note in report.notes)

    frame = report.to_dataframe()
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "Instance,Source,Nodes" in csv_text
    assert "N/A" in csv_text
    assert "Wind (m/s)" in csv_text
    assert list(frame["Instance"]) == ["synthetic_set_64"]

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["summary"]["rows_total"] == 1
    assert payload["config"]["random_seed"] == 42
    # Adapter assumptions and environment versions are recorded for reproducibility.
    assert payload["config"]["adapter"]["battery_joules"] == 360000.0
    assert payload["environment"]["python"]
    assert "numpy" in payload["environment"]["packages"]
    assert payload["rows"][0]["Instance"] == "synthetic_set_64"
    assert payload["rows"][0]["Wind (m/s)"] == 0.0


def test_smoke_suite_is_reproducible(stub_pipeline):
    config = BenchmarkConfig(sets=["set_66"], fleet_sizes=[2])
    first = run_smoke_suite(config)
    second = run_smoke_suite(config)
    assert [r.to_dict() for r in first.rows] == [r.to_dict() for r in second.rows]


def test_full_suite_requires_corpus_and_reports_failed_rows(tmp_path, stub_pipeline):
    """A manifest entry whose file is absent becomes a visible failed row."""
    manifest = _write_manifest(
        tmp_path,
        [_tiny_entry(), _tiny_entry(instance_id="tiny_2", path="missing.txt")],
    )
    config = BenchmarkConfig(manifest_path=manifest)
    report = run_benchmark_suite(config)

    by_id = {row.instance_id: row for row in report.rows}
    assert set(by_id) == {"tiny_1", "tiny_2"}
    assert by_id["tiny_1"].completed is True
    assert by_id["tiny_1"].bks is None
    assert by_id["tiny_2"].completed is False
    assert "not redistributed" in by_id["tiny_2"].error
    assert report.summary["rows_failed"] == 1
    assert "UNAVAILABLE" in report.notes[0] or "INCOMPLETE" in report.notes[0]


def test_full_suite_with_no_matching_instances_does_not_claim_thresholds(stub_pipeline):
    config = BenchmarkConfig(instance_ids=["nope"])
    report = run_benchmark_suite(config)
    assert report.rows == []
    assert report.summary["average_gap_to_bks_pct"]["met"] is None
    assert any("No official instances matched" in note for note in report.notes)


def test_full_suite_loads_real_manifest_instance(stub_pipeline):
    """End-to-end wiring against the checked-in Chao fixture (no BKS claimed)."""
    config = BenchmarkConfig(instance_ids=["set_64_1"], alns_iterations=5, alns_time_limit_sec=0.01)
    report = run_benchmark_suite(config)

    assert len(report.rows) == 1
    row = report.rows[0]
    assert row.instance_id == "set_64_1"
    assert row.nodes == 64
    assert row.completed is True
    assert row.bks is None
    assert row.to_dict()["Gap to BKS (%)"] == "N/A"


def test_real_pipeline_integration_on_tiny_chao_fixture():
    """Genuine (unstubbed) integration against the 5-node Chao fixture.

    Asserts safety and report-format properties under a bounded time limit, not a
    benchmark-performance claim.
    """
    instance = load_chao_instance(TINY_CHAO)
    assert instance.instance_name == "tiny_chao"

    result = run_single_benchmark(
        instance,
        bks=None,
        alns_iterations=30,
        time_limit_sec=0.2,
        run_baselines=False,
        cp_sat_time_limit_sec=0.2,
        instance_id="tiny_chao",
    )

    assert result.completed is True, result.error
    assert result.validation_status == "PASS"
    assert result.battery_violations == 0
    assert result.violations == []
    assert result.aeroscan_score is not None and result.aeroscan_score >= 0.0
    assert result.gap_to_bks_pct is None
    assert result.total_latency_sec >= result.solver_latency_sec >= 0.0
