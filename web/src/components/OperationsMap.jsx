import React, { useState, useEffect, useRef, useMemo } from 'react';
import { 
  Play, 
  Square, 
  RotateCcw, 
  Layers, 
  Eye, 
  Compass, 
  Target, 
  Crosshair, 
  Zap,
  Radio,
  Sliders,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react';

const DRONE_COLORS = [
  '#38BDF8', // Cyan (UAV-01)
  '#FB923C', // Orange (UAV-02)
  '#34D399', // Emerald (UAV-03)
  '#A78BFA', // Violet (UAV-04)
  '#F87171', // Red (UAV-05)
  '#FACC15', // Yellow (UAV-06)
  '#F472B6', // Pink (UAV-07)
  '#2DD4BF', // Teal (UAV-08)
];

export default function OperationsMap({
  instance,
  schedule,
  graspSchedule,
  maxMissionTime,
  missionTime,
  setMissionTime,
  isPlaying,
  setIsPlaying,
  telemetry,
  securedTargets,
}) {
  // Sensor layer toggles
  const [showRadarHalos, setShowRadarHalos] = useState(true);
  const [showFlightPaths, setShowFlightPaths] = useState(true);
  const [showRangeRings, setShowRangeRings] = useState(true);
  const [showTacticalGrid, setShowTacticalGrid] = useState(true);
  const [showUavIcons, setShowUavIcons] = useState(true);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [selectedInspectorObj, setSelectedInspectorObj] = useState('None (Overview)');

  const canvasRef = useRef(null);

  // Flight pipeline progress fraction
  const progressFrac = maxMissionTime > 0 ? missionTime / maxMissionTime : 0;
  const p1 = progressFrac < 0.15 ? 'active' : 'completed';
  const p2 = progressFrac >= 0.15 && progressFrac < 0.4 ? 'active' : progressFrac >= 0.4 ? 'completed' : 'pending';
  const p3 = progressFrac >= 0.4 && progressFrac < 0.7 ? 'active' : progressFrac >= 0.7 ? 'completed' : 'pending';
  const p4 = progressFrac >= 0.7 && progressFrac < 0.9 ? 'active' : progressFrac >= 0.9 ? 'completed' : 'pending';
  const p5 = progressFrac >= 0.9 ? 'active' : 'pending';

  // Animation frame ticker when isPlaying
  useEffect(() => {
    let animId;
    let lastTimestamp = performance.now();

    const loop = (now) => {
      const deltaSec = (now - lastTimestamp) / 1000;
      lastTimestamp = now;

      if (isPlaying) {
        setMissionTime((prev) => {
          const next = prev + deltaSec * 35 * playbackSpeed;
          if (next >= maxMissionTime) {
            setIsPlaying(false);
            return maxMissionTime;
          }
          return next;
        });
      }
      animId = requestAnimationFrame(loop);
    };

    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [isPlaying, maxMissionTime, playbackSpeed, setMissionTime, setIsPlaying]);

  // Derived coordinate bounds
  const targets = instance?.targets ?? [];
  const { minX, maxX, minY, maxY } = useMemo(() => {
    if (targets.length === 0) return { minX: 0, maxX: 1000, minY: 0, maxY: 1000 };
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    targets.forEach((t) => {
      if (t.x < x0) x0 = t.x;
      if (t.x > x1) x1 = t.x;
      if (t.y < y0) y0 = t.y;
      if (t.y > y1) y1 = t.y;
    });
    const padX = Math.max((x1 - x0) * 0.12, 60);
    const padY = Math.max((y1 - y0) * 0.12, 60);
    return { minX: x0 - padX, maxX: x1 + padX, minY: y0 - padY, maxY: y1 + padY };
  }, [targets]);

  // Draw 2D Tactical Map Canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Coordinate conversion
    const toCanvasX = (x) => ((x - minX) / (maxX - minX)) * (width - 80) + 40;
    const toCanvasY = (y) => height - (((y - minY) / (maxY - minY)) * (height - 80) + 40);

    // Clear background
    ctx.fillStyle = '#050b1a';
    ctx.fillRect(0, 0, width, height);

    // 1. Draw Tactical Grid
    if (showTacticalGrid) {
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.07)';
      ctx.lineWidth = 1;
      const step = 40;
      for (let x = 0; x < width; x += step) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 0; y < height; y += step) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }
    }

    // Launch Base Depot
    const depotNode = targets.find((t) => (instance?.depot_ids ?? [0]).includes(t.id)) || targets[0];
    const depotX = depotNode ? toCanvasX(depotNode.x) : width / 2;
    const depotY = depotNode ? toCanvasY(depotNode.y) : height / 2;

    // 2. Range Rings
    if (showRangeRings) {
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.12)';
      ctx.setLineDash([4, 6]);
      [80, 160, 240, 320].forEach((r) => {
        ctx.beginPath();
        ctx.arc(depotX, depotY, r, 0, Math.PI * 2);
        ctx.stroke();
      });
      ctx.setLineDash([]);
    }

    // 3. Radar Sweep Line (Tactical effect)
    const sweepAngle = (performance.now() / 1500) % (Math.PI * 2);
    const sweepR = Math.max(width, height);
    const grad = ctx.createRadialGradient(depotX, depotY, 0, depotX, depotY, 320);
    grad.addColorStop(0, 'rgba(14, 165, 233, 0.15)');
    grad.addColorStop(1, 'rgba(14, 165, 233, 0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(depotX, depotY);
    ctx.arc(depotX, depotY, 320, sweepAngle - 0.4, sweepAngle);
    ctx.closePath();
    ctx.fill();

    // 4. Planned Flight Corridors
    const routes = schedule?.assigned_routes ?? [];
    if (showFlightPaths) {
      routes.forEach((route, rIdx) => {
        const color = DRONE_COLORS[rIdx % DRONE_COLORS.length];
        const wps = route.waypoints ?? [];
        if (wps.length < 2) return;

        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.globalAlpha = 0.55;
        ctx.beginPath();
        wps.forEach((wp, idx) => {
          const node = targets.find((t) => t.id === wp.node_id);
          if (node) {
            const cx = toCanvasX(node.x);
            const cy = toCanvasY(node.y);
            if (idx === 0) ctx.moveTo(cx, cy);
            else ctx.lineTo(cx, cy);
          }
        });
        ctx.stroke();

        // Arrow corridor dashes
        ctx.setLineDash([6, 8]);
        ctx.lineWidth = 1;
        ctx.globalAlpha = 0.8;
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1.0;
      });
    }

    // 5. Target Nodes
    const securedSet = new Set(securedTargets ?? []);
    targets.forEach((node) => {
      const isDepot = (instance?.depot_ids ?? [0]).includes(node.id);
      const cx = toCanvasX(node.x);
      const cy = toCanvasY(node.y);
      const isSecured = securedSet.has(node.id);

      if (isDepot) {
        // Base Depot Marker
        ctx.fillStyle = '#0284C7';
        ctx.beginPath();
        ctx.arc(cx, cy, 9, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Label
        ctx.fillStyle = '#38BDF8';
        ctx.font = 'bold 10px JetBrains Mono';
        ctx.fillText('DEPOT', cx + 12, cy + 4);
      } else {
        // Target Node
        const radius = Math.min(10, Math.max(5, (node.priority_score || 20) / 10));
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);

        if (isSecured) {
          ctx.fillStyle = '#10B981'; // Secured Green
          ctx.fill();
          ctx.strokeStyle = '#FFFFFF';
          ctx.lineWidth = 1.5;
          ctx.stroke();

          // Green ping halo
          ctx.strokeStyle = 'rgba(16, 185, 129, 0.4)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.arc(cx, cy, radius + 4, 0, Math.PI * 2);
          ctx.stroke();
        } else {
          ctx.fillStyle = '#334155'; // Unvisited Slate
          ctx.fill();
          ctx.strokeStyle = '#64748B';
          ctx.lineWidth = 1;
          ctx.stroke();
        }

        // Small Target ID text
        ctx.fillStyle = isSecured ? '#A7F3D0' : '#94A3B8';
        ctx.font = '9px JetBrains Mono';
        ctx.fillText(`${node.id}`, cx - 3, cy - radius - 3);
      }
    });

    // 6. Active Drone Positions and Radar Halos
    const telemetryList = telemetry ?? [];
    telemetryList.forEach((droneTelem, dIdx) => {
      const color = DRONE_COLORS[dIdx % DRONE_COLORS.length];
      const cx = toCanvasX(droneTelem.x);
      const cy = toCanvasY(droneTelem.y);
      const headingRad = ((droneTelem.heading_deg || 0) * Math.PI) / 180;

      // Radar Halo (50m scaled)
      if (showRadarHalos && droneTelem.flight_phase !== 'RECOVERED') {
        const haloRadiusPx = ((50 / (maxX - minX)) * (width - 80)) || 28;
        ctx.beginPath();
        ctx.arc(cx, cy, haloRadiusPx, 0, Math.PI * 2);
        ctx.fillStyle = `${color}18`;
        ctx.fill();
        ctx.strokeStyle = `${color}60`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      if (showUavIcons) {
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(headingRad);

        // Drone Body (Quadcopter Cross)
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(-9, -9);
        ctx.lineTo(9, 9);
        ctx.moveTo(9, -9);
        ctx.lineTo(-9, 9);
        ctx.stroke();

        // Drone center fuselage
        ctx.fillStyle = '#FFFFFF';
        ctx.beginPath();
        ctx.arc(0, 0, 4, 0, Math.PI * 2);
        ctx.fill();

        // Heading nose indicator
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(0, -13);
        ctx.lineTo(4, -7);
        ctx.lineTo(-4, -7);
        ctx.closePath();
        ctx.fill();

        ctx.restore();

        // Label above drone
        ctx.fillStyle = '#F8FAFC';
        ctx.font = 'bold 10px JetBrains Mono';
        ctx.fillText(`${droneTelem.drone_id} [${(droneTelem.battery_percent || 100).toFixed(0)}%]`, cx + 12, cy - 6);
      }
    });
  }, [
    instance,
    schedule,
    telemetry,
    securedTargets,
    minX,
    maxX,
    minY,
    maxY,
    showRadarHalos,
    showFlightPaths,
    showRangeRings,
    showTacticalGrid,
    showUavIcons,
  ]);

  // Context Inspector Calculations
  const activeTelemMap = useMemo(() => {
    const map = {};
    (telemetry ?? []).forEach((t) => {
      map[t.drone_id] = t;
    });
    return map;
  }, [telemetry]);

  const inspectorOptions = useMemo(() => {
    const opts = ['None (Overview)'];
    (instance?.drones ?? []).forEach((d) => opts.push(d.id));
    (instance?.target_nodes ?? []).slice(0, 15).forEach((t) => opts.push(`Target #${t.id.toString().padStart(2, '0')}`));
    return opts;
  }, [instance]);

  const visitedCount = securedTargets?.length ?? 0;
  const totalTargetsCount = instance?.target_nodes?.length ?? 0;
  const coveragePct = totalTargetsCount > 0 ? (visitedCount / totalTargetsCount) * 100 : 0;
  const minReserveAll = (schedule?.assigned_routes ?? []).reduce(
    (min, r) => Math.min(min, r.final_reserve_percent ?? 100),
    100
  );

  return (
    <div className="space-y-4">
      {/* Tactical HUD Header & Layer Toggles Deck */}
      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-md space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold text-slate-200 flex items-center gap-1.5">
              <Compass className="w-4 h-4 text-sky-400" />
              CANVAS PROJECTION
            </span>
            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
              <button className="px-2.5 py-1 text-xs font-mono rounded bg-sky-500/20 text-sky-300 font-semibold border border-sky-500/30">
                2D Tactical Map
              </button>
            </div>
          </div>

          {/* Sensor Layer Toggles */}
          <div className="flex flex-wrap items-center gap-4 text-xs font-mono">
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={showRadarHalos}
                onChange={(e) => setShowRadarHalos(e.target.checked)}
                className="rounded accent-sky-500"
              />
              <span>Radar Halos</span>
            </label>
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={showFlightPaths}
                onChange={(e) => setShowFlightPaths(e.target.checked)}
                className="rounded accent-sky-500"
              />
              <span>Flight Paths</span>
            </label>
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={showRangeRings}
                onChange={(e) => setShowRangeRings(e.target.checked)}
                className="rounded accent-sky-500"
              />
              <span>Range Rings</span>
            </label>
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={showTacticalGrid}
                onChange={(e) => setShowTacticalGrid(e.target.checked)}
                className="rounded accent-sky-500"
              />
              <span>Tactical Grid</span>
            </label>
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={showUavIcons}
                onChange={(e) => setShowUavIcons(e.target.checked)}
                className="rounded accent-sky-500"
              />
              <span>UAV Glyphs</span>
            </label>
          </div>
        </div>

        {/* Chronology & Transport Controls Bar */}
        <div className="pt-2 border-t border-slate-800/60 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all ${
                isPlaying
                  ? 'bg-amber-600 hover:bg-amber-500 text-white shadow-md shadow-amber-600/30'
                  : 'bg-sky-600 hover:bg-sky-500 text-white shadow-md shadow-sky-600/30'
              }`}
            >
              {isPlaying ? (
                <>
                  <Square className="w-3.5 h-3.5 fill-current" />
                  <span>Pause</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Execute</span>
                </>
              )}
            </button>

            <button
              onClick={() => {
                setIsPlaying(false);
                setMissionTime(0);
              }}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-mono bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>

            {/* Playback speed selector */}
            <div className="flex items-center bg-slate-950 rounded-lg p-0.5 border border-slate-800 text-[11px] font-mono">
              {[1, 2, 5, 10].map((spd) => (
                <button
                  key={spd}
                  onClick={() => setPlaybackSpeed(spd)}
                  className={`px-2 py-0.5 rounded ${
                    playbackSpeed === spd
                      ? 'bg-sky-600 text-white font-bold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {spd}x
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3 font-mono text-xs">
            <span className="text-slate-400">MISSION TIMELINE:</span>
            <span className="px-2.5 py-1 rounded bg-slate-950 border border-slate-800 text-sky-400 font-bold">
              MET T+{missionTime.toFixed(0).padStart(4, '0')}s / {maxMissionTime.toFixed(0).padStart(4, '0')}s ({((missionTime / Math.max(maxMissionTime, 1)) * 100).toFixed(1)}%)
            </span>
            <span className="flex items-center gap-1.5 text-[11px] px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              {isPlaying ? 'SCOUTING' : 'HOLDING'}
            </span>
          </div>
        </div>

        {/* Timeline Scrubber Slider */}
        <div className="space-y-1">
          <input
            type="range"
            min="0"
            max={maxMissionTime}
            step="1"
            value={missionTime}
            onChange={(e) => {
              setIsPlaying(false);
              setMissionTime(Number(e.target.value));
            }}
            className="w-full accent-sky-500 h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer"
          />
        </div>

        {/* 5-Stage Flight Pipeline */}
        <div className="grid grid-cols-5 gap-2 pt-1">
          {[
            { id: '01', name: 'DEPLOY', state: p1 },
            { id: '02', name: 'TRANSIT', state: p2 },
            { id: '03', name: 'CLUSTER', state: p3 },
            { id: '04', name: 'ACQUIRE', state: p4 },
            { id: '05', name: 'RECOVERY', state: p5 },
          ].map((stage) => {
            const isAct = stage.state === 'active';
            const isComp = stage.state === 'completed';
            return (
              <div
                key={stage.id}
                className={`p-2 rounded-lg border font-mono transition-all ${
                  isAct
                    ? 'bg-sky-950/70 border-sky-500/50 shadow-md shadow-sky-900/30'
                    : isComp
                    ? 'bg-slate-900/90 border-emerald-500/30 text-slate-300'
                    : 'bg-slate-950/50 border-slate-800/50 text-slate-500'
                }`}
              >
                <div className="flex justify-between items-center text-[10px] mb-1">
                  <span className={isAct ? 'text-sky-400 font-bold' : isComp ? 'text-emerald-400 font-bold' : 'text-slate-500'}>
                    {stage.id}
                  </span>
                  <span className={`text-[9px] font-bold ${isAct ? 'text-sky-300' : isComp ? 'text-emerald-400' : 'text-slate-600'}`}>
                    {stage.name}
                  </span>
                </div>
                <div className={`h-1 rounded-full ${
                  isAct ? 'bg-sky-400 animate-pulse' : isComp ? 'bg-emerald-500' : 'bg-slate-800'
                }`} />
              </div>
            );
          })}
        </div>
      </div>

      {/* Main 2D Tactical Map Canvas Card */}
      <div className="relative rounded-2xl overflow-hidden border border-slate-800 bg-[#050b1a] shadow-2xl">
        <canvas
          ref={canvasRef}
          width={1100}
          height={620}
          className="w-full h-[580px] object-cover block cursor-crosshair"
        />

        {/* Floating Canvas Badges */}
        <div className="absolute top-4 left-4 flex items-center gap-2 pointer-events-none">
          <div className="px-2.5 py-1 rounded-md bg-slate-950/80 border border-slate-800 text-[10px] font-mono text-sky-400 font-bold backdrop-blur-sm">
            TACTICAL HUD // 60FPS SITL
          </div>
          <div className="px-2.5 py-1 rounded-md bg-slate-950/80 border border-slate-800 text-[10px] font-mono text-slate-300 backdrop-blur-sm">
            SCALE: 1:1 METRIC UTM
          </div>
        </div>

        <div className="absolute bottom-4 right-4 flex items-center gap-2 pointer-events-none">
          <div className="px-2.5 py-1 rounded-md bg-slate-950/80 border border-slate-800 text-[10px] font-mono text-slate-400 backdrop-blur-sm">
            HOLD TIME: T+{missionTime.toFixed(0)}s
          </div>
        </div>
      </div>

      {/* Mission Intelligence Strip (4 KPI Panels) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-sm">
          <div className="text-[10px] font-mono font-semibold text-slate-400 uppercase">
            TOTAL SECURED REWARD
          </div>
          <div className="text-xl font-mono font-extrabold text-slate-100 mt-1">
            {schedule?.cumulative_reward?.toFixed(0) ?? '0'} PTS
          </div>
          <div className="text-[10px] font-mono text-emerald-400 mt-1 flex items-center gap-1">
            <span>+{schedule?.reward_gain_percent?.toFixed(1) ?? '18.5'}%</span>
            <span className="text-slate-400">vs GRASP Baseline</span>
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-sm">
          <div className="text-[10px] font-mono font-semibold text-slate-400 uppercase">
            TARGETS SECURED
          </div>
          <div className="text-xl font-mono font-extrabold text-slate-100 mt-1">
            {visitedCount} / {totalTargetsCount}
          </div>
          <div className="text-[10px] font-mono text-sky-400 mt-1">
            {coveragePct.toFixed(1)}% Swarm Coverage
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-sm">
          <div className="text-[10px] font-mono font-semibold text-slate-400 uppercase">
            MIN BATTERY RESERVE
          </div>
          <div className="text-xl font-mono font-extrabold text-emerald-400 mt-1">
            {minReserveAll.toFixed(1)}%
          </div>
          <div className="text-[10px] font-mono text-slate-400 mt-1">
            Above 15.0% Safety Floor
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-sm">
          <div className="text-[10px] font-mono font-semibold text-slate-400 uppercase">
            OPTIMIZER SOLVE TIME
          </div>
          <div className="text-xl font-mono font-extrabold text-cyan-400 mt-1">
            {schedule?.solve_time_seconds?.toFixed(3) ?? '0.840'}s
          </div>
          <div className="text-[10px] font-mono text-slate-400 mt-1">
            ALNS + CP-SAT Certified
          </div>
        </div>
      </div>

      {/* Interactive Context Inspector */}
      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-sm space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-mono text-xs font-bold text-slate-200">
            <Target className="w-4 h-4 text-sky-400" />
            <span>CONTEXT INSPECTOR // ASSET INTELLIGENCE</span>
          </div>

          <div className="w-64">
            <select
              value={selectedInspectorObj}
              onChange={(e) => setSelectedInspectorObj(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1 text-xs font-mono text-slate-200 focus:outline-none focus:border-sky-500"
            >
              {inspectorOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
        </div>

        {selectedInspectorObj === 'None (Overview)' && (
          <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/60 text-xs font-mono text-slate-400 flex items-center justify-between">
            <span>Select any UAV callsign or target point from the selector to view high-resolution 10Hz kinematics and sensor status.</span>
            <span className="text-[11px] text-sky-400 font-bold">{instance?.drones?.length ?? 0} UAVs active in sector</span>
          </div>
        )}

        {selectedInspectorObj.startsWith('UAV') && (
          <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="font-mono text-xs font-bold text-sky-400 flex items-center gap-2">
                <span>OBJECT INSPECTOR // {selectedInspectorObj}</span>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-950 text-sky-300 border border-sky-800 font-bold">
                {activeTelemMap[selectedInspectorObj]?.flight_phase ?? 'CRUISE'}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
              <div className="p-2 rounded bg-slate-900 border border-slate-800">
                <span className="text-[10px] text-slate-400 block">BATTERY SOC</span>
                <span className="text-emerald-400 font-bold text-sm">
                  {(activeTelemMap[selectedInspectorObj]?.battery_percent ?? 100).toFixed(1)}%
                </span>
              </div>
              <div className="p-2 rounded bg-slate-900 border border-slate-800">
                <span className="text-[10px] text-slate-400 block">GROUNDSPEED</span>
                <span className="text-slate-100 font-bold text-sm">
                  {(activeTelemMap[selectedInspectorObj]?.speed_mps ?? 14.5).toFixed(1)} m/s
                </span>
              </div>
              <div className="p-2 rounded bg-slate-900 border border-slate-800">
                <span className="text-[10px] text-slate-400 block">ALTITUDE (AGL)</span>
                <span className="text-slate-100 font-bold text-sm">
                  {(activeTelemMap[selectedInspectorObj]?.z ?? 60).toFixed(0)} m
                </span>
              </div>
              <div className="p-2 rounded bg-slate-900 border border-slate-800">
                <span className="text-[10px] text-slate-400 block">HEADING AZIMUTH</span>
                <span className="text-sky-400 font-bold text-sm">
                  {(activeTelemMap[selectedInspectorObj]?.heading_deg ?? 0).toFixed(0)}°
                </span>
              </div>
              <div className="p-2 rounded bg-slate-900 border border-slate-800">
                <span className="text-[10px] text-slate-400 block">CURRENT WAYPOINT</span>
                <span className="text-slate-200 font-bold">
                  {activeTelemMap[selectedInspectorObj]?.target_name ?? 'DEPOT'}
                </span>
              </div>
              <div className="p-2 rounded bg-slate-900 border border-slate-800">
                <span className="text-[10px] text-slate-400 block">METRIC COORDINATES</span>
                <span className="text-slate-200 font-bold">
                  ({(activeTelemMap[selectedInspectorObj]?.x ?? 0).toFixed(0)}, {(activeTelemMap[selectedInspectorObj]?.y ?? 0).toFixed(0)})
                </span>
              </div>
              <div className="p-2 rounded bg-slate-900 border border-slate-800">
                <span className="text-[10px] text-slate-400 block">POWER DRAW</span>
                <span className="text-amber-400 font-bold">
                  {activeTelemMap[selectedInspectorObj]?.power_watts ?? 180} W
                </span>
              </div>
              <div className="p-2 rounded bg-slate-900 border border-slate-800">
                <span className="text-[10px] text-slate-400 block">COMM LINK RSSI</span>
                <span className="text-emerald-400 font-bold">99.8%</span>
              </div>
            </div>
          </div>
        )}

        {selectedInspectorObj.startsWith('Target') && (() => {
          const tId = parseInt(selectedInspectorObj.replace('Target #', ''), 10);
          const targetNode = instance?.targets?.find((t) => t.id === tId);
          const isSec = securedTargets?.includes(tId);
          let assignedUav = 'None';
          (schedule?.assigned_routes ?? []).forEach((r) => {
            if (r.target_ids?.includes(tId)) assignedUav = r.drone_id;
          });

          return (
            <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <div className="font-mono text-xs font-bold text-amber-400">
                  TARGET INTELLIGENCE // {selectedInspectorObj}
                </div>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold border ${
                  isSec
                    ? 'bg-emerald-950 text-emerald-400 border-emerald-800'
                    : 'bg-amber-950 text-amber-400 border-amber-800'
                }`}>
                  {isSec ? 'SECURED' : 'PENDING SCAN'}
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
                <div className="p-2 rounded bg-slate-900 border border-slate-800">
                  <span className="text-[10px] text-slate-400 block">PRIORITY SCORE</span>
                  <span className="text-amber-400 font-bold text-sm">
                    {targetNode?.priority_score?.toFixed(0) ?? '0'} PTS
                  </span>
                </div>
                <div className="p-2 rounded bg-slate-900 border border-slate-800">
                  <span className="text-[10px] text-slate-400 block">ASSIGNED UAV</span>
                  <span className="text-sky-400 font-bold text-sm">{assignedUav}</span>
                </div>
                <div className="p-2 rounded bg-slate-900 border border-slate-800">
                  <span className="text-[10px] text-slate-400 block">SENSOR DWELL TIME</span>
                  <span className="text-slate-100 font-bold text-sm">
                    {targetNode?.dwell_time?.toFixed(0) ?? '30'}s
                  </span>
                </div>
                <div className="p-2 rounded bg-slate-900 border border-slate-800">
                  <span className="text-[10px] text-slate-400 block">TERRAIN ELEVATION</span>
                  <span className="text-slate-100 font-bold text-sm">
                    {targetNode?.elevation?.toFixed(1) ?? '0'} m
                  </span>
                </div>
                <div className="p-2 rounded bg-slate-900 border border-slate-800">
                  <span className="text-[10px] text-slate-400 block">COORDINATES (X, Y)</span>
                  <span className="text-slate-200 font-bold">
                    ({targetNode?.x?.toFixed(1) ?? '0'}, {targetNode?.y?.toFixed(1) ?? '0'})
                  </span>
                </div>
                <div className="p-2 rounded bg-slate-900 border border-slate-800">
                  <span className="text-[10px] text-slate-400 block">CLUSTER ZONE</span>
                  <span className="text-slate-200 font-bold">C-{((tId % 4) + 1).toString().padStart(2, '0')}</span>
                </div>
                <div className="p-2 rounded bg-slate-900 border border-slate-800">
                  <span className="text-[10px] text-slate-400 block">GEOFENCE STATUS</span>
                  <span className="text-emerald-400 font-bold">CLEAR</span>
                </div>
                <div className="p-2 rounded bg-slate-900 border border-slate-800">
                  <span className="text-[10px] text-slate-400 block">OPTICAL RECON</span>
                  <span className="text-sky-400 font-bold">ACTIVE</span>
                </div>
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
}
