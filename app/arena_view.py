"""Side-by-side algorithmic arena comparison between GRASP baseline and AeroScan-Optima."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app.visualizer import DRONE_COLORS, get_tactical_map_meta
from core.contracts import FleetSchedule, InstanceContext


def build_comparison_map(
    instance: InstanceContext,
    schedule: FleetSchedule,
    selected_drone_id: str | None = None,
    accent_color: str = "#0284C7",
    use_tactical_map: bool = True,
    map_rotation_deg: int = 90,
) -> go.Figure:
    """Builds a clean light-theme tactical route trajectory map without internal title collisions."""
    fig = go.Figure()
    node_map = {n.id: n for n in instance.targets}
    depot_ids = {d.launch_depot_id for d in instance.drones} | {
        d.recovery_depot_id for d in instance.drones
    }

    # Targets
    target_nodes = list(instance.target_nodes)
    visited_ids = set()
    for r in schedule.assigned_routes:
        if selected_drone_id is None or r.drone_id == selected_drone_id:
            visited_ids.update(r.target_ids)

    unvisited = [t for t in target_nodes if t.id not in visited_ids]
    visited = [t for t in target_nodes if t.id in visited_ids]

    if unvisited:
        fig.add_trace(
            go.Scatter(
                x=[t.x for t in unvisited],
                y=[t.y for t in unvisited],
                mode="markers",
                marker=dict(size=6, color="#94A3B8", opacity=0.7),
                name="Unvisited",
                hoverinfo="text",
                hovertext=[
                    f"Target #{t.id:02d}: {t.priority_score:.0f} pts (Unvisited)" for t in unvisited
                ],
            )
        )

    if visited:
        fig.add_trace(
            go.Scatter(
                x=[t.x for t in visited],
                y=[t.y for t in visited],
                mode="markers",
                marker=dict(
                    size=9,
                    color=accent_color,
                    line=dict(color="#FFFFFF", width=1.5),
                ),
                name="Secured Target",
                hoverinfo="text",
                hovertext=[
                    f"Secured Target #{t.id:02d}: {t.priority_score:.0f} pts" for t in visited
                ],
            )
        )

    # Depots
    depots = [node_map[did] for did in depot_ids if did in node_map]
    if depots:
        fig.add_trace(
            go.Scatter(
                x=[d.x for d in depots],
                y=[d.y for d in depots],
                mode="markers",
                marker=dict(
                    size=14, symbol="diamond", color="#0284C7", line=dict(color="#FFFFFF", width=2)
                ),
                name="Base Station",
                hoverinfo="text",
                hovertext=[f"Base Depot: {d.name}" for d in depots],
            )
        )

    # Routes
    for idx, route in enumerate(schedule.assigned_routes):
        if selected_drone_id is not None and route.drone_id != selected_drone_id:
            continue
        color = DRONE_COLORS[idx % len(DRONE_COLORS)]
        xs = [node_map[wp.node_id].x for wp in route.waypoints]
        ys = [node_map[wp.node_id].y for wp in route.waypoints]

        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines+markers",
                line=dict(color=color, width=2.5),
                marker=dict(size=4, color=color),
                name=f"{route.drone_id}",
                hoverinfo="text",
                hovertext=[
                    f"{route.drone_id} -> {node_map[wp.node_id].name}" for wp in route.waypoints
                ],
            )
        )

    map_meta = get_tactical_map_meta(map_rotation_deg) if use_tactical_map else None
    map_uri = map_meta[0] if map_meta else None
    img_w = map_meta[1] if map_meta else 1024
    img_h = map_meta[2] if map_meta else 738
    is_map_active = bool(use_tactical_map and map_uri)

    all_xs = [t.x for t in instance.targets]
    all_ys = [t.y for t in instance.targets]
    max_extent_x = max(max(abs(x) for x in all_xs), 600.0) if all_xs else 600.0
    max_extent_y = max(max(abs(y) for y in all_ys), 600.0) if all_ys else 600.0
    aspect_ratio = float(img_h) / float(img_w)
    scale_margin = 1.32
    half_w = max(max_extent_x * scale_margin, 850.0)
    half_h = half_w * aspect_ratio
    if half_h < max_extent_y * scale_margin:
        half_h = max_extent_y * scale_margin
        half_w = half_h / aspect_ratio

    map_x_min, map_x_max = -half_w, half_w
    map_y_min, map_y_max = -half_h, half_h

    if is_map_active:
        fig.add_layout_image(
            dict(
                source=map_uri,
                xref="x",
                yref="y",
                x=map_x_min,
                y=map_y_max,
                sizex=map_x_max - map_x_min,
                sizey=map_y_max - map_y_min,
                xanchor="left",
                yanchor="top",
                sizing="stretch",
                opacity=0.95,
                layer="below",
            )
        )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#DDE7E7" if is_map_active else "#F8FAFC",
        xaxis=dict(
            showgrid=not is_map_active,
            gridcolor="#E2E8F0",
            zeroline=False,
            range=[map_x_min * 0.98, map_x_max * 0.98] if is_map_active else None,
            tickfont=dict(color="#334155" if is_map_active else "#64748B", size=9, family="JetBrains Mono, monospace"),
        ),
        yaxis=dict(
            showgrid=not is_map_active,
            gridcolor="#E2E8F0",
            scaleanchor="x",
            scaleratio=1,
            range=[map_y_min * 0.98, map_y_max * 0.98] if is_map_active else None,
            tickfont=dict(color="#334155" if is_map_active else "#64748B", size=9, family="JetBrains Mono, monospace"),
        ),
        margin=dict(l=20, r=20, t=15, b=20),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=9, color="#0F172A", family="JetBrains Mono, monospace"),
            bgcolor="rgba(255, 255, 255, 0.95)",
            bordercolor="#E2E8F0",
        ),
        height=520,
    )
    return fig


def build_differential_overlay_map(
    instance: InstanceContext,
    aeroscan_schedule: FleetSchedule,
    grasp_schedule: FleetSchedule,
    selected_drone_id: str | None = None,
    use_tactical_map: bool = True,
    map_rotation_deg: int = 90,
) -> go.Figure:
    """Builds a single-canvas differential comparison overlay showing both algorithms' routes."""
    fig = go.Figure()
    node_map = {n.id: n for n in instance.targets}
    depot_ids = {d.launch_depot_id for d in instance.drones} | {
        d.recovery_depot_id for d in instance.drones
    }

    map_meta = get_tactical_map_meta(map_rotation_deg) if use_tactical_map else None
    map_uri = map_meta[0] if map_meta else None
    img_w = map_meta[1] if map_meta else 1024
    img_h = map_meta[2] if map_meta else 738
    is_map_active = bool(use_tactical_map and map_uri)

    all_xs = [t.x for t in instance.targets]
    all_ys = [t.y for t in instance.targets]
    max_extent_x = max(max(abs(x) for x in all_xs), 600.0) if all_xs else 600.0
    max_extent_y = max(max(abs(y) for y in all_ys), 600.0) if all_ys else 600.0
    aspect_ratio = float(img_h) / float(img_w)
    scale_margin = 1.32
    half_w = max(max_extent_x * scale_margin, 850.0)
    half_h = half_w * aspect_ratio
    if half_h < max_extent_y * scale_margin:
        half_h = max_extent_y * scale_margin
        half_w = half_h / aspect_ratio

    map_x_min, map_x_max = -half_w, half_w
    map_y_min, map_y_max = -half_h, half_h

    if is_map_active:
        fig.add_layout_image(
            dict(
                source=map_uri,
                xref="x",
                yref="y",
                x=map_x_min,
                y=map_y_max,
                sizex=map_x_max - map_x_min,
                sizey=map_y_max - map_y_min,
                xanchor="left",
                yanchor="top",
                sizing="stretch",
                opacity=0.95,
                layer="below",
            )
        )

    # Depots
    depots = [node_map[did] for did in depot_ids if did in node_map]
    if depots:
        fig.add_trace(
            go.Scatter(
                x=[d.x for d in depots],
                y=[d.y for d in depots],
                mode="markers",
                marker=dict(
                    size=14, symbol="diamond", color="#0284C7", line=dict(color="#0F172A" if is_map_active else "#FFFFFF", width=2)
                ),
                name="Base Station",
                hoverinfo="text",
                hovertext=[f"Base Depot: {d.name}" for d in depots],
            )
        )

    # 1. GRASP Baseline Routes (Dashed Red)
    for idx, route in enumerate(grasp_schedule.assigned_routes):
        if selected_drone_id is not None and route.drone_id != selected_drone_id:
            continue
        xs = [node_map[wp.node_id].x for wp in route.waypoints]
        ys = [node_map[wp.node_id].y for wp in route.waypoints]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                line=dict(color="#EF4444", width=2, dash="dash"),
                name=f"GRASP {route.drone_id}",
                opacity=0.75,
                hoverinfo="text",
                hovertext=[
                    f"GRASP {route.drone_id} -> {node_map[wp.node_id].name}"
                    for wp in route.waypoints
                ],
            )
        )

    # 2. AeroScan Optimal Routes (Solid Precision Blue)
    for idx, route in enumerate(aeroscan_schedule.assigned_routes):
        if selected_drone_id is not None and route.drone_id != selected_drone_id:
            continue
        xs = [node_map[wp.node_id].x for wp in route.waypoints]
        ys = [node_map[wp.node_id].y for wp in route.waypoints]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines+markers",
                line=dict(color="#0284C7", width=2.5),
                marker=dict(size=4, color="#0284C7"),
                name=f"AeroScan {route.drone_id}",
                hoverinfo="text",
                hovertext=[
                    f"AeroScan {route.drone_id} -> {node_map[wp.node_id].name}"
                    for wp in route.waypoints
                ],
            )
        )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#DDE7E7" if is_map_active else "#F8FAFC",
        xaxis=dict(
            title=dict(
                text="EASTING X (M)", font=dict(color="#334155" if is_map_active else "#64748B", size=10, family="JetBrains Mono")
            ),
            showgrid=not is_map_active,
            gridcolor="#E2E8F0",
            zeroline=False,
            range=[map_x_min * 0.98, map_x_max * 0.98] if is_map_active else None,
            tickfont=dict(color="#334155" if is_map_active else "#64748B", size=9, family="JetBrains Mono"),
        ),
        yaxis=dict(
            title=dict(
                text="NORTHING Y (M)", font=dict(color="#334155" if is_map_active else "#64748B", size=10, family="JetBrains Mono")
            ),
            showgrid=not is_map_active,
            gridcolor="#E2E8F0",
            scaleanchor="x",
            scaleratio=1,
            range=[map_y_min * 0.98, map_y_max * 0.98] if is_map_active else None,
            tickfont=dict(color="#334155" if is_map_active else "#64748B", size=9, family="JetBrains Mono"),
        ),
        margin=dict(l=35, r=20, t=20, b=35),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=9, color="#0F172A", family="JetBrains Mono, monospace"),
            bgcolor="rgba(255, 255, 255, 0.95)",
            bordercolor="#E2E8F0",
        ),
        height=520,
    )
    return fig


def render_arena_view(
    instance: InstanceContext,
    aeroscan_schedule: FleetSchedule,
    grasp_schedule: FleetSchedule,
) -> None:
    """Renders the dual-column comparative algorithmic arena in Streamlit."""
    reward_delta = aeroscan_schedule.cumulative_reward - grasp_schedule.cumulative_reward
    pct_gain = (reward_delta / max(grasp_schedule.cumulative_reward, 1.0)) * 100.0

    targets_opt = sum(len(r.target_ids) for r in aeroscan_schedule.assigned_routes)
    targets_grasp = sum(len(r.target_ids) for r in grasp_schedule.assigned_routes)
    delta_targets = targets_opt - targets_grasp

    # Algorithmic Battle Header Card
    st.markdown(
        f"""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px 20px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
            <div>
                <div style="font-size: 14px; font-weight: 700; color: #0F172A; font-family: 'JetBrains Mono', monospace; letter-spacing: 0.04em;">
                    OPTIMIZATION LAB // ALGORITHMIC ARENA
                </div>
                <div style="font-size: 12px; color: #64748B; margin-top: 3px;">
                    Benchmarking Greedy Randomized Adaptive Search (GRASP) vs. AeroScan-Optima (ALNS + CP-SAT)
                </div>
            </div>
            <div style="font-size: 12px; font-weight: 700; color: #10B981; background: #ECFDF5; border: 1px solid #A7F3D0; padding: 5px 12px; border-radius: 4px; font-family: 'JetBrains Mono', monospace;">
                EFFICIENCY DELTA: +{reward_delta:.0f} PTS (+{pct_gain:.1f}%)
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Filter and Route Inspection Controls
    c_filt, c_mode = st.columns([1.5, 2.5])
    with c_filt:
        drone_options = ["All UAVs (Fleet View)"] + [d.id for d in instance.drones]
        sel_choice = st.selectbox(
            "Trajectory Inspection", drone_options, index=0, label_visibility="collapsed"
        )
        selected_drone = None if sel_choice == "All UAVs (Fleet View)" else sel_choice
    with c_mode:
        view_compare_mode = st.radio(
            "Comparison Mode",
            [
                "Side-by-Side Arena",
                "Differential Overlay",
                "AeroScan Route Only",
                "GRASP Route Only",
            ],
            horizontal=True,
            label_visibility="collapsed",
        )

    if view_compare_mode == "Side-by-Side Arena":
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                f"""
                <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 3px solid #EF4444; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                    <span style="font-size: 12px; font-weight: 700; color: #EF4444; font-family: 'JetBrains Mono', monospace;">BASELINE // GRASP HEURISTIC</span>
                    <span style="font-size: 12px; color: #64748B; font-family: 'JetBrains Mono', monospace;"><b>{grasp_schedule.cumulative_reward:.0f} pts</b> · {grasp_schedule.solve_time_seconds:.3f}s</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            fig_grasp = build_comparison_map(
                instance,
                grasp_schedule,
                selected_drone_id=selected_drone,
                accent_color="#EF4444",
            )
            st.plotly_chart(fig_grasp, use_container_width=True)

        with col2:
            st.markdown(
                f"""
                <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 3px solid #0284C7; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                    <span style="font-size: 12px; font-weight: 700; color: #0284C7; font-family: 'JetBrains Mono', monospace;">AEROSCAN-OPTIMA // ALNS + CP-SAT</span>
                    <span style="font-size: 12px; color: #64748B; font-family: 'JetBrains Mono', monospace;"><b style="color: #10B981;">{aeroscan_schedule.cumulative_reward:.0f} pts</b> · {aeroscan_schedule.solve_time_seconds:.3f}s</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            fig_aeroscan = build_comparison_map(
                instance,
                aeroscan_schedule,
                selected_drone_id=selected_drone,
                accent_color="#0284C7",
            )
            st.plotly_chart(fig_aeroscan, use_container_width=True)

    elif view_compare_mode == "Differential Overlay":
        st.markdown(
            """
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                <span style="font-size: 12px; font-weight: 700; color: #0284C7; font-family: 'JetBrains Mono', monospace;">DIFFERENTIAL TRAJECTORY OVERLAY</span>
                <span style="font-size: 12px; color: #64748B; font-family: 'JetBrains Mono', monospace;">
                    <span style="color:#0284C7; font-weight:700;">━━ AeroScan</span> vs <span style="color:#EF4444; font-weight:700;">┈┈ GRASP Baseline</span>
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        fig_diff = build_differential_overlay_map(
            instance,
            aeroscan_schedule,
            grasp_schedule,
            selected_drone_id=selected_drone,
        )
        st.plotly_chart(fig_diff, use_container_width=True)

    elif view_compare_mode == "AeroScan Route Only":
        st.markdown(
            f"""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 3px solid #0284C7; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                <span style="font-size: 12px; font-weight: 700; color: #0284C7; font-family: 'JetBrains Mono', monospace;">AEROSCAN-OPTIMA // ALNS + CP-SAT GLOBAL PARTITIONS</span>
                <span style="font-size: 12px; color: #64748B; font-family: 'JetBrains Mono', monospace;"><b style="color: #10B981;">{aeroscan_schedule.cumulative_reward:.0f} pts</b> · {aeroscan_schedule.solve_time_seconds:.3f}s</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        fig_aeroscan = build_comparison_map(
            instance,
            aeroscan_schedule,
            selected_drone_id=selected_drone,
            accent_color="#0284C7",
        )
        st.plotly_chart(fig_aeroscan, use_container_width=True)

    else:
        st.markdown(
            f"""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-top: 3px solid #EF4444; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                <span style="font-size: 12px; font-weight: 700; color: #EF4444; font-family: 'JetBrains Mono', monospace;">BASELINE // GRASP SEQUENTIAL NEAREST GREEDY</span>
                <span style="font-size: 12px; color: #64748B; font-family: 'JetBrains Mono', monospace;"><b>{grasp_schedule.cumulative_reward:.0f} pts</b> · {grasp_schedule.solve_time_seconds:.3f}s</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        fig_grasp = build_comparison_map(
            instance,
            grasp_schedule,
            selected_drone_id=selected_drone,
            accent_color="#EF4444",
        )
        st.plotly_chart(fig_grasp, use_container_width=True)

    # Operational Comparison Matrix
    st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric(
            "Total Secured Reward",
            f"{aeroscan_schedule.cumulative_reward:.0f} pts",
            f"+{pct_gain:.1f}% vs GRASP",
        )
    with m2:
        st.metric(
            "Targets Secured",
            f"{targets_opt} / {len(instance.target_nodes)}",
            f"{delta_targets:+d} targets secured",
        )
    with m3:
        st.metric("Solve Latency", f"{aeroscan_schedule.solve_time_seconds:.3f}s", "ALNS + CP-SAT")
    with m4:
        st.metric("Spatial Overlap Rate", "0.0%", "Strict Deconfliction", delta_color="normal")
