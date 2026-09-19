"""Side-by-side algorithmic arena comparison between GRASP baseline and AeroScan-Optima."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app.visualizer import DRONE_COLORS
from core.contracts import FleetSchedule, InstanceContext


def build_comparison_map(
    instance: InstanceContext,
    schedule: FleetSchedule,
    title: str,
) -> go.Figure:
    """Builds a static route trajectory map for comparative algorithmic inspection."""
    fig = go.Figure()
    node_map = {n.id: n for n in instance.targets}
    depot_ids = {d.launch_depot_id for d in instance.drones} | {d.recovery_depot_id for d in instance.drones}

    # Targets
    target_nodes = [t for t in instance.target_nodes]
    visited_ids = set()
    for r in schedule.assigned_routes:
        visited_ids.update(r.target_ids)

    unvisited = [t for t in target_nodes if t.id not in visited_ids]
    visited = [t for t in target_nodes if t.id in visited_ids]

    if unvisited:
        fig.add_trace(
            go.Scatter(
                x=[t.x for t in unvisited],
                y=[t.y for t in unvisited],
                mode="markers",
                marker=dict(size=8, color="#555555", opacity=0.6),
                name="Missed Target",
                hoverinfo="none",
            )
        )

    if visited:
        fig.add_trace(
            go.Scatter(
                x=[t.x for t in visited],
                y=[t.y for t in visited],
                mode="markers",
                marker=dict(
                    size=12,
                    color=[t.priority_score for t in visited],
                    colorscale="YlOrRd",
                    showscale=False,
                    line=dict(color="#FFFFFF", width=1),
                ),
                name="Collected Target",
                hoverinfo="text",
                hovertext=[f"#{t.id}: {t.priority_score} pts" for t in visited],
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
                marker=dict(size=18, symbol="triangle-up", color="#2979FF"),
                name="Depot",
                hoverinfo="none",
            )
        )

    # Routes
    for idx, route in enumerate(schedule.assigned_routes):
        color = DRONE_COLORS[idx % len(DRONE_COLORS)]
        xs = [node_map[wp.node_id].x for wp in route.waypoints]
        ys = [node_map[wp.node_id].y for wp in route.waypoints]

        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines+markers",
                line=dict(color=color, width=2.5),
                marker=dict(size=5, color=color),
                name=f"{route.drone_id} ({route.total_reward:.0f} pts)",
                hoverinfo="none",
            )
        )

    fig.update_layout(
        template="plotly_dark",
        title=dict(text=title, font=dict(size=14)),
        xaxis=dict(showgrid=True, gridcolor="#262626", zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="#262626", scaleanchor="x", scaleratio=1),
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)),
        height=450,
    )
    return fig


def render_arena_view(
    instance: InstanceContext,
    aeroscan_schedule: FleetSchedule,
    grasp_schedule: FleetSchedule,
) -> None:
    """Renders the dual-column comparative arena in Streamlit."""
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("⚠️ Organizer GRASP Baseline")
        st.markdown(
            f"**Score**: `{grasp_schedule.cumulative_reward:.1f} pts` | "
            f"**Solve Time**: `{grasp_schedule.solve_time_seconds:.3f}s`"
        )
        fig_grasp = build_comparison_map(
            instance,
            grasp_schedule,
            title=f"GRASP: Route Cannibalization ({grasp_schedule.cumulative_reward:.0f} pts)",
        )
        st.plotly_chart(fig_grasp, use_container_width=True)
        st.caption(
            "🛑 *Pathological Cannibalization*: Drone 1 grabs nearby high-value targets; "
            "subsequent drones are forced into long transit detours for low-value outliers."
        )

    with col2:
        gain = aeroscan_schedule.reward_gain_percent
        st.subheader(f"🚀 AeroScan-Optima (+{gain:.1f}%)")
        st.markdown(
            f"**Score**: `{aeroscan_schedule.cumulative_reward:.1f} pts` | "
            f"**Solve Time**: `{aeroscan_schedule.solve_time_seconds:.3f}s`"
        )
        fig_optima = build_comparison_map(
            instance,
            aeroscan_schedule,
            title=f"AeroScan-Optima: Deconflicted Sectors ({aeroscan_schedule.cumulative_reward:.0f} pts)",
        )
        st.plotly_chart(fig_optima, use_container_width=True)
        st.caption(
            "✅ *Provable Deconfliction*: ALNS generates rich candidate pools; "
            "CP-SAT Set Packing partitions targets into non-overlapping optimal sectors."
        )
