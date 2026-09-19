"""Plotly-based light-theme geospatial tactical operations map, 3D topography, and battery telemetry visualizers."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import plotly.graph_objects as go

from app.telemetry import compute_battery_curves, get_fleet_telemetry_at_time
from core.contracts import FleetSchedule, InstanceContext

# High-Visibility Aerospace Light Operational Palette
DRONE_COLORS = [
    "#0284C7",  # AeroScan Primary Blue (UAV-01)
    "#6366F1",  # Precision Indigo (UAV-02)
    "#0D9488",  # Deep Teal (UAV-03)
    "#D97706",  # Amber Gold (UAV-04)
    "#E11D48",  # Crimson Rose (UAV-05)
    "#7C3AED",  # Royal Violet (UAV-06)
    "#059669",  # Emerald (UAV-07)
    "#C2410C",  # Burnt Orange (UAV-08)
]


def create_radar_circle(
    center_x: float, center_y: float, radius: float = 50.0, num_pts: int = 48
) -> tuple[list[float], list[float]]:
    """Generates (x, y) coordinates of a circular radar scanning halo or range ring."""
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
    selected_uav_id: str | None = None,
) -> go.Figure:
    """
    Builds an award-grade 2D spatial tactical operations map in a sophisticated light theme.
    Features subtle coordinate gridlines, range rings, priority gradients,
    corridors, directional UAV vectors, and high-legibility telemetry.
    """
    fig = go.Figure()
    node_map = {n.id: n for n in instance.targets}
    depot_ids = {d.launch_depot_id for d in instance.drones} | {d.recovery_depot_id for d in instance.drones}

    # Determine secured targets and active kinematics at current timestamp
    secured_targets: set[int] = set()
    active_telemetry: list[dict[str, Any]] = []
    if schedule and schedule.assigned_routes:
        active_telemetry, secured_targets = get_fleet_telemetry_at_time(
            schedule, current_time_sec, instance
        )

    # 0. Concentric Tactical Range Rings (Depot Centric)
    if show_range_rings and depot_ids:
        main_depot_id = list(depot_ids)[0]
        if main_depot_id in node_map:
            center_node = node_map[main_depot_id]
            for r_dist in [300.0, 600.0, 1000.0, 1500.0]:
                rx, ry = create_radar_circle(center_node.x, center_node.y, radius=r_dist, num_pts=64)
                fig.add_trace(
                    go.Scatter(
                        x=rx,
                        y=ry,
                        mode="lines",
                        line=dict(color="rgba(2, 132, 199, 0.22)", width=1, dash="dot"),
                        hoverinfo="none",
                        showlegend=False,
                    )
                )
                # Range ring distance tag
                fig.add_trace(
                    go.Scatter(
                        x=[center_node.x + r_dist],
                        y=[center_node.y],
                        mode="text",
                        text=[f"R-{int(r_dist)}m"],
                        textposition="middle right",
                        textfont=dict(color="#64748B", size=9, family="JetBrains Mono, monospace"),
                        hoverinfo="none",
                        showlegend=False,
                    )
                )

    # 1. Target Nodes: Unsecured (Priority Scaled) vs. Secured (Emerald Glow)
    targets_unsecured = [t for t in instance.target_nodes if t.id not in secured_targets]
    targets_secured = [t for t in instance.target_nodes if t.id in secured_targets]

    if targets_unsecured:
        fig.add_trace(
            go.Scatter(
                x=[t.x for t in targets_unsecured],
                y=[t.y for t in targets_unsecured],
                mode="markers",
                marker=dict(
                    size=[max(8, min(20, 6 + t.priority_score * 0.35)) for t in targets_unsecured],
                    color=[t.priority_score for t in targets_unsecured],
                    colorscale=[
                        [0.0, "#94A3B8"],  # Slate Gray (Low Priority)
                        [0.4, "#0284C7"],  # Operational Blue
                        [0.75, "#F59E0B"],  # High Priority Amber
                        [1.0, "#EA580C"],  # Critical Amber-Orange
                    ],
                    showscale=True,
                    colorbar=dict(
                        title=dict(
                            text="PRIORITY SCORE",
                            font=dict(color="#475569", size=10, family="JetBrains Mono, monospace"),
                        ),
                        thickness=10,
                        len=0.55,
                        tickfont=dict(color="#64748B", size=9, family="JetBrains Mono, monospace"),
                        outlinecolor="#CBD5E1",
                        outlinewidth=1,
                        bgcolor="rgba(255, 255, 255, 0.95)",
                    ),
                    line=dict(color="#FFFFFF", width=1.5),
                    opacity=0.92,
                ),
                name="Pending Target",
                hovertext=[
                    f"<b>TARGET #{t.id:02d} · {t.name}</b><br>"
                    f"Status: <span style='color:#F59E0B; font-weight:600;'>PENDING SCAN</span><br>"
                    f"Priority Score: <b>{t.priority_score:.0f} pts</b><br>"
                    f"Sensor Dwell: <b>{t.dwell_time:.0f}s</b><br>"
                    f"Elevation: <b>{t.elevation:.1f} m</b><br>"
                    f"Location: <b>({t.x:.0f}, {t.y:.0f})</b>"
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
                    line=dict(color="#FFFFFF", width=2),
                    opacity=0.98,
                ),
                name="Secured Target",
                hovertext=[
                    f"<b>SECURED TARGET #{t.id:02d} · {t.name}</b><br>"
                    f"Status: <span style='color:#10B981; font-weight:600;'>CAPTURED / SECURED</span><br>"
                    f"Reward Secured: <b>{t.priority_score:.0f} pts</b><br>"
                    f"Elevation: <b>{t.elevation:.1f} m</b>"
                    for t in targets_secured
                ],
                hoverinfo="text",
            )
        )

    # 2. Base Station / Depot Nodes
    depot_nodes = [node_map[did] for did in depot_ids if did in node_map]
    if depot_nodes:
        # Base Station Scanning Halo
        for d in depot_nodes:
            hx, ry = create_radar_circle(d.x, d.y, radius=75.0, num_pts=48)
            fig.add_trace(
                go.Scatter(
                    x=hx,
                    y=ry,
                    mode="lines",
                    line=dict(color="rgba(2, 132, 199, 0.35)", width=1),
                    fill="toself",
                    fillcolor="rgba(2, 132, 199, 0.06)",
                    hoverinfo="none",
                    showlegend=False,
                )
            )

        fig.add_trace(
            go.Scatter(
                x=[d.x for d in depot_nodes],
                y=[d.y for d in depot_nodes],
                mode="markers+text",
                marker=dict(
                    size=16,
                    symbol="diamond",
                    color="#0284C7",
                    line=dict(color="#FFFFFF", width=2),
                ),
                text=[f"  {d.name.upper()}" for d in depot_nodes],
                textposition="middle right",
                textfont=dict(color="#0F172A", size=10, family="JetBrains Mono, monospace"),
                name="Base Station Depot",
                hovertext=[
                    f"<b>BASE STATION</b>: {d.name}<br>"
                    f"Launch & Recovery Depot<br>"
                    f"Coordinates: ({d.x:.1f}, {d.y:.1f})<br>"
                    f"Elevation: {d.elevation:.1f}m"
                    for d in depot_nodes
                ],
                hoverinfo="text",
            )
        )

    # 3. Planned Route Corridors (Clean Flight Corridors)
    if schedule:
        for idx, route in enumerate(schedule.assigned_routes):
            color = DRONE_COLORS[idx % len(DRONE_COLORS)]
            is_focused = (selected_uav_id is None) or (route.drone_id == selected_uav_id)
            alpha_val = 0.65 if is_focused else 0.18
            line_w = 2.0 if is_focused else 1.0

            coords_x = [node_map[wp.node_id].x for wp in route.waypoints]
            coords_y = [node_map[wp.node_id].y for wp in route.waypoints]

            fig.add_trace(
                go.Scatter(
                    x=coords_x,
                    y=coords_y,
                    mode="lines",
                    line=dict(color=color, width=line_w, dash="dot"),
                    opacity=alpha_val,
                    name=f"{route.drone_id} Corridor",
                    hoverinfo="none",
                )
            )

    # 4. Flown Breadcrumb Track (Historical Trajectory up to current_time_sec)
    if show_breadcrumbs and schedule:
        for idx, route in enumerate(schedule.assigned_routes):
            color = DRONE_COLORS[idx % len(DRONE_COLORS)]
            is_focused = (selected_uav_id is None) or (route.drone_id == selected_uav_id)
            if not is_focused:
                continue

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
                        name=f"{route.drone_id} Flown Track",
                        hoverinfo="none",
                        showlegend=False,
                    )
                )

    # 5. Live UAV Kinematic Positions, Radar Halos, and Heading Vectors
    for idx, telem in enumerate(active_telemetry):
        color = DRONE_COLORS[idx % len(DRONE_COLORS)]
        is_focused = (selected_uav_id is None) or (telem["drone_id"] == selected_uav_id)
        if not is_focused:
            continue

        # Dynamic Radar Halo
        if show_radar_halos and telem["flight_phase"] != "STANDBY":
            hx, hy = create_radar_circle(telem["x"], telem["y"], radius=45.0)
            fig.add_trace(
                go.Scatter(
                    x=hx,
                    y=hy,
                    mode="lines",
                    line=dict(color=color, width=1),
                    fill="toself",
                    fillcolor=f"rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.12)",
                    hoverinfo="none",
                    showlegend=False,
                )
            )

        # Directional Heading Vector Line (22m vector in heading direction)
        heading_rad = math.radians(telem.get("heading_deg", 0.0))
        vec_len = 22.0
        vec_x = telem["x"] + vec_len * math.sin(heading_rad)
        vec_y = telem["y"] + vec_len * math.cos(heading_rad)

        fig.add_trace(
            go.Scatter(
                x=[telem["x"], vec_x],
                y=[telem["y"], vec_y],
                mode="lines",
                line=dict(color="#0F172A", width=2),
                hoverinfo="none",
                showlegend=False,
            )
        )

        # Vehicle Center Marker
        fig.add_trace(
            go.Scatter(
                x=[telem["x"]],
                y=[telem["y"]],
                mode="markers+text",
                marker=dict(
                    size=13,
                    symbol="circle",
                    color=color,
                    line=dict(color="#FFFFFF", width=2.5),
                ),
                text=[f"  {telem['drone_id']}"],
                textposition="middle right",
                textfont=dict(color="#0F172A", size=10, family="JetBrains Mono, monospace"),
                name=f"Live {telem['drone_id']}",
                hovertext=(
                    f"<b>{telem['drone_id']} // TELEMETRY</b><br>"
                    f"Phase: <b>{telem['flight_phase']}</b><br>"
                    f"Groundspeed: <b>{telem['speed_mps']:.1f} m/s</b><br>"
                    f"Altitude: <b>{telem['z']:.1f} m</b><br>"
                    f"Heading: <b>{telem.get('heading_deg', 0):.0f}°</b><br>"
                    f"Battery SoC: <b>{telem['battery_percent']:.1f}%</b><br>"
                    f"Target: <b>{telem.get('target_name', 'DEPOT')}</b>"
                ),
                hoverinfo="text",
                showlegend=False,
            )
        )

    # Professional Light Geospatial Layout
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#F8FAFC",
        xaxis=dict(
            title=dict(text="EASTING X (M)", font=dict(color="#64748B", size=10, family="JetBrains Mono, monospace")),
            gridcolor="#E2E8F0",
            zerolinecolor="#CBD5E1",
            showgrid=True,
            zeroline=False,
            tickfont=dict(color="#64748B", size=9, family="JetBrains Mono, monospace"),
        ),
        yaxis=dict(
            title=dict(text="NORTHING Y (M)", font=dict(color="#64748B", size=10, family="JetBrains Mono, monospace")),
            gridcolor="#E2E8F0",
            zerolinecolor="#CBD5E1",
            scaleanchor="x",
            scaleratio=1,
            showgrid=True,
            zeroline=False,
            tickfont=dict(color="#64748B", size=9, family="JetBrains Mono, monospace"),
        ),
        margin=dict(l=40, r=24, t=24, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="right",
            x=1,
            font=dict(color="#0F172A", size=10, family="JetBrains Mono, monospace"),
            bgcolor="rgba(255, 255, 255, 0.94)",
            bordercolor="#E2E8F0",
            borderwidth=1,
        ),
        hovermode="closest",
        height=680,
    )
    return fig


def build_3d_terrain_mission_figure(
    instance: InstanceContext,
    schedule: FleetSchedule | None = None,
    current_time_sec: float = 0.0,
) -> go.Figure:
    """
    Builds a 3D Topographic Terrain & Flight Altitude Visualizer in clean light geospatial theme.
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
                opacity=0.9,
            ),
            name="Target Nodes",
            hovertext=[
                f"Target #{t.id:02d}: {t.name} (Priority: {t.priority_score:.0f}, Elev: {t.elevation:.1f}m)"
                for t in targets
            ],
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
                line=dict(color="rgba(100, 116, 139, 0.25)", width=1),
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
                marker=dict(size=7, symbol="diamond", color="#0284C7"),
                text=[d.name.upper() for d in depot_nodes],
                textposition="bottom center",
                textfont=dict(color="#0F172A", size=9, family="JetBrains Mono, monospace"),
                name="Base Station",
                hoverinfo="text",
            )
        )

    # 4. 3D Flight corridors
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
                    textfont=dict(color="#0F172A", size=9, family="JetBrains Mono, monospace"),
                    name=f"Live 3D {telem['drone_id']}",
                    hovertext=f"{telem['drone_id']} | Alt: {telem['z']:.1f}m | SoC: {telem['battery_percent']:.1f}%",
                    hoverinfo="text",
                    showlegend=False,
                )
            )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        scene=dict(
            xaxis=dict(
                title="X (m)",
                backgroundcolor="#F8FAFC",
                gridcolor="#E2E8F0",
                showbackground=True,
                tickfont=dict(color="#64748B", size=9, family="JetBrains Mono"),
            ),
            yaxis=dict(
                title="Y (m)",
                backgroundcolor="#F8FAFC",
                gridcolor="#E2E8F0",
                showbackground=True,
                tickfont=dict(color="#64748B", size=9, family="JetBrains Mono"),
            ),
            zaxis=dict(
                title="ALT (m)",
                backgroundcolor="#F8FAFC",
                gridcolor="#E2E8F0",
                showbackground=True,
                tickfont=dict(color="#64748B", size=9, family="JetBrains Mono"),
            ),
            camera=dict(eye=dict(x=1.4, y=-1.4, z=1.1)),
            bgcolor="#FFFFFF",
        ),
        margin=dict(l=10, r=10, t=20, b=10),
        height=650,
    )
    return fig


def build_battery_soc_figure(
    schedule: FleetSchedule,
    instance: InstanceContext,
    current_time_sec: float = 0.0,
) -> go.Figure:
    """
    Renders the Battery State-of-Charge (SoC %) depletion curves over time in clean light theme.
    Clearly highlights the 15% Safety Floor and live scrubber timeline.
    """
    df = compute_battery_curves(schedule, instance)
    fig = go.Figure()

    max_t = float(df["Time_sec"].max()) if not df.empty else 2400.0

    # 1. Critical Hazard Zone (<15% Safety Floor)
    fig.add_shape(
        type="rect",
        x0=0,
        x1=max_t,
        y0=0,
        y1=15.0,
        fillcolor="rgba(239, 68, 68, 0.08)",
        line=dict(width=0),
        layer="below",
    )

    # 2. Battery SoC Depletion Curves
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
                hovertext=[f"<b>{drone_id}</b>: {val:.1f}% SoC at {int(t)}s" for val, t in zip(df[col], df["Time_sec"])],
                hoverinfo="text",
            )
        )

    # 3. 15% Safety Threshold Line
    fig.add_trace(
        go.Scatter(
            x=[0, max_t],
            y=[15.0, 15.0],
            mode="lines+text",
            name="15% Safety Threshold",
            line=dict(color="#EF4444", width=1.5, dash="dash"),
            text=["", "<b>CRITICAL SAFETY FLOOR (15%)</b>"],
            textposition="top right",
            textfont=dict(color="#EF4444", size=9, family="JetBrains Mono, monospace"),
        )
    )

    # 4. Active mission time scrubber marker
    fig.add_vline(
        x=current_time_sec,
        line_width=1.5,
        line_dash="dot",
        line_color="#0284C7",
        annotation_text=f"t={int(current_time_sec)}s",
        annotation_position="top left",
        annotation_font=dict(color="#0284C7", size=10, family="JetBrains Mono, monospace"),
    )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#F8FAFC",
        xaxis=dict(
            title=dict(text="MISSION TIME (SEC)", font=dict(color="#64748B", size=10, family="JetBrains Mono, monospace")),
            gridcolor="#E2E8F0",
            showgrid=True,
            tickfont=dict(color="#64748B", size=9, family="JetBrains Mono, monospace"),
        ),
        yaxis=dict(
            title=dict(text="BATTERY SOC (%)", font=dict(color="#64748B", size=10, family="JetBrains Mono, monospace")),
            range=[0, 105],
            gridcolor="#E2E8F0",
            showgrid=True,
            tickfont=dict(color="#64748B", size=9, family="JetBrains Mono, monospace"),
        ),
        margin=dict(l=40, r=24, t=24, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="right",
            x=1,
            font=dict(color="#0F172A", size=10, family="JetBrains Mono, monospace"),
            bgcolor="rgba(255, 255, 255, 0.95)",
            bordercolor="#E2E8F0",
            borderwidth=1,
        ),
        height=420,
    )
    return fig
