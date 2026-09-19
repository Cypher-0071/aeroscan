# Sub-PRD 1: Tier-1 ALNS Route Exploration Engine

**Engineer**: **Person 1 — Lead Metaheuristic Engineer**  
**Owned Modules**: `core/alns.py`, `core/operators.py`, `core/local_search.py`  
**Owned Tests**: `tests/test_alns.py`, `tests/test_operators.py`  
**Upstream Dependency**: Consumes `InstanceContext` from Person 3 (uses `tests/mock_instance.py` until integration).  
**Downstream Deliverable**: Produces `RoutePool` for Person 2's Set Packing solver.  

---

## 1. Role Mission & Objectives
As the **Lead Metaheuristic Engineer**, your mission is to build the high-speed exploration engine that discovers thousands of structurally diverse, energy-feasible, and high-scoring single-drone candidate trajectories. 

You do **not** need to worry about multi-drone route collisions or target overlap across the fleet — the Tier-2 Master Solver (Person 2) handles fleet deconfliction via Set Packing. Your single goal is: **produce the richest, highest-quality route pool $\Omega_k$ for each drone in under $2.0\text{ seconds}$**.

---

## 2. Detailed Technical Requirements

### 2.1 ALNS Framework (`core/alns.py`)
- **Initial Seed Construction**: Implement a quick greedy insertion heuristic that constructs an initial feasible route for each drone $k \in \mathcal{K}$ using a randomized restricted candidate list (RCL, $\alpha = 0.2$).
- **Adaptive Multi-Armed Bandit Roulette Wheel**:
  - Maintain selection probabilities $p_d$ and $p_r$ for each destroy and repair operator.
  - In each iteration $t$:
    1. Select destroy operator $d$ and repair operator $r$ with probability proportional to their current weights $w_d, w_r$.
    2. Destroy $q \in [2, \max(3, \lfloor 0.35 \cdot |S| \rfloor)]$ targets from current route.
    3. Repair route by re-inserting unassigned targets.
    4. Apply 2-opt local search and immediate slack-filling.
    5. Cache new feasible route into `RoutePool.routes_by_drone[k]`.
  - Update operator scores every segment of $\delta = 50$ iterations:
    - $\sigma_1 = 15$ pts: New global best route found.
    - $\sigma_2 = 8$ pts: Improved current route.
    - $\sigma_3 = 3$ pts: Non-improving route accepted under Simulated Annealing acceptance criterion ($P(\text{accept}) = \exp(-\Delta / T)$).
  - Operator weight update: $w_{d}^{(t+1)} = \lambda w_d^{(t)} + (1 - \lambda) \frac{\text{score}_d}{\text{timesUsed}_d}$ with reaction factor $\lambda = 0.8$.

### 2.2 The 4 Destroy Operators (`core/operators.py`)
1. **Shaw Spatio-Temporal Relatedness Destroy**:
   Define relatedness $R(i, j) = \phi_1 \frac{d_{ij}}{\max d} + \phi_2 \frac{|t_{\text{arr}, i} - t_{\text{arr}, j}|}{\max t} + \phi_3 \frac{|R_i - R_j|}{\max R}$.
   Remove a seed target $i$, then iteratively remove targets with minimum $R(i, j)$.
2. **Worst-Cost Efficiency Detour Destroy**:
   Compute target efficiency $\eta_i = \frac{R_i}{\Delta \text{Energy}_i}$ where $\Delta \text{Energy}_i = E_{p, i} + E_{i, s} - E_{p, s}$.
   Sort targets in ascending order of $\eta_i$ and remove $q$ worst-performing detours with randomized bias $i = \lfloor |S| \cdot r^p \rfloor$.
3. **Radial Angular Cone Destroy**:
   Compute polar angle $\theta_i = \text{atan2}(y_i - y_{\text{depot}}, x_i - x_{\text{depot}})$.
   Select an angular center $\theta_0$ and remove all targets within cone $[\theta_0 - \Delta \theta, \theta_0 + \Delta \theta]$.
4. **Contiguous String Destroy**:
   Select a continuous sub-chain of $L \in [2, 6]$ adjacent targets along the route and eject the entire segment simultaneously.

### 2.3 The 3 Repair Operators (`core/operators.py`)
1. **Greedy Insertion**:
   Evaluate every unassigned target $u$ across every insertion slot $(i, i+1)$. Insert target giving maximum $\Delta R / \Delta E$ without violating $T_{\max}$ or $0.85 B_k$.
2. **Regret-2 Insertion**:
   Compute difference between best insertion cost $c_1(u)$ and second-best insertion cost $c_2(u)$. Target with highest regret $\Delta = c_2(u) - c_1(u)$ is inserted first.
3. **Corrected Big-M Regret-3 Insertion**:
   Evaluate top 3 insertion positions. If an unassigned target only has 1 or 2 feasible insertion positions before violating battery limits, assign penalty cost $M = 10^6$ to missing slots:
   $$\text{Regret}_3(u) = \sum_{r=2}^3 (c_r(u) - c_1(u))$$
   This guarantees that time-critical targets nearing deadline expiration are scheduled before slots close.

### 2.4 Local Search & Immediate Slack-Filling (`core/local_search.py`)
- **2-Opt Geometric De-Crossing**: Reverses segment $[i \dots j]$ if $t_{i, j} + t_{i+1, j+1} < t_{i, i+1} + t_{j, j+1}$ and energy is reduced.
- **Immediate Slack-Filling (Key Innovation)**:
  Any seconds saved by 2-opt ($\Delta t_{\text{saved}} > 0$) immediately trigger an Add-move scanner that checks the unassigned target pool and greedily inserts new high-value targets into the newly created temporal slack.

---

## 3. Interface Contract Compliance

### Inputs You Consume (from Person 3):
```python
# Context passed to your solve function:
instance: InstanceContext
# You have access to:
# - instance.targets: list of targets with .x, .y, .priority_score, .dwell_time
# - instance.time_matrix: 2D numpy array of travel times
# - instance.energy_matrix: 2D numpy array of travel energies
# - instance.drones: list of drone battery and speed limits
```

### Outputs You Must Deliver (to Person 2):
```python
from core.contracts import RoutePool, CandidateRoute, WaypointVisit

def explore_route_pool(instance: InstanceContext, max_iterations: int = 800, time_limit_sec: float = 1.8) -> RoutePool:
    """
    Executes ALNS and returns a populated RoutePool object.
    Must guarantee:
    1. Every route in RoutePool starts at launch_depot and ends at recovery_depot.
    2. Every route satisfies: total_energy <= 0.85 * drone.battery_joules.
    3. Every route satisfies: total_time <= drone.max_flight_time.
    4. Waypoint arrival and departure timestamps are continuous and dwell times are added.
    """
    ...
```

---

## 4. Standalone Test Plan (Zero External Dependencies)
You will develop against `tests/mock_instance.py`:
- `test_destroy_operators()`: Verify that each destroy operator removes exactly $q$ targets.
- `test_repair_operators()`: Verify that repaired routes never exceed $0.85 \times \text{Battery}$.
- `test_2opt_slack_refill()`: Verify that 2-opt reduces route length and slack filling adds score.
- `test_route_pool_uniqueness()`: Verify that candidate route pool contains unique target sets.
