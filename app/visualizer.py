"""Plotly-based minimal, ultra-premium mission spatial map, 3D topographic radar, and telemetry visualizers."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import plotly.graph_objects as go

from app.telemetry import compute_battery_curves, get_fleet_telemetry_at_time
from core.contracts import FleetSchedule, InstanceContext

# Curated High-End Defense Palette (Matte, High-Legibility)
DRONE_COLORS = [
    "#38BDF8",  # Ice Blue (UAV-01)
    "#818CF8",  # Periwinkle / Indigo (UAV-02)
    "#34D399",  # Mint Emerald (UAV-03)
    "#FBBF24",  # Warm Amber (UAV-04)
    "#F43F5E",  # Precision Rose (UAV-05)
    "#A78BFA",  # Lavender (UAV-06)
    "#2DD4BF",  # Cyan Teal (UAV-07)
    "#FB923C",  # Tangerine (UAV-08)
]


def create_radar_circle(
    center_x: float, center_y: float, radius: float = 50.0, num_pts: int = 40
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
    show_breadcrumbs: bool = True,
    show_range_rings: bool = True,
) -> go.Figure:
    """
    Builds an ultra-clean, minimal, premium 2D spatial tactical map.
    Eliminates text clutter, overlapping labels, and garish neon styling in favor of
    crisp geometric markers, subtle hairline rings, and elegant flight corridors.
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

    # 0. Concentric Range Rings (Subtle Radar Grid)
    if show_range_rings and depot_ids:
        main_depot_id = list(depot_ids)[0]
        if main_depot_id in node_map:
            center_node = node_map[main_depot_id]
            for r_dist in [250.0, 500.0, 1000.0, 1500.0]:
                rx, ry = create_radar_circle(center_node.x, center_node.y, radius=r_dist, num_pts=60)
                fig.add_trace(
                    go.Scatter(
                        x=rx,
                        y=ry,
                        mode="lines",
                        line=dict(color="rgba(255, 255, 255, 0.04)", width=1, dash="dot"),
                        hoverinfo="none",
                        showlegend=False,
                    )
                )

    # 1. Target nodes (unvisited vs secured)
    targets_unsecured = [t for t in instance.target_nodes if t.id not in secured_targets]
    targets_secured = [t for t in instance.target_nodes if t.id in secured_targets]

    if targets_unsecured:
        fig.add_trace(
            go.Scatter(
                x=[t.x for t in targets_unsecured],
                y=[t.y for t in targets_unsecured],
                mode="markers",
                marker=dict(
                    size=[max(8, min(18, 6 + t.priority_score * 0.3)) for t in targets_unsecured],
                    color=[t.priority_score for t in targets_unsecured],
                    colorscale=[
                        [0.0, "#1E293B"],
                        [0.35, "#334155"],
                        [0.7, "#D97706"],
                        [1.0, "#F59E0B"],
                    ],
                    showscale=True,
                    colorbar=dict(
                        title=dict(text="Target Priority", font=dict(color="#94A3B8", size=11)),
                        thickness=10,
                        len=0.65,
                        tickfont=dict(color="#64748B", size=9),
                        outlinecolor="rgba(255, 255, 255, 0.1)",
                        outlinewidth=1,
                    ),
                    line=dict(color="#475569", width=1),
                    opacity=0.9,
                ),
                name="Pending Targets",
                hovertext=[
                    f"<b>Target #{t.id}</b>: {t.name}<br>"
                    f"Priority: <b>{t.priority_score:.0f} pts</b><br>"
                    f"Sensor Dwell: <b>{t.dwell_time:.0f}s</b><br>"
                    f"Elevation: <b>{t.elevation:.1f} m</b>"
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
                mode="markers",
                marker=dict(
                    size=12,
                    color="#10B981",
                    symbol="circle",
                    line=dict(color="#064E3B", width=2),
                    opacity=0.95,
                ),
                name="Secured Targets",
                hovertext=[
                    f"<b>✓ SECURED Target #{t.id}</b>: {t.name}<br>"
                    f"Reward Captured: <b>{t.priority_score:.0f} pts</b>"
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
                    size=16,
                    symbol="diamond",
                    color="#38BDF8",
                    line=dict(color="#FFFFFF", width=1.5),
                ),
                text=[f"  {d.name}" for d in depot_nodes],
                textposition="middle right",
                textfont=dict(color="#94A3B8", size=10, family="Inter, sans-serif"),
                name="Base Station",
                hovertext=[f"<b>Base Station</b>: {d.name}<br>Coords: ({d.x:.1f}, {d.y:.1f})" for d in depot_nodes],
                hoverinfo="text",
            )
        )

    # 3. Route polylines (Planned Corridors)
    if schedule:
        for idx, route in enumerate(schedule.assigned_routes):
            color = DRONE_COLORS[idx % len(DRONE_COLORS)]
            coords_x = [node_map[wp.node_id].x for wp in route.waypoints]
            coords_y = [node_map[wp.node_id].y for wp in route.waypoints]

            fig.add_trace(
                go.Scatter(
                    x=coords_x,
                    y=coords_y,
                    mode="lines",
                    line=dict(color=color, width=1.5, dash="dot"),
                    opacity=0.4,
                    name=f"{route.drone_id} Plan ({route.total_reward:.0f} pts)",
                    hoverinfo="none",
                )
            )

    # 4. Active Breadcrumbs Trail (Flown Path up to t_sec)
    if show_breadcrumbs and schedule:
        for idx, route in enumerate(schedule.assigned_routes):
            color = DRONE_COLORS[idx % len(DRONE_COLORS)]
            crumbs_x: list[float] = []
            crumbs_y: list[float] = []

            for i, wp in enumerate(route.waypoints):
                node = node_map[wp.node_id]
                if wp.arrival_time <= current_time_sec:
                    crumbs_x.append(node.x)
                    crumbs_y.append(node.y)
                elif i > 0 and route.waypoints[i - 1].departure_time < current_time_sec < wp.arrival_time:
                    prev_node = node_map[route.waypoints[i - 1].node_id]
                    frac = (current_time_sec - route.waypoints[i - 1].departure_time) / max(
                        wp.arrival_time - route.waypoints[i - 1].departure_time, 1e-4
                    )
                    crumbs_x.append(prev_node.x + frac * (node.x - prev_node.x))
                    crumbs_y.append(prev_node.y + frac * (node.y - prev_node.y))
                    break

            if len(crumbs_x) >= 2:
                fig.add_trace(
                    go.Scatter(
                        x=crumbs_x,
                        y=crumbs_y,
                        mode="lines+markers",
                        line=dict(color=color, width=2.5),
                        marker=dict(size=4, color=color),
                        name=f"{route.drone_id} Track",
                        hoverinfo="none",
                        showlegend=False,
                    )
                )

    # 5. Real-time drone positions & radar halos
    for idx, telem in enumerate(active_telemetry):
        color = DRONE_COLORS[idx % len(DRONE_COLORS)]

        # Halo
        if show_radar_halos and telem["flight_phase"] != "STANDBY":
            hx, hy = create_radar_circle(telem["x"], telem["y"], radius=50.0)
            fig.add_trace(
                go.Scatter(
                    x=hx,
                    y=hy,
                    mode="lines",
                    line=dict(color=color, width=1, dash="solid"),
                    fill="toself",
                    fillcolor=f"rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.12)",
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
                    size=12,
                    symbol="circle",
                    color=color,
                    line=dict(color="#FFFFFF", width=1.5),
                ),
                text=[f"  {telem['drone_id']}"],
                textposition="middle right",
                textfont=dict(color="#E2E8F0", size=10, family="Inter, sans-serif"),
                name=f"Live {telem['drone_id']}",
                hovertext=(
                    f"<b>{telem['drone_id']} Telemetry</b><br>"
                    f"State: <b>{telem['status']}</b><br>"
                    f"Speed: <b>{telem['speed_mps']:.1f} m/s</b><br>"
                    f"Altitude: <b>{telem['z']:.1f} m</b><br>"
                    f"Battery SoC: <b>{telem['battery_percent']:.1f}%</b>"
                ),
                hoverinfo="text",
                showlegend=False,
            )
        )

    # Minimal Dark Slate Layout
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#05070A",
        plot_bgcolor="#07090D",
        xaxis=dict(
            title=dict(text="X (m)", font=dict(color="#484F58", size=10, family="JetBrains Mono, monospace")),
            gridcolor="rgba(255,255,255,0.04)",
            zerolinecolor="rgba(255,255,255,0.08)",
            showgrid=True,
            zeroline=False,
            tickfont=dict(color="#484F58", size=9, family="JetBrains Mono, monospace"),
        ),
        yaxis=dict(
            title=dict(text="Y (m)", font=dict(color="#484F58", size=10, family="JetBrains Mono, monospace")),
            gridcolor="rgba(255,255,255,0.04)",
            zerolinecolor="rgba(255,255,255,0.08)",
            scaleanchor="x",
            scaleratio=1,
            showgrid=True,
            zeroline=False,
            tickfont=dict(color="#484F58", size=9, family="JetBrains Mono, monospace"),
        ),
        margin=dict(l=40, r=24, t=24, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="right",
            x=1,
            font=dict(color="#6E7681", size=10, family="JetBrains Mono, monospace"),
            bgcolor="rgba(7,9,13,0.8)",
            bordercolor="rgba(255,255,255,0.06)",
            borderwidth=1,
        ),
        hovermode="closest",
        height=560,
    )
    return fig


def build_3d_terrain_mission_figure(
    instance: InstanceContext,
    schedule: FleetSchedule | None = None,
    current_time_sec: float = 0.0,
) -> go.Figure:
    """
    Builds a minimal, clean 3D Topographic Terrain & Flight Altitude Visualizer.
    """
    fig = go.Figure()
    node_map = {n.id: n for n in instance.targets}
    depot_ids = {d.launch_depot_id for d in instance.drones} | {d.recovery_depot_id for d in instance.drones}

    # 1. Target nodes in 3D
    targets = instance.target_nodes
    fig.add_trace(
        go.Scatter3d(
            x=[t.x for t in targets],
            y=[t.y for t in targets],
            z=[t.elevation for t in targets],
            mode="markers",
            marker=dict(
                size=[max(3, min(8, 2 + t.priority_score * 0.12)) for t in targets],
                color=[t.priority_score for t in targets],
                colorscale="Viridis",
                showscale=False,
                opacity=0.85,
            ),
            name="Target Nodes",
            hovertext=[f"Target #{t.id}: {t.name} (Priority: {t.priority_score:.0f}, Elev: {t.elevation:.1f}m)" for t in targets],
            hoverinfo="text",
        )
    )

    # 2. Subtle elevation drop lines
    for t in targets:
        fig.add_trace(
            go.Scatter3d(
                x=[t.x, t.x],
                y=[t.y, t.y],
                z=[0.0, t.elevation],
                mode="lines",
                line=dict(color="rgba(255, 255, 255, 0.08)", width=1),
                hoverinfo="none",
                showlegend=False,
            )
        )

    # 3. Base Depots in 3D
    depot_nodes = [node_map[did] for did in depot_ids if did in node_map]
    if depot_nodes:
        fig.add_trace(
            go.Scatter3d(
                x=[d.x for d in depot_nodes],
                y=[d.y for d in depot_nodes],
                z=[d.elevation for d in depot_nodes],
                mode="markers+text",
                marker=dict(size=7, symbol="diamond", color="#38BDF8"),
                text=[d.name for d in depot_nodes],
                textposition="bottom center",
                textfont=dict(color="#94A3B8", size=9),
                name="Base Station",
                hoverinfo="text",
            )
        )

    # 4. 3D Flight paths
    if schedule:
        for idx, route in enumerate(schedule.assigned_routes):
            color = DRONE_COLORS[idx % len(DRONE_COLORS)]
            xs = [node_map[wp.node_id].x for wp in route.waypoints]
            ys = [node_map[wp.node_id].y for wp in route.waypoints]
            zs = [max(60.0, node_map[wp.node_id].elevation + 20.0) for wp in route.waypoints]

            fig.add_trace(
                go.Scatter3d(
                    x=xs,
                    y=ys,
                    z=zs,
                    mode="lines",
                    line=dict(color=color, width=3),
                    name=f"{route.drone_id} Corridor",
                )
            )

    # 5. Live Drone 3D Positions
    if schedule:
        active_telemetry, _ = get_fleet_telemetry_at_time(schedule, current_time_sec, instance)
        for idx, telem in enumerate(active_telemetry):
            color = DRONE_COLORS[idx % len(DRONE_COLORS)]
            fig.add_trace(
                go.Scatter3d(
                    x=[telem["x"]],
                    y=[telem["y"]],
                    z=[telem["z"]],
                    mode="markers+text",
                    marker=dict(size=6, color=color, symbol="circle"),
                    text=[f" {telem['drone_id']}"],
                    textposition="top center",
                    textfont=dict(color="#E2E8F0", size=9),
                    name=f"Live 3D {telem['drone_id']}",
                    hovertext=f"{telem['drone_id']} | Alt: {telem['z']:.1f}m | SoC: {telem['battery_percent']:.1f}%",
                    hoverinfo="text",
                    showlegend=False,
                )
            )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#05070A",
        scene=dict(
            xaxis=dict(title="X (m)", backgroundcolor="#07090D", gridcolor="rgba(255,255,255,0.06)", showbackground=True, tickfont=dict(color="#484F58", size=9, family="JetBrains Mono")),
            yaxis=dict(title="Y (m)", backgroundcolor="#07090D", gridcolor="rgba(255,255,255,0.06)", showbackground=True, tickfont=dict(color="#484F58", size=9, family="JetBrains Mono")),
            zaxis=dict(title="ALT (m)", backgroundcolor="#07090D", gridcolor="rgba(255,255,255,0.06)", showbackground=True, tickfont=dict(color="#484F58", size=9, family="JetBrains Mono")),
            camera=dict(eye=dict(x=1.4, y=-1.4, z=1.1)),
            bgcolor="#05070A",
        ),
        margin=dict(l=10, r=10, t=20, b=10),
        height=560,
    )
    return fig


def build_battery_soc_figure(
    schedule: FleetSchedule,
    instance: InstanceContext,
    current_time_sec: float = 0.0,
) -> go.Figure:
    """
    Renders the Battery State-of-Charge (SoC %) depletion curves over time.
    """
    df = compute_battery_curves(schedule, instance)
    fig = go.Figure()

    max_t = float(df["Time_sec"].max()) if not df.empty else 2400.0

    # 1. Subtle hazard zone below 15%
    fig.add_shape(
        type="rect",
        x0=0,
        x1=max_t,
        y0=0,
        y1=15.0,
        fillcolor="rgba(244, 63, 94, 0.08)",
        line=dict(width=0),
        layer="below",
    )

    # 2. Battery SoC Curves
    cols = [c for c in df.columns if "SoC" in c]
    for idx, col in enumerate(cols):
        drone_id = col.replace(" SoC (%)", "")
        color = DRONE_COLORS[idx % len(DRONE_COLORS)]
        fig.add_trace(
            go.Scatter(
                x=df["Time_sec"],
                y=df[col],
                mode="lines",
                name=f"{drone_id}",
                line=dict(color=color, width=2.5),
                hovertext=[f"{drone_id}: {val:.1f}% at {int(t)}s" for val, t in zip(df[col], df["Time_sec"])],
                hoverinfo="text",
            )
        )

    # 3. 15% Safety Floor Line
    fig.add_trace(
        go.Scatter(
            x=[0, max_t],
            y=[15.0, 15.0],
            mode="lines+text",
            name="15% Reserve Floor",
            line=dict(color="#F43F5E", width=1.5, dash="dash"),
            text=["", "<b>RESERVE FLOOR (15%)</b>"],
            textposition="top right",
            textfont=dict(color="#F43F5E", size=9, family="Inter, sans-serif"),
        )
    )

    # 4. Current mission scrubber vertical indicator
    fig.add_vline(
        x=current_time_sec,
        line_width=1.5,
        line_dash="dot",
        line_color="#38BDF8",
        annotation_text=f"t={int(current_time_sec)}s",
        annotation_position="top left",
        annotation_font=dict(color="#38BDF8", size=10, family="Inter, sans-serif"),
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#05070A",
        plot_bgcolor="#07090D",
        xaxis=dict(
            title=dict(text="Time (s)", font=dict(color="#484F58", size=10, family="JetBrains Mono, monospace")),
            gridcolor="rgba(255,255,255,0.04)",
            showgrid=True,
            tickfont=dict(color="#484F58", size=9, family="JetBrains Mono, monospace"),
        ),
        yaxis=dict(
            title=dict(text="SoC (%)", font=dict(color="#484F58", size=10, family="JetBrains Mono, monospace")),
            range=[0, 105],
            gridcolor="rgba(255,255,255,0.04)",
            showgrid=True,
            tickfont=dict(color="#484F58", size=9, family="JetBrains Mono, monospace"),
        ),
        margin=dict(l=40, r=24, t=24, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="right",
            x=1,
            font=dict(color="#6E7681", size=10, family="JetBrains Mono, monospace"),
            bgcolor="rgba(7,9,13,0.8)",
            bordercolor="rgba(255,255,255,0.06)",
            borderwidth=1,
        ),
        height=420,
    )
    return fig
