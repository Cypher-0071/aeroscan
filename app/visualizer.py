"""Plotly-based interactive mission spatial map and telemetry visualizer."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import plotly.graph_objects as go

from app.telemetry import compute_battery_curves, get_fleet_telemetry_at_time
from core.contracts import FleetSchedule, InstanceContext

DRONE_COLORS = [
    "#00E5FF",  # Cyan (UAV-01)
    "#FF9100",  # Orange (UAV-02)
    "#D500F9",  # Magenta (UAV-03)
    "#76FF03",  # Lime (UAV-04)
    "#FF1744",  # Red (UAV-05)
    "#FFD600",  # Yellow (UAV-06)
    "#00B0FF",  # Light Blue (UAV-07)
    "#C51162",  # Deep Pink (UAV-08)
]


def create_radar_circle(
    center_x: float, center_y: float, radius: float = 50.0, num_pts: int = 32
) -> tuple[list[float], list[float]]:
    """Generates (x, y) coordinates of a circular radar scanning halo."""
    angles = np.linspace(0, 2 * math.pi, num_pts)
    xs = [center_x + radius * math.cos(a) for a in angles]
    ys = [center_y + radius * math.sin(a) for a in angles]
    return xs, ys


def build_mission_map_figure(
    instance: InstanceContext,
    schedule: FleetSchedule | None = None,
    current_time_sec: float = 0.0,
    show_radar_halos: bool = True,
) -> go.Figure:
    """
    Builds the interactive 2D spatial mission map with drone trajectories,
    real-time drone position markers, radar coverage halos, and secured target states.
    """
    fig = go.Figure()
    node_map = {n.id: n for n in instance.targets}
    depot_ids = {d.launch_depot_id for d in instance.drones} | {d.recovery_depot_id for d in instance.drones}

    # Determine secured targets at current timestamp
    secured_targets: set[int] = set()
    active_telemetry: list[dict[str, Any]] = []
    if schedule and schedule.assigned_routes:
        active_telemetry, secured_targets = get_fleet_telemetry_at_time(
            schedule, current_time_sec, instance
        )

    # 1. Target nodes (unvisited vs secured)
    targets_unsecured = [t for t in instance.target_nodes if t.id not in secured_targets]
    targets_secured = [t for t in instance.target_nodes if t.id in secured_targets]

    if targets_unsecured:
        fig.add_trace(
            go.Scatter(
                x=[t.x for t in targets_unsecured],
                y=[t.y for t in targets_unsecured],
                mode="markers+text",
                marker=dict(
                    size=[max(10, min(24, 8 + t.priority_score * 0.4)) for t in targets_unsecured],
                    color=[t.priority_score for t in targets_unsecured],
                    colorscale="YlOrRd",
                    showscale=True,
                    colorbar=dict(title=dict(text="Target Priority", side="right"), thickness=12, len=0.6),
                    line=dict(color="#FFFFFF", width=1.5),
                ),
                text=[f"#{t.id}" for t in targets_unsecured],
                textposition="top center",
                name="Pending Targets",
                hovertext=[
                    f"Target #{t.id}: {t.name}<br>Priority: {t.priority_score}<br>Dwell: {t.dwell_time}s<br>Elevation: {t.elevation}m"
                    for t in targets_unsecured
                ],
                hoverinfo="text",
            )
        )

    if targets_secured:
        fig.add_trace(
            go.Scatter(
                x=[t.x for t in targets_secured],
                y=[t.y for t in targets_secured],
                mode="markers+text",
                marker=dict(
                    size=16,
                    color="#00E676",  # Bright green
                    symbol="circle",
                    line=dict(color="#004D40", width=2),
                ),
                text=[f"✓ #{t.id}" for t in targets_secured],
                textposition="top center",
                name="Secured Targets",
                hovertext=[
                    f"✓ SECURED #{t.id}: {t.name}<br>Priority: {t.priority_score} pts"
                    for t in targets_secured
                ],
                hoverinfo="text",
            )
        )

    # 2. Depot nodes
    depot_nodes = [node_map[did] for did in depot_ids if did in node_map]
    if depot_nodes:
        fig.add_trace(
            go.Scatter(
                x=[d.x for d in depot_nodes],
                y=[d.y for d in depot_nodes],
                mode="markers+text",
                marker=dict(
                    size=22,
                    symbol="triangle-up",
                    color="#2979FF",
                    line=dict(color="#FFFFFF", width=2),
                ),
                text=[d.name for d in depot_nodes],
                textposition="bottom center",
                name="Base Camps (Depots)",
                hovertext=[f"Base Camp: {d.name}<br>Coords: ({d.x:.1f}, {d.y:.1f})" for d in depot_nodes],
                hoverinfo="text",
            )
        )

    # 3. Route polylines
    if schedule:
        for idx, route in enumerate(schedule.assigned_routes):
            color = DRONE_COLORS[idx % len(DRONE_COLORS)]
            coords_x = [node_map[wp.node_id].x for wp in route.waypoints]
            coords_y = [node_map[wp.node_id].y for wp in route.waypoints]

            fig.add_trace(
                go.Scatter(
                    x=coords_x,
                    y=coords_y,
                    mode="lines+markers",
                    line=dict(color=color, width=3),
                    marker=dict(size=6, color=color),
                    name=f"{route.drone_id} Flight Path ({route.total_reward:.0f} pts)",
                    hoverinfo="none",
                )
            )

    # 4. Real-time drone positions & radar halos
    for idx, telem in enumerate(active_telemetry):
        color = DRONE_COLORS[idx % len(DRONE_COLORS)]
        # Halo
        if show_radar_halos:
            hx, hy = create_radar_circle(telem["x"], telem["y"], radius=50.0)
            fig.add_trace(
                go.Scatter(
                    x=hx,
                    y=hy,
                    mode="lines",
                    line=dict(color=color, width=1, dash="dot"),
                    fill="toself",
                    fillcolor=f"rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.15)",
                    hoverinfo="none",
                    showlegend=False,
                )
            )

        # Vehicle marker
        fig.add_trace(
            go.Scatter(
                x=[telem["x"]],
                y=[telem["y"]],
                mode="markers+text",
                marker=dict(
                    size=16,
                    symbol="cross",
                    color=color,
                    line=dict(color="#FFFFFF", width=2),
                ),
                text=[f"🛸 {telem['drone_id']} ({telem['battery_percent']:.0f}%)"],
                textposition="top right",
                name=f"Live {telem['drone_id']}",
                hovertext=(
                    f"<b>{telem['drone_id']} Live Status</b><br>"
                    f"Status: {telem['status']}<br>"
                    f"Speed: {telem['speed_mps']:.1f} m/s<br>"
                    f"Altitude: {telem['z']:.1f} m<br>"
                    f"Battery: {telem['battery_percent']:.1f}%"
                ),
                hoverinfo="text",
                showlegend=False,
            )
        )

    # Map layout styling
    fig.update_layout(
        template="plotly_dark",
        title=dict(
            text=f"Mission Spatial Radar View — t = {int(current_time_sec)}s ({int(current_time_sec//60):02d}:{int(current_time_sec%60):02d} min)",
            font=dict(size=16),
        ),
        xaxis=dict(title="East-West (meters)", gridcolor="#333333", zeroline=False),
        yaxis=dict(title="North-South (meters)", gridcolor="#333333", scaleanchor="x", scaleratio=1),
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="closest",
    )
    return fig


def build_battery_soc_figure(
    schedule: FleetSchedule,
    instance: InstanceContext,
    current_time_sec: float = 0.0,
) -> go.Figure:
    """
    Renders the Battery State-of-Charge (SoC %) depletion curves over time,
    with a red dashed reference line at 15% (Mandatory Safety Reserve Floor).
    """
    df = compute_battery_curves(schedule, instance)
    fig = go.Figure()

    cols = [c for c in df.columns if "SoC" in c]
    for idx, col in enumerate(cols):
        drone_id = col.replace(" SoC (%)", "")
        color = DRONE_COLORS[idx % len(DRONE_COLORS)]
        fig.add_trace(
            go.Scatter(
                x=df["Time_sec"],
                y=df[col],
                mode="lines",
                name=f"{drone_id} SoC",
                line=dict(color=color, width=2.5),
            )
        )

    # 15% Safety Floor Line
    max_t = df["Time_sec"].max() if not df.empty else 2400.0
    fig.add_trace(
        go.Scatter(
            x=[0, max_t],
            y=[15.0, 15.0],
            mode="lines",
            name="15% Safety Reserve Floor",
            line=dict(color="#FF1744", width=2, dash="dash"),
        )
    )

    # Current mission scrubber vertical indicator
    fig.add_vline(
        x=current_time_sec,
        line_width=2,
        line_dash="dot",
        line_color="#00E5FF",
        annotation_text="Scrubber",
        annotation_position="top right",
    )

    fig.update_layout(
        template="plotly_dark",
        title=dict(text="Fleet Battery State-of-Charge (SoC) Depletion Curves", font=dict(size=15)),
        xaxis=dict(title="Mission Time (seconds)", gridcolor="#333333"),
        yaxis=dict(title="Remaining Battery (%)", range=[0, 105], gridcolor="#333333"),
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig
