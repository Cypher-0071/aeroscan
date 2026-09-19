"""Aerodynamics and Energy Physics Engine for AeroScan-Optima.

Implements:
1. Blade Element Momentum Theory (BEMT) hover power draw.
2. Forward flight aerodynamic drag polars and best-range airspeed (V_br).
3. Vector wind drift groundspeed resolution resulting in asymmetric travel time
   and transit energy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class DroneAeroParams:
    """Aerodynamic and physical parameters for an industrial multi-rotor (e.g. DJI Matrice class)."""
    mass_kg: float = 4.5                # Total takeoff mass in kg
    gravity_mps2: float = 9.81          # Gravitational acceleration
    num_rotors: int = 4                 # Quadcopter configuration
    rotor_radius_m: float = 0.28        # Rotor radius in meters
    air_density_kgpm3: float = 1.225    # Standard sea-level air density (rho)
    rotor_solidity: float = 0.08        # Rotor blade solidity ratio (sigma)
    blade_drag_coeff: float = 0.025     # Rotor blade zero-lift drag coefficient (Cd0)
    hover_tip_speed_mps: float = 68.0   # Rotor blade tip speed at hover (Omega * R)
    tip_speed_mps: float = 140.0        # Max rotor blade tip speed in forward flight (V_tip)
    body_drag_coeff: float = 0.48       # Fuselage parasitic drag coefficient
    body_frontal_area_m2: float = 0.075 # Fuselage frontal area in m^2
    avionics_power_w: float = 45.0      # Hover inspection draw (avionics + LIDAR/sensor payload)
    cruise_avionics_power_w: float = 10.0 # Forward cruise avionics draw (sensors in transit standby)


def calculate_hover_power(params: DroneAeroParams = DroneAeroParams()) -> float:
    """
    Computes static hover power draw using Actuator Disk and Blade Element Momentum Theory (BEMT).

    P_hover = P_induced + P_profile + P_avionics
    P_induced = T^(3/2) / sqrt(2 * rho * A)
    P_profile = (1/8) * rho * sigma * Cd0 * A * (Omega * R)^3
    """
    thrust = params.mass_kg * params.gravity_mps2
    disk_area = params.num_rotors * math.pi * (params.rotor_radius_m ** 2)

    # Induced power
    p_induced = (thrust ** 1.5) / math.sqrt(2.0 * params.air_density_kgpm3 * disk_area)

    # Blade profile drag power
    p_profile = (
        0.125
        * params.air_density_kgpm3
        * params.rotor_solidity
        * params.blade_drag_coeff
        * disk_area
        * (params.hover_tip_speed_mps ** 3)
    )

    total_power = p_induced + p_profile + params.avionics_power_w
    return float(total_power)


def calculate_cruise_power(airspeed_mps: float, params: DroneAeroParams = DroneAeroParams()) -> float:
    """
    Computes forward flight cruise power draw using forward flight drag polars.

    P_cruise(V) = P_0 * (1 + 3 * V^2 / V_tip^2)
                + P_i * (sqrt(1 + V^4 / (4 * v_0^4)) - V^2 / (2 * v_0^2))^(1/2)
                + 0.5 * rho * Cd_body * A_body * V^3
                + P_avionics_cruise
    """
    v = max(0.0, float(airspeed_mps))
    thrust = params.mass_kg * params.gravity_mps2
    disk_area = params.num_rotors * math.pi * (params.rotor_radius_m ** 2)

    # Hover induced velocity v_0
    v_0 = math.sqrt(thrust / (2.0 * params.air_density_kgpm3 * disk_area))

    # Profile power at hover P_0
    p_0 = (
        0.125
        * params.air_density_kgpm3
        * params.rotor_solidity
        * params.blade_drag_coeff
        * disk_area
        * (params.hover_tip_speed_mps ** 3)
    )

    # Induced power at hover P_i
    p_i = (thrust ** 1.5) / math.sqrt(2.0 * params.air_density_kgpm3 * disk_area)

    # Profile term in forward flight
    term_profile = p_0 * (1.0 + 3.0 * (v ** 2) / (params.tip_speed_mps ** 2))

    # Induced term in forward flight
    ratio = (v ** 2) / (2.0 * (v_0 ** 2))
    inner = math.sqrt(1.0 + (v ** 4) / (4.0 * (v_0 ** 4))) - ratio
    term_induced = p_i * math.sqrt(max(0.0, inner))

    # Parasitic fuselage drag
    term_parasitic = 0.5 * params.air_density_kgpm3 * params.body_drag_coeff * params.body_frontal_area_m2 * (v ** 3)

    total_power = term_profile + term_induced + term_parasitic + params.cruise_avionics_power_w
    return float(total_power)


def find_best_range_speed(params: DroneAeroParams = DroneAeroParams(), v_min: float = 5.0, v_max: float = 25.0) -> float:
    """
    Computes best-range airspeed V_br = argmin_V (P(V) / V), minimizing energy per meter.
    """
    speeds = np.linspace(v_min, v_max, 201)
    powers = np.array([calculate_cruise_power(v, params) for v in speeds])
    specific_energies = powers / speeds
    min_idx = int(np.argmin(specific_energies))
    return float(speeds[min_idx])


def resolve_groundspeed(
    displacement_xy: tuple[float, float],
    wind_vector_xy: tuple[float, float],
    cruise_airspeed_mps: float = 14.5,
) -> tuple[float, float]:
    """
    Resolves ground speed V_g and travel time t_ij along displacement vector in presence of wind.

    Solves: |V_g * u_hat - W| = V_cruise
    V_g^2 - 2 * (W . u_hat) * V_g + (|W|^2 - V_cruise^2) = 0

    Returns:
        (groundspeed_mps, transit_time_seconds)
    """
    dx, dy = displacement_xy
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return (cruise_airspeed_mps, 0.0)

    u_x = dx / dist
    u_y = dy / dist
    w_x, w_y = wind_vector_xy

    w_dot_u = w_x * u_x + w_y * u_y
    w_mag_sq = w_x ** 2 + w_y ** 2
    v_cruise_sq = cruise_airspeed_mps ** 2

    discriminant = (w_dot_u ** 2) + (v_cruise_sq - w_mag_sq)

    if discriminant < 0:
        # Crosswind exceeds aircraft cruise airspeed envelope (W_cross > V_cruise).
        # Headway is clamped to a safe minimum positive speed (0.5 m/s) representing severe penalty.
        vg = max(0.5, w_dot_u) if w_dot_u > 0 else 0.5
    else:
        vg = w_dot_u + math.sqrt(discriminant)
        if vg < 0.5:
            # Aircraft encounters extreme headwind exceeding cruise airspeed
            vg = 0.5

    travel_time = dist / vg
    return (float(vg), float(travel_time))


def compute_dwell_energy(dwell_time_seconds: float, params: DroneAeroParams = DroneAeroParams()) -> float:
    """Computes total energy in Joules consumed during static inspection dwell."""
    p_hover = calculate_hover_power(params)
    return float(p_hover * max(0.0, dwell_time_seconds))


def compute_cost_matrices(
    nodes_xy: np.ndarray,
    wind_speed_mps: float = 0.0,
    wind_direction_deg: float = 0.0,
    cruise_speed_mps: float = 14.5,
    params: DroneAeroParams = DroneAeroParams(),
) -> tuple[np.ndarray, np.ndarray]:
    """
    Computes asymmetric time (seconds) and energy (Joules) matrices for an array of node coordinates.

    nodes_xy: Shape [N, 2] array of (x, y) coordinates in meters.
    wind_speed_mps: Ambient wind speed in m/s.
    wind_direction_deg: Meteorological wind heading in degrees (0 = North/from North, or angle in degrees).
    """
    n = len(nodes_xy)
    time_matrix = np.zeros((n, n), dtype=np.float64)
    energy_matrix = np.zeros((n, n), dtype=np.float64)

    # Convert wind speed and direction to Cartesian vector (W_x, W_y) blowing towards
    rad = math.radians(wind_direction_deg)
    # Wind vector blowing towards direction:
    wind_x = wind_speed_mps * math.cos(rad)
    wind_y = wind_speed_mps * math.sin(rad)
    wind_vector = (wind_x, wind_y)

    cruise_power = calculate_cruise_power(cruise_speed_mps, params)

    for i in range(n):
        xi, yi = nodes_xy[i]
        for j in range(n):
            if i == j:
                continue
            xj, yj = nodes_xy[j]
            disp = (xj - xi, yj - yi)
            vg, t_sec = resolve_groundspeed(disp, wind_vector, cruise_speed_mps)
            time_matrix[i, j] = t_sec
            energy_matrix[i, j] = cruise_power * t_sec

    return (time_matrix, energy_matrix)
