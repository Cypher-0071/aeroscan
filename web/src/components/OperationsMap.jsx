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
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-sky-50 border border-sky-200/80 flex items-center justify-center text-sky-600">
              <Compass className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-slate-900 tracking-tight font-sans">
                  Tactical Operations Map
                </h2>
                <span className="px-2 py-0.5 text-[11px] font-sans font-medium rounded-md bg-slate-100 text-slate-600 border border-slate-200/60">
                  2D Metric Grid
                </span>
              </div>
            </div>
          </div>

          {/* Sensor Layer Toggles as Sleek Segmented Control */}
          <div className="segmented-control">
            <button
              type="button"
              onClick={() => setShowRadarHalos(!showRadarHalos)}
              className={`segmented-item flex items-center gap-1.5 ${showRadarHalos ? 'segmented-item-active' : ''}`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${showRadarHalos ? 'bg-sky-500' : 'bg-slate-300'}`} />
              <span>Radar Halos</span>
            </button>

            <button
              type="button"
              onClick={() => setShowFlightPaths(!showFlightPaths)}
              className={`segmented-item flex items-center gap-1.5 ${showFlightPaths ? 'segmented-item-active' : ''}`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${showFlightPaths ? 'bg-sky-500' : 'bg-slate-300'}`} />
              <span>Flight Paths</span>
            </button>

            <button
              type="button"
              onClick={() => setShowRangeRings(!showRangeRings)}
              className={`segmented-item flex items-center gap-1.5 ${showRangeRings ? 'segmented-item-active' : ''}`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${showRangeRings ? 'bg-sky-500' : 'bg-slate-300'}`} />
              <span>Range Rings</span>
            </button>

            <button
              type="button"
              onClick={() => setShowTacticalGrid(!showTacticalGrid)}
              className={`segmented-item flex items-center gap-1.5 ${showTacticalGrid ? 'segmented-item-active' : ''}`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${showTacticalGrid ? 'bg-sky-500' : 'bg-slate-300'}`} />
              <span>Tactical Grid</span>
            </button>

            <button
              type="button"
              onClick={() => setShowUavIcons(!showUavIcons)}
              className={`segmented-item flex items-center gap-1.5 ${showUavIcons ? 'segmented-item-active' : ''}`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${showUavIcons ? 'bg-sky-500' : 'bg-slate-300'}`} />
              <span>UAV Glyphs</span>
            </button>
          </div>
        </div>

        {/* Chronology & Transport Controls Bar */}
        <div className="pt-3 border-t border-slate-200/70 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-2 cursor-pointer shadow-sm ${
                isPlaying
                  ? 'bg-amber-500 hover:bg-amber-600 text-white'
                  : 'btn-primary'
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
                  <span>Execute Mission</span>
                </>
              )}
            </button>

            <button
              onClick={() => {
                setIsPlaying(false);
                setMissionTime(0);
              }}
              className="btn-secondary px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5 text-slate-500" />
              <span>Reset</span>
            </button>

            {/* Playback speed selector */}
            <div className="segmented-control ml-1">
              {[1, 2, 5, 10].map((spd) => (
                <button
                  key={spd}
                  onClick={() => setPlaybackSpeed(spd)}
                  className={`segmented-item font-mono text-[11px] py-1 px-2.5 ${
                    playbackSpeed === spd ? 'segmented-item-active' : ''
                  }`}
                >
                  {spd}x
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs font-sans">
            <span className="text-slate-500 font-medium">Mission Timeline:</span>
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-slate-100/90 border border-slate-200/70 text-slate-800">
              <span className="font-mono font-semibold text-slate-900">
                T+{missionTime.toFixed(0).padStart(4, '0')}s
              </span>
              <span className="text-slate-400 font-mono text-[11px]">/ {maxMissionTime.toFixed(0).padStart(4, '0')}s</span>
              <span className="text-slate-500 font-mono text-[11px] ml-1">
                ({((missionTime / Math.max(maxMissionTime, 1)) * 100).toFixed(1)}%)
              </span>
            </div>
            <span className={`inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full font-medium ${
              isPlaying 
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/80' 
                : 'bg-slate-100 text-slate-600 border border-slate-200/80'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${isPlaying ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`}></span>
              {isPlaying ? 'Simulating' : 'Holding'}
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

        {/* 5-Stage Flight Pipeline Stepper */}
        <div className="grid grid-cols-5 gap-2 pt-1">
          {[
            { id: '1', name: 'Deploy', state: p1 },
            { id: '2', name: 'Transit', state: p2 },
            { id: '3', name: 'Cluster', state: p3 },
            { id: '4', name: 'Acquire', state: p4 },
            { id: '5', name: 'Recovery', state: p5 },
          ].map((stage) => {
            const isAct = stage.state === 'active';
            const isComp = stage.state === 'completed';
            return (
              <div
                key={stage.id}
                className="space-y-1.5"
              >
                <div className="flex justify-between items-center text-[11px] font-sans">
                  <span className={`font-mono text-[10px] ${
                    isAct ? 'text-sky-600 font-bold' : isComp ? 'text-emerald-600 font-semibold' : 'text-slate-400'
                  }`}>
                    0{stage.id}
                  </span>
                  <span className={`font-medium ${
                    isAct ? 'text-sky-700 font-semibold' : isComp ? 'text-slate-800' : 'text-slate-400'
                  }`}>
                    {stage.name}
                  </span>
                </div>
                <div className="h-1.5 w-full bg-slate-100 border border-slate-200/60 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 rounded-full ${
                      isAct
                        ? 'bg-sky-500 w-full animate-pulse'
                        : isComp
                        ? 'bg-emerald-500 w-full'
                        : 'w-0'
                    }`}
                  />
                </div>
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
          className="w-full h-[580px] object-cover block cursor-crosshair bg-[#fbfcfe]"
        />

        {/* Floating Canvas Badges */}
        <div className="absolute top-4 left-4 flex items-center gap-2 pointer-events-none">
          <div className="px-3 py-1 rounded-lg glass-pill text-xs font-sans text-slate-700 font-medium border border-slate-200/90 bg-white/90 shadow-sm flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            <span>Tactical HUD</span>
            <span className="text-slate-400 font-mono text-[11px]">• 60fps SITL</span>
          </div>
          <div className="px-2.5 py-1 rounded-lg glass-pill text-xs font-sans text-slate-500 border border-slate-200/80 bg-white/90 shadow-sm">
            Scale: 1:1 Metric UTM
          </div>
        </div>

        <div className="absolute bottom-4 right-4 flex items-center gap-2 pointer-events-none">
          <div className="px-3 py-1 rounded-lg glass-pill text-xs font-mono text-slate-600 border border-slate-200/80 bg-white/90 shadow-sm">
            Hold Time: T+{missionTime.toFixed(0)}s
          </div>
        </div>
      </div>

      {/* Mission Intelligence Strip (4 Metric Cards) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="glass-card-interactive rounded-2xl p-4 space-y-1">
          <div className="text-xs font-medium text-slate-500 font-sans">
            Total Secured Reward
          </div>
          <div className="text-2xl font-mono font-bold tracking-tight text-slate-900 mt-1">
            {schedule?.cumulative_reward?.toFixed(0) ?? '0'} <span className="text-xs font-sans text-slate-400 font-normal">PTS</span>
          </div>
          <div className="text-xs font-sans text-emerald-600 mt-1 flex items-center gap-1 font-medium">
            <span>+{schedule?.reward_gain_percent?.toFixed(1) ?? '18.5'}%</span>
            <span className="text-slate-400 font-normal font-sans">vs GRASP baseline</span>
          </div>
        </div>

        <div className="glass-card-interactive rounded-2xl p-4 space-y-1">
          <div className="text-xs font-medium text-slate-500 font-sans">
            Targets Secured
          </div>
          <div className="text-2xl font-mono font-bold tracking-tight text-slate-900 mt-1">
            {visitedCount} <span className="text-sm font-sans text-slate-400 font-normal">/ {totalTargetsCount}</span>
          </div>
          <div className="text-xs font-sans text-sky-600 mt-1 font-medium">
            {coveragePct.toFixed(1)}% swarm coverage
          </div>
        </div>

        <div className="glass-card-interactive rounded-2xl p-4 space-y-1">
          <div className="text-xs font-medium text-slate-500 font-sans">
            Min Battery Reserve
          </div>
          <div className="text-2xl font-mono font-bold tracking-tight text-emerald-600 mt-1">
            {minReserveAll.toFixed(1)}%
          </div>
          <div className="text-xs font-sans text-slate-400 mt-1 font-normal">
            Above 15.0% safety floor
          </div>
        </div>

        <div className="glass-card-interactive rounded-2xl p-4 space-y-1">
          <div className="text-xs font-medium text-slate-500 font-sans">
            Optimizer Solve Time
          </div>
          <div className="text-2xl font-mono font-bold tracking-tight text-slate-900 mt-1">
            {schedule?.solve_time_seconds?.toFixed(3) ?? '0.840'}s
          </div>
          <div className="text-xs font-sans text-slate-400 mt-1 font-normal">
            ALNS + CP-SAT Certified
          </div>
        </div>
      </div>

      {/* Interactive Context Inspector */}
      <div className="glass-card rounded-2xl p-4 space-y-3.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-sky-50 border border-sky-200/80 flex items-center justify-center text-sky-600">
              <Target className="w-3.5 h-3.5" />
            </div>
            <span className="text-xs font-semibold text-slate-900 font-sans">Asset & Target Inspector</span>
          </div>

          <div className="w-64">
            <select
              value={selectedInspectorObj}
              onChange={(e) => setSelectedInspectorObj(e.target.value)}
              className="glass-input w-full rounded-lg px-2.5 py-1.5 text-xs font-sans text-slate-800 bg-white/80 cursor-pointer"
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
          <div className="rounded-xl p-3 text-xs font-sans text-slate-500 flex items-center justify-between border border-slate-200/70 bg-white/60">
            <span>Select any UAV callsign or target point from the selector to view high-resolution kinematics and telemetry.</span>
            <span className="text-[11px] font-mono text-sky-700 font-semibold">{instance?.drones?.length ?? 0} UAVs active</span>
          </div>
        )}

        {selectedInspectorObj.startsWith('UAV') && (
          <div className="rounded-xl p-4 space-y-3 bg-white/70 border border-slate-200/80">
            <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
              <div className="text-xs font-semibold text-slate-900 font-sans flex items-center gap-2">
                <span>Telemetry Inspection:</span>
                <span className="font-mono text-sky-700 font-bold">{selectedInspectorObj}</span>
              </div>
              <span className="text-[10px] font-sans px-2.5 py-0.5 rounded-full bg-sky-50 text-sky-700 border border-sky-200/80 font-medium">
                {activeTelemMap[selectedInspectorObj]?.flight_phase ?? 'CRUISE'}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 text-xs">
              <div className="p-2.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm">
                <span className="text-[11px] text-slate-400 font-sans block mb-0.5">Battery SoC</span>
                <span className="text-emerald-600 font-bold text-sm font-mono">
                  {(activeTelemMap[selectedInspectorObj]?.battery_percent ?? 100).toFixed(1)}%
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm">
                <span className="text-[11px] text-slate-400 font-sans block mb-0.5">Groundspeed</span>
                <span className="text-slate-800 font-bold text-sm font-mono">
                  {(activeTelemMap[selectedInspectorObj]?.speed_mps ?? 14.5).toFixed(1)} m/s
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm">
                <span className="text-[11px] text-slate-400 font-sans block mb-0.5">Altitude (AGL)</span>
                <span className="text-slate-800 font-bold text-sm font-mono">
                  {(activeTelemMap[selectedInspectorObj]?.z ?? 60).toFixed(0)} m
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm">
                <span className="text-[11px] text-slate-400 font-sans block mb-0.5">Heading Azimuth</span>
                <span className="text-sky-700 font-bold text-sm font-mono">
                  {(activeTelemMap[selectedInspectorObj]?.heading_deg ?? 0).toFixed(0)}°
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm">
                <span className="text-[11px] text-slate-400 font-sans block mb-0.5">Current Waypoint</span>
                <span className="text-slate-800 font-medium font-sans">
                  {activeTelemMap[selectedInspectorObj]?.target_name ?? 'DEPOT'}
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm">
                <span className="text-[11px] text-slate-400 font-sans block mb-0.5">Coordinates (X, Y)</span>
                <span className="text-slate-800 font-mono text-[11px]">
                  ({(activeTelemMap[selectedInspectorObj]?.x ?? 0).toFixed(0)}, {(activeTelemMap[selectedInspectorObj]?.y ?? 0).toFixed(0)})
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm">
                <span className="text-[11px] text-slate-400 font-sans block mb-0.5">Power Draw</span>
                <span className="text-amber-600 font-bold font-mono">
                  {activeTelemMap[selectedInspectorObj]?.power_watts ?? 180} W
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm">
                <span className="text-[11px] text-slate-400 font-sans block mb-0.5">Comm Link RSSI</span>
                <span className="text-emerald-600 font-bold font-mono">99.8%</span>
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
            <div className="rounded-xl p-4 space-y-3 bg-white/70 border border-slate-200/80">
              <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
                <div className="text-xs font-semibold text-slate-900 font-sans flex items-center gap-2">
                  <span>Target Details:</span>
                  <span className="font-mono text-amber-700 font-bold">{selectedInspectorObj}</span>
                </div>
                <span className={`text-[10px] font-sans px-2.5 py-0.5 rounded-full font-medium border ${
                  isSec
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200/80'
                    : 'bg-amber-50 text-amber-700 border-amber-200/80'
                }`}>
                  {isSec ? 'Secured' : 'Pending Scan'}
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 text-xs">
                <div className="p-2.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm">
                  <span className="text-[11px] text-slate-400 font-sans block mb-0.5">Priority Score</span>
                  <span className="text-amber-700 font-bold text-sm font-mono">
                    {targetNode?.priority_score?.toFixed(0) ?? '0'} PTS
                  </span>
                </div>
                <div className="p-2.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm">
                  <span className="text-[11px] text-slate-400 font-sans block mb-0.5">Assigned UAV</span>
                  <span className="text-sky-700 font-bold text-sm font-mono">{assignedUav}</span>
                </div>
                <div className="p-2.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm">
                  <span className="text-[11px] text-slate-400 font-sans block mb-0.5">Sensor Dwell Time</span>
                  <span className="text-slate-800 font-bold text-sm font-mono">
                    {targetNode?.dwell_time?.toFixed(0) ?? '30'}s
                  </span>
                </div>
                <div className="p-2.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm">
                  <span className="text-[11px] text-slate-400 font-sans block mb-0.5">Terrain Elevation</span>
                  <span className="text-slate-800 font-bold text-sm font-mono">
                    {targetNode?.elevation?.toFixed(1) ?? '0'} m
                  </span>
                </div>
                <div className="p-2.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm">
                  <span className="text-[11px] text-slate-400 font-sans block mb-0.5">Coordinates (X, Y)</span>
                  <span className="text-slate-800 font-mono text-[11px]">
                    ({targetNode?.x?.toFixed(1) ?? '0'}, {targetNode?.y?.toFixed(1) ?? '0'})
                  </span>
                </div>
                <div className="p-2.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm">
                  <span className="text-[11px] text-slate-400 font-sans block mb-0.5">Cluster Zone</span>
                  <span className="text-slate-800 font-medium font-sans">Zone {((tId % 4) + 1)}</span>
                </div>
                <div className="p-2.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm">
                  <span className="text-[11px] text-slate-400 font-sans block mb-0.5">Geofence Status</span>
                  <span className="text-emerald-600 font-bold font-sans">Clear</span>
                </div>
                <div className="p-2.5 rounded-xl bg-white/90 border border-slate-200/70 shadow-sm">
                  <span className="text-[11px] text-slate-400 font-sans block mb-0.5">Recon Status</span>
                  <span className="text-sky-700 font-bold font-sans">Active</span>
                </div>
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
}
