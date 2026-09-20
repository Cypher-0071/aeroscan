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
    energy_per_distance,
    find_best_range_speed,
    hover_power_breakdown,
    resolve_groundspeed,
    wind_to_vector,
)

# ---------------------------------------------------------------------------
# Hover power
# ---------------------------------------------------------------------------


def test_bemt_hover_power_magnitude():
    """Verify that BEMT hover power for 4.5kg drone is physically realistic (300 - 350 W)."""
    params = DroneAeroParams(mass_kg=4.5)
    p_hover = calculate_hover_power(params)
    assert 300.0 <= p_hover <= 350.0, f"Hover power {p_hover:.1f}W outside expected 300-350W range"


def test_default_hover_power_regression():
    """Pin the calibrated default hover power so parameter drift is caught."""
    assert calculate_hover_power() == pytest.approx(328.66, abs=1.0)


def test_hover_power_breakdown_components_sum_to_total():
    """Induced + profile + avionics components must reconstruct the public hover result."""
    breakdown = hover_power_breakdown()
    assert breakdown.total_w == pytest.approx(
        breakdown.induced_w + breakdown.profile_w + breakdown.avionics_w, rel=1e-12
    )
    assert breakdown.total_w == pytest.approx(calculate_hover_power(), rel=1e-12)
    assert breakdown.induced_w > 0.0
    assert breakdown.profile_w > 0.0
    assert breakdown.avionics_w == pytest.approx(45.0)


def test_default_params_are_not_shared_mutables():
    """Calling without params must not expose or mutate a module-level default instance."""
    first = DroneAeroParams(mass_kg=9.0)
    assert calculate_hover_power(first) > calculate_hover_power()
    # A later default call is unaffected by the custom instance above.
    assert calculate_hover_power() == pytest.approx(328.66, abs=1.0)


@pytest.mark.parametrize(
    "overrides",
    [
        {"mass_kg": 0.0},
        {"mass_kg": -1.0},
        {"num_rotors": 0},
        {"rotor_radius_m": 0.0},
        {"air_density_kgpm3": 0.0},
        {"rotor_solidity": -0.1},
        {"blade_drag_coeff": 0.0},
        {"hover_tip_speed_mps": 0.0},
        {"tip_speed_mps": -5.0},
        {"avionics_power_w": -1.0},
    ],
)
def test_invalid_aero_params_raise(overrides):
    """Physically impossible parameters must raise a useful ValueError."""
    params = DroneAeroParams(**overrides)
    with pytest.raises(ValueError):
        calculate_hover_power(params)


# ---------------------------------------------------------------------------
# Cruise polar and best range
# ---------------------------------------------------------------------------


def test_cruise_power_efficiency():
    """Verify that forward cruise flight at V_br consumes 20-45% less power than static hover."""
    params = DroneAeroParams()
    p_hover = calculate_hover_power(params)
    v_br = find_best_range_speed(params)
    assert 12.0 <= v_br <= 18.0, f"V_br {v_br:.1f} m/s outside aerodynamic envelope"

    p_cruise = calculate_cruise_power(v_br, params)
    assert p_cruise < p_hover, f"Cruise power {p_cruise:.1f}W must be lower than hover power {p_hover:.1f}W"
    savings_ratio = (p_hover - p_cruise) / p_hover
    assert 0.20 <= savings_ratio <= 0.45, f"Cruise savings {savings_ratio*100:.1f}% outside expected 20-45% range"


def test_cruise_power_is_robust_at_small_speed():
    """The polar must be finite and positive as airspeed tends to zero."""
    for v in (0.0, 1e-6, 0.01, 0.5):
        power = calculate_cruise_power(v)
        assert math.isfinite(power)
        assert power > 0.0


def test_cruise_power_rejects_negative_speed():
    with pytest.raises(ValueError):
        calculate_cruise_power(-0.5)


def test_energy_per_distance_rejects_non_positive_speed():
    for bad in (0.0, -3.0):
        with pytest.raises(ValueError):
            energy_per_distance(bad)


def test_find_best_range_speed_is_deterministic():
    first = find_best_range_speed()
    second = find_best_range_speed()
    assert first == second
    assert 12.0 <= first <= 18.0


def test_find_best_range_speed_minimizes_energy_per_meter():
    """The returned airspeed must beat its immediate grid neighbours."""
    v_br = find_best_range_speed(resolution=201)
    assert energy_per_distance(v_br) <= energy_per_distance(v_br + 0.1)
    assert energy_per_distance(v_br) <= energy_per_distance(v_br - 0.1)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"v_min": 0.0},
        {"v_min": -1.0},
        {"v_min": 20.0, "v_max": 10.0},
        {"resolution": 1},
    ],
)
def test_find_best_range_speed_validates_search_config(kwargs):
    with pytest.raises(ValueError):
        find_best_range_speed(**kwargs)


# ---------------------------------------------------------------------------
# Wind convention and groundspeed resolution
# ---------------------------------------------------------------------------


def test_wind_to_vector_convention():
    """0 degrees is +x/East and the angle increases counter-clockwise."""
    assert wind_to_vector(10.0, 0.0) == pytest.approx((10.0, 0.0), abs=1e-9)
    assert wind_to_vector(10.0, 90.0) == pytest.approx((0.0, 10.0), abs=1e-9)
    assert wind_to_vector(10.0, 180.0) == pytest.approx((-10.0, 0.0), abs=1e-9)
    with pytest.raises(ValueError):
        wind_to_vector(-1.0, 0.0)


def test_zero_length_displacement_has_no_transit_time():
    vg, t = resolve_groundspeed((0.0, 0.0), (5.0, 0.0), 14.5)
    assert vg == pytest.approx(14.5)
    assert t == 0.0


def test_resolve_groundspeed_rejects_non_positive_airspeed():
    with pytest.raises(ValueError):
        resolve_groundspeed((100.0, 0.0), (0.0, 0.0), 0.0)


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


def test_crosswind_exceeding_airspeed_is_unreachable():
    """A crosswind stronger than the airspeed makes the track physically untrackable."""
    vg, t = resolve_groundspeed((500.0, 0.0), (0.0, 20.0), 14.5)
    assert vg == math.inf
    assert t == math.inf


def test_exact_headwind_is_unreachable():
    """An exact headwind equal to the airspeed leaves zero forward progress."""
    vg, t = resolve_groundspeed((500.0, 0.0), (-14.5, 0.0), 14.5)
    assert vg == math.inf
    assert t == math.inf


def test_overwhelming_headwind_is_unreachable():
    vg, t = resolve_groundspeed((500.0, 0.0), (-20.0, 0.0), 14.5)
    assert vg == math.inf
    assert t == math.inf


# ---------------------------------------------------------------------------
# Cost matrices
# ---------------------------------------------------------------------------


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


def test_cost_matrices_are_symmetric_without_wind():
    coords = np.array([[0.0, 0.0], [400.0, 250.0], [-120.0, 300.0]])
    t_mat, e_mat = compute_cost_matrices(coords, wind_speed_mps=0.0)
    assert np.allclose(t_mat, t_mat.T)
    assert np.allclose(e_mat, e_mat.T)


def test_cost_matrix_invariants():
    """Shape, dtype, contiguity, diagonals, and unreachable-arc consistency."""
    coords = np.array([[0.0, 0.0], [400.0, 0.0], [0.0, 400.0], [-400.0, -400.0]])
    t_mat, e_mat = compute_cost_matrices(coords, wind_speed_mps=3.0, wind_direction_deg=30.0)

    for matrix in (t_mat, e_mat):
        assert matrix.shape == (4, 4)
        assert matrix.dtype == np.float64
        assert matrix.flags["C_CONTIGUOUS"]
        assert np.all(np.diag(matrix) == 0.0)
        assert np.all(np.isfinite(matrix))
    assert t_mat[0, 1] < t_mat[1, 0]
    assert e_mat[0, 1] < e_mat[1, 0]


def test_cost_matrices_propagate_unreachable_arcs():
    """Impossible wind must yield np.inf in BOTH matrices, never a clamped slow arc."""
    coords = np.array([[0.0, 0.0], [500.0, 0.0], [0.0, 500.0]])
    t_mat, e_mat = compute_cost_matrices(
        coords, wind_speed_mps=20.0, wind_direction_deg=90.0, cruise_speed_mps=14.5
    )
    assert t_mat[0, 1] == np.inf
    assert e_mat[0, 1] == np.inf
    assert np.array_equal(np.isfinite(t_mat), np.isfinite(e_mat))
    # Diagonal stays exactly zero even when other arcs are unreachable.
    assert t_mat[0, 0] == 0.0
    assert e_mat[2, 2] == 0.0


def test_cost_matrices_energy_uses_cruise_power_and_transit_only():
    """Transit energy equals cruise power * transit time; dwell energy is charged elsewhere."""
    coords = np.array([[0.0, 0.0], [500.0, 0.0]])
    _t_mat, e_mat = compute_cost_matrices(coords, wind_speed_mps=0.0, cruise_speed_mps=14.5)
    expected_time = 500.0 / 14.5
    cruise_power = calculate_cruise_power(14.5)
    assert e_mat[0, 1] == pytest.approx(cruise_power * expected_time, rel=1e-9)
    # 30 s of dwell is strictly additional energy, never folded into transit.
    assert compute_dwell_energy(30.0) > 0.0


def test_cost_matrices_reject_bad_inputs():
    with pytest.raises(ValueError):
        compute_cost_matrices(np.array([0.0, 1.0]))
    with pytest.raises(ValueError):
        compute_cost_matrices(np.array([[0.0, 0.0], [np.nan, 1.0]]))
    with pytest.raises(ValueError):
        compute_cost_matrices(np.array([[0.0, 0.0]]), cruise_speed_mps=0.0)


# ---------------------------------------------------------------------------
# Dwell energy
# ---------------------------------------------------------------------------


def test_dwell_energy_positive():
    """Verify dwell energy calculation matches hover power times duration."""
    params = DroneAeroParams()
    p_hover = calculate_hover_power(params)
    energy = compute_dwell_energy(30.0, params)
    assert energy == pytest.approx(p_hover * 30.0, rel=1e-3)


def test_dwell_energy_clamps_negative_duration():
    assert compute_dwell_energy(-5.0) == 0.0
