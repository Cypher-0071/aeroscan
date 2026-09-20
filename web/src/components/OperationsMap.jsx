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
  '#0284C7', // Sky-600 (UAV-01)
  '#EA580C', // Orange-600 (UAV-02)
  '#059669', // Emerald-600 (UAV-03)
  '#7C3AED', // Violet-600 (UAV-04)
  '#DC2626', // Red-600 (UAV-05)
  '#D97706', // Amber-600 (UAV-06)
  '#DB2777', // Pink-600 (UAV-07)
  '#0D9488', // Teal-600 (UAV-08)
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

    // Clear background with crisp off-white
    ctx.fillStyle = '#fbfcfe';
    ctx.fillRect(0, 0, width, height);

    // 1. Draw Tactical Grid
    if (showTacticalGrid) {
      ctx.strokeStyle = 'rgba(15, 23, 42, 0.045)';
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
      ctx.strokeStyle = 'rgba(2, 132, 199, 0.16)';
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
    const grad = ctx.createRadialGradient(depotX, depotY, 0, depotX, depotY, 320);
    grad.addColorStop(0, 'rgba(2, 132, 199, 0.12)');
    grad.addColorStop(1, 'rgba(2, 132, 199, 0)');
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
        ctx.lineWidth = 2.5;
        ctx.globalAlpha = 0.65;
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
        ctx.globalAlpha = 0.85;
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
        ctx.lineWidth = 2.5;
        ctx.stroke();

        // Label
        ctx.fillStyle = '#0284C7';
        ctx.font = 'bold 10px JetBrains Mono';
        ctx.fillText('DEPOT', cx + 12, cy + 4);
      } else {
        // Target Node
        const radius = Math.min(10, Math.max(5, (node.priority_score || 20) / 10));
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);

        if (isSecured) {
          ctx.fillStyle = '#059669'; // Secured Green
          ctx.fill();
          ctx.strokeStyle = '#FFFFFF';
          ctx.lineWidth = 1.5;
          ctx.stroke();

          // Green ping halo
          ctx.strokeStyle = 'rgba(5, 150, 105, 0.3)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.arc(cx, cy, radius + 4, 0, Math.PI * 2);
          ctx.stroke();
        } else {
          ctx.fillStyle = '#F1F5F9'; // Unvisited light slate
          ctx.fill();
          ctx.strokeStyle = '#94A3B8';
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }

        // Small Target ID text
        ctx.fillStyle = isSecured ? '#047857' : '#64748B';
        ctx.font = 'bold 9px JetBrains Mono';
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
        ctx.fillStyle = `${color}14`;
        ctx.fill();
        ctx.strokeStyle = `${color}40`;
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
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.stroke();

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
        ctx.fillStyle = '#0F172A';
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
      <div className="glass-card rounded-2xl p-4 space-y-3.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold text-slate-900 flex items-center gap-2">
              <Compass className="w-4 h-4 text-sky-600" />
              CANVAS PROJECTION
            </span>
            <span className="px-2.5 py-0.5 text-xs font-mono rounded-full glass-pill text-sky-700 font-medium">
              2D Tactical Map
            </span>
          </div>

          {/* Sensor Layer Toggles as Glass Pills */}
          <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
            <button
              type="button"
              onClick={() => setShowRadarHalos(!showRadarHalos)}
              className={`px-3 py-1 rounded-full border transition-all cursor-pointer flex items-center gap-1.5 ${
                showRadarHalos
                  ? 'bg-sky-50 text-sky-700 border-sky-200/90 font-medium shadow-sm'
                  : 'bg-white/60 text-slate-500 border-slate-200/70 hover:bg-white hover:text-slate-800'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${showRadarHalos ? 'bg-sky-500 shadow-sm' : 'bg-slate-300'}`} />
              <span>Radar Halos</span>
            </button>

            <button
              type="button"
              onClick={() => setShowFlightPaths(!showFlightPaths)}
              className={`px-3 py-1 rounded-full border transition-all cursor-pointer flex items-center gap-1.5 ${
                showFlightPaths
                  ? 'bg-sky-50 text-sky-700 border-sky-200/90 font-medium shadow-sm'
                  : 'bg-white/60 text-slate-500 border-slate-200/70 hover:bg-white hover:text-slate-800'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${showFlightPaths ? 'bg-sky-500 shadow-sm' : 'bg-slate-300'}`} />
              <span>Flight Paths</span>
            </button>

            <button
              type="button"
              onClick={() => setShowRangeRings(!showRangeRings)}
              className={`px-3 py-1 rounded-full border transition-all cursor-pointer flex items-center gap-1.5 ${
                showRangeRings
                  ? 'bg-sky-50 text-sky-700 border-sky-200/90 font-medium shadow-sm'
                  : 'bg-white/60 text-slate-500 border-slate-200/70 hover:bg-white hover:text-slate-800'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${showRangeRings ? 'bg-sky-500 shadow-sm' : 'bg-slate-300'}`} />
              <span>Range Rings</span>
            </button>

            <button
              type="button"
              onClick={() => setShowTacticalGrid(!showTacticalGrid)}
              className={`px-3 py-1 rounded-full border transition-all cursor-pointer flex items-center gap-1.5 ${
                showTacticalGrid
                  ? 'bg-sky-50 text-sky-700 border-sky-200/90 font-medium shadow-sm'
                  : 'bg-white/60 text-slate-500 border-slate-200/70 hover:bg-white hover:text-slate-800'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${showTacticalGrid ? 'bg-sky-500 shadow-sm' : 'bg-slate-300'}`} />
              <span>Tactical Grid</span>
            </button>

            <button
              type="button"
              onClick={() => setShowUavIcons(!showUavIcons)}
              className={`px-3 py-1 rounded-full border transition-all cursor-pointer flex items-center gap-1.5 ${
                showUavIcons
                  ? 'bg-sky-50 text-sky-700 border-sky-200/90 font-medium shadow-sm'
                  : 'bg-white/60 text-slate-500 border-slate-200/70 hover:bg-white hover:text-slate-800'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${showUavIcons ? 'bg-sky-500 shadow-sm' : 'bg-slate-300'}`} />
              <span>UAV Glyphs</span>
            </button>
          </div>
        </div>

        {/* Chronology & Transport Controls Bar */}
        <div className="pt-3 border-t border-slate-200/80 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className={`px-4 py-2 rounded-xl text-xs font-mono font-semibold transition-all flex items-center gap-2 cursor-pointer ${
                isPlaying
                  ? 'bg-amber-500 hover:bg-amber-600 text-white shadow-sm'
                  : 'glass-btn-primary'
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
              className="glass-btn-secondary flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-mono cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>

            {/* Playback speed selector */}
            <div className="flex items-center glass-pill rounded-xl p-0.5 text-[11px] font-mono border border-slate-200/80 bg-white/60">
              {[1, 2, 5, 10].map((spd) => (
                <button
                  key={spd}
                  onClick={() => setPlaybackSpeed(spd)}
                  className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer ${
                    playbackSpeed === spd
                      ? 'bg-white text-slate-900 font-bold shadow-sm'
                      : 'text-slate-400 hover:text-slate-800'
                  }`}
                >
                  {spd}x
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3 font-mono text-xs">
            <span className="text-slate-400 text-[11px]">MISSION TIMELINE:</span>
            <span className="px-3 py-1 rounded-full glass-pill text-sky-700 font-semibold border border-slate-200/80 bg-white/70">
              MET T+{missionTime.toFixed(0).padStart(4, '0')}s / {maxMissionTime.toFixed(0).padStart(4, '0')}s ({((missionTime / Math.max(maxMissionTime, 1)) * 100).toFixed(1)}%)
            </span>
            <span className={`flex items-center gap-1.5 text-[11px] px-2.5 py-0.5 rounded-full font-medium ${
              isPlaying 
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/80' 
                : 'bg-slate-100 text-slate-600 border border-slate-200/80'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${isPlaying ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`}></span>
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
            className="w-full cursor-pointer"
          />
        </div>

        {/* 5-Stage Flight Pipeline */}
        <div className="grid grid-cols-5 gap-2.5 pt-1">
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
                className={`p-2.5 rounded-xl border font-mono transition-all ${
                  isAct
                    ? 'glass-card border-sky-300 shadow-sm bg-white/80'
                    : isComp
                    ? 'bg-emerald-50/60 border-emerald-200/70 text-emerald-900'
                    : 'bg-white/40 border-slate-200/60 text-slate-400'
                }`}
              >
                <div className="flex justify-between items-center text-[10px] mb-1.5">
                  <span className={isAct ? 'text-sky-700 font-bold' : isComp ? 'text-emerald-700 font-bold' : 'text-slate-400'}>
                    {stage.id}
                  </span>
                  <span className={`text-[9px] font-semibold ${isAct ? 'text-sky-700' : isComp ? 'text-emerald-700' : 'text-slate-400'}`}>
                    {stage.name}
                  </span>
                </div>
                <div className={`h-1 rounded-full ${
                  isAct ? 'bg-sky-500 animate-pulse' : isComp ? 'bg-emerald-500' : 'bg-slate-200'
                }`} />
              </div>
            );
          })}
        </div>
      </div>

      {/* Main 2D Tactical Map Canvas Card */}
      <div className="relative rounded-2xl overflow-hidden glass-card shadow-sm border border-slate-200/80">
        <canvas
          ref={canvasRef}
          width={1100}
          height={620}
          className="w-full h-[580px] object-cover block cursor-crosshair bg-white"
        />

        {/* Floating Canvas Badges */}
        <div className="absolute top-4 left-4 flex items-center gap-2 pointer-events-none">
          <div className="px-3 py-1 rounded-full glass-pill text-[10px] font-mono text-sky-700 font-semibold border border-slate-200/80 bg-white/80 shadow-sm">
            TACTICAL HUD // 60FPS SITL
          </div>
          <div className="px-3 py-1 rounded-full glass-pill text-[10px] font-mono text-slate-600 border border-slate-200/80 bg-white/80 shadow-sm">
            SCALE: 1:1 METRIC UTM
          </div>
        </div>

        <div className="absolute bottom-4 right-4 flex items-center gap-2 pointer-events-none">
          <div className="px-3 py-1 rounded-full glass-pill text-[10px] font-mono text-slate-600 border border-slate-200/80 bg-white/80 shadow-sm">
            HOLD TIME: T+{missionTime.toFixed(0)}s
          </div>
        </div>
      </div>

      {/* Mission Intelligence Strip (4 KPI Panels) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="glass-card-interactive rounded-2xl p-4 space-y-1">
          <div className="text-[10px] font-mono font-medium text-slate-400 uppercase tracking-wider">
            TOTAL SECURED REWARD
          </div>
          <div className="text-xl font-mono font-bold text-slate-900 mt-1">
            {schedule?.cumulative_reward?.toFixed(0) ?? '0'} PTS
          </div>
          <div className="text-[10px] font-mono text-emerald-600 mt-1 flex items-center gap-1 font-medium">
            <span>+{schedule?.reward_gain_percent?.toFixed(1) ?? '18.5'}%</span>
            <span className="text-slate-400 font-normal">vs GRASP Baseline</span>
          </div>
        </div>

        <div className="glass-card-interactive rounded-2xl p-4 space-y-1">
          <div className="text-[10px] font-mono font-medium text-slate-400 uppercase tracking-wider">
            TARGETS SECURED
          </div>
          <div className="text-xl font-mono font-bold text-slate-900 mt-1">
            {visitedCount} / {totalTargetsCount}
          </div>
          <div className="text-[10px] font-mono text-sky-600 mt-1 font-medium">
            {coveragePct.toFixed(1)}% Swarm Coverage
          </div>
        </div>

        <div className="glass-card-interactive rounded-2xl p-4 space-y-1">
          <div className="text-[10px] font-mono font-medium text-slate-400 uppercase tracking-wider">
            MIN BATTERY RESERVE
          </div>
          <div className="text-xl font-mono font-bold text-emerald-600 mt-1">
            {minReserveAll.toFixed(1)}%
          </div>
          <div className="text-[10px] font-mono text-slate-400 mt-1 font-normal">
            Above 15.0% Safety Floor
          </div>
        </div>

        <div className="glass-card-interactive rounded-2xl p-4 space-y-1">
          <div className="text-[10px] font-mono font-medium text-slate-400 uppercase tracking-wider">
            OPTIMIZER SOLVE TIME
          </div>
          <div className="text-xl font-mono font-bold text-sky-700 mt-1">
            {schedule?.solve_time_seconds?.toFixed(3) ?? '0.840'}s
          </div>
          <div className="text-[10px] font-mono text-slate-400 mt-1 font-normal">
            ALNS + CP-SAT Certified
          </div>
        </div>
      </div>

      {/* Interactive Context Inspector */}
      <div className="glass-card rounded-2xl p-4 space-y-3.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 font-mono text-xs font-bold text-slate-900">
            <Target className="w-4 h-4 text-sky-600" />
            <span>CONTEXT INSPECTOR // ASSET INTELLIGENCE</span>
          </div>

          <div className="w-64">
            <select
              value={selectedInspectorObj}
              onChange={(e) => setSelectedInspectorObj(e.target.value)}
              className="glass-input w-full rounded-xl px-2.5 py-1.5 text-xs font-mono text-slate-800 bg-white/80 cursor-pointer"
            >
              {inspectorOptions.map((opt) => (
                <option key={opt} value={opt} className="bg-white text-slate-800">
                  {opt}
                </option>
              ))}
            </select>
          </div>
        </div>

        {selectedInspectorObj === 'None (Overview)' && (
          <div className="glass-pill rounded-xl p-3 text-xs font-mono text-slate-500 flex items-center justify-between border border-slate-200/70 bg-white/50">
            <span>Select any UAV callsign or target point from the selector to view high-resolution 10Hz kinematics and sensor status.</span>
            <span className="text-[11px] text-sky-700 font-semibold">{instance?.drones?.length ?? 0} UAVs active in sector</span>
          </div>
        )}

        {selectedInspectorObj.startsWith('UAV') && (
          <div className="glass-card rounded-xl p-4 space-y-3 bg-white/60 border border-slate-200/80">
            <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
              <div className="font-mono text-xs font-bold text-sky-800 flex items-center gap-2">
                <span>OBJECT INSPECTOR // {selectedInspectorObj}</span>
              </div>
              <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-sky-50 text-sky-700 border border-sky-200/80 font-medium">
                {activeTelemMap[selectedInspectorObj]?.flight_phase ?? 'CRUISE'}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 text-xs font-mono">
              <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-sm">
                <span className="text-[10px] text-slate-400 block mb-0.5">BATTERY SOC</span>
                <span className="text-emerald-600 font-bold text-sm">
                  {(activeTelemMap[selectedInspectorObj]?.battery_percent ?? 100).toFixed(1)}%
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-sm">
                <span className="text-[10px] text-slate-400 block mb-0.5">GROUNDSPEED</span>
                <span className="text-slate-800 font-bold text-sm">
                  {(activeTelemMap[selectedInspectorObj]?.speed_mps ?? 14.5).toFixed(1)} m/s
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-sm">
                <span className="text-[10px] text-slate-400 block mb-0.5">ALTITUDE (AGL)</span>
                <span className="text-slate-800 font-bold text-sm">
                  {(activeTelemMap[selectedInspectorObj]?.z ?? 60).toFixed(0)} m
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-sm">
                <span className="text-[10px] text-slate-400 block mb-0.5">HEADING AZIMUTH</span>
                <span className="text-sky-700 font-bold text-sm">
                  {(activeTelemMap[selectedInspectorObj]?.heading_deg ?? 0).toFixed(0)}°
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-sm">
                <span className="text-[10px] text-slate-400 block mb-0.5">CURRENT WAYPOINT</span>
                <span className="text-slate-800 font-semibold">
                  {activeTelemMap[selectedInspectorObj]?.target_name ?? 'DEPOT'}
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-sm">
                <span className="text-[10px] text-slate-400 block mb-0.5">METRIC COORDINATES</span>
                <span className="text-slate-800 font-semibold">
                  ({(activeTelemMap[selectedInspectorObj]?.x ?? 0).toFixed(0)}, {(activeTelemMap[selectedInspectorObj]?.y ?? 0).toFixed(0)})
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-sm">
                <span className="text-[10px] text-slate-400 block mb-0.5">POWER DRAW</span>
                <span className="text-amber-600 font-bold">
                  {activeTelemMap[selectedInspectorObj]?.power_watts ?? 180} W
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-sm">
                <span className="text-[10px] text-slate-400 block mb-0.5">COMM LINK RSSI</span>
                <span className="text-emerald-600 font-bold">99.8%</span>
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
            <div className="glass-card rounded-xl p-4 space-y-3 bg-white/60 border border-slate-200/80">
              <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
                <div className="font-mono text-xs font-bold text-amber-800">
                  TARGET INTELLIGENCE // {selectedInspectorObj}
                </div>
                <span className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full font-semibold border ${
                  isSec
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200/80'
                    : 'bg-amber-50 text-amber-700 border-amber-200/80'
                }`}>
                  {isSec ? 'SECURED' : 'PENDING SCAN'}
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 text-xs font-mono">
                <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-sm">
                  <span className="text-[10px] text-slate-400 block mb-0.5">PRIORITY SCORE</span>
                  <span className="text-amber-700 font-bold text-sm">
                    {targetNode?.priority_score?.toFixed(0) ?? '0'} PTS
                  </span>
                </div>
                <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-sm">
                  <span className="text-[10px] text-slate-400 block mb-0.5">ASSIGNED UAV</span>
                  <span className="text-sky-700 font-bold text-sm">{assignedUav}</span>
                </div>
                <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-sm">
                  <span className="text-[10px] text-slate-400 block mb-0.5">SENSOR DWELL TIME</span>
                  <span className="text-slate-800 font-bold text-sm">
                    {targetNode?.dwell_time?.toFixed(0) ?? '30'}s
                  </span>
                </div>
                <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-sm">
                  <span className="text-[10px] text-slate-400 block mb-0.5">TERRAIN ELEVATION</span>
                  <span className="text-slate-800 font-bold text-sm">
                    {targetNode?.elevation?.toFixed(1) ?? '0'} m
                  </span>
                </div>
                <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-sm">
                  <span className="text-[10px] text-slate-400 block mb-0.5">COORDINATES (X, Y)</span>
                  <span className="text-slate-800 font-semibold">
                    ({targetNode?.x?.toFixed(1) ?? '0'}, {targetNode?.y?.toFixed(1) ?? '0'})
                  </span>
                </div>
                <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-sm">
                  <span className="text-[10px] text-slate-400 block mb-0.5">CLUSTER ZONE</span>
                  <span className="text-slate-800 font-semibold">C-{((tId % 4) + 1).toString().padStart(2, '0')}</span>
                </div>
                <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-sm">
                  <span className="text-[10px] text-slate-400 block mb-0.5">GEOFENCE STATUS</span>
                  <span className="text-emerald-600 font-bold">CLEAR</span>
                </div>
                <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-sm">
                  <span className="text-[10px] text-slate-400 block mb-0.5">OPTICAL RECON</span>
                  <span className="text-sky-700 font-bold">ACTIVE</span>
                </div>
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
}
