# Person 3 Implementation Plan: Physics, Instances, and Benchmarks

## Purpose and scope

This plan covers the work assigned by `docs/team_prd_person3_physics_benchmarks.md`:

- `core/physics.py`
- `core/instance.py`
- `benchmarks/chao_loader.py`
- `benchmarks/benchmark_runner.py`
- `tests/test_physics.py`
- `tests/test_instance.py`
- `tests/test_benchmarks.py`

The deliverable is a reliable `InstanceContext` for the ALNS engine, CP-SAT solver, and dashboard. It must contain validated metric coordinates, drone specifications, and float64 wind-corrected directed time and energy matrices. Person 3 owns preprocessing and benchmark reporting, not route construction, scheduling, baseline implementation, or UI behavior.

## Repository context gathered

### Existing implementation

| Area | Current state | Required follow-up |
| --- | --- | --- |
| Physics | BEMT-style hover power, cruise power, best-range grid search, wind groundspeed, dwell energy, and pairwise cost matrices exist. | Calibrate and document the parameter assumptions; define one unambiguous wind convention; make invalid wind cases explicit rather than silently turning them into a usable route. |
| Instance ingestion | JSON, GeoJSON feature collections, and a simplified Chao text format are parsed. Local equirectangular WGS-84 projection is available. | Add CSV support, robust schema validation, coordinate-system detection/normalization, detailed parse errors, and validation of depot and drone references. |
| Chao data | Only `data/chao_instances/set_64_1.txt` is checked in. The canonical loader synthesizes four topologies and has a small set-level BKS table. | Replace synthetic benchmark generation as the benchmark source with a manifest-driven loader for the actual 387 files and per-instance BKS metadata. Retain synthetic instances only as explicit test fixtures if useful. |
| Benchmark runner | It can run the Person 1 and Person 2 pipeline and create a DataFrame/optional CSV. | Make corpus discovery, result provenance, failure handling, aggregate acceptance calculations, reproducible configuration, and CSV output first-class. |
| Tests | Tests cover hover range, asymmetric wind, basic JSON/text parsing, and one end-to-end synthetic benchmark. | Add requirements-level tests for all formats, invariants, deterministic datasets, bad inputs, benchmark manifest coverage, and report metrics. |

### Important integration facts

- `core/contracts.py` is the shared contract. Do not change its public fields without agreement from Persons 1, 2, and 4. Its matrix axis order follows the order of `InstanceContext.targets`; consumers must use node IDs through `get_transit_time` and `get_transit_energy`, not use a node ID as a raw matrix index.
- Person 1 consumes `InstanceContext` through `core/alns.py` and route evaluation. Person 2 consumes it through the set-packing/validator path. Person 4 uses it to display maps and mission metadata.
- Travel matrices describe transit only. Target dwell energy remains `calculate_hover_power(...) * target.dwell_time` and is charged by route evaluation. This boundary must stay documented and tested so dwell energy is not accidentally added twice.
- Benchmark execution is an integration activity. The loader and report format can be built independently, but the final score and validation fields require Person 1 and Person 2 APIs to be stable.

## Decisions to settle before implementation

1. **Wind direction convention.** Publish one convention for every public API: recommended convention is a Cartesian vector expressed as the direction the air mass moves, with `0° = +x/East` and angles increasing counter-clockwise. If mission input must support meteorological "from" bearings, convert them at ingestion and name the source field `direction_from_degrees`. The current prose and code do not agree, so this must be fixed before adding data.
2. **Wind feasibility policy.** A crosswind stronger than a drone's airspeed makes a track untrackable. Recommended behavior is to mark that directed arc unreachable (`time_matrix` and `energy_matrix` are `np.inf`) rather than clamp it to `0.5 m/s`, which can create a physically impossible but solver-feasible flight. Exact-headwind cases need the same explicit policy.
3. **Projection policy.** Keep the dependency-free local equirectangular projection for compact SAR missions. For UTM accuracy or broad geographic extents, add `pyproj` as an explicit project dependency and record the chosen CRS/origin in parsing metadata or the instance name/report. Do not silently treat longitude/latitude as meter coordinates.
4. **Benchmark source of truth.** Obtain a licensed/versioned 387-instance corpus plus an authoritative per-instance BKS table. Do not claim the PRD's 99.8% BKS result from synthetic geometries or a fabricated fallback BKS.
5. **Benchmark semantics.** Chao TOP scores and route-length budgets are not physically identical to UAV energy constraints. Define and document the adapter: how Chao distance/budget maps to `max_flight_time`, energy capacity, dwell time, and wind. Run official BKS comparisons under a compatibility configuration, and label any physics-enabled run as a separate scenario rather than comparing it directly to published BKS.

## Implementation sequence

### Step 1: Freeze the Person 3 contract and acceptance inputs

1. Read `core/contracts.py`, the three downstream modules, and their tests before changing the producer behavior.
2. Add a short module-level contract note in the Person 3 code documenting units: meters, seconds, Joules, Watts, degrees at public input boundaries, and radians only where stored internally.
3. Define loader guarantees:
   - targets are ordered deterministically;
   - target IDs are unique;
   - all drone launch/recovery depot IDs exist;
   - matrices are C-contiguous `np.float64`, square, and match target count;
   - diagonal matrix entries are zero;
   - unreachable arcs are represented consistently;
   - `ambient_wind` has one documented representation.
4. Confirm with the team whether depot nodes remain inside `InstanceContext.targets` (the current contract does this) and whether heterogeneous cruise speeds require per-drone matrices. Do not quietly change a shared `[N, N]` matrix contract.
5. Create fixtures for one Cartesian mission, one WGS-84 mission, one CSV mission, malformed inputs, and a tiny known Chao-format file. Fixtures must be small, static, and human-readable.

**Exit criteria:** a written public-input convention and a testable invariant list are agreed; no downstream code needs to infer units or matrix indexing.

### Step 2: Harden `core/physics.py`

1. Replace mutable dataclass default instances in public function signatures with `params: DroneAeroParams | None = None`, resolving the default inside the function. This prevents shared mutable defaults while preserving the API's behavior.
2. Keep `DroneAeroParams` as the single source for mass, rotor geometry, air density, drag, payload, and avionics assumptions. Clarify whether `avionics_power_w` includes the sensor payload and use names that match that decision.
3. Validate physical parameter domains at the boundary: positive mass/radius/density/tip speeds, non-negative power terms, and positive airspeed search bounds. Raise a useful `ValueError` for invalid parameters.
4. Refactor hover power into named induced, profile, and payload/avionics components internally or through a diagnostic helper. Preserve `calculate_hover_power` as the simple public result used by the route layer.
5. Make the cruise polar numerically robust at small positive speed. Reject zero or negative speeds in energy-per-distance calculations instead of allowing division by zero or a misleading optimum.
6. Make `find_best_range_speed` deterministic and configurable: validate the search interval and resolution, then return the minimizing airspeed. Use a bounded scalar minimizer only if adding SciPy dependence is justified; the current NumPy grid is sufficient if its resolution is explicit and tested.
7. Implement the selected wind convention once through a `wind_to_vector(...)` helper. `resolve_groundspeed` should accept a Cartesian vector only, which avoids direction-convention duplication.
8. Implement the selected unreachable-arc policy in `resolve_groundspeed` and surface it through `compute_cost_matrices`. Do not convert impossible physics into an arbitrarily slow valid arc.
9. Compute cost matrices using preallocated C-contiguous float64 arrays. Verify zero-wind symmetry, directed asymmetry under wind, zeros on the diagonal, finite values only for reachable arcs, and consistent energy units.
10. Keep dwell energy separate from transit cost matrices and expose a single `compute_dwell_energy` calculation for route consumers.

**Exit criteria:** the default hover result is within the PRD target band, the best-range result has a documented value/range, wind direction and infeasibility behavior are explicit, and every physics result has unit/invariant tests.

### Step 3: Complete `core/instance.py`

1. Split parsing from context construction so each parser returns normalized records and only the builder creates matrices. This makes parser tests independent of aerodynamic calculations.
2. Add an input-format dispatcher for `.json`, `.geojson`, `.csv`, and `.txt`; reject unknown suffixes with a message listing supported types.
3. Define and implement a CSV schema for targets, with required `id`, `x`, `y`, and `priority_score` columns plus optional name, elevation, dwell time, coordinate-system fields, and a documented way to supply fleet/wind metadata. If a single CSV cannot safely describe a fleet, require a companion mission JSON instead of inventing defaults invisibly.
4. Strengthen JSON parsing:
   - support current mission JSON and GeoJSON `FeatureCollection` inputs;
   - validate geometry type and coordinate arity;
   - distinguish explicit Cartesian `x/y` from WGS-84 `longitude/latitude`;
   - retain zero-valued scores and dwell times exactly;
   - report the JSON path/feature index for malformed data.
5. Project raw WGS-84 coordinates into meters before creating `TargetNode`s. Use one origin/CRS per mission and test known north/east offsets. Preserve the simple local projection unless the team elects `pyproj` in Step 1.
6. Strengthen Chao text parsing:
   - validate header fields and declared node count;
   - validate every node record, duplicate IDs, and exactly one declared depot strategy;
   - preserve the source budget and fleet size;
   - isolate any adapter assumptions such as dwell times and battery capacity in named configuration, not hard-coded parser behavior.
7. Validate the fleet after parsing: non-empty fleet where required, unique drone IDs, positive energy/time/speed, and existing launch/recovery depots. Preserve explicitly configured heterogeneous specs.
8. Build matrix coordinates in the same deterministic order as `targets`, call the physics engine, enforce the Step 1 matrix invariants, then construct `InstanceContext`.
9. Clarify wind override behavior. Recommended: `None` means use file wind; a supplied value, including `0.0`, explicitly overrides it. The existing default arguments cannot distinguish an intentional zero-wind override from omission.

**Exit criteria:** all advertised input formats produce a validated, deterministic `InstanceContext`; invalid files fail with actionable messages; file wind, override wind, depots, and matrix ordering are unambiguous.

### Step 4: Replace synthetic Chao benchmarking with corpus-backed loading

1. Add a benchmark manifest, for example `data/chao_instances/manifest.json` or a versioned CSV, with one row per official instance: relative path, set, instance ID, node count, vehicle count, route-length budget, BKS, source/version, and optional checksum.
2. Add all authorized raw instance files under `data/chao_instances/` or document a reproducible, non-committed acquisition step if redistribution is not permitted. Do not write generated benchmark files into source directories during normal test runs.
3. Refactor `benchmarks/chao_loader.py` to:
   - discover instances from the manifest rather than hard-coded set names;
   - load a specific instance by stable ID/path;
   - expose filtered enumeration by set, node count, and fleet size;
   - return official BKS from manifest metadata;
   - check file existence, declared dimensions, and checksums where applicable.
4. Remove the use of Python's randomized `hash(set_name)` seed for benchmark generation. If synthetic helper instances remain, use an explicit fixed seed and name them `synthetic_*` so they cannot be confused with Chao data.
5. Keep a compact checked-in fixture subset for fast unit tests. Mark full-387 execution as an integration/benchmark command and skip it with a clear reason when the corpus is absent.
6. Make the Chao-to-UAV adapter explicit and configurable. The benchmark report must record adapter parameters, wind, battery reserve, dwell policy, and solver versions/configuration.

**Exit criteria:** the loader can prove that all expected corpus entries are present and unique, retrieve an official BKS without fallbacks, and distinguish official from synthetic instances in both API results and reports.

### Step 5: Make `benchmarks/benchmark_runner.py` reproducible and auditable

1. Define a `BenchmarkConfig` dataclass with instance selection, fleet-size selection, physics/adapter settings, ALNS iteration/time limit, CP-SAT limit if exposed, random seed, output path, and whether baselines run.
2. Define a report row schema that includes: instance ID/source, BKS, score, gap, GRASP/GA scores, latency split by preprocessing/ALNS/master/audit, route count, battery violations, schedule status, validation status, and error text when a run fails.
3. Change `run_single_benchmark` to accept explicit instance metadata rather than manufacturing a BKS from the returned score. Missing BKS must yield `N/A`, not a calculated near-optimal score.
4. Measure each stage with `time.perf_counter()` and keep total latency distinct from solver-only latency. This is required to support the PRD's latency claims honestly.
5. Run the pipeline through stable public entry points from Persons 1 and 2. Treat an unavailable or failed downstream solver as a reported failed row; do not hide it by substituting a synthetic result.
6. Calculate fleet-level safety from `audit_fleet_schedule` and retain all violations, not only strings containing `Battery`.
7. Aggregate results with documented denominators: completed official instances, BKS-comparable instances, valid schedules, and failed/skipped instances. Calculate average gap only from rows with an official BKS and completed schedule.
8. Always write a deterministic CSV when requested and optionally a JSON sidecar containing configuration, environment versions, timestamps, and summary metrics. Do not use a timestamp in the report filename unless the caller asks for one.
9. Provide a small smoke-suite CLI/default that uses checked-in fixtures, and a separate full-suite command requiring the manifest/corpus. The full suite must report whether it meets `<0.15%` average BKS gap, `<2.5s` average latency, and zero battery violations; it must never claim these thresholds merely because the runner executed.

**Exit criteria:** a benchmark report is reproducible from its config and data version, every aggregate can be traced to rows, failures are visible, and BKS metrics use authoritative metadata only.

### Step 6: Expand the Person 3 test suite

1. Add physics unit tests for component/domain validation, zero-wind symmetry, tailwind/headwind asymmetry, crosswind behavior, impossible-wind policy, diagonal zeros, float64 contiguous matrices, and `dwell_energy == hover_power * dwell_time`.
2. Add an expected-value/regression test for the calibrated default hover power and a bounded best-range speed result. Avoid over-precise assertions where a documented numerical search resolution is intentional.
3. Add parser tests for JSON Cartesian missions, GeoJSON WGS-84 projection, CSV input, raw Chao text, wind overrides including intentional zero wind, non-contiguous IDs, multiple depots if supported, malformed records, duplicate IDs, missing depots, bad fleet specs, and declared-count mismatches.
4. Add context-invariant tests covering matrix shape/dtype/contiguity, node ID lookup correctness, deterministic ordering, and no double-counted dwell energy.
5. Add Chao-loader tests for manifest completeness, lookup by stable ID, per-instance BKS retrieval, corrupted/missing fixture behavior, and deterministic synthetic fixtures if retained.
6. Add runner tests with mocked/stubbed Person 1 and Person 2 pipeline calls so report math, missing BKS, failure rows, CSV contents, and aggregate denominators can be tested without expensive optimization.
7. Retain one small genuine integration test against the checked-in Chao fixture once the downstream APIs are stable. Bound its time limit and assert safety/format properties instead of a benchmark-performance claim.
8. Run the owned test set first, then the full repository suite, and run Ruff after implementation. Record benchmark results separately from unit-test results.

**Exit criteria:** every PRD behavior is represented by a fast deterministic test or a clearly labeled integration benchmark, and owned tests do not depend on unavailable full-corpus data.

### Step 7: Integrate and hand off

1. Give Person 1 a sample `InstanceContext` covering asymmetric wind, arbitrary node IDs, and feasible/infeasible arcs. Confirm route evaluation handles the chosen `np.inf` policy.
2. Give Person 2 the same fixture and confirm validator behavior for matrix lookups, reserve accounting, and an empty safe route.
3. Give Person 4 a mission fixture with stable target/depot metadata and verify the UI can read coordinates, wind metadata, and schedule-facing node IDs without raw matrix access.
4. Publish the loader entry point, input schemas, units, wind convention, error behavior, fixture paths, and benchmark command in the README or an appropriate technical doc.
5. Run one end-to-end mission with `data/sample_mission.json`, one official-format fixture with zero wind, and one wind-enabled case. Archive the generated benchmark report outside tracked source data unless it is an intentional reviewed artifact.

**Exit criteria:** all three consumers can construct and use the produced `InstanceContext`; the team has a documented command and data prerequisites for smoke and full benchmarks.

## Definition of done

- All four owned modules implement the PRD requirements that are feasible with the agreed corpus and adapter policy.
- JSON, GeoJSON, CSV, and Chao text ingestion are validated and unit-tested.
- Physics matrices use documented units, wind direction semantics, and unreachable-arc behavior.
- The official benchmark manifest covers 387 known instances, or the repository clearly reports the corpus as unavailable and does not make the coverage claim.
- Benchmark reports never fabricate BKS or suppress failed runs.
- Owned tests, full tests, and lint pass in the project environment.
- Downstream owners have a versioned, documented `InstanceContext` handoff fixture and no unresolved ambiguity about matrix indexing, depots, dwell charging, or wind metadata.

## Suggested execution order for a short hackathon window

1. Settle wind and Chao-adapter decisions; add contract-invariant tests.
2. Harden physics and context building because every downstream module relies on them.
3. Add CSV/GeoJSON validation and fixtures.
4. Build the manifest-backed loader and compact benchmark fixture path.
5. Refactor runner reporting with mocked downstream calls.
6. Integrate against the real ALNS/CP-SAT pipeline and run the smoke suite.
7. Acquire/run the full corpus only after the above is stable; treat its measured results as evidence, not an assumption.
