# Sub-PRD 4: Mission Control Dashboard, Telemetry & SITL Export

**Engineer**: **Person 4 — Full-Stack Mission Control UI Engineer**  
**Owned Modules**: `app/dashboard.py`, `app/visualizer.py`, `app/telemetry.py`, `app/arena_view.py`, `app/exporter.py`  
**Owned Tests**: `tests/test_ui_components.py`, `tests/test_telemetry.py`  
**Upstream Dependency**: Consumes `FleetSchedule` from Person 2 and `InstanceContext` from Person 3 (uses `tests/mock_schedule.json` until integration).  
**Downstream Deliverable**: The complete runnable, interactive user-facing Streamlit application (`streamlit run app/dashboard.py`) and exportable flight plans.  

---

## 1. Role Mission & Objectives
As the **Full-Stack Mission Control UI Engineer**, you are the public face of the project:
1. Build the **Streamlit Mission Control Center** that judges will interact with during live evaluation.
2. Implement the **Real-Time Mission Time-Slider**: scrubbing the slider from $0\text{ to }T_{\max}$ must smoothly update the live coordinates of all drones, their radar coverage halos, and target acquisition flags.
3. Build the **Side-by-Side Arena View**: split-screen visual comparison highlighting the tangled, cannibalized GRASP baseline routes on the left vs. clean, deconflicted AeroScan-Optima routes on the right.
4. Provide one-click **MAVLink / QGroundControl `.plan` flight plan export**.

---

## 2. Detailed Technical Requirements

### 2.1 Mission Control Center Layout (`app/dashboard.py`)
- **Header**: Project title, selected scenario/dataset, status badges (`[SOLVER: OPTIMAL]`, `[BKS GAP: 0.12%]`, `[SOLVE TIME: 1.84s]`).
- **Sidebar Controls**:
  - Scenario Selector: Load Chao 64/66/100/102 instances or upload custom GeoJSON.
  - Wind Vector Sliders: Ambient Wind Speed ($0\text{--}15\text{ m/s}$), Wind Direction ($0\text{--}360^\circ$).
  - Fleet Slider: Number of UAVs ($2\text{--}8$).
  - Solver Trigger: `[🚀 Run Matheuristic Optimization]`.
- **Top Metric Cards**:
  - `Total Collected Score`: e.g. **840 pts** (`+18.4% vs GRASP`).
  - `Solve Latency`: e.g. **1.84s**.
  - `Targets Reached`: e.g. **24 / 32**.
  - `Min Fleet Battery Reserve`: e.g. **18.2%** (`PASS: >15% Floor`).

### 2.2 Interactive Map & Telemetry Simulator (`app/visualizer.py`, `app/telemetry.py`)
- **Plotly Spatial Map**:
  - Target Markers: Sized and colored by priority score (bright yellow/red for high-value targets, dull grey for low-value).
  - Depot Markers: Large blue triangles indicating launch/recovery coordinates.
  - Drone Route Polylines: Color-coded lines with directional arrows for each drone $k$.
- **Real-Time Mission Time-Slider (`st.slider`)**:
  - User can drag slider from $t = 0\text{ to }t = T_{\max}$ in increments of 1 second.
  - At timestamp $t$, `app/telemetry.py` interpolates the exact $(x, y, z)$ position of each drone between its waypoints.
  - Render an animated vehicle marker for each drone with a pulsing radar scan halo ($r = 50\text{ m}$).
  - Visited targets before timestamp $t$ toggle to "SEARCHED / SECURED" green checkmarks.

### 2.3 Battery State-of-Charge (SoC) Depletion Graph
- Line chart displaying Battery % vs. Mission Time (seconds) for each drone.
- A horizontal dashed red line at **15%** clearly marked: `Mandatory Emergency Reserve Floor`.
- Visual proof that all curves terminate safely above the red line.

### 2.4 Side-by-Side Arena View (`app/arena_view.py`)
- Dual-column split screen:
  - **Left Column**: `Organizer GRASP Baseline` (710 pts). Displays tangled, overlapping loops where Drone 1 cannibalized targets near the depot, stranding Drones 2 & 3.
  - **Right Column**: `AeroScan-Optima Matheuristic` (840 pts, $+18.4\%$). Displays clean, deconflicted convex route clusters solved by Set Packing.

### 2.5 Hardware & SITL Waypoint Exporter (`app/exporter.py`)
- Button: `[📥 Download QGroundControl .plan]`:
  - Serializes each drone's trajectory into standard QGroundControl mission plan JSON (`MAV_CMD_NAV_WAYPOINT`, latitude, longitude, altitude, hold time $t_{\text{dwell}}$).
- Button: `[📥 Download Mission Telemetry Audit (CSV)]`:
  - Full CSV log of waypoint sequences, arrival times, energy burned, and target scores.

---

## 3. Interface Contract Compliance

### Inputs You Consume (from Person 2 & Person 3):
- `InstanceContext` (from Person 3)
- `FleetSchedule` (from Person 2)

### Starting with Mock Fixture (Day 0):
You do not wait for the solver. Load `tests/mock_schedule.json`:
```python
import json
from core.contracts import FleetSchedule

# In your app/dashboard.py:
if "schedule" not in st.session_state:
    st.session_state.schedule = load_mock_schedule("tests/mock_schedule.json")
```

---

## 4. Standalone Test Plan (Zero External Dependencies)
You will develop self-contained UI and interpolation tests:
- `test_telemetry_interpolation()`: For a drone flying from $(0,0)$ at $t=0$ to $(100,0)$ at $t=10$, verify position at $t=5$ is exactly $(50,0)$.
- `test_qgc_plan_export_format()`: Verify that exported `.plan` file matches QGroundControl schema version 1.
- `test_streamlit_app_loads()`: Run `streamlit run app/dashboard.py --server.headless true` to assert zero syntax or import errors.
