"""Dynamic Execute-Mission flight simulator HTML generator.

Renders N quadcopter drones (N = fleet size) scouting the target field on a
dark canvas with smooth 60fps motion, trails, radar halos and live telemetry.
"""

from __future__ import annotations

import json
import math

BASE = {"x": 90, "y": 240, "label": "Base D (0,0)"}
TARGETS = [
    {"id": 1, "x": 200, "y": 160, "score": 50},
    {"id": 2, "x": 260, "y": 110, "score": 45},
    {"id": 3, "x": 190, "y": 350, "score": 40},
    {"id": 4, "x": 450, "y": 220, "score": 60},
    {"id": 5, "x": 570, "y": 260, "score": 70},
]
COLORS = ["#38BDF8", "#FB923C", "#34D399", "#A78BFA", "#F87171", "#FACC15", "#F472B6", "#2DD4BF"]
SPEED_PX_S = 26.0


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def plan_fleet(num_drones: int) -> tuple[list[dict], list[dict], float]:
    """Round-robin target assignment with greedy nearest-neighbor ordering.

    Returns (drones, events, sim_max) where each drone has a waypoint path,
    cumulative arrival times and total flight time.
    """
    n = max(1, min(int(num_drones), 8))
    order = sorted(TARGETS, key=lambda t: (t["x"], t["y"]))
    drones = []
    events: list[dict] = []
    for i in range(n):
        assigned = [dict(t) for t in order[i::n]]
        # Greedy nearest-neighbor from base for a natural-looking tour.
        tour, pos = [], (BASE["x"], BASE["y"])
        remaining = list(assigned)
        while remaining:
            nxt = min(remaining, key=lambda t: _dist(pos, (t["x"], t["y"])))
            tour.append(nxt)
            pos = (nxt["x"], nxt["y"])
            remaining.remove(nxt)
        pts = [(BASE["x"], BASE["y"])] + [(t["x"], t["y"]) for t in tour] + [(BASE["x"], BASE["y"])]
        times, cum = [0.0], 0.0
        for a, b in zip(pts[:-1], pts[1:]):
            cum += _dist(a, b) / SPEED_PX_S
            times.append(round(cum, 2))
        total = round(max(cum, 4.0), 2)
        drones.append(
            {
                "id": f"UAV-{i + 1:02d}",
                "label": f"UAV-{'ABCDEFGH'[i]}",
                "color": COLORS[i % len(COLORS)],
                "path": [[round(x, 1), round(y, 1)] for x, y in pts],
                "total": total,
            }
        )
        for t, arr in zip(tour, times[1 : len(tour) + 1]):
            events.append({"t": arr, "target": t["id"], "score": t["score"]})
    events.sort(key=lambda e: e["t"])
    sim_max = round(max([d["total"] for d in drones] + [10.0]), 1)
    return drones, events, sim_max


def render_mission_sim_html(num_drones: int) -> str:
    drones, events, sim_max = plan_fleet(num_drones)
    total_score = sum(t["score"] for t in TARGETS)
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
      <span class="badge">Max Battery: 40 units</span>
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
            <div class="metric-value good" id="targetsSecured">0 / 5</div>
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
      TARGETS.forEach(t => {
        ctx.fillStyle = '#FACC15';
        ctx.beginPath(); ctx.arc(t.x, t.y, 16, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#CA8A04'; ctx.lineWidth = 2; ctx.stroke();
        ctx.fillStyle = '#0F172A'; ctx.font = 'bold 12px sans-serif'; ctx.textAlign = 'center';
        ctx.fillText("T" + t.id, t.x, t.y + 4);
        ctx.fillStyle = '#94A3B8'; ctx.font = '11px sans-serif';
        ctx.fillText(t.score + " pts", t.x, t.y + 28);
      });
    }

    function interpolatePath(path, total, t) {
      const frac = Math.max(0, Math.min(1, t / Math.max(total, 1e-6)));
      // arc-length param
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
        const bat = Math.max(15.0, 100 - 85 * Math.min(simTime, d.total) / Math.max(d.total, 1e-6));
        const el = document.getElementById('bat' + i);
        if (el) el.innerText = bat.toFixed(1) + "%";
      });
      const slider = document.getElementById('simSlider');
      if (slider && document.activeElement !== slider) slider.value = simTime;
      const lbl = document.getElementById('simTimeLabel');
      if (lbl) lbl.innerText = simTime.toFixed(1) + "s";
      let secured = 0, score = 0;
      EVENTS.forEach(e => { if (simTime >= e.t) { secured++; score += e.score; } });
      const elS = document.getElementById('targetsSecured');
      if (elS) elS.innerText = Math.min(secured, TARGETS.length) + " / " + TARGETS.length;
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
    html = html.replace("__BASE__", json.dumps(BASE))
    html = html.replace("__TARGETS__", json.dumps(TARGETS))
    html = html.replace("__DRONES__", json.dumps(drones))
    html = html.replace("__EVENTS__", json.dumps(events))
    return html
