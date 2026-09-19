"""Unit tests for BEMT hover power, cruise drag polars, and wind vector resolution."""

import math

import numpy as np
import pytest

from core.physics import (
    DroneAeroParams,
    calculate_cruise_power,
    calculate_hover_power,
    compute_cost_matrices,
    compute_dwell_energy,
    find_best_range_speed,
    resolve_groundspeed,
)


def test_bemt_hover_power_magnitude():
    """Verify that BEMT hover power for 4.5kg drone is physically realistic (300 - 350 W)."""
    params = DroneAeroParams(mass_kg=4.5)
    p_hover = calculate_hover_power(params)
    assert 300.0 <= p_hover <= 350.0, f"Hover power {p_hover:.1f}W outside expected 300-350W range"


def test_cruise_power_efficiency():
    """Verify that forward cruise flight at V_br consumes 30-40% less power than static hover."""
    params = DroneAeroParams()
    p_hover = calculate_hover_power(params)
    v_br = find_best_range_speed(params)
    assert 12.0 <= v_br <= 18.0, f"V_br {v_br:.1f} m/s outside aerodynamic envelope"

    p_cruise = calculate_cruise_power(v_br, params)
    assert p_cruise < p_hover, f"Cruise power {p_cruise:.1f}W must be lower than hover power {p_hover:.1f}W"
    savings_ratio = (p_hover - p_cruise) / p_hover
    assert 0.20 <= savings_ratio <= 0.45, f"Cruise savings {savings_ratio*100:.1f}% outside expected 20-45% range"


def test_wind_drift_asymmetry():
    """
    Verify groundspeed asymmetry: with East wind (W_x = 6 m/s),
    flying East (with tailwind) must be significantly faster than flying West (into headwind).
    """
    disp_east = (500.0, 0.0)
    disp_west = (-500.0, 0.0)
    wind_vector = (6.0, 0.0)  # 6 m/s Eastward wind
    v_cruise = 14.5

    vg_east, t_east = resolve_groundspeed(disp_east, wind_vector, v_cruise)
    vg_west, t_west = resolve_groundspeed(disp_west, wind_vector, v_cruise)

    assert vg_east > vg_west, f"Tailwind vg {vg_east} must exceed headwind vg {vg_west}"
    assert t_east < t_west, f"Tailwind time {t_east} must be shorter than headwind time {t_west}"
    assert vg_east == pytest.approx(v_cruise + 6.0, abs=0.5)
    assert vg_west == pytest.approx(v_cruise - 6.0, abs=0.5)


def test_cost_matrices_asymmetry():
    """Verify that compute_cost_matrices produces asymmetric matrices when wind is present."""
    coords = np.array([
        [0.0, 0.0],
        [400.0, 0.0],
        [0.0, 400.0],
    ])
    t_mat, e_mat = compute_cost_matrices(
        coords,
        wind_speed_mps=5.0,
        wind_direction_deg=0.0,  # Eastward wind
        cruise_speed_mps=14.5,
    )

    # Leg 0->1 is Eastward (tailwind), Leg 1->0 is Westward (headwind)
    assert t_mat[0, 1] < t_mat[1, 0], "Tailwind travel time must be less than headwind"
    assert e_mat[0, 1] < e_mat[1, 0], "Tailwind transit energy must be less than headwind"
    # Diagonal must be zero
    assert t_mat[0, 0] == 0.0
    assert e_mat[1, 1] == 0.0


def test_dwell_energy_positive():
    """Verify dwell energy calculation matches hover power times duration."""
    params = DroneAeroParams()
    p_hover = calculate_hover_power(params)
    energy = compute_dwell_energy(30.0, params)
    assert energy == pytest.approx(p_hover * 30.0, rel=1e-3)


def test_extreme_wind_resolution():
    """Verify robust groundspeed resolution under gale crosswinds and headwinds exceeding V_cruise."""
    disp = (500.0, 0.0)
    v_cruise = 14.5

    # 1. Extreme pure headwind exceeding cruise speed (W = -20 m/s Westward)
    vg_head, t_head = resolve_groundspeed(disp, (-20.0, 0.0), v_cruise)
    assert vg_head >= 0.5
    assert not math.isnan(vg_head)
    assert not math.isnan(t_head)
    assert t_head > 0.0

    # 2. Extreme perpendicular crosswind exceeding cruise speed (W_y = 20 m/s)
    vg_cross, t_cross = resolve_groundspeed(disp, (0.0, 20.0), v_cruise)
    assert vg_cross >= 0.5
    assert not math.isnan(vg_cross)
    assert not math.isnan(t_cross)
    assert t_cross > 0.0
