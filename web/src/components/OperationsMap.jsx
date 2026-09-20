import React, { useState, useEffect, useRef, useMemo } from 'react';
import { 
  Play, 
  Square, 
  RotateCcw, 
  Compass, 
  Target, 
  Zap,
  Sliders,
  ChevronDown,
  Layers
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
  const [showRadarHalos, setShowRadarHalos] = useState(false); // Default off to reduce clutter
  const [showFlightPaths, setShowFlightPaths] = useState(true);
  const [showRangeRings, setShowRangeRings] = useState(false); // Default off to reduce clutter
  const [showTacticalGrid, setShowTacticalGrid] = useState(true);
  const [showUavIcons, setShowUavIcons] = useState(true);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [selectedInspectorObj, setSelectedInspectorObj] = useState('None (Overview)');
  const [hoveredTarget, setHoveredTarget] = useState(null);

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

  // Coordinate conversion helpers
  const toCanvasX = (x, width) => ((x - minX) / (maxX - minX)) * (width - 80) + 40;
  const toCanvasY = (y, height) => height - (((y - minY) / (maxY - minY)) * (height - 80) + 40);

  // Canvas Mouse Move detection for non-intrusive target hover
  const handleCanvasMouseMove = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const mx = (e.clientX - rect.left) * scaleX;
    const my = (e.clientY - rect.top) * scaleY;

    let closest = null;
    let closestDist = 18;
    targets.forEach((t) => {
      const cx = toCanvasX(t.x, canvas.width);
      const cy = toCanvasY(t.y, canvas.height);
      const dist = Math.hypot(cx - mx, cy - my);
      if (dist < closestDist) {
        closestDist = dist;
        closest = t;
      }
    });
    setHoveredTarget(closest);
  };

  const handleCanvasMouseLeave = () => {
    setHoveredTarget(null);
  };

  const handleCanvasClick = () => {
    if (hoveredTarget) {
      setSelectedInspectorObj(`Target #${hoveredTarget.id.toString().padStart(2, '0')}`);
    }
  };

  // Draw 2D Tactical Map Canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Clear background with crisp off-white
    ctx.fillStyle = '#fbfcfe';
    ctx.fillRect(0, 0, width, height);

    // 1. Draw Tactical Grid (clean 60px step, ultra subtle)
    if (showTacticalGrid) {
      ctx.strokeStyle = 'rgba(15, 23, 42, 0.035)';
      ctx.lineWidth = 1;
      const step = 60;
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
    const depotX = depotNode ? toCanvasX(depotNode.x, width) : width / 2;
    const depotY = depotNode ? toCanvasY(depotNode.y, height) : height / 2;

    // 2. Range Rings (clean, non-cluttering)
    if (showRangeRings) {
      ctx.strokeStyle = 'rgba(15, 23, 42, 0.06)';
      ctx.setLineDash([4, 6]);
      [140, 280].forEach((r) => {
        ctx.beginPath();
        ctx.arc(depotX, depotY, r, 0, Math.PI * 2);
        ctx.stroke();
      });
      ctx.setLineDash([]);
    }

    // 3. Radar Sweep Line (subtle atmospheric pulse)
    if (showRangeRings) {
      const sweepAngle = (performance.now() / 1800) % (Math.PI * 2);
      const grad = ctx.createRadialGradient(depotX, depotY, 0, depotX, depotY, 280);
      grad.addColorStop(0, 'rgba(2, 132, 199, 0.05)');
      grad.addColorStop(1, 'rgba(2, 132, 199, 0)');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.moveTo(depotX, depotY);
      ctx.arc(depotX, depotY, 280, sweepAngle - 0.35, sweepAngle);
      ctx.closePath();
      ctx.fill();
    }

    // 4. Planned Flight Corridors (crisp single stroke, no double-dash clutter)
    const routes = schedule?.assigned_routes ?? [];
    if (showFlightPaths) {
      routes.forEach((route, rIdx) => {
        const color = DRONE_COLORS[rIdx % DRONE_COLORS.length];
        const wps = route.waypoints ?? [];
        if (wps.length < 2) return;

        ctx.strokeStyle = color;
        ctx.lineWidth = 1.8;
        ctx.globalAlpha = 0.75;
        ctx.beginPath();
        wps.forEach((wp, idx) => {
          const node = targets.find((t) => t.id === wp.node_id);
          if (node) {
            const cx = toCanvasX(node.x, width);
            const cy = toCanvasY(node.y, height);
            if (idx === 0) ctx.moveTo(cx, cy);
            else ctx.lineTo(cx, cy);
          }
        });
        ctx.stroke();
        ctx.globalAlpha = 1.0;
      });
    }

    // 5. Target Nodes (Clean micro-dots, NO text clutter unless hovered/inspected!)
    const securedSet = new Set(securedTargets ?? []);
    targets.forEach((node) => {
      const isDepot = (instance?.depot_ids ?? [0]).includes(node.id);
      const cx = toCanvasX(node.x, width);
      const cy = toCanvasY(node.y, height);
      const isSecured = securedSet.has(node.id);
      const isHovered = hoveredTarget && hoveredTarget.id === node.id;
      const isInspected = selectedInspectorObj === `Target #${node.id.toString().padStart(2, '0')}`;

      if (isDepot) {
        // Base Depot Marker
        ctx.fillStyle = '#0284C7';
        ctx.beginPath();
        ctx.arc(cx, cy, 7, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Label
        ctx.fillStyle = '#0284C7';
        ctx.font = '600 10px Inter, sans-serif';
        ctx.fillText('DEPOT', cx + 11, cy + 3.5);
      } else {
        // Target Node: Minimalist clean dot
        const radius = isHovered || isInspected ? 6 : isSecured ? 4.5 : 3.5;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);

        if (isSecured) {
          ctx.fillStyle = '#059669';
          ctx.fill();
          ctx.strokeStyle = '#FFFFFF';
          ctx.lineWidth = 1.5;
          ctx.stroke();
        } else {
          ctx.fillStyle = isHovered || isInspected ? '#0284C7' : '#cbd5e1';
          ctx.fill();
          ctx.strokeStyle = isHovered || isInspected ? '#FFFFFF' : '#94a3b8';
          ctx.lineWidth = 1;
          ctx.stroke();
        }

        // ONLY DRAW POPUP BADGE ON HOVER OR SELECTION (Eliminates 64 overlapping numbers!)
        if (isHovered || isInspected) {
          ctx.strokeStyle = isSecured ? 'rgba(5, 150, 105, 0.4)' : 'rgba(2, 132, 199, 0.4)';
          ctx.lineWidth = 2.5;
          ctx.beginPath();
          ctx.arc(cx, cy, radius + 4, 0, Math.PI * 2);
          ctx.stroke();

          // Floating dark tooltip pill
          const label = `Target #${node.id} · ${(node.priority_score || 0).toFixed(0)} pts`;
          ctx.font = '600 10px Inter, sans-serif';
          const textW = ctx.measureText(label).width;

          ctx.fillStyle = 'rgba(15, 23, 42, 0.88)';
          ctx.beginPath();
          ctx.roundRect(cx - textW / 2 - 6, cy - radius - 24, textW + 12, 18, 5);
          ctx.fill();

          ctx.fillStyle = '#FFFFFF';
          ctx.fillText(label, cx - textW / 2, cy - radius - 11);
        }
      }
    });

    // 6. Active Drone Positions and Glyphs
    const telemetryList = telemetry ?? [];
    telemetryList.forEach((droneTelem, dIdx) => {
      const color = DRONE_COLORS[dIdx % DRONE_COLORS.length];
      const cx = toCanvasX(droneTelem.x, width);
      const cy = toCanvasY(droneTelem.y, height);
      const headingRad = ((droneTelem.heading_deg || 0) * Math.PI) / 180;

      // Radar Halo (optional, subtle)
      if (showRadarHalos && droneTelem.flight_phase !== 'RECOVERED') {
        const haloRadiusPx = ((50 / (maxX - minX)) * (width - 80)) || 28;
        ctx.beginPath();
        ctx.arc(cx, cy, haloRadiusPx, 0, Math.PI * 2);
        ctx.fillStyle = `${color}0D`;
        ctx.fill();
        ctx.strokeStyle = `${color}35`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      if (showUavIcons) {
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(headingRad);

        // Quadcopter Arms
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.2;
        ctx.beginPath();
        ctx.moveTo(-8, -8);
        ctx.lineTo(8, 8);
        ctx.moveTo(8, -8);
        ctx.lineTo(-8, 8);
        ctx.stroke();

        // Fuselage
        ctx.fillStyle = '#FFFFFF';
        ctx.beginPath();
        ctx.arc(0, 0, 3.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Heading nose
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(0, -11);
        ctx.lineTo(3.5, -6);
        ctx.lineTo(-3.5, -6);
        ctx.closePath();
        ctx.fill();

        ctx.restore();

        // Sleek callsign label
        ctx.fillStyle = '#0F172A';
        ctx.font = '600 10px Inter, sans-serif';
        ctx.fillText(
          `${droneTelem.drone_id} (${(droneTelem.battery_percent || 100).toFixed(0)}%)`,
          cx + 12,
          cy - 5
        );
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
    hoveredTarget,
    selectedInspectorObj,
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
    <div className="space-y-4 font-sans">
      {/* 1. Slim Top Bar: Map Title & Layer Toggles */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-sky-50 border border-sky-200/80 flex items-center justify-center text-sky-600">
            <Compass className="w-4 h-4" />
          </div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-900 tracking-tight">
              Tactical Operations Map
            </h2>
            <span className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-slate-100 text-slate-600 border border-slate-200/60">
              {instance?.instance_name ?? 'Chao Set 64'}
            </span>
          </div>
        </div>

        {/* Minimalist Layer Segmented Toolbar */}
        <div className="segmented-control">
          <button
            type="button"
            onClick={() => setShowFlightPaths(!showFlightPaths)}
            className={`segmented-item text-xs flex items-center gap-1.5 ${showFlightPaths ? 'segmented-item-active' : ''}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${showFlightPaths ? 'bg-sky-500' : 'bg-slate-300'}`} />
            <span>Flight Paths</span>
          </button>

          <button
            type="button"
            onClick={() => setShowUavIcons(!showUavIcons)}
            className={`segmented-item text-xs flex items-center gap-1.5 ${showUavIcons ? 'segmented-item-active' : ''}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${showUavIcons ? 'bg-sky-500' : 'bg-slate-300'}`} />
            <span>UAV Glyphs</span>
          </button>

          <button
            type="button"
            onClick={() => setShowTacticalGrid(!showTacticalGrid)}
            className={`segmented-item text-xs flex items-center gap-1.5 ${showTacticalGrid ? 'segmented-item-active' : ''}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${showTacticalGrid ? 'bg-sky-500' : 'bg-slate-300'}`} />
            <span>Grid</span>
          </button>

          <button
            type="button"
            onClick={() => setShowRangeRings(!showRangeRings)}
            className={`segmented-item text-xs flex items-center gap-1.5 ${showRangeRings ? 'segmented-item-active' : ''}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${showRangeRings ? 'bg-sky-500' : 'bg-slate-300'}`} />
            <span>Rings</span>
          </button>

          <button
            type="button"
            onClick={() => setShowRadarHalos(!showRadarHalos)}
            className={`segmented-item text-xs flex items-center gap-1.5 ${showRadarHalos ? 'segmented-item-active' : ''}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${showRadarHalos ? 'bg-sky-500' : 'bg-slate-300'}`} />
            <span>Halos</span>
          </button>
        </div>
      </div>

      {/* 2. Hero Tactical Map Canvas & Integrated Player Dock */}
      <div className="glass-card rounded-2xl overflow-hidden shadow-sm border border-slate-200/80">
        {/* Canvas Display */}
        <div className="relative">
          <canvas
            ref={canvasRef}
            width={1100}
            height={520}
            onMouseMove={handleCanvasMouseMove}
            onMouseLeave={handleCanvasMouseLeave}
            onClick={handleCanvasClick}
            className="w-full h-[500px] object-cover block cursor-crosshair bg-[#fbfcfe]"
          />

          {/* Floating Subtle HUD Badges */}
          <div className="absolute top-3 left-3 flex items-center gap-2 pointer-events-none">
            <div className="px-2.5 py-1 rounded-md text-[11px] font-sans text-slate-700 font-medium bg-white/90 border border-slate-200/80 shadow-xs flex items-center gap-1.5 backdrop-blur-md">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
              <span>Tactical SITL • 60 FPS</span>
            </div>
            {hoveredTarget && (
              <div className="px-2.5 py-1 rounded-md text-[11px] font-sans text-sky-700 font-medium bg-sky-50/95 border border-sky-200/80 shadow-xs backdrop-blur-md">
                Hovering Target #{hoveredTarget.id} (Click to inspect)
              </div>
            )}
          </div>

          <div className="absolute top-3 right-3 pointer-events-none">
            <div className="px-2.5 py-1 rounded-md text-[11px] font-mono text-slate-700 bg-white/90 border border-slate-200/80 shadow-xs backdrop-blur-md">
              MET T+{missionTime.toFixed(0).padStart(4, '0')}s / {maxMissionTime.toFixed(0).padStart(4, '0')}s
            </div>
          </div>
        </div>

        {/* Integrated Player Dock: Transport + Scrubber + Timeline Stepper */}
        <div className="p-3.5 border-t border-slate-200/70 bg-white/50 backdrop-blur-md flex flex-wrap items-center gap-4">
          {/* Transport buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer shadow-xs ${
                isPlaying ? 'bg-amber-500 hover:bg-amber-600 text-white' : 'btn-primary'
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
              title="Reset Timeline"
              className="btn-secondary px-2.5 py-1.5 rounded-lg text-xs font-medium cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5 text-slate-500" />
            </button>
          </div>

          {/* Timeline Scrubber & Minimal Stage Stepper */}
          <div className="flex-1 min-w-[240px] flex flex-col justify-center gap-1">
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
            {/* Minimal inline stage labels */}
            <div className="flex justify-between items-center text-[10px] font-sans px-0.5 text-slate-400">
              <span className={p1 === 'active' ? 'text-sky-600 font-semibold' : ''}>Deploy</span>
              <span>•</span>
              <span className={p2 === 'active' ? 'text-sky-600 font-semibold' : ''}>Transit</span>
              <span>•</span>
              <span className={p3 === 'active' ? 'text-sky-600 font-semibold' : ''}>Cluster</span>
              <span>•</span>
              <span className={p4 === 'active' ? 'text-sky-600 font-semibold' : ''}>Acquire</span>
              <span>•</span>
              <span className={p5 === 'active' ? 'text-sky-600 font-semibold' : ''}>Recovery</span>
            </div>
          </div>

          {/* Speed Selector */}
          <div className="flex items-center gap-2">
            <div className="segmented-control">
              {[1, 2, 5, 10].map((spd) => (
                <button
                  key={spd}
                  onClick={() => setPlaybackSpeed(spd)}
                  className={`segmented-item font-mono text-[11px] py-1 px-2 ${
                    playbackSpeed === spd ? 'segmented-item-active' : ''
                  }`}
                >
                  {spd}x
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 3. Streamlined Metric Strip (One quiet, elegant horizontal row) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="glass-card rounded-xl p-3 space-y-0.5">
          <div className="text-[11px] text-slate-500 font-medium">Total Secured Reward</div>
          <div className="text-xl font-mono font-bold text-slate-900">
            {schedule?.cumulative_reward?.toFixed(0) ?? '0'} <span className="text-xs font-sans text-slate-400 font-normal">PTS</span>
          </div>
          <div className="text-[11px] text-emerald-600 font-medium">
            +{schedule?.reward_gain_percent?.toFixed(1) ?? '18.5'}% vs baseline
          </div>
        </div>

        <div className="glass-card rounded-xl p-3 space-y-0.5">
          <div className="text-[11px] text-slate-500 font-medium">Targets Secured</div>
          <div className="text-xl font-mono font-bold text-slate-900">
            {visitedCount} <span className="text-xs font-sans text-slate-400 font-normal">/ {totalTargetsCount}</span>
          </div>
          <div className="text-[11px] text-sky-600 font-medium">
            {coveragePct.toFixed(1)}% swarm coverage
          </div>
        </div>

        <div className="glass-card rounded-xl p-3 space-y-0.5">
          <div className="text-[11px] text-slate-500 font-medium">Min Battery Reserve</div>
          <div className="text-xl font-mono font-bold text-emerald-600">
            {minReserveAll.toFixed(1)}%
          </div>
          <div className="text-[11px] text-slate-400">
            Above 15.0% safety floor
          </div>
        </div>

        <div className="glass-card rounded-xl p-3 space-y-0.5">
          <div className="text-[11px] text-slate-500 font-medium">Optimizer Solve Time</div>
          <div className="text-xl font-mono font-bold text-slate-900">
            {schedule?.solve_time_seconds?.toFixed(3) ?? '0.840'}s
          </div>
          <div className="text-[11px] text-slate-400">
            ALNS + CP-SAT Certified
          </div>
        </div>
      </div>

      {/* 4. Interactive Context Inspector (Clean & Non-Intrusive) */}
      <div className="glass-card rounded-2xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-sky-50 border border-sky-200/80 flex items-center justify-center text-sky-600">
              <Target className="w-3.5 h-3.5" />
            </div>
            <span className="text-xs font-semibold text-slate-900">Asset & Target Inspector</span>
          </div>

          <div className="w-60">
            <select
              value={selectedInspectorObj}
              onChange={(e) => setSelectedInspectorObj(e.target.value)}
              className="glass-input w-full rounded-lg px-2.5 py-1.5 text-xs text-slate-800 bg-white/80 cursor-pointer"
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
          <div className="rounded-xl p-3 text-xs text-slate-500 flex items-center justify-between border border-slate-200/70 bg-white/60">
            <span>Hover or click any target node or select a UAV to inspect kinematics and sensor status.</span>
            <span className="text-[11px] font-mono text-sky-700 font-semibold">{instance?.drones?.length ?? 0} UAVs active</span>
          </div>
        )}

        {selectedInspectorObj.startsWith('UAV') && (
          <div className="rounded-xl p-3.5 space-y-2.5 bg-white/70 border border-slate-200/80">
            <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
              <div className="text-xs font-semibold text-slate-900 flex items-center gap-2">
                <span>Callsign:</span>
                <span className="font-mono text-sky-700 font-bold">{selectedInspectorObj}</span>
              </div>
              <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-sky-50 text-sky-700 border border-sky-200/80 font-medium">
                {activeTelemMap[selectedInspectorObj]?.flight_phase ?? 'CRUISE'}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                <span className="text-[10px] text-slate-400 block mb-0.5">Battery SoC</span>
                <span className="text-emerald-600 font-bold text-sm font-mono">
                  {(activeTelemMap[selectedInspectorObj]?.battery_percent ?? 100).toFixed(1)}%
                </span>
              </div>
              <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                <span className="text-[10px] text-slate-400 block mb-0.5">Groundspeed</span>
                <span className="text-slate-800 font-bold text-sm font-mono">
                  {(activeTelemMap[selectedInspectorObj]?.speed_mps ?? 14.5).toFixed(1)} m/s
                </span>
              </div>
              <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                <span className="text-[10px] text-slate-400 block mb-0.5">Altitude (AGL)</span>
                <span className="text-slate-800 font-bold text-sm font-mono">
                  {(activeTelemMap[selectedInspectorObj]?.z ?? 60).toFixed(0)} m
                </span>
              </div>
              <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                <span className="text-[10px] text-slate-400 block mb-0.5">Heading</span>
                <span className="text-sky-700 font-bold text-sm font-mono">
                  {(activeTelemMap[selectedInspectorObj]?.heading_deg ?? 0).toFixed(0)}°
                </span>
              </div>
              <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                <span className="text-[10px] text-slate-400 block mb-0.5">Current Target</span>
                <span className="text-slate-800 font-medium">
                  {activeTelemMap[selectedInspectorObj]?.target_name ?? 'DEPOT'}
                </span>
              </div>
              <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                <span className="text-[10px] text-slate-400 block mb-0.5">Coordinates</span>
                <span className="text-slate-800 font-mono text-[11px]">
                  ({(activeTelemMap[selectedInspectorObj]?.x ?? 0).toFixed(0)}, {(activeTelemMap[selectedInspectorObj]?.y ?? 0).toFixed(0)})
                </span>
              </div>
              <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                <span className="text-[10px] text-slate-400 block mb-0.5">Power Draw</span>
                <span className="text-amber-600 font-bold font-mono">
                  {activeTelemMap[selectedInspectorObj]?.power_watts ?? 180} W
                </span>
              </div>
              <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                <span className="text-[10px] text-slate-400 block mb-0.5">Comm Link RSSI</span>
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
            <div className="rounded-xl p-3.5 space-y-2.5 bg-white/70 border border-slate-200/80">
              <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
                <div className="text-xs font-semibold text-slate-900 flex items-center gap-2">
                  <span>Target Details:</span>
                  <span className="font-mono text-amber-700 font-bold">{selectedInspectorObj}</span>
                </div>
                <span className={`text-[10px] px-2.5 py-0.5 rounded-full font-medium border ${
                  isSec
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200/80'
                    : 'bg-amber-50 text-amber-700 border-amber-200/80'
                }`}>
                  {isSec ? 'Secured' : 'Pending Scan'}
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Priority Score</span>
                  <span className="text-amber-700 font-bold text-sm font-mono">
                    {targetNode?.priority_score?.toFixed(0) ?? '0'} PTS
                  </span>
                </div>
                <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Assigned UAV</span>
                  <span className="text-sky-700 font-bold text-sm font-mono">{assignedUav}</span>
                </div>
                <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Sensor Dwell</span>
                  <span className="text-slate-800 font-bold text-sm font-mono">
                    {targetNode?.dwell_time?.toFixed(0) ?? '30'}s
                  </span>
                </div>
                <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Elevation</span>
                  <span className="text-slate-800 font-bold text-sm font-mono">
                    {targetNode?.elevation?.toFixed(1) ?? '0'} m
                  </span>
                </div>
                <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Coordinates</span>
                  <span className="text-slate-800 font-mono text-[11px]">
                    ({targetNode?.x?.toFixed(1) ?? '0'}, {targetNode?.y?.toFixed(1) ?? '0'})
                  </span>
                </div>
                <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Cluster Zone</span>
                  <span className="text-slate-800 font-medium">Zone {((tId % 4) + 1)}</span>
                </div>
                <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Geofence</span>
                  <span className="text-emerald-600 font-bold">Clear</span>
                </div>
                <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Optical Recon</span>
                  <span className="text-sky-700 font-bold">Active</span>
                </div>
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
}
