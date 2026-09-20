# AeroScan-Optima: Matheuristic Multi-Drone Search Coverage Platform

> **Target Track**: Optimization Track — Problem Statement 05 (Multi-Drone Search Coverage Under Energy Constraints / TOP-DC)  
> **Team**: AeroScan-Optima Engineering Team  
> **Version**: 1.0.0

---

## Overview

**AeroScan-Optima** is an enterprise-grade autonomous aerial mission planning and optimization platform designed for critical time-sensitive operations, including disaster search-and-rescue (SAR), pipeline surveillance, forest fire perimeter tracking, and maritime reconnaissance.

The platform solves the **Team Orienteering Problem with Drone Constraints (TOP-DC)**: dispatching a heterogeneous fleet of uncrewed aerial vehicles (UAVs) with strict battery endurance limits across non-uniform, high-priority target zones to maximize cumulative search score while guaranteeing zero battery exhaustion, respecting operational safety reserves, and delivering mathematically certified schedules in sub-3-second latency.

---

## Key Features

1. **Two-Tier Matheuristic Framework**:
   - **Tier-1 Exploration (ALNS)**: Adaptive Large Neighborhood Search with 4 destroy and 3 repair operators, Multi-Armed Bandit roulette adaptation, and 2-opt geometric smoothing with immediate slack-filling.
   - **Tier-2 Master Optimization (CP-SAT)**: Exact 0-1 Set Packing Integer Linear Program solved via Google OR-Tools CP-SAT in $<0.25$ seconds, eliminating multi-drone route collisions and route cannibalization.

2. **Physics-Informed Aerodynamic Engine**:
   - Blade Element Momentum Theory (BEMT) hover power model ($P_{\text{hover}} \approx 320\text{ W}$).
   - Forward flight drag polar with best-range speed ($V_{\text{br}} \approx 14.5\text{ m/s}$).
   - Vector wind drift groundspeed resolution leading to asymmetric travel time ($t_{ij} \neq t_{ji}$) and energy consumption ($E_{ij} \neq E_{ji}$).

3. **Guaranteed Operational Safety**:
   - Hard 15% State-of-Charge (SoC) safety reserve floor on all drone batteries.
   - Independent constraint validator verifying 0% battery violations, 0% subtours, and 0% target overlap.
   - Sensor inspection dwell times absorbed into timeline slack arrays.

4. **Live Mission Control Center UI**:
   - Streamlit dashboard with real-time mission time-slider scrubbing.
   - Dynamic UAV waypoint interpolation, radar coverage halos ($r = 50\text{ m}$), and live target acquisition toggles.
   - Side-by-side visual arena (GRASP baseline vs AeroScan-Optima).
   - QGroundControl `.plan` and MAVLink waypoint exporter.

5. **Benchmark & Validation Suite**:
   - Manifest-driven Chao et al. (1996) loader with per-instance BKS metadata, provenance, and corpus availability reporting.
   - Auditable CSV/JSON reports with per-stage latency, honest `N/A` gaps when no authoritative BKS exists, and visible failed rows.
   - Comparative baselines: Organizer GRASP and Genetic Algorithm (GA).
   - The full 387-instance Chao corpus is **not** redistributed; BKS and latency claims are only reported once the authorized files are present (see [Person 3 handoff](docs/person3_instance_context_handoff.md)).

---

## Architecture & Directory Layout

```
aeroscan-optima/
├── core/
│   ├── contracts.py         # Strict dataclass interface contracts
│   ├── physics.py           # BEMT hover, drag polars, wind vector resolution
│   ├── instance.py          # Mission ingestion, coordinate projection, cost matrices
│   ├── operators.py         # 4 Destroy & 3 Repair ALNS operators
│   ├── local_search.py      # 2-Opt smoothing & immediate slack-filling
│   ├── alns.py              # Tier-1 ALNS route exploration engine
│   ├── set_packing.py       # Tier-2 Google OR-Tools CP-SAT Set Packing solver
│   └── validator.py         # Independent battery reserve, deadline, & subtour auditor
├── baselines/
│   ├── grasp.py             # Sequential greedy baseline (organizer model)
│   └── genetic.py           # Genetic Algorithm baseline
├── benchmarks/
│   ├── chao_loader.py       # Chao et al. benchmark suite loader
│   └── benchmark_runner.py  # Comparative benchmark harness & report generator
├── app/
│   ├── dashboard.py         # Streamlit Mission Control Center
│   ├── visualizer.py        # Plotly interactive spatial map & radar halos
│   ├── telemetry.py         # Real-time drone position & battery SoC simulator
│   ├── arena_view.py        # Split-screen algorithmic comparison
│   └── exporter.py          # QGroundControl .plan & MAVLink CSV exporter
├── data/
│   ├── sample_mission.json  # Mountain SAR scenario
│   └── chao_instances/      # manifest.json + checked-in Chao-format fixture
├── tests/                   # Independent unit and integration test suite
└── docs/                    # System specifications & team collaboration guide
```

---

## Quickstart

### Prerequisites
- Python 3.10+
- `uv` package manager

### Installation
```bash
# Create virtual environment
uv venv

# Install dependencies (including development tools)
uv pip install -e ".[dev]"
```

### Running Tests
```bash
uv run pytest -v
```

### Launching Mission Control UI
```bash
uv run streamlit run app/dashboard.py
```

### Running Comparative Benchmarks
```bash
# Fast deterministic smoke suite (synthetic fixtures; no corpus required)
uv run python -m benchmarks.benchmark_runner

# Official manifest/corpus suite (requires the authorized Chao instance files)
uv run python -m benchmarks.benchmark_runner --full \
    --output-csv reports/benchmark.csv --output-json reports/benchmark.json
```

---

## Mission Ingestion & `InstanceContext`

The platform ingests **JSON**, **GeoJSON**, **CSV** (with a `<stem>.meta.json` mission sidecar),
and **Chao TOP `.txt`** instances into a validated `InstanceContext`:

```python
from core.instance import build_instance_context

# Wind override: None -> use file wind; 0.0 -> intentional zero wind
instance = build_instance_context("data/sample_mission.json", wind_speed_mps=0.0, wind_dir_deg=0.0)
```

* Coordinates are meters; WGS-84 lat/lon is projected once per mission (CRS and origin recorded).
* Wind direction uses one convention: the direction the air mass moves **towards**, `0° = +x`/East, counter-clockwise. Meteorological "from" bearings are supplied as `direction_from_degrees` and converted at ingestion.
* Untrackable arcs (crosswind above airspeed, exact/overwhelming headwind) are marked `np.inf` in **both** cost matrices instead of being clamped to a physically impossible speed.
* Transit matrices hold transit only; dwell energy is `compute_dwell_energy(...)` and is charged by the route layer.
* All formats fail with actionable errors naming the file, JSON path/feature index, or CSV row.

Full contract, schemas, fixtures, and benchmark guidance:
[`docs/person3_instance_context_handoff.md`](docs/person3_instance_context_handoff.md).
