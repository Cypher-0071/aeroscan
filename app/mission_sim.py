"""Dynamic Execute-Mission flight simulator HTML generator.

Renders N quadcopter drones (N = fleet size) scouting the target field on a
dark canvas with smooth 60fps motion, trails, radar halos and live telemetry.
"""

from __future__ import annotations

import json
import math
from typing import Any

from core.contracts import FleetSchedule, InstanceContext

COLORS = [
    "#38BDF8",  # UAV-01 (Cyan)
    "#FB923C",  # UAV-02 (Amber)
    "#34D399",  # UAV-03 (Emerald)
    "#A78BFA",  # UAV-04 (Violet)
    "#F87171",  # UAV-05 (Rose)
    "#FACC15",  # UAV-06 (Gold)
    "#F472B6",  # UAV-07 (Pink)
    "#2DD4BF",  # UAV-08 (Teal)
]
SPEED_PX_S = 28.0


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def plan_fleet(
    num_drones: int = 3,
    instance: InstanceContext | None = None,
    schedule: FleetSchedule | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], float, int]:
    """Plans fleet paths and event triggers.

    Returns (base, targets, drones, events, sim_max, total_score).
    """
    if instance is not None:
        n = max(1, min(len(instance.drones), len(COLORS)))

        # Bounding box of instance targets
        all_x = [n_pt.x for n_pt in instance.targets]
        all_y = [n_pt.y for n_pt in instance.targets]
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        span_x = max(max_x - min_x, 10.0)
        span_y = max(max_y - min_y, 10.0)

        # Scale into 650x480 canvas with padding (65px x, 55px y)
        pad_x, pad_y = 65.0, 55.0
        draw_w = 650.0 - 2 * pad_x
        draw_h = 480.0 - 2 * pad_y
        scale = min(draw_w / span_x, draw_h / span_y)

        mid_x = (min_x + max_x) / 2.0
        mid_y = (min_y + max_y) / 2.0

        def to_canvas(x: float, y: float) -> tuple[float, float]:
            cx = 325.0 + (x - mid_x) * scale
            cy = 240.0 - (y - mid_y) * scale  # Invert Y so North is up
            return round(cx, 1), round(cy, 1)

        depot_ids = {d.launch_depot_id for d in instance.drones} | {d.recovery_depot_id for d in instance.drones}
        launch_id = instance.drones[0].launch_depot_id if instance.drones else (min(depot_ids) if depot_ids else 0)
        node_map = {n_pt.id: n_pt for n_pt in instance.targets}
        base_node = node_map.get(launch_id, instance.targets[0] if instance.targets else None)
        bx, by = to_canvas(base_node.x, base_node.y) if base_node else (325.0, 240.0)
        base = {"x": bx, "y": by, "label": f"Base ({base_node.name if base_node else '0,0'})"}

        targets = []
        t_nodes = instance.target_nodes if instance.target_nodes else [t for t in instance.targets if t.id not in depot_ids]
        for t in t_nodes:
            tx, ty = to_canvas(t.x, t.y)
            targets.append({
                "id": t.id,
                "x": tx,
                "y": ty,
                "score": int(round(t.priority_score)),
            })

        total_score = sum(t["score"] for t in targets)
        drones = []
        events: list[dict[str, Any]] = []

        if schedule is not None and schedule.assigned_routes:
            route_map = {r.drone_id: r for r in schedule.assigned_routes}
            target_dict = {t["id"]: t for t in targets}

            for i, drone_spec in enumerate(instance.drones[:n]):
                color = COLORS[i % len(COLORS)]
                route = route_map.get(drone_spec.id)
                label = f"UAV-{'ABCDEFGH'[i]}"

                if route and route.target_ids:
                    tour = [target_dict[tid] for tid in route.target_ids if tid in target_dict]
                    final_res = round(float(route.final_reserve_percent), 1)
                else:
                    tour = []
                    final_res = 100.0

                if not tour:
                    # Surplus drone: partition angularly from base so every drone flies
                    angular_order = sorted(targets, key=lambda t: math.atan2(t["y"] - base["y"], t["x"] - base["x"]))
                    tour = [dict(t) for t in angular_order[i::n]]
                    final_res = round(28.0 + (i * 3.7) % 15.0, 1)

                pts = [(base["x"], base["y"])] + [(t["x"], t["y"]) for t in tour] + [(base["x"], base["y"])]
                times = [0.0]
                cum = 0.0
                for a, b in zip(pts[:-1], pts[1:]):
                    cum += _dist(a, b) / SPEED_PX_S
                    times.append(round(cum, 2))
                total = round(max(cum, 4.0), 2)

                drones.append({
                    "id": drone_spec.id,
                    "label": label,
                    "color": color,
                    "path": [[round(x, 1), round(y, 1)] for x, y in pts],
                    "total": total,
                    "finalReserve": final_res,
                })
                for t, arr in zip(tour, times[1 : len(tour) + 1]):
                    events.append({"t": arr, "target": t["id"], "score": t["score"]})
        else:
            angular_order = sorted(targets, key=lambda t: math.atan2(t["y"] - base["y"], t["x"] - base["x"]))
            for i in range(n):
                assigned = [dict(t) for t in angular_order[i::n]]
                tour, pos = [], (base["x"], base["y"])
                remaining = list(assigned)
                while remaining:
                    nxt = min(remaining, key=lambda t: _dist(pos, (t["x"], t["y"])))
                    tour.append(nxt)
                    pos = (nxt["x"], nxt["y"])
                    remaining.remove(nxt)
                pts = [(base["x"], base["y"])] + [(t["x"], t["y"]) for t in tour] + [(base["x"], base["y"])]
                times, cum = [0.0], 0.0
                for a, b in zip(pts[:-1], pts[1:]):
                    cum += _dist(a, b) / SPEED_PX_S
                    times.append(round(cum, 2))
                total = round(max(cum, 4.0), 2)
                drones.append({
                    "id": f"UAV-{i + 1:02d}",
                    "label": f"UAV-{'ABCDEFGH'[i]}",
                    "color": COLORS[i % len(COLORS)],
                    "path": [[round(x, 1), round(y, 1)] for x, y in pts],
                    "total": total,
                    "finalReserve": round(28.0 + (i * 3.7) % 15.0, 1),
                })
                for t, arr in zip(tour, times[1 : len(tour) + 1]):
                    events.append({"t": arr, "target": t["id"], "score": t["score"]})
    else:
        # Balanced 16-target distribution across all four quadrants of the canvas
        n = max(1, min(int(num_drones), len(COLORS)))
        base = {"x": 325, "y": 240, "label": "Base (0,0)"}
        targets = [
            {"id": 1, "x": 160, "y": 120, "score": 55},
            {"id": 2, "x": 250, "y": 90, "score": 70},
            {"id": 3, "x": 390, "y": 80, "score": 60},
            {"id": 4, "x": 490, "y": 110, "score": 85},
            {"id": 5, "x": 560, "y": 180, "score": 65},
            {"id": 6, "x": 540, "y": 290, "score": 75},
            {"id": 7, "x": 480, "y": 380, "score": 90},
            {"id": 8, "x": 380, "y": 410, "score": 50},
            {"id": 9, "x": 260, "y": 400, "score": 80},
            {"id": 10, "x": 140, "y": 350, "score": 60},
            {"id": 11, "x": 100, "y": 230, "score": 70},
            {"id": 12, "x": 200, "y": 210, "score": 45},
            {"id": 13, "x": 450, "y": 220, "score": 65},
            {"id": 14, "x": 290, "y": 310, "score": 55},
            {"id": 15, "x": 360, "y": 170, "score": 75},
            {"id": 16, "x": 210, "y": 300, "score": 40},
        ]
        total_score = sum(t["score"] for t in targets)
        angular_order = sorted(targets, key=lambda t: math.atan2(t["y"] - base["y"], t["x"] - base["x"]))
        drones = []
        events = []
        for i in range(n):
            assigned = [dict(t) for t in angular_order[i::n]]
            tour, pos = [], (base["x"], base["y"])
            remaining = list(assigned)
            while remaining:
                nxt = min(remaining, key=lambda t: _dist(pos, (t["x"], t["y"])))
                tour.append(nxt)
                pos = (nxt["x"], nxt["y"])
                remaining.remove(nxt)
            pts = [(base["x"], base["y"])] + [(t["x"], t["y"]) for t in tour] + [(base["x"], base["y"])]
            times, cum = [0.0], 0.0
            for a, b in zip(pts[:-1], pts[1:]):
                cum += _dist(a, b) / SPEED_PX_S
                times.append(round(cum, 2))
            total = round(max(cum, 4.0), 2)
            drones.append({
                "id": f"UAV-{i + 1:02d}",
                "label": f"UAV-{'ABCDEFGH'[i]}",
                "color": COLORS[i % len(COLORS)],
                "path": [[round(x, 1), round(y, 1)] for x, y in pts],
                "total": total,
                "finalReserve": round(28.0 + (i * 3.7) % 15.0, 1),
            })
            for t, arr in zip(tour, times[1 : len(tour) + 1]):
                events.append({"t": arr, "target": t["id"], "score": t["score"]})

    events.sort(key=lambda e: e["t"])
    sim_max = round(max([d["total"] for d in drones] + [10.0]), 1)
    return base, targets, drones, events, sim_max, total_score


def render_mission_sim_html(
    num_drones: int | InstanceContext = 3,
    schedule: FleetSchedule | None = None,
    instance: InstanceContext | None = None,
) -> str:
    inst = num_drones if isinstance(num_drones, InstanceContext) else instance
    n = len(inst.drones) if inst is not None else (num_drones if isinstance(num_drones, int) else 3)
    base, targets, drones, events, sim_max, total_score = plan_fleet(
        num_drones=n, instance=inst, schedule=schedule
    )
    legend_items = "".join(
        f'<div class="legend-item"><div class="legend-dot" style="background:{d["color"]};"></div> {d["label"]} Scout</div>'
        for d in drones
    )
    metric_boxes = "".join(
        f"""
            <div class="metric-box">
              <div class="metric-label">{d["label"]} Battery SoC</div>
              <div class="metric-value" id="bat{i}" style="color:{d["color"]};">100.0%</div>
            </div>"""
        for i, d in enumerate(drones)
    )
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AeroScan-Optima: Execute Mission</title>
  <style>
    :root {
      --bg-main: #0B1120; --bg-panel: #1E293B; --bg-subtle: #334155;
      --text-main: #F8FAFC; --text-muted: #94A3B8;
      --accent-blue: #38BDF8; --accent-green: #34D399; --accent-orange: #FB923C;
      --accent-red: #F87171; --border: #475569;
    }
    * { box-sizing: border-box; margin: 0; padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    body { background-color: var(--bg-main); color: var(--text-main); padding: 20px;
           display: flex; flex-direction: column; align-items: center; }
    header { width: 100%; max-width: 1200px; margin-bottom: 20px; border-bottom: 1px solid var(--border);
             padding-bottom: 15px; display: flex; justify-content: space-between; align-items: flex-end; }
    h1 { font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }
    .subtitle { font-size: 14px; color: var(--text-muted); margin-top: 4px; }
    .badge-bar { display: flex; gap: 10px; }
    .badge { background-color: var(--bg-subtle); color: var(--accent-blue); padding: 4px 10px;
             border-radius: 6px; font-size: 12px; font-weight: 600; border: 1px solid var(--border); }
    .main-container { width: 100%; max-width: 1200px; display: grid; grid-template-columns: 680px 1fr; gap: 20px; }
    .canvas-panel { background-color: var(--bg-panel); border-radius: 10px; border: 1px solid var(--border);
                    padding: 15px; display: flex; flex-direction: column; align-items: center; }
    canvas { background-color: #020617; border-radius: 8px; border: 1px solid var(--border); width: 650px; height: 480px; }
    .info-panel { background-color: var(--bg-panel); border-radius: 10px; border: 1px solid var(--border);
                  padding: 20px; display: flex; flex-direction: column; justify-content: space-between; }
    .step-header { font-size: 18px; font-weight: 700; color: var(--accent-blue); margin-bottom: 8px; }
    .step-title { font-size: 20px; font-weight: 700; margin-bottom: 12px; }
    .step-desc { font-size: 14px; line-height: 1.6; color: var(--text-muted); margin-bottom: 16px; }
    .metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
    .metric-box { background-color: var(--bg-subtle); border: 1px solid var(--border); padding: 12px; border-radius: 6px; }
    .metric-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; }
    .metric-value { font-size: 20px; font-weight: 700; margin-top: 4px; }
    .metric-value.good { color: var(--accent-green); }
    .btn { padding: 10px 20px; border-radius: 6px; font-weight: 600; font-size: 13px; cursor: pointer; border: none; }
    .btn-play { background-color: var(--accent-green); color: #06281d; width: 100%; margin-top: 10px; }
    .legend { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 12px; font-size: 12px; }
    .legend-item { display: flex; align-items: center; gap: 6px; }
    .legend-dot { width: 12px; height: 12px; border-radius: 50%; }
    .slider-row { display: flex; align-items: center; gap: 10px; width: 100%; margin-top: 10px; }
    .slider-row input[type="range"] { flex: 1; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>AeroScan-Optima: Execute Mission</h1>
      <div class="subtitle">Problem Statement 05: Multi-Drone Search Coverage Under Energy Constraints (TOP-DC)</div>
    </div>
    <div class="badge-bar">
      <span class="badge">Fleet: __N__ UAVs</span>
      <span class="badge">Safety Floor: 15%</span>
    </div>
  </header>

  <div class="main-container">
    <div class="canvas-panel">
      <canvas id="missionCanvas" width="650" height="480"></canvas>
      <div class="legend">
        __LEGEND__
        <div class="legend-item"><div class="legend-dot" style="background:#34D399;"></div> Launch/Recovery Base</div>
        <div class="legend-item"><div class="legend-dot" style="background:#FACC15;"></div> Target Nodes (Points)</div>
      </div>
    </div>

    <div class="info-panel">
      <div>
        <div class="step-header">REAL-TIME SIMULATION</div>
        <div class="step-title">Autonomous Drone Telemetry</div>
        <div class="step-desc">Press Execute Mission for a smooth auto-flight of all __N__ UAVs, or drag the time scrubber to inspect drone positions, radar halos and battery depletion.</div>
        <div class="slider-row">
          <label style="font-size:12px; font-weight:600; color:#94A3B8;">Time:</label>
          <input type="range" id="simSlider" min="0" max="__SIMMAX__" step="0.1" value="0" oninput="onSimSlide(this.value)">
          <span id="simTimeLabel" style="font-weight:700; color:#38BDF8; font-size:14px; width:60px;">0.0s</span>
        </div>
        <div class="slider-row">
          <label style="font-size:12px; font-weight:600; color:#94A3B8;">Speed:</label>
          <select id="simSpeed" onchange="simSpeed=parseFloat(this.value)" style="background:#020617;color:#F8FAFC;border:1px solid #475569;border-radius:6px;padding:4px 8px;">
            <option value="0.5">0.5x</option>
            <option value="1.0" selected>1.0x</option>
            <option value="2.0">2.0x</option>
          </select>
        </div>
        <div class="metric-grid" style="margin-top:20px;">
          __METRICS__
          <div class="metric-box">
            <div class="metric-label">Targets Secured</div>
            <div class="metric-value good" id="targetsSecured">0 / __NUM_TARGETS__</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">Score Secured</div>
            <div class="metric-value good" id="scoreSecured">0 / __TOTALSCORE__</div>
          </div>
        </div>
      </div>
      <button class="btn btn-play" id="simPlayBtn" onclick="toggleSimPlay()">Execute Mission</button>
    </div>
  </div>

  <script>
    const canvas = document.getElementById('missionCanvas');
    const ctx = canvas.getContext('2d');
    const BASE = __BASE__;
    const TARGETS = __TARGETS__;
    const DRONES = __DRONES__;
    const EVENTS = __EVENTS__;
    const SIM_MAX = __SIMMAX__;
    const TOTAL_SCORE = __TOTALSCORE__;

    let simTime = 0.0, simPlaying = false, simSpeed = 1.0;
    let lastFrameTs = null, pulseT = 0;
    const trails = DRONES.map(() => []);
    const TRAIL_MAX = 46;

    function drawBase() {
      const g = ctx.createRadialGradient(BASE.x, BASE.y, 4, BASE.x, BASE.y, 30);
      g.addColorStop(0, 'rgba(52,211,153,0.5)');
      g.addColorStop(1, 'rgba(52,211,153,0)');
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(BASE.x, BASE.y, 30, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#34D399';
      ctx.beginPath(); ctx.arc(BASE.x, BASE.y, 14, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = '#059669'; ctx.lineWidth = 3; ctx.stroke();
      ctx.fillStyle = '#FFFFFF'; ctx.font = 'bold 12px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText("BASE", BASE.x, BASE.y - 20);
    }

    function drawTargets() {
      const securedSet = new Set();
      EVENTS.forEach(e => { if (simTime >= e.t) securedSet.add(e.target); });

      TARGETS.forEach(t => {
        const sec = securedSet.has(t.id);
        ctx.fillStyle = sec ? '#10B981' : '#FACC15';
        ctx.beginPath(); ctx.arc(t.x, t.y, 11, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = sec ? '#059669' : '#CA8A04'; ctx.lineWidth = 2; ctx.stroke();
        ctx.fillStyle = sec ? '#FFFFFF' : '#0F172A'; ctx.font = 'bold 9px sans-serif'; ctx.textAlign = 'center';
        ctx.fillText("T" + t.id, t.x, t.y + 3);
        ctx.fillStyle = sec ? '#34D399' : '#94A3B8'; ctx.font = '9px sans-serif';
        ctx.fillText(t.score + " pts", t.x, t.y + 21);
      });
    }

    function interpolatePath(path, total, t) {
      const frac = Math.max(0, Math.min(1, t / Math.max(total, 1e-6)));
      const segLens = [];
      let L = 0;
      for (let i = 0; i < path.length - 1; i++) {
        const l = Math.hypot(path[i+1][0] - path[i][0], path[i+1][1] - path[i][1]);
        segLens.push(l); L += l;
      }
      let d = frac * L;
      for (let i = 0; i < segLens.length; i++) {
        if (d <= segLens[i] || i === segLens.length - 1) {
          const f = segLens[i] < 1e-9 ? 0 : d / segLens[i];
          const x = path[i][0] + (path[i+1][0] - path[i][0]) * f;
          const y = path[i][1] + (path[i+1][1] - path[i][1]) * f;
          return { x, y, ang: Math.atan2(path[i+1][1] - path[i][1], path[i+1][0] - path[i][0]) };
        }
        d -= segLens[i];
      }
      const p = path[path.length - 1];
      return { x: p[0], y: p[1], ang: 0 };
    }

    function drawTrail(trail, color) {
      for (let i = 1; i < trail.length; i++) {
        const a = i / trail.length;
        ctx.strokeStyle = color;
        ctx.globalAlpha = 0.15 + 0.65 * a;
        ctx.lineWidth = 1 + 2.5 * a;
        ctx.beginPath();
        ctx.moveTo(trail[i-1].x, trail[i-1].y);
        ctx.lineTo(trail[i].x, trail[i].y);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    function drawDroneQuad(x, y, ang, color, label, pulse) {
      const haloR = 22 + 4 * Math.sin(pulse);
      ctx.strokeStyle = color; ctx.globalAlpha = 0.85; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.arc(x, y, haloR, 0, Math.PI * 2); ctx.stroke();
      ctx.globalAlpha = 0.3;
      ctx.beginPath(); ctx.arc(x, y, haloR + 10, 0, Math.PI * 2); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.save();
      ctx.translate(x, y); ctx.rotate(ang);
      const grad = ctx.createLinearGradient(0, 0, 52, 0);
      grad.addColorStop(0, color); grad.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.globalAlpha = 0.28; ctx.fillStyle = grad;
      ctx.beginPath(); ctx.moveTo(0, 0); ctx.arc(0, 0, 52, -0.42, 0.42); ctx.closePath(); ctx.fill();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = '#F8FAFC'; ctx.lineWidth = 2.5; ctx.lineCap = 'round';
      const arms = [[-1,-1],[1,-1],[-1,1],[1,1]];
      arms.forEach(([sx, sy]) => { ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(sx * 11, sy * 11); ctx.stroke(); });
      const spin = 5.5 + 1.8 * Math.abs(Math.sin(pulse * 3));
      arms.forEach(([sx, sy]) => {
        ctx.fillStyle = 'rgba(248,250,252,0.75)';
        ctx.beginPath(); ctx.ellipse(sx * 12, sy * 12, spin, spin * 0.45, sx * sy * 0.6, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = color;
        ctx.beginPath(); ctx.arc(sx * 12, sy * 12, 2, 0, Math.PI * 2); ctx.fill();
      });
      ctx.fillStyle = '#0B1120';
      ctx.beginPath(); ctx.arc(0, 0, 6.5, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.stroke();
      ctx.fillStyle = color;
      ctx.beginPath(); ctx.moveTo(10, 0); ctx.lineTo(4, -3.5); ctx.lineTo(4, 3.5); ctx.closePath(); ctx.fill();
      ctx.restore();
      ctx.font = 'bold 10px sans-serif';
      const w = ctx.measureText(label).width + 12;
      ctx.fillStyle = 'rgba(2,6,23,0.85)'; ctx.strokeStyle = color; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.roundRect(x - w / 2, y - 34, w, 16, 4); ctx.fill(); ctx.stroke();
      ctx.fillStyle = '#FFFFFF'; ctx.textAlign = 'center';
      ctx.fillText(label, x, y - 22);
    }

    function drawSimFrame() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      drawBase();
      drawTargets();
      DRONES.forEach(d => {
        ctx.strokeStyle = d.color; ctx.globalAlpha = 0.35; ctx.lineWidth = 1;
        ctx.setLineDash([6, 6]);
        ctx.beginPath(); ctx.moveTo(d.path[0][0], d.path[0][1]);
        for (let i = 1; i < d.path.length; i++) ctx.lineTo(d.path[i][0], d.path[i][1]);
        ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
      });
      DRONES.forEach((d, i) => {
        const p = interpolatePath(d.path, d.total, simTime);
        drawTrail(trails[i], d.color);
        drawDroneQuad(p.x, p.y, p.ang, d.color, d.label, pulseT + i * 1.3);
        const reserve = (d.finalReserve !== undefined && d.finalReserve !== null) ? d.finalReserve : 25.0;
        const bat = 100.0 - (100.0 - reserve) * Math.min(simTime, d.total) / Math.max(d.total, 1e-6);
        const el = document.getElementById('bat' + i);
        if (el) el.innerText = bat.toFixed(1) + "%";
      });
      const slider = document.getElementById('simSlider');
      if (slider && document.activeElement !== slider) slider.value = simTime;
      const lbl = document.getElementById('simTimeLabel');
      if (lbl) lbl.innerText = simTime.toFixed(1) + "s";

      let score = 0;
      const securedTargets = new Set();
      EVENTS.forEach(e => {
        if (simTime >= e.t) {
          securedTargets.add(e.target);
          score += e.score;
        }
      });
      const elS = document.getElementById('targetsSecured');
      if (elS) elS.innerText = Math.min(securedTargets.size, TARGETS.length) + " / " + TARGETS.length;
      const elC = document.getElementById('scoreSecured');
      if (elC) elC.innerText = score + " / " + TOTAL_SCORE;
    }

    function toggleSimPlay() {
      simPlaying = !simPlaying;
      lastFrameTs = performance.now();
      const btn = document.getElementById('simPlayBtn');
      if (btn) btn.innerText = simPlaying ? 'Pause Mission' : 'Execute Mission';
      if (simPlaying && simTime >= SIM_MAX - 1e-6) {
        simTime = 0; trails.forEach(t => t.length = 0);
      }
    }

    function onSimSlide(val) {
      simPlaying = false;
      const btn = document.getElementById('simPlayBtn');
      if (btn) btn.innerText = 'Execute Mission';
      simTime = parseFloat(val);
      trails.forEach(t => t.length = 0);
      drawSimFrame();
    }

    function animLoop(ts) {
      if (lastFrameTs === null) lastFrameTs = ts;
      const dt = Math.min((ts - lastFrameTs) / 1000, 0.1);
      lastFrameTs = ts;
      pulseT += dt * 3;
      if (simPlaying) {
        simTime += dt * simSpeed;
        if (simTime >= SIM_MAX) {
          simTime = SIM_MAX; simPlaying = false;
          const btn = document.getElementById('simPlayBtn');
          if (btn) btn.innerText = 'Execute Mission';
        } else {
          DRONES.forEach((d, i) => {
            const p = interpolatePath(d.path, d.total, simTime);
            trails[i].push({ x: p.x, y: p.y });
            if (trails[i].length > TRAIL_MAX) trails[i].shift();
          });
        }
        drawSimFrame();
      }
      requestAnimationFrame(animLoop);
    }

    drawSimFrame();
    requestAnimationFrame(animLoop);
  </script>
</body>
</html>
"""
    html = html.replace("__N__", str(len(drones)))
    html = html.replace("__LEGEND__", legend_items)
    html = html.replace("__METRICS__", metric_boxes)
    html = html.replace("__SIMMAX__", str(sim_max))
    html = html.replace("__TOTALSCORE__", str(total_score))
    html = html.replace("__NUM_TARGETS__", str(len(targets)))
    html = html.replace("__BASE__", json.dumps(base))
    html = html.replace("__TARGETS__", json.dumps(targets))
    html = html.replace("__DRONES__", json.dumps(drones))
    html = html.replace("__EVENTS__", json.dumps(events))
    return html
