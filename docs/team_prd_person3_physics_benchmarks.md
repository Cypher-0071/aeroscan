# Sub-PRD 3: Aerodynamics, Energy Physics & Benchmark Suite

**Engineer**: **Person 3 — Aerodynamics & Benchmark Engineer**  
**Owned Modules**: `core/physics.py`, `core/instance.py`, `benchmarks/chao_loader.py`, `benchmarks/benchmark_runner.py`  
**Owned Tests**: `tests/test_physics.py`, `tests/test_instance.py`, `tests/test_benchmarks.py`  
**Upstream Dependency**: Standalone! Ingests raw Chao benchmark `.txt` files and GeoJSON/JSON mission maps.  
**Downstream Deliverable**: Produces precomputed `InstanceContext` containing metric coordinates, drone specs, and wind-corrected asymmetric cost matrices $\mathbf{T}$ and $\mathbf{E}$ for Persons 1, 2, and 4.  

---

## 1. Role Mission & Objectives
As the **Aerodynamics & Benchmark Engineer**, you establish the physical reality and scientific validation of the platform:
1. Model the **aerodynamic power draw** of industrial multi-rotors: static sensor dwell hover ($320\text{ W}$), forward flight drag polars, and asymmetric wind drift ($t_{ij} \neq t_{ji}$).
2. Build the **Chao et al. (1996) 387-instance benchmark loader** and automated verification harness to prove $>99.8\%$ BKS optimality.
3. Deliver the clean, precomputed `InstanceContext` data contract that powers the rest of the team's solvers.

---

## 2. Detailed Technical Requirements

### 2.1 Physics Engine (`core/physics.py`)
Multi-rotor UAV power does not scale linearly with distance. Implement the following physical models:

1. **Blade Element Momentum Theory (BEMT) Hover Power**:
   When hovering over target $i$ for inspection dwell $t_{\text{dwell}, i}$, total power is:
   $$P_{\text{hover}} = \frac{T^{3/2}}{\sqrt{2 \rho A}} + \frac{1}{8} \rho \sigma C_{d0} A (\Omega R)^3 + P_{\text{avionics}} + P_{\text{sensor}}$$
   - Default Parameters: Drone mass $m = 4.5\text{ kg}$, $g = 9.81\text{ m/s}^2$, rotor radius $R = 0.28\text{ m}$, 4 rotors ($A = 4 \pi R^2$), air density $\rho = 1.225\text{ kg/m}^3$, solidity $\sigma = 0.08$, profile drag $C_{d0} = 0.025$, tip speed $\Omega R = 140\text{ m/s}$, avionics + gimbal LIDAR $P_{\text{avionics}} = 45\text{ W}$.
   - Typical output: $P_{\text{hover}} \approx 320\text{ W}$.
   - Energy per dwell: $E_{\text{dwell}, i} = P_{\text{hover}} \cdot t_{\text{dwell}, i}\text{ Joules}$.

2. **Forward Flight Drag Polar & Airspeed ($V_{\text{br}}$)**:
   In forward cruise:
   $$P_{\text{cruise}}(V_a) = P_0 \left(1 + \frac{3V_a^2}{V_{\text{tip}}^2}\right) + P_i \left(\sqrt{1 + \frac{V_a^4}{4 v_0^4}} - \frac{V_a^2}{2 v_0^2}\right)^{1/2} + \frac{1}{2} \rho C_{D, \text{body}} A_{\text{body}} V_a^3 + P_{\text{avionics}}$$
   - Precompute optimal range airspeed $V_{\text{br}} = \arg\min_{V_a} \frac{P(V_a)}{V_a} \approx 14.5\text{ m/s}$.

3. **Asymmetric Wind Drift & Ground Speed Resolution**:
   Given target vector $\vec{D}_{ij} = (x_j - x_i, y_j - y_i)$ with unit direction $\hat{u}_{ij}$, and ambient wind vector $\vec{W} = (W_x, W_y)$:
   Ground velocity $\vec{V}_g = V_g \hat{u}_{ij}$ must satisfy:
   $$|\vec{V}_g - \vec{W}| = V_{\text{cruise}}$$
   Solve the quadratic equation for groundspeed $V_g$:
   $$V_g^2 - 2 (\vec{W} \cdot \hat{u}_{ij}) V_g + (|\vec{W}|^2 - V_{\text{cruise}}^2) = 0$$
   $$V_g(i \to j) = (\vec{W} \cdot \hat{u}_{ij}) + \sqrt{(\vec{W} \cdot \hat{u}_{ij})^2 + (V_{\text{cruise}}^2 - |\vec{W}|^2)}$$
   - Travel time: $t_{ij} = \frac{\|\vec{D}_{ij}\|}{V_g(i \to j)}$.
   - Transit energy: $E_{\text{transit}, ij} = P_{\text{cruise}}(V_{\text{cruise}}) \cdot t_{ij}$.
   - Notice that if $\vec{W} \neq 0$, $V_g(i \to j) \neq V_g(j \to i)$, which guarantees $t_{ij} \neq t_{ji}$ (asymmetric graph).

### 2.2 Instance Loader & Geodetic Projections (`core/instance.py`)
- Ingest JSON, CSV, and standard TOP benchmark `.txt` files.
- If input coordinates are WGS-84 (lat/lon), project to UTM Cartesian coordinates $(x, y)$ in meters using `pyproj` or standard haversine metric projection.
- Precompute and store `time_matrix` and `energy_matrix` as contiguous `numpy.ndarray` (float64) for ultra-fast lookup by ALNS.

### 2.3 Chao et al. (1996) Benchmark Suite (`benchmarks/`)
- Ingest the 387 standard Chao TOP instances:
  - Set 64: 64 nodes (tight clusters)
  - Set 66: 66 nodes (diamond topology)
  - Set 100: 100 nodes (radial concentric)
  - Set 102: 102 nodes (random uniform)
- Implement `benchmarks/benchmark_runner.py` that iterates through all instances, runs Person 1 & 2's solver pipeline, and outputs a formatted CSV report verifying:
  - Average Gap to BKS: $<0.15\%$
  - Average Solve Latency: $<2.5\text{ seconds}$
  - Battery violation count: $0$

---

## 3. Interface Contract Compliance

### Outputs You Deliver (to Persons 1, 2, and 4):
```python
from core.contracts import InstanceContext, TargetNode, DroneSpec

def build_instance_context(
    filepath: str, 
    wind_speed_mps: float = 0.0, 
    wind_dir_deg: float = 0.0
) -> InstanceContext:
    """
    Parses instance file, applies BEMT physics and wind drift,
    and returns precomputed InstanceContext.
    """
    ...
```

---

## 4. Standalone Test Plan (Zero External Dependencies)
You will develop self-contained verification tests:
- `test_bemt_power_positive()`: Verify that hover power is within $300\text{--}350\text{ W}$ for $4.5\text{ kg}$ drone.
- `test_wind_drift_asymmetry()`: With a $5\text{ m/s}$ East wind, assert $t(A \to B) < t(B \to A)$ for East-West transit.
- `test_chao_loader_integrity()`: Assert that Set 64 loads exactly 64 targets with correct published BKS scores.
