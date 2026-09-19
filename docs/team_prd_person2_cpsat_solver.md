# Sub-PRD 2: Tier-2 CP-SAT Master Solver, Validator & Baselines

**Engineer**: **Person 2 — Mathematical Optimization Engineer**  
**Owned Modules**: `core/set_packing.py`, `core/validator.py`, `baselines/grasp.py`, `baselines/genetic.py`  
**Owned Tests**: `tests/test_set_packing.py`, `tests/test_validator.py`, `tests/test_baselines.py`  
**Upstream Dependency**: Consumes `RoutePool` from Person 1 and `InstanceContext` from Person 3 (uses `tests/mock_routes.py` until integration).  
**Downstream Deliverable**: Produces certified `FleetSchedule` for Person 4's Mission Control UI.  

---

## 1. Role Mission & Objectives
As the **Mathematical Optimization Engineer**, you own the global optimality and mathematical integrity of the platform:
1. Formulate and solve the **Exact 0-1 Set Packing Master Problem** using Google OR-Tools CP-SAT, combining candidate routes from all drones into an airtight, non-overlapping global schedule in $<0.25\text{ seconds}$.
2. Build the **Independent Constraint Verification Engine** (`core/validator.py`) that mathematically verifies 0% battery violations, 0% subtours, and 0% target duplication.
3. Implement the **Organizer GRASP Baseline** and **Standard Genetic Algorithm** to demonstrate our **$+15.3\%$ performance superiority** in the hackathon arena.

---

## 2. Detailed Technical Requirements

### 2.1 Google OR-Tools CP-SAT Master Solver (`core/set_packing.py`)
- **Mathematical Model**:
  Given route pool $\Omega_k$ for each drone $k \in \mathcal{K}$:
  $$\max \sum_{k \in \mathcal{K}} \sum_{r \in \Omega_k} R_{k, r} \cdot z_{k, r}$$
  Subject to:
  $$\sum_{r \in \Omega_k} z_{k, r} \le 1 \quad \forall k \in \mathcal{K} \quad \text{(At most one route selected per drone)}$$
  $$\sum_{k \in \mathcal{K}} \sum_{r \in \Omega_k : i \in r} z_{k, r} \le 1 \quad \forall i \in \mathcal{V}_{\text{targets}} \quad \text{(No target visited by more than one drone)}$$
  $$z_{k, r} \in \{0, 1\}$$
- **OR-Tools Implementation**:
  ```python
  from ortools.sat.python import cp_model

  model = cp_model.CpModel()
  z = {}
  for k, routes in route_pool.routes_by_drone.items():
      for r_idx, route in enumerate(routes):
          z[(k, r_idx)] = model.NewBoolVar(f"z_{k}_{r_idx}")

  # Constraint 1: Drone assignment limit
  for k, routes in route_pool.routes_by_drone.items():
      model.Add(sum(z[(k, r_idx)] for r_idx in range(len(routes))) <= 1)

  # Constraint 2: Target uniqueness
  for target_id in all_target_ids:
      matching_routes = [
          z[(k, r_idx)]
          for k, routes in route_pool.routes_by_drone.items()
          for r_idx, route in enumerate(routes)
          if target_id in route.target_ids
      ]
      if matching_routes:
          model.Add(sum(matching_routes) <= 1)

  # Objective: Maximize reward
  objective = sum(
      route.total_reward * z[(k, r_idx)]
      for k, routes in route_pool.routes_by_drone.items()
      for r_idx, route in enumerate(routes)
  )
  model.Maximize(objective)
  ```
- **Execution Budget**: Set solver parameters: `solver.parameters.max_time_in_seconds = 0.5`. On Set Packing formulations with 5,000 routes, CP-SAT routinely terminates with proof of optimality in $\approx 0.05\text{--}0.15\text{ seconds}$.

### 2.2 Independent Constraint Validator (`core/validator.py`)
Implement an uncompromising audit function that inspects any generated `FleetSchedule`:
1. **Battery Reserve Verification**:
   For every selected route, verify:
   $$E_{\text{total}} \le 0.85 \cdot B_k \iff \text{Remaining SoC} \ge 15.0\%$$
   Raise `AssertionError("Fatal: Battery safety margin breached")` if $<15.0\%$.
2. **Flight Deadline Verification**:
   Verify arrival time at recovery depot $t_{\text{arrival}} \le T_{\max, k}$.
3. **Depot Decoupling Flow Verification**:
   Verify waypoint 0 is `launch_depot_id` and final waypoint is `recovery_depot_id`.
4. **Target Deconfliction Verification**:
   Compute intersection of `target_ids` across all assigned drones. Assert $\text{len}(T_a \cap T_b) == 0$ for all $a \neq b$.

### 2.3 Baseline Solvers for Comparative Arena
1. **Organizer GRASP Baseline (`baselines/grasp.py`)**:
   Implement the standard sequential greedy randomized adaptive search procedure:
   - For drone $1 \dots K$: Greedily build route picking from top $\alpha = 0.3$ best $\Delta R / \Delta \text{dist}$ targets.
   - Remove visited targets and repeat for next drone.
   - Demonstrates the severe route cannibalization problem.
2. **Genetic Algorithm Baseline (`baselines/genetic.py`)**:
   Standard permutation chromosome representation with Order Crossover (OX) and Swap Mutation, penalizing deadline breaches via fitness decay. Demonstrates high violation rates and local minima plateaus.

---

## 3. Interface Contract Compliance

### Inputs You Consume (from Person 1 & Person 3):
- `InstanceContext` (from Person 3)
- `RoutePool` (from Person 1)

### Outputs You Deliver (to Person 4):
```python
from core.contracts import FleetSchedule, CandidateRoute

def solve_fleet_schedule(
    instance: InstanceContext, 
    route_pool: RoutePool
) -> FleetSchedule:
    """
    Solves Set Packing, runs baselines, validates constraints,
    and returns the complete FleetSchedule.
    """
    ...
```

---

## 4. Standalone Test Plan (Zero External Dependencies)
You will develop against `tests/mock_routes.py`:
- `test_set_packing_feasibility()`: Verify CP-SAT returns valid assignments without overlapping targets.
- `test_validator_catches_violations()`: Inject an artificially long route and assert that `core/validator.py` catches it.
- `test_baseline_comparison()`: Verify that GRASP baseline runs in $<0.2\text{s}$ and returns a valid schedule with lower score.
