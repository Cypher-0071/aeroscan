import base64
import math
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from app.telemetry import compute_battery_curves, get_fleet_telemetry_at_time
from core.contracts import FleetSchedule, InstanceContext

_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
_MAP_IMAGE_PATH = _ASSETS_DIR / "tactical_city_map.jpg"
_CACHED_MAP_DATA_URIS: dict[int, tuple[str, int, int]] = {}


def get_tactical_map_meta(rotation_deg: int = 90) -> tuple[str, int, int] | None:
    """Returns (base64_data_uri, width, height) of the tactical map asset rotated by rotation_deg degrees."""
    rotation_deg = rotation_deg % 360
    if rotation_deg in _CACHED_MAP_DATA_URIS:
        return _CACHED_MAP_DATA_URIS[rotation_deg]

    if not _MAP_IMAGE_PATH.exists():
        return None

    import io

    from PIL import Image

    with Image.open(_MAP_IMAGE_PATH) as img:
        if rotation_deg != 0:
            # In PIL, -deg rotates clockwise so 90 deg rotates clockwise
            img = img.rotate(-rotation_deg, expand=True)
        w, h = img.size
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        uri = f"data:image/jpeg;base64,{b64}"
        _CACHED_MAP_DATA_URIS[rotation_deg] = (uri, w, h)
        return uri, w, h


def get_tactical_map_data_uri(rotation_deg: int = 90) -> str | None:
    """Returns base64 data URI of the tactical illustrated city map asset, cached in memory."""
    meta = get_tactical_map_meta(rotation_deg)
    return meta[0] if meta else None


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


def create_drone_quadcopter_icon(
    center_x: float,
    center_y: float,
    heading_deg: float = 0.0,
    size_m: float = 34.0,
) -> tuple[str, float, float]:
    """Builds a heading-rotated quadcopter SVG data-URI icon for map rendering.

    The icon is drawn nose-up in a 100x100 viewBox and pre-rotated by the
    compass heading (0° = North / +Y, 90° = East / +X) so the UAV silhouette
    always points along its direction of travel. Returns (data_uri, width_m,
    height_m) suitable for ``fig.add_layout_image`` in data coordinates.
    """
    stroke = "#FFFFFF"  # white aviation outline for contrast on busy basemap
    body_fill = "#0F172A"  # dark fuselage = max contrast on light map
    accent_fill = "#38BDF8"  # bright cyan accent

    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
      <g transform="rotate({heading_deg % 360:.1f} 50 50)">
        <!-- outer glow disc -->
        <circle cx="50" cy="50" r="46" fill="rgba(2,132,199,0.25)" stroke="white" stroke-width="3"/>
        <!-- Nadir sensor gimbal -->
        <circle cx="50" cy="56" r="7.5" fill="#0F172A" stroke="{stroke}" stroke-width="2.5"/>
        <circle cx="50" cy="56" r="3.0" fill="#FBBF24"/>
        <!-- Fuselage -->
        <ellipse cx="50" cy="47" rx="12" ry="15" fill="{body_fill}" stroke="{stroke}" stroke-width="4"/>
        <path d="M50 30 L50 44" stroke="{accent_fill}" stroke-width="4" stroke-linecap="round"/>
        <path d="M44 36 L50 26 L56 36 Z" fill="{accent_fill}" stroke="white" stroke-width="1.5"/>
        <!-- Arms + rotors -->
        <line x1="42.5" y1="39.5" x2="26" y2="28" stroke="{stroke}" stroke-width="5" stroke-linecap="round"/>
        <line x1="57.5" y1="39.5" x2="74" y2="28" stroke="{stroke}" stroke-width="5" stroke-linecap="round"/>
        <line x1="42.5" y1="54.5" x2="26" y2="66" stroke="{stroke}" stroke-width="5" stroke-linecap="round"/>
        <line x1="57.5" y1="54.5" x2="74" y2="66" stroke="{stroke}" stroke-width="5" stroke-linecap="round"/>
        <ellipse cx="24" cy="26" rx="15" ry="8" fill="#0F172A" stroke="{accent_fill}" stroke-width="3" transform="rotate(-40 24 26)"/>
        <ellipse cx="76" cy="26" rx="15" ry="8" fill="#0F172A" stroke="{accent_fill}" stroke-width="3" transform="rotate(40 76 26)"/>
        <ellipse cx="24" cy="68" rx="15" ry="8" fill="#0F172A" stroke="{accent_fill}" stroke-width="3" transform="rotate(40 24 68)"/>
        <ellipse cx="76" cy="68" rx="15" ry="8" fill="#0F172A" stroke="{accent_fill}" stroke-width="3" transform="rotate(-40 76 68)"/>
        <circle cx="24" cy="26" r="4.5" fill="{accent_fill}" stroke="white" stroke-width="2"/>
        <circle cx="76" cy="26" r="4.5" fill="{accent_fill}" stroke="white" stroke-width="2"/>
        <circle cx="24" cy="68" r="4.5" fill="{accent_fill}" stroke="white" stroke-width="2"/>
        <circle cx="76" cy="68" r="4.5" fill="{accent_fill}" stroke="white" stroke-width="2"/>
      </g>
    </svg>
    """
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}", size_m, size_m


def build_mission_map_figure(  # noqa: PLR0913
    instance: InstanceContext,
    schedule: FleetSchedule | None = None,
    current_time_sec: float = 0.0,
    show_radar_halos: bool = True,
    show_breadcrumbs: bool = True,
    show_range_rings: bool = True,
    selected_uav_id: str | None = None,
    use_tactical_map: bool = True,
    map_opacity: float = 1.0,
    map_rotation_deg: int = 90,
    show_uav_icons: bool = True,
) -> go.Figure:
    """
    Builds an award-grade 2D spatial tactical operations map rendered on the rotated tactical city map underlay.
    Features subtle coordinate gridlines, range rings, priority gradients,
    corridors, directional UAV vectors, and high-legibility telemetry.
    """
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

    # Calculate optimal map coordinate bounds centered at depot
    all_xs = [t.x for t in instance.targets]
    all_ys = [t.y for t in instance.targets]
    max_extent_x = max(max(abs(x) for x in all_xs), 600.0) if all_xs else 600.0
    max_extent_y = max(max(abs(y) for y in all_ys), 600.0) if all_ys else 600.0

    # Image aspect ratio based on rotated dimensions
    aspect_ratio = float(img_h) / float(img_w)
    scale_margin = 1.32
    half_w = max(max_extent_x * scale_margin, 850.0)
    half_h = half_w * aspect_ratio
    if half_h < max_extent_y * scale_margin:
        half_h = max_extent_y * scale_margin
        half_w = half_h / aspect_ratio

    map_x_min, map_x_max = -half_w, half_w
    map_y_min, map_y_max = -half_h, half_h

    # Add tactical city map image layout underlay
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
                opacity=map_opacity,
                layer="below",
            )
        )

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
            max_bound = max(half_w, half_h) * 0.95
            ring_radii = [r for r in [300.0, 600.0, 900.0, 1200.0, 1500.0] if r <= max_bound]
            if not ring_radii:
                ring_radii = [300.0, 600.0]

            for r_dist in ring_radii:
                rx, ry = create_radar_circle(
                    center_node.x, center_node.y, radius=r_dist, num_pts=64
                )
                fig.add_trace(
                    go.Scatter(
                        x=rx,
                        y=ry,
                        mode="lines",
                        line=dict(
                            color="rgba(2, 132, 199, 0.45)" if is_map_active else "rgba(2, 132, 199, 0.20)",
                            width=1.5 if is_map_active else 1.0,
                            dash="dot",
                        ),
                        hoverinfo="none",
                        showlegend=False,
                    )
                )
                # Range ring distance tag on right perimeter
                fig.add_trace(
                    go.Scatter(
                        x=[center_node.x + r_dist],
                        y=[center_node.y],
                        mode="text",
                        text=[f"R-{int(r_dist)}m"],
                        textposition="middle right",
                        textfont=dict(
                            color="#0F172A" if is_map_active else "#64748B",
                            size=9,
                            family="JetBrains Mono, monospace",
                        ),
                        hoverinfo="none",
                        showlegend=False,
                    )
                )

    # 1. Target Nodes: Unsecured (Priority Scaled) vs. Secured (Emerald Glow)
    targets_unsecured = [t for t in instance.target_nodes if t.id not in secured_targets]
    targets_secured = [t for t in instance.target_nodes if t.id in secured_targets]

    # 1a. Priority Glow Backing: soft halo ring under every pending target so
    # points stay legible over the illustrated tactical map underlay.
    if targets_unsecured:
        fig.add_trace(
            go.Scatter(
                x=[t.x for t in targets_unsecured],
                y=[t.y for t in targets_unsecured],
                mode="markers",
                marker=dict(
                    size=[max(16, min(34, 12 + t.priority_score * 0.5)) for t in targets_unsecured],
                    color="rgba(248, 250, 252, 0.55)",
                    symbol="circle",
                    line=dict(width=0),
                    opacity=0.9,
                ),
                hoverinfo="none",
                showlegend=False,
            )
        )

    if targets_unsecured:
        fig.add_trace(
            go.Scatter(
                x=[t.x for t in targets_unsecured],
                y=[t.y for t in targets_unsecured],
                mode="markers",
                marker=dict(
                    size=[max(14, min(30, 10 + t.priority_score * 0.45)) for t in targets_unsecured],
                    color=[t.priority_score for t in targets_unsecured],
                    colorscale=[
                        [0.0, "#475569"],  # Slate Gray (Low Priority)
                        [0.35, "#0284C7"],  # Operational Blue
                        [0.70, "#F59E0B"],  # High Priority Amber
                        [1.0, "#EA580C"],  # Critical Amber-Orange
                    ],
                    showscale=True,
                    colorbar=dict(
                        title=dict(
                            text="PRIORITY",
                            font=dict(color="#0F172A", size=10, family="JetBrains Mono, monospace"),
                        ),
                        thickness=10,
                        len=0.55,
                        tickfont=dict(color="#334155", size=9, family="JetBrains Mono, monospace"),
                        outlinecolor="#CBD5E1",
                        outlinewidth=1,
                        bgcolor="rgba(255, 255, 255, 0.95)",
                    ),
                    line=dict(color="white", width=2.5),
                    opacity=1.0,
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
                    size=18,
                    color="#10B981",
                    symbol="circle",
                    line=dict(color="white", width=2.5),
                    opacity=1.0,
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
                    line=dict(
                        color="rgba(2, 132, 199, 0.5)" if is_map_active else "rgba(2, 132, 199, 0.35)",
                        width=1.5 if is_map_active else 1.0,
                    ),
                    fill="toself",
                    fillcolor="rgba(2, 132, 199, 0.12)" if is_map_active else "rgba(2, 132, 199, 0.06)",
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
                    size=18 if is_map_active else 16,
                    symbol="diamond",
                    color="#0284C7",
                    line=dict(color="#0F172A" if is_map_active else "#FFFFFF", width=2),
                ),
                text=[f"  {d.name.upper()}" for d in depot_nodes],
                textposition="middle right",
                textfont=dict(
                    color="#0F172A",
                    size=11 if is_map_active else 10,
                    family="JetBrains Mono, monospace",
                ),
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

    # 3. Planned Route Corridors (High-visibility flight paths)
    if schedule:
        for idx, route in enumerate(schedule.assigned_routes):
            color = DRONE_COLORS[idx % len(DRONE_COLORS)]
            is_focused = (selected_uav_id is None) or (route.drone_id == selected_uav_id)
            alpha_val = 0.98 if is_focused else 0.25
            line_w = 5.0 if is_focused else 2.0

            coords_x = [node_map[wp.node_id].x for wp in route.waypoints]
            coords_y = [node_map[wp.node_id].y for wp in route.waypoints]

            # White casing underneath for contrast over busy basemap
            if is_focused:
                fig.add_trace(
                    go.Scatter(
                        x=coords_x,
                        y=coords_y,
                        mode="lines",
                        line=dict(color="rgba(255, 255, 255, 0.95)", width=line_w + 4.0),
                        hoverinfo="none",
                        showlegend=False,
                    )
                )

            fig.add_trace(
                go.Scatter(
                    x=coords_x,
                    y=coords_y,
                    mode="lines",
                    line=dict(color=color, width=line_w),
                    opacity=alpha_val,
                    name=f"{route.drone_id} Corridor",
                    hoverinfo="none",
                )
            )

            # Visit-order sequence numbers so scout order is obvious
            if is_focused and len(coords_x) >= 2:
                seq_x = []
                seq_y = []
                seq_text = []
                for order, wp in enumerate(route.waypoints[1:-1], start=1):
                    node = node_map[wp.node_id]
                    seq_x.append(node.x)
                    seq_y.append(node.y)
                    seq_text.append(str(order))
                if seq_x:
                    fig.add_trace(
                        go.Scatter(
                            x=seq_x,
                            y=seq_y,
                            mode="markers+text",
                            marker=dict(size=20, color=color, line=dict(color="white", width=2)),
                            text=seq_text,
                            textposition="middle center",
                            textfont=dict(color="white", size=10, family="JetBrains Mono, monospace"),
                            hoverinfo="none",
                            showlegend=False,
                        )
                    )

            # Directional chevrons: keep the sense of travel readable along the corridor
            if is_focused and len(coords_x) >= 2:
                chev_x: list[float] = []
                chev_y: list[float] = []
                for i in range(1, len(coords_x)):
                    seg_dx = coords_x[i] - coords_x[i - 1]
                    seg_dy = coords_y[i] - coords_y[i - 1]
                    seg_len = math.hypot(seg_dx, seg_dy)
                    if seg_len < 60.0:
                        continue
                    ux, uy = seg_dx / seg_len, seg_dy / seg_len
                    tip = 0.62
                    bx, by = coords_x[i - 1] + tip * seg_dx, coords_y[i - 1] + tip * seg_dy
                    size = 11.0
                    chev_x.extend(
                        [
                            bx - size * ux + 0.55 * size * uy,
                            bx + size * ux,
                            bx - size * ux - 0.55 * size * uy,
                            bx - size * ux + 0.55 * size * uy,
                        ]
                    )
                    chev_y.extend(
                        [
                            by - size * uy - 0.55 * size * ux,
                            by + size * uy,
                            by - size * uy + 0.55 * size * ux,
                            by - size * uy - 0.55 * size * ux,
                        ]
                    )
                if chev_x:
                    fig.add_trace(
                        go.Scatter(
                            x=chev_x,
                            y=chev_y,
                            mode="lines",
                            line=dict(color=color, width=2.0),
                            opacity=min(0.85, alpha_val + 0.25),
                            hoverinfo="none",
                            showlegend=False,
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
                elif (
                    i > 0
                    and route.waypoints[i - 1].departure_time < current_time_sec < wp.arrival_time
                ):
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
                        mode="lines",
                        line=dict(color="rgba(255, 255, 255, 0.95)", width=9.0),
                        hoverinfo="none",
                        showlegend=False,
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=crumbs_x,
                        y=crumbs_y,
                        mode="lines+markers",
                        line=dict(color=color, width=6.0),
                        marker=dict(size=7, color=color, line=dict(color="white", width=1.5)),
                        name=f"{route.drone_id} Flown Track",
                        hoverinfo="none",
                        showlegend=False,
                    )
                )

    # 5. Live UAV Kinematic Positions: quadcopter SVG icons, scan cones, reticles
    # Always render every drone so it is never "invisible". Drones without an
    # assigned scouting route hold in formation around the depot so the full
    # fleet count selected in the sidebar stays visible.
    deployed_telemetry = list(enumerate(active_telemetry))
    routed_ids = {r.drone_id for r in schedule.assigned_routes} if schedule else set()
    n_deployed = len(deployed_telemetry)

    for idx, telem in deployed_telemetry:
        color = DRONE_COLORS[idx % len(DRONE_COLORS)]
        is_focused = (selected_uav_id is None) or (telem["drone_id"] == selected_uav_id)
        if not is_focused:
            continue

        ux, uy = telem["x"], telem["y"]
        if telem["drone_id"] not in routed_ids and n_deployed > 1:
            hold_angle = 2 * math.pi * idx / max(n_deployed, 1)
            ux = ux + 85.0 * math.cos(hold_angle)
            uy = uy + 85.0 * math.sin(hold_angle)
        heading_deg = float(telem.get("heading_deg", 0.0))
        heading_rad = math.radians(heading_deg)
        fwd_x, fwd_y = math.sin(heading_rad), math.cos(heading_rad)

        # Dynamic Radar Halo + pulsing sensor footprint rings
        if show_radar_halos:
            hx, hy = create_radar_circle(ux, uy, radius=60.0)
            fig.add_trace(
                go.Scatter(
                    x=hx,
                    y=hy,
                    mode="lines",
                    line=dict(color=color, width=2.0),
                    fill="toself",
                    fillcolor=f"rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.22)",
                    hoverinfo="none",
                    showlegend=False,
                )
            )
            for halo_r, halo_alpha in ((85.0, 0.45), (110.0, 0.22)):
                px, py = create_radar_circle(ux, uy, radius=halo_r, num_pts=56)
                fig.add_trace(
                    go.Scatter(
                        x=px,
                        y=py,
                        mode="lines",
                        line=dict(color=color, width=1.5),
                        opacity=halo_alpha,
                        hoverinfo="none",
                        showlegend=False,
                    )
                )

        # Forward scan cone: sensor field-of-view projected in the heading direction
        cone_len, cone_half_deg = 135.0, 24.0
        left_rad = heading_rad + math.radians(cone_half_deg)
        right_rad = heading_rad - math.radians(cone_half_deg)
        rgb = (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))
        fig.add_trace(
            go.Scatter(
                x=[ux, ux + cone_len * math.sin(left_rad), ux + cone_len * fwd_x,
                   ux + cone_len * math.sin(right_rad), ux],
                y=[uy, uy + cone_len * math.cos(left_rad), uy + cone_len * fwd_y,
                   uy + cone_len * math.cos(right_rad), uy],
                mode="lines",
                line=dict(color=color, width=1.4),
                fill="toself",
                fillcolor=f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 0.14)",
                hoverinfo="none",
                showlegend=False,
            )
        )

        # Heading tick vector (nose direction reference)
        vec_len = 55.0
        fig.add_trace(
            go.Scatter(
                x=[ux, ux + vec_len * fwd_x],
                y=[uy, uy + vec_len * fwd_y],
                mode="lines",
                line=dict(color="white", width=5),
                hoverinfo="none",
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[ux, ux + vec_len * fwd_x],
                y=[uy, uy + vec_len * fwd_y],
                mode="lines",
                line=dict(color="#0F172A", width=2.5),
                hoverinfo="none",
                showlegend=False,
            )
        )

        # Dark backing disc so the drone pops off the busy basemap
        fig.add_trace(
            go.Scatter(
                x=[ux],
                y=[uy],
                mode="markers",
                marker=dict(size=42, color="#0F172A", line=dict(color="white", width=3)),
                hoverinfo="none",
                showlegend=False,
            )
        )

        # Callout leader line to the UAV callsign label
        fig.add_trace(
            go.Scatter(
                x=[ux + 20.0, ux + 70.0],
                y=[uy + 20.0, uy + 62.0],
                mode="lines",
                line=dict(color="white", width=4),
                opacity=0.95,
                hoverinfo="none",
                showlegend=False,
            )
        )
        # Staggered callout side per drone so labels never stack with big fleets
        callout_side = 1.0 if idx % 2 == 0 else -1.0
        callout_y = 62.0 + (idx // 2) * 34.0
        fig.add_trace(
            go.Scatter(
                x=[ux + 20.0 * callout_side, ux + 70.0 * callout_side],
                y=[uy + 20.0, uy + callout_y],
                mode="lines",
                line=dict(color=color, width=2),
                opacity=1.0,
                hoverinfo="none",
                showlegend=False,
            )
        )

        # Quadcopter SVG drone icon, rotated to the live compass heading
        if show_uav_icons:
            icon_uri, icon_w, icon_h = create_drone_quadcopter_icon(
                ux, uy, heading_deg=heading_deg, size_m=130.0
            )
            fig.add_layout_image(
                dict(
                    source=icon_uri,
                    xref="x",
                    yref="y",
                    x=ux,
                    y=uy,
                    sizex=icon_w,
                    sizey=icon_h,
                    xanchor="center",
                    yanchor="middle",
                    layer="above",
                )
            )

        # Target-lock reticle locking onto the UAV's current destination
        tgt = node_map.get(telem.get("current_node_id"))
        if tgt is not None and math.hypot(tgt.x - ux, tgt.y - uy) > 1.0:
            r_lock = 52.0
            lx, ly = create_radar_circle(tgt.x, tgt.y, radius=r_lock, num_pts=4)
            lock_marker = go.Scatter(
                x=lx,
                y=ly,
                mode="lines",
                line=dict(color="white", width=5),
                hoverinfo="none",
                showlegend=False,
            )
            fig.add_trace(lock_marker)
            fig.add_trace(
                go.Scatter(
                    x=lx,
                    y=ly,
                    mode="lines",
                    line=dict(color=color, width=3.0),
                    hoverinfo="none",
                    showlegend=False,
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[tgt.x, tgt.x, tgt.x - r_lock * 0.55, tgt.x + r_lock * 0.55],
                    y=[tgt.y - r_lock * 0.55, tgt.y + r_lock * 0.55, tgt.y, tgt.y],
                    mode="lines",
                    line=dict(color=color, width=1.2),
                    opacity=0.7,
                    hoverinfo="none",
                    showlegend=False,
                )
            )

        # High-contrast telemetry chip beside the icon (staggered per drone)
        phase_label = str(telem.get("flight_phase", "ACTIVE"))
        if telem["drone_id"] not in routed_ids:
            phase_label = "HOLDING"
        fig.add_trace(
            go.Scatter(
                x=[ux + 95.0 * callout_side],
                y=[uy + callout_y + 23.0],
                mode="markers+text",
                marker=dict(
                    size=12,
                    symbol="square",
                    color=color,
                    line=dict(color="white", width=2.5),
                ),
                text=[
                    f"<span style='background:#0F172A; color:#FFFFFF; padding:5px 12px;"
                    f"border:2px solid {color}; border-radius:8px; font-weight:800; font-size:15px; font-family:JetBrains Mono, monospace; white-space:nowrap;'>"
                    f"{telem['drone_id']} · {telem['battery_percent']:.0f}% · {phase_label}</span>"
                ],
                textposition="middle right" if callout_side > 0 else "middle left",
                textfont=dict(color="#FFFFFF", size=15, family="JetBrains Mono, monospace"),
                name=f"Live {telem['drone_id']}",
                hovertext=(
                    f"<b>{telem['drone_id']} // TELEMETRY</b><br>"
                    f"Phase: <b>{telem['flight_phase']}</b><br>"
                    f"Groundspeed: <b>{telem['speed_mps']:.1f} m/s</b><br>"
                    f"Altitude: <b>{telem['z']:.1f} m</b><br>"
                    f"Heading: <b>{heading_deg:.0f}°</b><br>"
                    f"Battery SoC: <b>{telem['battery_percent']:.1f}%</b><br>"
                    f"Scanning: <b>{telem.get('target_name', 'DEPOT')}</b>"
                ),
                hoverinfo="text",
                showlegend=False,
            )
        )

    # Professional Light Geospatial Layout
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#DDE7E7" if is_map_active else "#F8FAFC",
        xaxis=dict(
            title=dict(
                text="EASTING X (M)",
                font=dict(color="#334155" if is_map_active else "#64748B", size=10, family="JetBrains Mono, monospace"),
            ),
            gridcolor="rgba(15, 23, 42, 0.08)" if is_map_active else "#E2E8F0",
            zerolinecolor="#CBD5E1",
            showgrid=not is_map_active,
            zeroline=False,
            range=[map_x_min * 0.98, map_x_max * 0.98] if is_map_active else None,
            constrain="domain",
            tickfont=dict(color="#334155" if is_map_active else "#64748B", size=9, family="JetBrains Mono, monospace"),
        ),
        yaxis=dict(
            title=dict(
                text="NORTHING Y (M)",
                font=dict(color="#334155" if is_map_active else "#64748B", size=10, family="JetBrains Mono, monospace"),
            ),
            gridcolor="rgba(15, 23, 42, 0.08)" if is_map_active else "#E2E8F0",
            zerolinecolor="#CBD5E1",
            scaleanchor="x",
            scaleratio=1,
            showgrid=not is_map_active,
            zeroline=False,
            range=[map_y_min * 0.98, map_y_max * 0.98] if is_map_active else None,
            tickfont=dict(color="#334155" if is_map_active else "#64748B", size=9, family="JetBrains Mono, monospace"),
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
        hovermode="closest",
        height=720,
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
    depot_ids = {d.launch_depot_id for d in instance.drones} | {
        d.recovery_depot_id for d in instance.drones
    }

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
                hovertext=[
                    f"<b>{drone_id}</b>: {val:.1f}% SoC at {int(t)}s"
                    for val, t in zip(df[col], df["Time_sec"])
                ],
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
            title=dict(
                text="MISSION TIME (SEC)",
                font=dict(color="#64748B", size=10, family="JetBrains Mono, monospace"),
            ),
            gridcolor="#E2E8F0",
            showgrid=True,
            tickfont=dict(color="#64748B", size=9, family="JetBrains Mono, monospace"),
        ),
        yaxis=dict(
            title=dict(
                text="BATTERY SOC (%)",
                font=dict(color="#64748B", size=10, family="JetBrains Mono, monospace"),
            ),
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
        height=400,
    )
    return fig


def build_uav_kinematics_figure(
    schedule: FleetSchedule,
    instance: InstanceContext,
    uav_id: str,
    current_time_sec: float = 300.0,
) -> go.Figure:
    """
    Builds a synchronized dual-axis kinematics chart for the selected UAV.
    Tracks Battery SoC (%) on Primary Axis and Altitude (m) / Speed (m/s) on Secondary Axis.
    """
    df = compute_battery_curves(schedule, instance)
    col_name = f"{uav_id} SoC (%)"
    u_idx = 0
    for i, r in enumerate(schedule.assigned_routes):
        if r.drone_id == uav_id:
            u_idx = i
            break
    color = DRONE_COLORS[u_idx % len(DRONE_COLORS)]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if not df.empty and col_name in df.columns:
        times = df["Time_sec"]
        soc = df[col_name]

        # Primary Axis: Battery SoC
        fig.add_trace(
            go.Scatter(
                x=times,
                y=soc,
                name="Battery SoC (%)",
                line=dict(color=color, width=2.5),
                hoverinfo="text",
                hovertext=[f"{uav_id} SoC: {val:.1f}% at {int(t)}s" for val, t in zip(soc, times)],
            ),
            secondary_y=False,
        )

        # Secondary Axis: Synthesized Altitude Envelope (m)
        alt_values = [
            0.0 if t < 30 or t > max(times) - 30 else (60.0 + 10.0 * math.sin(t / 120.0))
            for t in times
        ]
        fig.add_trace(
            go.Scatter(
                x=times,
                y=alt_values,
                name="Altitude (m)",
                line=dict(color="#64748B", width=1.5, dash="dash"),
                hoverinfo="text",
                hovertext=[f"Alt: {val:.0f}m at {int(t)}s" for val, t in zip(alt_values, times)],
            ),
            secondary_y=True,
        )

    # 15% Safety Floor on Battery axis
    fig.add_shape(
        type="line",
        x0=0,
        x1=float(df["Time_sec"].max()) if not df.empty else 1800.0,
        y0=15.0,
        y1=15.0,
        line=dict(color="#EF4444", width=1.5, dash="dot"),
        secondary_y=False,
    )

    # Current mission time scrubber marker
    fig.add_vline(
        x=current_time_sec,
        line_width=1.5,
        line_dash="dot",
        line_color="#0284C7",
        annotation_text=f"t={int(current_time_sec)}s",
        annotation_position="top left",
        annotation_font=dict(color="#0284C7", size=9, family="JetBrains Mono, monospace"),
    )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#F8FAFC",
        xaxis=dict(
            title=dict(
                text="MISSION TIME (SEC)",
                font=dict(color="#64748B", size=10, family="JetBrains Mono, monospace"),
            ),
            gridcolor="#E2E8F0",
            showgrid=True,
            tickfont=dict(color="#64748B", size=9, family="JetBrains Mono, monospace"),
        ),
        margin=dict(l=35, r=35, t=25, b=35),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#0F172A", size=9, family="JetBrains Mono, monospace"),
            bgcolor="rgba(255, 255, 255, 0.95)",
            bordercolor="#E2E8F0",
        ),
        height=380,
    )
    fig.update_yaxes(
        title_text="BATTERY SOC (%)",
        title_font=dict(color=color, size=10, family="JetBrains Mono, monospace"),
        range=[0, 105],
        gridcolor="#E2E8F0",
        secondary_y=False,
        tickfont=dict(color=color, size=9, family="JetBrains Mono"),
    )
    fig.update_yaxes(
        title_text="ALTITUDE (M)",
        title_font=dict(color="#64748B", size=10, family="JetBrains Mono, monospace"),
        range=[0, 100],
        gridcolor="#E2E8F0",
        secondary_y=True,
        tickfont=dict(color="#64748B", size=9, family="JetBrains Mono"),
    )
    return fig


def build_energy_breakdown_figure() -> go.Figure:
    """
    Builds a high-density horizontal stacked bar visualization of power allocation across flight modes.
    """
    fig = go.Figure()
    categories = ["Fleet Subsystems"]

    fig.add_trace(
        go.Bar(
            y=categories,
            x=[61.4],
            name="Cruise Propulsion (61.4%)",
            orientation="h",
            marker=dict(color="#0284C7"),
        )
    )
    fig.add_trace(
        go.Bar(
            y=categories,
            x=[22.8],
            name="Sensor Dwell & Hover (22.8%)",
            orientation="h",
            marker=dict(color="#0D9488"),
        )
    )
    fig.add_trace(
        go.Bar(
            y=categories,
            x=[15.8],
            name="Wind Drift Compensation (15.8%)",
            orientation="h",
            marker=dict(color="#F59E0B"),
        )
    )

    fig.update_layout(
        barmode="stack",
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        xaxis=dict(
            title=dict(
                text="POWER ALLOCATION (%)",
                font=dict(color="#64748B", size=10, family="JetBrains Mono"),
            ),
            range=[0, 100],
            gridcolor="#E2E8F0",
            tickfont=dict(color="#64748B", size=9, family="JetBrains Mono"),
        ),
        yaxis=dict(showticklabels=False),
        margin=dict(l=10, r=20, t=10, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(color="#0F172A", size=9, family="JetBrains Mono"),
        ),
        height=130,
    )
    return fig


def build_animated_mission_map_figure(
    instance: InstanceContext,
    schedule: FleetSchedule | None = None,
    n_frames: int = 60,
    show_range_rings: bool = True,
    use_tactical_map: bool = True,
    map_opacity: float = 0.88,
    map_rotation_deg: int = 90,
) -> go.Figure:
    """Smooth browser-side animated mission map (no Streamlit reruns = no blink).

    All motion is Plotly frames + Play/Pause buttons rendered once. Drones glide
    along corridors, trails grow, and targets flip pending -> secured per frame.
    """
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
                opacity=map_opacity,
                layer="below",
            )
        )

    max_time = max((r.total_flight_time for r in schedule.assigned_routes), default=1800.0) if schedule else 1800.0
    if max_time <= 0:
        max_time = 1800.0
    frame_times = [max_time * k / max(n_frames - 1, 1) for k in range(n_frames)]

    # ---- static: range rings ----
    if show_range_rings and depot_ids:
        main_depot_id = list(depot_ids)[0]
        if main_depot_id in node_map:
            center_node = node_map[main_depot_id]
            max_bound = max(half_w, half_h) * 0.95
            ring_radii = [r for r in [300.0, 600.0, 900.0] if r <= max_bound] or [300.0, 600.0]
            for r_dist in ring_radii:
                rx, ry = create_radar_circle(center_node.x, center_node.y, radius=r_dist, num_pts=64)
                fig.add_trace(go.Scatter(x=rx, y=ry, mode="lines",
                    line=dict(color="rgba(2,132,199,0.4)", width=1.5, dash="dot"),
                    hoverinfo="none", showlegend=False))

    # ---- static: premium target base (glow + priority core) ----
    pending = list(instance.target_nodes)
    if pending:
        fig.add_trace(go.Scatter(
            x=[t.x for t in pending], y=[t.y for t in pending], mode="markers",
            marker=dict(size=[max(22, min(40, 16 + t.priority_score * 0.55)) for t in pending],
                color="rgba(255,255,255,0.9)", symbol="circle", line=dict(width=0)),
            hoverinfo="none", showlegend=False))
        fig.add_trace(go.Scatter(
            x=[t.x for t in pending], y=[t.y for t in pending], mode="markers",
            marker=dict(size=[max(15, min(30, 10 + t.priority_score * 0.45)) for t in pending],
                color=[t.priority_score for t in pending],
                colorscale=[[0.0, "#334155"], [0.4, "#0284C7"], [0.7, "#F59E0B"], [1.0, "#EA580C"]],
                showscale=True,
                colorbar=dict(title=dict(text="PRIORITY",
                    font=dict(color="#0F172A", size=10, family="JetBrains Mono, monospace")),
                    thickness=10, len=0.55,
                    tickfont=dict(color="#334155", size=9, family="JetBrains Mono, monospace"),
                    outlinecolor="#CBD5E1", outlinewidth=1, bgcolor="rgba(255,255,255,0.95)"),
                line=dict(color="white", width=2.5), opacity=1.0),
            name="Target",
            hovertext=[f"<b>TARGET #{t.id:02d}</b> · {t.priority_score:.0f} pts" for t in pending],
            hoverinfo="text"))

    # ---- static: corridors (white casing + solid color) + order badges ----
    if schedule:
        for idx, route in enumerate(schedule.assigned_routes):
            color = DRONE_COLORS[idx % len(DRONE_COLORS)]
            cx = [node_map[wp.node_id].x for wp in route.waypoints]
            cy = [node_map[wp.node_id].y for wp in route.waypoints]
            fig.add_trace(go.Scatter(x=cx, y=cy, mode="lines",
                line=dict(color="rgba(255,255,255,0.9)", width=7.0),
                hoverinfo="none", showlegend=False))
            fig.add_trace(go.Scatter(x=cx, y=cy, mode="lines",
                line=dict(color=color, width=4.0),
                name=f"{route.drone_id} Route", hoverinfo="none"))
            seq_x, seq_y, seq_t = [], [], []
            for order, wp in enumerate(route.waypoints[1:-1], start=1):
                n = node_map[wp.node_id]
                seq_x.append(n.x)
                seq_y.append(n.y)
                seq_t.append(str(order))
            if seq_x:
                fig.add_trace(go.Scatter(x=seq_x, y=seq_y, mode="markers+text",
                    marker=dict(size=19, color="white", line=dict(color=color, width=2.5)),
                    text=seq_t, textposition="middle center",
                    textfont=dict(color="#0F172A", size=10, family="JetBrains Mono, monospace"),
                    hoverinfo="none", showlegend=False))

    # ---- static: depots ----
    depot_nodes = [node_map[d] for d in depot_ids if d in node_map]
    if depot_nodes:
        fig.add_trace(go.Scatter(
            x=[d.x for d in depot_nodes], y=[d.y for d in depot_nodes],
            mode="markers+text",
            marker=dict(size=20, symbol="diamond", color="#0284C7", line=dict(color="white", width=3)),
            text=[f"  {d.name.upper()}" for d in depot_nodes], textposition="middle right",
            textfont=dict(color="#0F172A", size=11, family="JetBrains Mono, monospace"),
            name="Base", hoverinfo="none"))

    # Snapshot static traces — every frame must repeat them, otherwise
    # Plotly maps frame data onto figure traces by index and statics get clobbered.
    base_data = list(fig.data)

    # ---- dynamic: initial frame placeholders (replaced by frames) ----
    fleet_drones = list(instance.drones)
    route_map = {r.drone_id: r for r in schedule.assigned_routes} if schedule else {}
    for idx, drone in enumerate(fleet_drones):
        color = DRONE_COLORS[idx % len(DRONE_COLORS)]
        did = drone.id
        fig.add_trace(go.Scatter(x=[], y=[], mode="lines",
            line=dict(color="rgba(255,255,255,0.9)", width=8), hoverinfo="none", showlegend=False))
        fig.add_trace(go.Scatter(x=[], y=[], mode="lines+markers",
            line=dict(color=color, width=5),
            marker=dict(size=7, color=color, line=dict(color="white", width=2)),
            hoverinfo="none", showlegend=False, name=f"{did} trail"))
        fig.add_trace(go.Scatter(x=[], y=[], mode="markers+text",
            marker=dict(size=32, color="#0F172A", line=dict(color="white", width=3.5)),
            text=[], textposition="top center",
            textfont=dict(color="#0F172A", size=14, family="JetBrains Mono, monospace"),
            hoverinfo="none", showlegend=False, name=did))
    fig.add_trace(go.Scatter(x=[], y=[], mode="markers",
        marker=dict(size=20, color="#10B981", symbol="star", line=dict(color="white", width=2.5)),
        name="Secured", hoverinfo="none"))

    # ---- frames (each frame carries FULL styling — bare x/y resets to defaults) ----
    frames = []
    for k, t in enumerate(frame_times):
        dyn = []
        telems, secured = get_fleet_telemetry_at_time(schedule, t, instance) if schedule else ([], set())
        telem_by_id = {tm["drone_id"]: tm for tm in telems}
        for idx, drone in enumerate(fleet_drones):
            color = DRONE_COLORS[idx % len(DRONE_COLORS)]
            telem = telem_by_id.get(drone.id)
            if telem is None:
                dyn.extend([
                    go.Scatter(x=[], y=[], mode="lines",
                        line=dict(color="rgba(255,255,255,0.9)", width=8),
                        hoverinfo="none", showlegend=False),
                    go.Scatter(x=[], y=[], mode="lines+markers",
                        line=dict(color=color, width=5),
                        marker=dict(size=7, color=color, line=dict(color="white", width=2)),
                        hoverinfo="none", showlegend=False),
                    go.Scatter(x=[], y=[], mode="markers+text",
                        marker=dict(size=36, color="#0F172A", line=dict(color=color, width=4)),
                        text=[], textposition="top center",
                        textfont=dict(color="#0F172A", size=14, family="JetBrains Mono, monospace"),
                        hoverinfo="none", showlegend=False),
                ])
                continue
            route = route_map.get(drone.id)
            # trail up to t
            tx, ty = [], []
            if route:
                for i, wp in enumerate(route.waypoints):
                    node = node_map[wp.node_id]
                    if wp.arrival_time <= t:
                        tx.append(node.x)
                        ty.append(node.y)
                    elif i > 0 and route.waypoints[i-1].departure_time < t < wp.arrival_time:
                        prev = node_map[route.waypoints[i-1].node_id]
                        frac = (t - route.waypoints[i-1].departure_time) / max(wp.arrival_time - route.waypoints[i-1].departure_time, 1e-4)
                        tx.append(prev.x + frac * (node.x - prev.x))
                        ty.append(prev.y + frac * (node.y - prev.y))
                        break
            dyn.append(go.Scatter(x=tx, y=ty, mode="lines",
                line=dict(color="rgba(255,255,255,0.9)", width=8),
                hoverinfo="none", showlegend=False))
            dyn.append(go.Scatter(x=tx, y=ty, mode="lines+markers",
                line=dict(color=color, width=5),
                marker=dict(size=7, color=color, line=dict(color="white", width=2)),
                hoverinfo="none", showlegend=False, name=f"{drone.id} trail"))
            dyn.append(go.Scatter(
                x=[telem["x"]], y=[telem["y"]], mode="markers+text",
                marker=dict(size=36, color="#0F172A", line=dict(color=color, width=4)),
                text=[f"{telem['drone_id']} · {telem['battery_percent']:.0f}%"],
                textposition="top center",
                textfont=dict(color="#0F172A", size=14, family="JetBrains Mono, monospace"),
                hoverinfo="none", showlegend=False, name=drone.id))
        sec = [n for n in instance.target_nodes if n.id in secured]
        dyn.append(go.Scatter(x=[n.x for n in sec], y=[n.y for n in sec], mode="markers",
            marker=dict(size=22, color="#10B981", symbol="star", line=dict(color="white", width=3)),
            name="Secured", hoverinfo="none"))
        fdata = list(base_data) + dyn
        fdata = list(base_data) + dyn
        frames.append(go.Frame(data=fdata, name=f"{t:.0f}",
            layout=go.Layout(annotations=[dict(
                text=f"T+{t:.0f}s / {max_time:.0f}s",
                x=0.01, y=0.99, xref="paper", yref="paper",
                showarrow=False, font=dict(color="white", size=14, family="JetBrains Mono, monospace"),
                bgcolor="#0F172A", borderpad=6)])))
    fig.frames = frames
    # Seed visible mid-mission positions on load (placeholders are empty until PLAY).
    if frames:
        seed = frames[min(len(frames) // 3, len(frames) - 1)].data
        for fig_tr, seed_tr in zip(fig.data, seed):
            try:
                if seed_tr.x is not None:
                    fig_tr.x = seed_tr.x
                if seed_tr.y is not None:
                    fig_tr.y = seed_tr.y
                if getattr(seed_tr, "text", None):
                    fig_tr.text = seed_tr.text
            except Exception:
                pass

    fig.update_layout(
        template="plotly_white", paper_bgcolor="#FFFFFF", plot_bgcolor="#DDE7E7",
        xaxis=dict(title=dict(text="EASTING X (M)",
            font=dict(color="#334155", size=10, family="JetBrains Mono, monospace")),
            gridcolor="rgba(15,23,42,0.08)", zeroline=False,
            range=[map_x_min*0.98, map_x_max*0.98],
            constrain="domain",
            tickfont=dict(color="#334155", size=9, family="JetBrains Mono, monospace")),
        yaxis=dict(title=dict(text="NORTHING Y (M)",
            font=dict(color="#334155", size=10, family="JetBrains Mono, monospace")),
            gridcolor="rgba(15,23,42,0.08)", zeroline=False,
            scaleanchor="x", scaleratio=1,
            range=[map_y_min*0.98, map_y_max*0.98],
            tickfont=dict(color="#334155", size=9, family="JetBrains Mono, monospace")),
        margin=dict(l=40, r=24, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(color="#0F172A", size=10, family="JetBrains Mono, monospace"),
            bgcolor="rgba(255,255,255,0.95)", bordercolor="#E2E8F0", borderwidth=1),
        hovermode="closest", height=720,
        updatemenus=[dict(type="buttons", direction="left", x=0.0, y=1.08, showactive=False,
            buttons=[
                dict(label="▶ EXECUTE MISSION", method="animate",
                    args=[None, dict(frame=dict(duration=120, redraw=True),
                        fromcurrent=True, mode="immediate",
                        transition=dict(duration=80, easing="linear"))]),
                dict(label="⏸ PAUSE", method="animate",
                    args=[[None], dict(frame=dict(duration=0, redraw=False),
                        mode="immediate", transition=dict(duration=0))]),
            ])],
        sliders=[dict(active=0, x=0.12, len=0.88, xanchor="left", y=0, yanchor="top",
            pad=dict(b=10, t=40), currentvalue=dict(prefix="MISSION TIME T+",
                font=dict(color="#0284C7", size=13, family="JetBrains Mono, monospace")),
            steps=[dict(label=f"{t:.0f}s", method="animate",
                args=[[f"{t:.0f}"], dict(frame=dict(duration=0, redraw=True),
                    mode="immediate", transition=dict(duration=0))]) for t in frame_times])],
    )
    return fig
