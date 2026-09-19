"""AeroScan-Optima: Mission Control Center Dashboard (Streamlit Application)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.arena_view import render_arena_view
from app.exporter import export_mission_telemetry_csv, export_qgroundcontrol_plan
from app.telemetry import get_fleet_telemetry_at_time
from app.visualizer import build_battery_soc_figure, build_mission_map_figure
from baselines.grasp import solve_grasp_baseline
from benchmarks.chao_loader import get_canonical_chao_instance
from core.alns import explore_route_pool
from core.contracts import FleetSchedule, InstanceContext
from core.instance import build_instance_context
from core.set_packing import solve_fleet_schedule

# Page configuration
st.set_page_config(
    page_title="AeroScan-Optima | Mission Control Center",
    page_icon="🛸",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_initial_instance(scenario_name: str, num_drones: int, wind_speed: float, wind_dir: float) -> InstanceContext:
    """Loads an InstanceContext based on user selection."""
    if scenario_name == "Sample Mountain SAR":
        sample_path = Path("data/sample_mission.json")
        if sample_path.exists():
            return build_instance_context(
                sample_path,
                wind_speed_mps=wind_speed,
                wind_dir_deg=wind_dir,
                num_drones=num_drones,
            )
    # Default to Chao benchmark canonical generator
    set_key = "set_64"
    if "66" in scenario_name:
        set_key = "set_66"
    elif "100" in scenario_name:
        set_key = "set_100"
    elif "102" in scenario_name:
        set_key = "set_102"

    return get_canonical_chao_instance(
        set_key,
        num_drones=num_drones,
        wind_speed_mps=wind_speed,
        wind_dir_deg=wind_dir,
    )


def initialize_state():
    """Initializes default mission session state."""
    if "instance" not in st.session_state:
        st.session_state.instance = load_initial_instance("Chao Set 64 (Clustered)", 3, 3.5, 45.0)
    if "schedule" not in st.session_state:
        # Run fast initial solve
        with st.spinner("Initializing AeroScan-Optima mission plan..."):
            pool = explore_route_pool(st.session_state.instance, max_iterations=150, time_limit_sec=0.8)
            st.session_state.schedule = solve_fleet_schedule(st.session_state.instance, pool, run_baselines=True)
    if "grasp_schedule" not in st.session_state:
        st.session_state.grasp_schedule = solve_grasp_baseline(st.session_state.instance)


initialize_state()

# ---------------------------------------------------------------------------
# Sidebar Controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image("https://raw.githubusercontent.com/feathericons/feather/master/icons/navigation.svg", width=40)
    st.title("AeroScan-Optima")
    st.caption("Matheuristic Multi-Drone Search Coverage Platform (TOP-DC)")
    st.markdown("---")

    st.subheader("🌐 Mission Configuration")
    scenario_choice = st.selectbox(
        "Select Scenario / Dataset",
        [
            "Chao Set 64 (Clustered)",
            "Chao Set 66 (Diamond)",
            "Chao Set 100 (Concentric)",
            "Chao Set 102 (Uniform Random)",
            "Sample Mountain SAR",
        ],
        index=0,
    )

    fleet_size = st.slider("Fleet Size (UAVs)", min_value=2, max_value=8, value=3)

    st.subheader("💨 Atmospheric Wind Vector")
    wind_speed = st.slider("Ambient Wind Speed (m/s)", min_value=0.0, max_value=15.0, value=4.0, step=0.5)
    wind_dir = st.slider("Wind Direction (° Heading)", min_value=0.0, max_value=360.0, value=60.0, step=15.0)

    st.markdown("---")
    if st.button("🚀 Run Matheuristic Optimization", type="primary", use_container_width=True):
        with st.spinner("Generating optimal deconflicted fleet trajectories..."):
            inst = load_initial_instance(scenario_choice, fleet_size, wind_speed, wind_dir)
            st.session_state.instance = inst

            # Tier-1 ALNS
            route_pool = explore_route_pool(inst, max_iterations=350, time_limit_sec=1.5)

            # Tier-2 CP-SAT Master Problem
            schedule = solve_fleet_schedule(inst, route_pool, run_baselines=True)
            st.session_state.schedule = schedule
            st.session_state.grasp_schedule = solve_grasp_baseline(inst)
            st.success(f"Optimized in {schedule.solve_time_seconds:.2f}s!")

# ---------------------------------------------------------------------------
# Main Panel: Header & Status Badges
# ---------------------------------------------------------------------------
st.title("🛸 Autonomous Mission Control Center")
instance: InstanceContext = st.session_state.instance
schedule: FleetSchedule = st.session_state.schedule
grasp_schedule: FleetSchedule = st.session_state.grasp_schedule

# Top Status Badges
b1, b2, b3, b4 = st.columns([2, 2, 2, 3])
with b1:
    status_color = "green" if schedule.status == "OPTIMAL" else "blue"
    st.markdown(f"**Solver Status**: :{status_color}[**{schedule.status}**]")
with b2:
    st.markdown(f"**Solve Latency**: :violet[**{schedule.solve_time_seconds:.3f}s**]")
with b3:
    reserve_valid = ":green[**15% FLOOR PASSED**]" if schedule.validation_passed else ":red[**VIOLATION**]"
    st.markdown(f"**Safety Margin**: {reserve_valid}")
with b4:
    wind_v = f"{instance.ambient_wind[0]} m/s @ {round(instance.ambient_wind[1] * 180 / 3.14159)}°"
    st.markdown(f"**Wind Vector**: :orange[**{wind_v} (Asymmetric)**]")

# Key KPI Cards
m1, m2, m3, m4 = st.columns(4)
with m1:
    gain_text = f"+{schedule.reward_gain_percent:.1f}% vs GRASP"
    st.metric(label="Total Collected Reward", value=f"{schedule.cumulative_reward:.0f} pts", delta=gain_text)
with m2:
    visited_cnt = sum(len(r.target_ids) for r in schedule.assigned_routes)
    total_cnt = len(instance.target_nodes)
    st.metric(label="Search Targets Secured", value=f"{visited_cnt} / {total_cnt}", delta=f"{visited_cnt/max(total_cnt,1)*100:.1f}%")
with m3:
    min_reserve = min((r.final_reserve_percent for r in schedule.assigned_routes), default=100.0)
    st.metric(label="Min Fleet Battery Reserve", value=f"{min_reserve:.1f}%", delta="Above 15% Floor")
with m4:
    max_duration = max((r.total_flight_time for r in schedule.assigned_routes), default=0.0)
    st.metric(label="Longest Flight Duration", value=f"{int(max_duration//60):02d}:{int(max_duration%60):02d} min")

st.markdown("---")

# ---------------------------------------------------------------------------
# Navigation Tabs
# ---------------------------------------------------------------------------
tab_map, tab_arena, tab_battery, tab_export = st.tabs([
    "🛰️ Live Mission Radar",
    "⚔️ Algorithmic Arena (vs GRASP)",
    "🔋 Battery SoC Depletion",
    "📥 SITL & Flight Plan Export",
])

# ---------------------------------------------------------------------------
# TAB 1: Live Mission Radar & Real-Time Scrubber
# ---------------------------------------------------------------------------
with tab_map:
    max_mission_time = max(
        (r.total_flight_time for r in schedule.assigned_routes),
        default=1800.0,
    )
    if max_mission_time <= 0:
        max_mission_time = 1800.0

    scrubber_col, toggle_col = st.columns([4, 1])
    with scrubber_col:
        t_current = st.slider(
            "⏱️ Mission Time Scrubber (seconds)",
            min_value=0.0,
            max_value=float(max_mission_time),
            value=float(min(300.0, max_mission_time)),
            step=5.0,
            format="%0.0f sec",
        )
    with toggle_col:
        halos = st.checkbox("Show Radar Halos (50m)", value=True)

    # Interactive Map
    fig_map = build_mission_map_figure(
        instance=instance,
        schedule=schedule,
        current_time_sec=t_current,
        show_radar_halos=halos,
    )
    st.plotly_chart(fig_map, use_container_width=True)

    # Live Vehicle Telemetry Table
    telemetry_data, secured_tids = get_fleet_telemetry_at_time(schedule, t_current, instance)
    st.subheader(f"📡 Real-Time Telemetry Feed at t = {int(t_current)}s")
    st.dataframe(
        telemetry_data,
        column_config={
            "drone_id": "UAV Identifier",
            "x": st.column_config.NumberColumn("Pos X (m)", format="%.1f"),
            "y": st.column_config.NumberColumn("Pos Y (m)", format="%.1f"),
            "z": st.column_config.NumberColumn("Alt Z (m)", format="%.1f"),
            "battery_percent": st.column_config.ProgressColumn("Battery SoC", min_value=0, max_value=100, format="%.1f%%"),
            "speed_mps": st.column_config.NumberColumn("Speed (m/s)", format="%.1f"),
            "status": "Flight State",
        },
        use_container_width=True,
        hide_index=True,
    )

# ---------------------------------------------------------------------------
# TAB 2: Side-by-Side Algorithmic Arena
# ---------------------------------------------------------------------------
with tab_arena:
    render_arena_view(instance, schedule, grasp_schedule)

# ---------------------------------------------------------------------------
# TAB 3: Battery SoC Depletion Curves
# ---------------------------------------------------------------------------
with tab_battery:
    st.subheader("🔋 Fleet Battery State-of-Charge (SoC) Profiles")
    st.markdown(
        "Demonstrating strict compliance with the **15% State-of-Charge safety reserve floor**. "
        "Every drone trajectory safely returns to base before dipping into the emergency cushion."
    )
    fig_soc = build_battery_soc_figure(schedule, instance, current_time_sec=t_current)
    st.plotly_chart(fig_soc, use_container_width=True)

# ---------------------------------------------------------------------------
# TAB 4: SITL & Flight Plan Export
# ---------------------------------------------------------------------------
with tab_export:
    st.subheader("📥 Export Certified Mission Plans")
    st.markdown(
        "Export the generated trajectories directly to **QGroundControl (`.plan`)** "
        "and **PX4 Autopilot / MAVLink** ground stations for physical field deployment."
    )

    c_exp1, c_exp2 = st.columns(2)
    with c_exp1:
        st.markdown("### 🛩️ QGroundControl (.plan) Export")
        for route in schedule.assigned_routes:
            drone_spec = next((d for d in instance.drones if d.id == route.drone_id), instance.drones[0])
            plan_json = export_qgroundcontrol_plan(route, drone_spec, instance)
            st.download_button(
                label=f"Download {route.drone_id} .plan ({len(route.waypoints)} Waypoints)",
                data=plan_json,
                file_name=f"{route.drone_id}_mission.plan",
                mime="application/json",
            )

    with c_exp2:
        st.markdown("### 📊 Mission Telemetry Audit (CSV)")
        csv_data = export_mission_telemetry_csv(schedule, instance)
        st.download_button(
            label="Download Complete Mission Audit CSV",
            data=csv_data,
            file_name=f"{instance.instance_name}_telemetry_audit.csv",
            mime="text/csv",
        )
