"""Aerodynamics and Energy Physics Engine for AeroScan-Optima.

Implements:
1. Blade Element Momentum Theory (BEMT) hover power draw.
2. Forward flight aerodynamic drag polars and best-range airspeed (V_br).
3. Vector wind drift groundspeed resolution resulting in asymmetric travel time
   and transit energy.

Public input conventions (Person 3 contract)
--------------------------------------------
* Distance / coordinates: **meters** (metric Cartesian, e.g. local ENU or UTM).
* Time: **seconds**. Energy: **Joules**. Power: **Watts**.
* Angles accepted by public functions are **degrees**. Angles stored inside
  :attr:`~core.contracts.InstanceContext.ambient_wind` are radians.
* **Wind convention**: a wind vector is Cartesian and describes the direction the
  air mass *moves towards*. ``direction_deg = 0`` points along ``+x`` (East) and
  the angle increases counter-clockwise (``90`` -> ``+y``/North). This is the
  convention implemented by :func:`wind_to_vector`; it is *not* the meteorological
  "blowing from" bearing. Callers with a "from" bearing must convert it at
  ingestion (see ``core.instance``'s ``direction_from_degrees`` field).

Unreachable arcs
----------------
When a required track cannot be flown (crosswind greater than the drone's
airspeed, or an exact/overwhelming headwind), the arc is **unreachable** rather
than clamped to an arbitrary slow speed. Unreachable arcs are reported as
``math.inf`` by :func:`resolve_groundspeed` and appear as ``numpy.inf`` in both
the time and energy matrices. Consumers must treat any non-finite matrix entry
as infeasible; route evaluation already turns such a route into ``None``.

Travel matrices describe **transit only**. Target dwell energy is
``calculate_hover_power(...) * target.dwell_time`` and is charged separately by
the route layer through :func:`compute_dwell_energy`. Dwell energy is never baked
into the transit matrices.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# A nonzero but negligible length (meters); arcs shorter than this are treated as
# a zero-length hop with no transit time.
_MIN_DISTANCE_M = 1e-9


@dataclass
class DroneAeroParams:
    """Aerodynamic and physical parameters for an industrial multi-rotor (e.g. DJI Matrice class)."""

    mass_kg: float = 4.5  # Total takeoff mass in kg
    gravity_mps2: float = 9.81  # Gravitational acceleration
    num_rotors: int = 4  # Quadcopter configuration
    rotor_radius_m: float = 0.28  # Rotor radius in meters
    air_density_kgpm3: float = 1.225  # Standard sea-level air density (rho)
    rotor_solidity: float = 0.08  # Rotor blade solidity ratio (sigma)
    blade_drag_coeff: float = 0.025  # Rotor blade zero-lift drag coefficient (Cd0)
    hover_tip_speed_mps: float = 68.0  # Rotor blade tip speed at hover (Omega * R)
    tip_speed_mps: float = 140.0  # Max rotor blade tip speed in forward flight (V_tip)
    body_drag_coeff: float = 0.48  # Fuselage parasitic drag coefficient
    body_frontal_area_m2: float = 0.075  # Fuselage frontal area in m^2
    # ``avionics_power_w`` is the *hover* draw and includes the gimbal LIDAR and
    # the sensor payload, matching the PRD's P_avionics + P_sensor term.
    avionics_power_w: float = 45.0  # Hover inspection draw (avionics + LIDAR/sensor payload)
    cruise_avionics_power_w: float = (
        10.0  # Forward cruise avionics draw (sensors in transit standby)
    )


@dataclass(frozen=True)
class HoverPowerBreakdown:
    """Diagnostic split of hover power into its physical components (Watts)."""

    induced_w: float
    profile_w: float
    avionics_w: float
    total_w: float


def validate_aero_params(params: DroneAeroParams) -> None:
    """Validates physical parameter domains, raising ``ValueError`` when a parameter is unusable."""
    if params.mass_kg <= 0:
        raise ValueError(f"mass_kg must be positive, got {params.mass_kg!r}")
    if params.gravity_mps2 <= 0:
        raise ValueError(f"gravity_mps2 must be positive, got {params.gravity_mps2!r}")
    if params.num_rotors <= 0:
        raise ValueError(f"num_rotors must be positive, got {params.num_rotors!r}")
    if params.rotor_radius_m <= 0:
        raise ValueError(f"rotor_radius_m must be positive, got {params.rotor_radius_m!r}")
    if params.air_density_kgpm3 <= 0:
        raise ValueError(f"air_density_kgpm3 must be positive, got {params.air_density_kgpm3!r}")
    if params.rotor_solidity <= 0:
        raise ValueError(f"rotor_solidity must be positive, got {params.rotor_solidity!r}")
    if params.blade_drag_coeff <= 0:
        raise ValueError(f"blade_drag_coeff must be positive, got {params.blade_drag_coeff!r}")
    if params.hover_tip_speed_mps <= 0:
        raise ValueError(
            f"hover_tip_speed_mps must be positive, got {params.hover_tip_speed_mps!r}"
        )
    if params.tip_speed_mps <= 0:
        raise ValueError(f"tip_speed_mps must be positive, got {params.tip_speed_mps!r}")
    if params.body_drag_coeff < 0:
        raise ValueError(f"body_drag_coeff must be non-negative, got {params.body_drag_coeff!r}")
    if params.body_frontal_area_m2 < 0:
        raise ValueError(
            f"body_frontal_area_m2 must be non-negative, got {params.body_frontal_area_m2!r}"
        )
    if params.avionics_power_w < 0:
        raise ValueError(f"avionics_power_w must be non-negative, got {params.avionics_power_w!r}")
    if params.cruise_avionics_power_w < 0:
        raise ValueError(
            f"cruise_avionics_power_w must be non-negative, got {params.cruise_avionics_power_w!r}"
        )


def _resolve_params(params: DroneAeroParams | None) -> DroneAeroParams:
    """Returns ``params`` or a validated default. Avoids shared mutable defaults in signatures."""
    resolved = DroneAeroParams() if params is None else params
    validate_aero_params(resolved)
    return resolved


def _disk_area_m2(params: DroneAeroParams) -> float:
    return params.num_rotors * math.pi * (params.rotor_radius_m**2)


def hover_power_breakdown(params: DroneAeroParams | None = None) -> HoverPowerBreakdown:
    """Returns the induced, profile, and avionics components of hover power.

    P_hover = P_induced + P_profile + P_avionics
    P_induced = T^(3/2) / sqrt(2 * rho * A)
    P_profile = (1/8) * rho * sigma * Cd0 * A * (Omega * R)^3
    """
    p = _resolve_params(params)
    thrust = p.mass_kg * p.gravity_mps2
    disk_area = _disk_area_m2(p)

    p_induced = (thrust**1.5) / math.sqrt(2.0 * p.air_density_kgpm3 * disk_area)
    p_profile = (
        0.125
        * p.air_density_kgpm3
        * p.rotor_solidity
        * p.blade_drag_coeff
        * disk_area
        * (p.hover_tip_speed_mps**3)
    )
    return HoverPowerBreakdown(
        induced_w=float(p_induced),
        profile_w=float(p_profile),
        avionics_w=float(p.avionics_power_w),
        total_w=float(p_induced + p_profile + p.avionics_power_w),
    )


def calculate_hover_power(params: DroneAeroParams | None = None) -> float:
    """Computes static hover power draw in Watts using Actuator Disk and BEMT theory."""
    return hover_power_breakdown(params).total_w


def calculate_cruise_power(airspeed_mps: float, params: DroneAeroParams | None = None) -> float:
    """Computes forward flight cruise power draw in Watts using forward flight drag polars.

    P_cruise(V) = P_0 * (1 + 3 * V^2 / V_tip^2)
                + P_i * (sqrt(1 + V^4 / (4 * v_0^4)) - V^2 / (2 * v_0^2))^(1/2)
                + 0.5 * rho * Cd_body * A_body * V^3
                + P_avionics_cruise

    Zero airspeed is accepted (it degenerates to the hover polar). Negative
    airspeeds are rejected; use :func:`energy_per_distance` when the intent is
    energy per meter.
    """
    if airspeed_mps < 0:
        raise ValueError(f"airspeed_mps must be non-negative, got {airspeed_mps!r}")
    p = _resolve_params(params)
    v = float(airspeed_mps)
    thrust = p.mass_kg * p.gravity_mps2
    disk_area = _disk_area_m2(p)

    # Hover induced velocity v_0
    v_0 = math.sqrt(thrust / (2.0 * p.air_density_kgpm3 * disk_area))

    # Profile power at hover P_0
    p_0 = (
        0.125
        * p.air_density_kgpm3
        * p.rotor_solidity
        * p.blade_drag_coeff
        * disk_area
        * (p.hover_tip_speed_mps**3)
    )

    # Induced power at hover P_i
    p_i = (thrust**1.5) / math.sqrt(2.0 * p.air_density_kgpm3 * disk_area)

    # Profile term in forward flight
    term_profile = p_0 * (1.0 + 3.0 * (v**2) / (p.tip_speed_mps**2))

    # Induced term in forward flight (numerically safe at v -> 0)
    v_0_sq = v_0**2
    ratio = (v**2) / (2.0 * v_0_sq) if v_0_sq > 0.0 else 0.0
    inner = math.sqrt(1.0 + (v**4) / (4.0 * (v_0_sq**2) if v_0_sq > 0.0 else 1.0)) - ratio
    term_induced = p_i * math.sqrt(max(0.0, inner))

    # Parasitic fuselage drag
    term_parasitic = 0.5 * p.air_density_kgpm3 * p.body_drag_coeff * p.body_frontal_area_m2 * (v**3)

    total_power = term_profile + term_induced + term_parasitic + p.cruise_avionics_power_w
    return float(total_power)


def energy_per_distance(airspeed_mps: float, params: DroneAeroParams | None = None) -> float:
    """Returns cruise energy per meter (J/m) at ``airspeed_mps``.

    Raises ``ValueError`` for non-positive airspeeds: a stationary aircraft has no
    meaningful energy-per-distance and silently returning an infinite/large value
    would poison best-range searches.
    """
    if airspeed_mps <= 0:
        raise ValueError(f"airspeed_mps must be positive for energy/km, got {airspeed_mps!r}")
    return calculate_cruise_power(airspeed_mps, params) / airspeed_mps


def find_best_range_speed(
    params: DroneAeroParams | None = None,
    v_min: float = 5.0,
    v_max: float = 25.0,
    resolution: int = 201,
) -> float:
    """Computes best-range airspeed V_br = argmin_V (P(V) / V), minimizing energy per meter.

    Uses a deterministic bounded grid search. ``v_min``/``v_max`` are inclusive
    bounds in m/s and ``resolution`` is the number of grid samples (>= 2).
    """
    if v_min <= 0:
        raise ValueError(f"v_min must be positive, got {v_min!r}")
    if v_max <= v_min:
        raise ValueError(f"v_max ({v_max!r}) must be greater than v_min ({v_min!r})")
    if resolution < 2:
        raise ValueError(f"resolution must be at least 2, got {resolution!r}")

    p = _resolve_params(params)
    speeds = np.linspace(v_min, v_max, resolution, dtype=np.float64)
    specific_energies = np.array(
        [calculate_cruise_power(v, p) / v for v in speeds], dtype=np.float64
    )
    min_idx = int(np.argmin(specific_energies))
    return float(speeds[min_idx])


def wind_to_vector(speed_mps: float, direction_deg: float) -> tuple[float, float]:
    """Converts a wind speed and direction into a Cartesian (W_x, W_y) vector.

    The wind convention is documented at module level: the vector points in the
    direction the air mass moves *towards*, ``0`` degrees is ``+x`` (East) and
    angles increase counter-clockwise.
    """
    if speed_mps < 0:
        raise ValueError(f"wind speed_mps must be non-negative, got {speed_mps!r}")
    rad = math.radians(direction_deg)
    return (float(speed_mps * math.cos(rad)), float(speed_mps * math.sin(rad)))


def resolve_groundspeed(
    displacement_xy: tuple[float, float],
    wind_vector_xy: tuple[float, float],
    cruise_airspeed_mps: float = 14.5,
) -> tuple[float, float]:
    """Resolves ground speed V_g and travel time t_ij along a displacement with wind.

    Solves ``|V_g * u_hat - W| = V_cruise`` for the outgoing root:
    ``V_g^2 - 2 * (W . u_hat) * V_g + (|W|^2 - V_cruise^2) = 0``

    Returns:
        ``(groundspeed_mps, transit_time_seconds)``. An untrackable arc returns
        ``(math.inf, math.inf)`` (see the module-level unreachable-arc policy).
        A zero-length displacement returns ``(cruise_airspeed_mps, 0.0)``.
    """
    if cruise_airspeed_mps <= 0:
        raise ValueError(f"cruise_airspeed_mps must be positive, got {cruise_airspeed_mps!r}")

    dx, dy = displacement_xy
    dist = math.hypot(dx, dy)
    if dist < _MIN_DISTANCE_M:
        return (float(cruise_airspeed_mps), 0.0)

    u_x = dx / dist
    u_y = dy / dist
    w_x, w_y = wind_vector_xy

    w_dot_u = w_x * u_x + w_y * u_y
    w_mag_sq = w_x**2 + w_y**2
    v_cruise_sq = cruise_airspeed_mps**2

    discriminant = (w_dot_u**2) + (v_cruise_sq - w_mag_sq)

    if discriminant < 0.0:
        # Crosswind component exceeds the aircraft's airspeed envelope: the track
        # cannot be held at any positive groundspeed.
        return (math.inf, math.inf)

    vg = w_dot_u + math.sqrt(discriminant)
    if vg <= _MIN_DISTANCE_M:
        # Exact or overwhelming headwind: no forward progress is possible.
        return (math.inf, math.inf)

    return (float(vg), float(dist / vg))


def compute_dwell_energy(dwell_time_seconds: float, params: DroneAeroParams | None = None) -> float:
    """Computes total energy in Joules consumed during static inspection dwell.

    This is the single source of truth for dwell energy; it is intentionally kept
    out of the transit cost matrices.
    """
    p_hover = calculate_hover_power(params)
    return float(p_hover * max(0.0, dwell_time_seconds))


def compute_cost_matrices(
    nodes_xy: np.ndarray,
    wind_speed_mps: float = 0.0,
    wind_direction_deg: float = 0.0,
    cruise_speed_mps: float = 14.5,
    params: DroneAeroParams | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Computes asymmetric time (seconds) and energy (Joules) matrices for node coordinates.

    Args:
        nodes_xy: Shape ``[N, 2]`` array of ``(x, y)`` coordinates in meters.
        wind_speed_mps: Ambient wind speed in m/s (>= 0).
        wind_direction_deg: Wind direction in the module-level Cartesian convention
            (0 degrees = +x/East, increasing counter-clockwise).
        cruise_speed_mps: Cruise airspeed in m/s.
        params: Aerodynamic parameters; ``None`` uses validated defaults.

    Returns:
        ``(time_matrix, energy_matrix)`` as square, C-contiguous ``np.float64``
        arrays. Diagonal entries are ``0.0``. Unreachable directed arcs are
        ``np.inf`` in both matrices.
    """
    coords = np.asarray(nodes_xy, dtype=np.float64)
    if coords.ndim != 2 or coords.shape[1] != 2:
        raise ValueError(f"nodes_xy must have shape [N, 2], got {coords.shape}")
    if not np.all(np.isfinite(coords)):
        raise ValueError("nodes_xy must contain only finite coordinates")

    p = _resolve_params(params)
    if cruise_speed_mps <= 0:
        raise ValueError(f"cruise_speed_mps must be positive, got {cruise_speed_mps!r}")

    n = coords.shape[0]
    # Preallocated, C-contiguous float64 output.
    time_matrix = np.zeros((n, n), dtype=np.float64, order="C")
    energy_matrix = np.zeros((n, n), dtype=np.float64, order="C")

    wind_vector = wind_to_vector(wind_speed_mps, wind_direction_deg)
    cruise_power = calculate_cruise_power(cruise_speed_mps, p)

    for i in range(n):
        xi, yi = float(coords[i, 0]), float(coords[i, 1])
        for j in range(n):
            if i == j:
                continue
            disp = (float(coords[j, 0]) - xi, float(coords[j, 1]) - yi)
            vg, t_sec = resolve_groundspeed(disp, wind_vector, cruise_speed_mps)
            if not math.isfinite(vg) or not math.isfinite(t_sec):
                time_matrix[i, j] = np.inf
                energy_matrix[i, j] = np.inf
                continue
            time_matrix[i, j] = t_sec
            energy_matrix[i, j] = cruise_power * t_sec

    return (time_matrix, energy_matrix)
