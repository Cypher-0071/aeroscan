# Person 3 Handoff: `InstanceContext` Contract, Input Schemas & Benchmarks

**Owner**: Person 3 — Aerodynamics & Benchmark Engineer
**Owned modules**: `core/physics.py`, `core/instance.py`, `benchmarks/chao_loader.py`, `benchmarks/benchmark_runner.py`
**Consumers**: Person 1 (`core/alns.py`, `core/operators.py`), Person 2 (`core/set_packing.py`, `core/validator.py`), Person 4 (`app/`)

---

## 1. Public entry points

```python
from core.instance import build_instance_context      # mission → InstanceContext
from benchmarks.chao_loader import (
    load_instance,       # official instance by stable manifest ID
    load_chao_instance,  # any Chao-format file path
    iter_instances,      # manifest enumeration by set / node count / fleet size
    get_official_bks,    # authoritative BKS or None (never fabricated)
    corpus_status,       # how much of the official corpus is on disk
)
from benchmarks.benchmark_runner import (
    BenchmarkConfig, run_smoke_suite, run_benchmark_suite,
)
```

`build_instance_context(filepath, wind_speed_mps=None, wind_dir_deg=None, num_drones=None, aero_params=None, adapter=DEFAULT_CHAO_ADAPTER) -> InstanceContext`

---

## 2. Units and conventions

| Quantity | Unit / convention |
| --- | --- |
| Coordinates | meters (Cartesian). WGS-84 lat/lon is projected to meters at ingestion. |
| Time | seconds |
| Energy | Joules |
| Power | Watts |
| Angles at public input boundaries | degrees |
| `InstanceContext.ambient_wind` | `(speed_mps, direction_rad)` |
| Matrix axis order | same order as `InstanceContext.targets` |

**Always look up matrices by node ID** via `get_transit_time` / `get_transit_energy`. A node ID is not a matrix index.

### Wind convention

A wind vector is Cartesian and points in the direction the air mass moves **towards**:
`0° = +x` (East), increasing counter-clockwise (`90° = +y`/North). This is produced
by `core.physics.wind_to_vector`.

Mission files may instead carry a meteorological "blowing from" bearing as
`ambient_wind.direction_from_degrees`; it is converted at ingestion. Setting both
`direction_degrees` and `direction_from_degrees` is an error.

### Wind override semantics

| Call | Behavior |
| --- | --- |
| `wind_speed_mps=None, wind_dir_deg=None` | Use the wind declared in the file. |
| `wind_speed_mps=0.0, wind_dir_deg=0.0` | **Override** the file wind with zero wind. |
| Only one component supplied | The other defaults to `0.0`. |

`None` means "unspecified"; `0.0` means "intentionally calm". They are not interchangeable.

### Unreachable arcs (important for Persons 1 and 2)

When a track cannot be flown — crosswind greater than airspeed, or an exact/overwhelming
headwind — the directed arc is **unreachable**, not clamped to an artificially slow speed:

* `resolve_groundspeed(...)` returns `(math.inf, math.inf)`;
* both `time_matrix` and `energy_matrix` hold `np.inf` for that arc;
* `np.isfinite(time_matrix) == np.isfinite(energy_matrix)` is guaranteed.

`evaluate_route_trajectory` already propagates this: the route's energy/time becomes
`inf`, it fails the reserve/deadline check, and the function returns `None`.
Consumers must treat any non-finite matrix entry as infeasible and must never
`max()`/normalize a matrix containing `np.inf` without masking non-finite entries first.

### Dwell energy boundary

The transit matrices contain **transit only**. Target dwell energy is
`calculate_hover_power(params) * target.dwell_time`, exposed through the single
function `compute_dwell_energy(dwell_time, params)`. The route layer charges it and
must not add it a second time.

---

## 3. Supported input formats

| Format | Notes |
| --- | --- |
| `.json` | Mission JSON: `name`, `ambient_wind`, `drones`, `targets`. Targets use `x`/`y` (meters) **or** `longitude`/`latitude` + optional `origin`. |
| `.geojson` | `FeatureCollection` of `Point` features. `properties` carry `id`, `name`, `elevation`, `priority_score`, `dwell_time`. |
| `.csv` | Target table: required `id`, `priority_score`, and `x`/`y` **or** `longitude`/`latitude`; optional `name`, `elevation`, `dwell_time`. Fleet and wind come from a companion `<stem>.meta.json` sidecar — a bare CSV cannot describe a fleet, so no defaults are invented. |
| `.txt` | Chao et al. (1996) TOP format: `N K Tmax` then `N` records of `id x y score`. Exactly one zero-score depot is required. |

Unknown suffixes raise `ValueError` listing the supported types. Malformed data
raises `ValueError` naming the file, the JSON path or feature index, or the CSV row
number. Missing files raise `FileNotFoundError`.

Projection: WGS-84 inputs are projected once per mission with a dependency-free
equirectangular projection (`latlon_to_cartesian_meters`), using an explicit
`origin` when present, otherwise the first coordinate. The chosen CRS and origin are
recorded in the parse metadata. Do not feed raw longitude/latitude as meters.

---

## 4. Loader guarantees (tested invariants)

* targets are ordered deterministically and target IDs are unique;
* every drone `launch_depot_id`/`recovery_depot_id` exists in `targets`;
* drone IDs are unique, with positive `battery_joules`, `max_flight_time`,
  `cruise_speed`, and `safety_reserve_ratio` in `[0, 1)`;
* `time_matrix` and `energy_matrix` are square, `np.float64`, C-contiguous, sized to
  `len(targets)`, with a zero diagonal and matching unreachable-arc masks;
* heterogeneous fleet specs supplied in a file are preserved (only an explicit
  `num_drones` override clones the first spec);
* zero-valued priority scores and dwell times are retained exactly.

Verification helper: `core.instance.enforce_matrix_invariants`.

---

## 5. Fixtures

| Path | Purpose |
| --- | --- |
| `data/sample_mission.json` | Full Mountain SAR mission (20 targets, 3 drones). |
| `data/chao_instances/set_64_1.txt` | Checked-in Chao-format fixture (64 nodes, 3 vehicles). |
| `data/chao_instances/manifest.json` | Benchmark manifest: corpus declaration + instance rows. |
| `tests/fixtures/cartesian_mission.json` | Small Cartesian mission: arbitrary node IDs, 6 m/s east wind, zero dwell on one target. |
| `tests/fixtures/wgs84_mission.geojson` | GeoJSON WGS-84 with known north/east offsets and a meteorological "from" bearing. |
| `tests/fixtures/targets.csv` + `targets.meta.json` | CSV target table plus mission sidecar. |
| `tests/fixtures/tiny_chao.txt` | 5-node Chao-format fixture. |

**Handoff fixture for Persons 1, 2, 4** — asymmetric wind plus feasible and
infeasible arcs:

```python
from core.instance import build_instance_context
inst = build_instance_context(
    "tests/fixtures/cartesian_mission.json", wind_speed_mps=20.0, wind_dir_deg=90.0
)
# inst.time_matrix / inst.energy_matrix contain np.inf for untrackable arcs.
# Evaluate routes by node ID: inst.get_transit_time(100, 309)
```

---

## 6. Benchmarks

```bash
# Fast, deterministic smoke suite (synthetic fixtures, no corpus required)
uv run python -m benchmarks.benchmark_runner

# Official manifest/corpus suite
uv run python -m benchmarks.benchmark_runner --full \
    --output-csv reports/benchmark.csv --output-json reports/benchmark.json
```

Report rows include instance provenance, authoritative BKS + source/version, the
applied wind vector, per-stage latency (preprocess / ALNS / master / audit), total
vs solver latency, route count, battery violations, schedule status, validation
status, completion and error text. The JSON sidecar additionally records the full
`BenchmarkConfig` (including the `ChaoAdapterConfig` assumptions) and the
interpreter/library versions used for the run.

Report rules:

* a row with no authoritative BKS reports `N/A` for the gap and is excluded from
  the average-gap denominator — the runner never derives a reference score from the
  solver's own answer;
* a failing or unavailable downstream solver produces a visible failed row, not a
  substituted result;
* a PRD threshold with an empty denominator is reported as **not evaluated**, so a
  suite can never "pass" by running over nothing;
* output is deterministic: the CSV filename contains no timestamp unless the caller
  supplies one, and the JSON sidecar records the config, corpus status, and summary.

### Corpus status (honest reporting)

The 387-instance Chao corpus and its authoritative BKS table are **not** distributed
with this repository. `corpus_status()` reports the corpus as
`UNAVAILABLE/INCOMPLETE` and the manifest carries `bks: null` for the checked-in
fixture. The `>99.8%` BKS and `<2.5 s` latency claims must **not** be asserted until
the authorized instance files are added under `data/chao_instances/` and each is
listed in the manifest with its BKS source and version.

---

## 7. Verified status at handoff

Person 3 work is complete and verified: `pytest tests` passes 127 tests and
`ruff check .` is clean. Two measured findings are recorded here rather than
smoothed over, because both affect claims the team makes publicly.

### 7.1 The official corpus is absent

Only `data/chao_instances/set_64_1.txt` is checked in. `corpus_status()` therefore
reports `1 available, 1 declared, 387 expected` and `corpus_complete == False`, and
the manifest carries `bks: null`. No component asserts a BKS coverage or optimality
figure; gaps are `N/A` until authoritative metadata exists.

### 7.2 Measured latency exceeds the PRD target

With `--alns-iterations 20 --alns-time-limit 0.2`, the smoke CLI measured
`average_latency_sec ≈ 7.0` against the `2.5 s` PRD target, and the summary
correctly reported `met: false`. The cause is that `alns_time_limit_sec` does not
bound Person 1's seed construction, local search, or slack filling, so the wall
clock overruns the configured budget. This is a solver-performance issue, not a
reporting issue — the harness deliberately exposes it instead of hiding it.

---

## 8. Next actions (ordered)

1. **Bound ALNS latency** (Person 1) — make `explore_route_pool` honor
   `time_limit_sec` across seed construction, local search, and slack filling, so
   the benchmark latency target becomes measurable rather than aspirational.
   Acceptance: `average_latency_sec.met` is decided by real measurement.
2. **Mask non-finite matrix entries in the Shaw operator** (Person 1) —
   `destroy_shaw_relatedness` normalizes by the maximum transit time; with
   unreachable arcs that maximum is `inf` and relatedness becomes `nan`.
   Acceptance: destroy operators behave deterministically on a matrix containing
   `np.inf` (use the handoff fixture with `wind_speed_mps=20.0, wind_dir_deg=90.0`).
3. **Populate the corpus manifest** (Person 3, blocked) — add the authorized Chao
   instance files under `data/chao_instances/` with one manifest row each (path,
   set, nodes, vehicles, route-length budget, BKS, source, version, checksum).
   Acceptance: `corpus_complete` is `True` and average BKS gap is a measured value
   instead of `N/A`.

---

## 9. Open follow-ups

1. **Person 1**: `destroy_shaw_relatedness` normalizes by
   `max(np.max(time_matrix), 1.0)`. With unreachable arcs present that maximum is
   `inf`, producing `nan` relatedness values. Mask non-finite entries before
   normalizing.
2. **Team**: confirm depot nodes stay inside `InstanceContext.targets` (they do
   today) and whether heterogeneous cruise speeds eventually need per-drone
   matrices — the shared `[N, N]` contract assumes one cruise speed per instance.
3. **Team**: decide whether `pyproj`/UTM is required for broad geographic extents;
   the current projection is equirectangular and intended for compact SAR missions.
4. **Person 3 (blocked on corpus)**: populate the manifest with the authorized 387
   instances and per-instance BKS metadata, then measure — and report — the real
   gap and latency instead of assuming them (see §8).
