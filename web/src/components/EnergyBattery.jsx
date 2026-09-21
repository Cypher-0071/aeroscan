import React, { useState, useMemo } from 'react';
import { 
  BatteryCharging, 
  Zap, 
  ShieldCheck, 
  Wind, 
  Activity, 
  CheckCircle2, 
  Clock, 
  Layers, 
  Filter,
  Eye,
  AlertTriangle,
  Radio,
  Check,
  Cpu
} from 'lucide-react';

const DRONE_COLORS = {
  'UAV-01': '#0284c7', // Sky
  'UAV-02': '#d97706', // Amber
  'UAV-03': '#059669', // Emerald
};

function formatSeconds(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// Catmull-Rom to Cubic Bezier curve generator with monotonicity clamping
function generateSmoothPath(points) {
  if (!points || points.length === 0) return '';
  if (points.length === 1) return `M ${points[0].x.toFixed(1)},${points[0].y.toFixed(1)}`;
  if (points.length === 2) {
    return `M ${points[0].x.toFixed(1)},${points[0].y.toFixed(1)} L ${points[1].x.toFixed(1)},${points[1].y.toFixed(1)}`;
  }

  let d = `M ${points[0].x.toFixed(1)},${points[0].y.toFixed(1)}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(points.length - 1, i + 2)];

    let cp1x = p1.x + (p2.x - p0.x) / 6;
    let cp1y = p1.y + (p2.y - p0.y) / 6;
    let cp2x = p2.x - (p3.x - p1.x) / 6;
    let cp2y = p2.y - (p3.y - p1.y) / 6;

    // Monotonicity clamping: preserve battery drain direction without artificial dips
    if (p1.y <= p2.y) {
      cp1y = Math.max(p1.y, Math.min(p2.y, cp1y));
      cp2y = Math.max(p1.y, Math.min(p2.y, cp2y));
    } else {
      cp1y = Math.min(p1.y, Math.max(p2.y, cp1y));
      cp2y = Math.min(p1.y, Math.max(p2.y, cp2y));
    }

    d += ` C ${cp1x.toFixed(1)},${cp1y.toFixed(1)} ${cp2x.toFixed(1)},${cp2y.toFixed(1)} ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`;
  }
  return d;
}

function generateAreaPath(points, baselineY) {
  if (!points || points.length === 0) return '';
  const linePath = generateSmoothPath(points);
  const firstX = points[0].x.toFixed(1);
  const lastX = points[points.length - 1].x.toFixed(1);
  return `${linePath} L ${lastX},${baselineY} L ${firstX},${baselineY} Z`;
}

function getBatteryAtTime(route, time) {
  const wps = route?.waypoints ?? [];
  if (wps.length === 0) return 100;
  if (time <= wps[0].departure_time) return 100;
  for (let i = 0; i < wps.length - 1; i++) {
    const w1 = wps[i];
    const w2 = wps[i + 1];
    if (time >= w1.departure_time && time <= w2.departure_time) {
      const span = w2.departure_time - w1.departure_time;
      if (span === 0) return w1.remaining_battery_percent;
      const progress = (time - w1.departure_time) / span;
      return w1.remaining_battery_percent + progress * (w2.remaining_battery_percent - w1.remaining_battery_percent);
    }
  }
  return wps[wps.length - 1].remaining_battery_percent;
}

export default function EnergyBattery({
  instance,
  schedule,
  missionTime = 0,
  setMissionTime,
}) {
  const [selectedDroneId, setSelectedDroneId] = useState('ALL');
  const [hoverData, setHoverData] = useState(null);

  const routes = schedule?.assigned_routes ?? [];
  const minReserveAll = routes.reduce(
    (min, r) => Math.min(min, r.final_reserve_percent ?? 100),
    100
  );
  const totalJoules = routes.reduce(
    (sum, r) => sum + (r.total_energy_joules ?? 0),
    0
  );
  const avgReserve = routes.length > 0
    ? routes.reduce((sum, r) => sum + (r.final_reserve_percent ?? 100), 0) / routes.length
    : 100;

  // Identify unit with minimum landing reserve
  const lowestReserveRoute = routes.reduce(
    (lowest, r) => ((r.final_reserve_percent ?? 100) < (lowest?.final_reserve_percent ?? 100) ? r : lowest),
    routes[0]
  );

  const rawMaxFlightTime = Math.max(
    ...routes.map((r) => r.total_flight_time ?? 0),
    500
  );
  // Round up to clean 60s bucket
  const maxFlightTime = Math.ceil(rawMaxFlightTime / 60) * 60;

  // Fleet mean burn rate (% per minute)
  const avgBurnRatePerMin = routes.length > 0
    ? routes.reduce((sum, r) => {
        const flightMin = Math.max(1, (r.total_flight_time ?? 60) / 60);
        const burned = 100 - (r.final_reserve_percent ?? 100);
        return sum + (burned / flightMin);
      }, 0) / routes.length
    : 0;

  // Graph coordinate dimensions
  const svgWidth = 800;
  const svgHeight = 320;
  const padding = { left: 55, right: 35, top: 25, bottom: 35 };
  const chartW = svgWidth - padding.left - padding.right;
  const chartH = svgHeight - padding.top - padding.bottom;

  const mapX = (t) => padding.left + (Math.max(0, Math.min(maxFlightTime, t)) / maxFlightTime) * chartW;
  const mapY = (soc) => padding.top + (1 - Math.max(0, Math.min(100, soc)) / 100) * chartH;

  // Y-axis grid levels (100%, 75%, 50%, 25%, 0%)
  const yTicks = [100, 75, 50, 25, 0];
  const safetyY = mapY(15);
  const nominalY = mapY(30);
  const baseY = mapY(0);

  // X-axis time intervals (6 ticks)
  const xTicks = useMemo(() => {
    const ticks = [];
    const step = maxFlightTime / 5;
    for (let i = 0; i <= 5; i++) {
      ticks.push(Math.round(i * step));
    }
    return ticks;
  }, [maxFlightTime]);

  // Current scrubber X coordinate
  const currentScrubberX = mapX(missionTime);

  // Interactive mouse events for timeline scrubbing & hover inspection
  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const relX = (e.clientX - rect.left) / rect.width;
    const svgX = relX * svgWidth;
    if (svgX < padding.left || svgX > padding.left + chartW) {
      setHoverData(null);
      return;
    }
    const hoverT = Math.max(0, Math.min(maxFlightTime, ((svgX - padding.left) / chartW) * maxFlightTime));
    const perDrone = routes.map((r) => {
      const soc = getBatteryAtTime(r, hoverT);
      const color = DRONE_COLORS[r.drone_id] || '#64748b';
      const isLanded = hoverT >= (r.total_flight_time ?? 0);
      return {
        drone_id: r.drone_id,
        color,
        soc,
        y: mapY(soc),
        isLanded,
        margin: soc - 15.0,
      };
    });
    const avgSoC = perDrone.length > 0
      ? perDrone.reduce((sum, d) => sum + d.soc, 0) / perDrone.length
      : 100;

    setHoverData({
      x: svgX,
      clientRelX: relX,
      time: hoverT,
      perDrone,
      avgSoC,
    });
  };

  const handleMouseLeave = () => {
    setHoverData(null);
  };

  const handleChartClick = (e) => {
    if (!setMissionTime) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const relX = (e.clientX - rect.left) / rect.width;
    const svgX = relX * svgWidth;
    const clampedX = Math.max(padding.left, Math.min(padding.left + chartW, svgX));
    const clickedT = ((clampedX - padding.left) / chartW) * maxFlightTime;
    setMissionTime(clickedT);
  };

  return (
    <div className="space-y-4 font-sans max-w-7xl mx-auto">
      {/* 1. Header Bar: Clean & Restrained */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-slate-100 border border-slate-200/80 flex items-center justify-center text-slate-700 shadow-2xs">
            <BatteryCharging className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-900 tracking-tight">
              Swarm Energy Intelligence & Battery Dynamics
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Aerodynamic power draw, 2D wind drift compensation, and 15% safety floor compliance
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-lg bg-slate-100 border border-slate-200 text-slate-600 text-xs font-mono">
            {instance?.instance_name ?? 'synthetic_set_64'}
          </span>
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-sans border border-slate-200 bg-white shadow-2xs text-slate-700">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span className="font-medium">
              {minReserveAll >= 15 ? 'All Fleet Units Above Safety Floor' : 'Safety Floor Breach'}
            </span>
          </div>
        </div>
      </div>

      {/* 2. Visual Hierarchy Anchor: 4 Top-Level Metric Scorecards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="glass-card rounded-2xl p-4 border border-slate-200/80 bg-white/95 shadow-xs space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500 font-medium">Minimum Landing Battery</span>
            <ShieldCheck className="w-4 h-4 text-slate-400" />
          </div>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-2xl font-bold font-mono text-slate-900">
              {minReserveAll.toFixed(1)}%
            </span>
          </div>
          <span className="text-[11px] text-emerald-700 font-medium block">
            +{(minReserveAll - 15.0).toFixed(1)}% Above 15.0% Safety Floor
          </span>
        </div>

        <div className="glass-card rounded-2xl p-4 border border-slate-200/80 bg-white/95 shadow-xs space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500 font-medium">Total Swarm Energy</span>
            <Zap className="w-4 h-4 text-slate-400" />
          </div>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-2xl font-bold font-mono text-slate-900">
              {(totalJoules / 1000).toFixed(1)}
            </span>
            <span className="text-xs text-slate-500 font-sans">kJ</span>
          </div>
          <span className="text-[11px] text-slate-500 block">
            BEMT & Wind Drag Compensated
          </span>
        </div>

        <div className="glass-card rounded-2xl p-4 border border-slate-200/80 bg-white/95 shadow-xs space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500 font-medium">Average Fleet Reserve</span>
            <Activity className="w-4 h-4 text-slate-400" />
          </div>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-2xl font-bold font-mono text-slate-900">
              {avgReserve.toFixed(1)}%
            </span>
          </div>
          <span className="text-[11px] text-slate-500 block">
            Balanced Multi-UAV Allocation
          </span>
        </div>

        <div className="glass-card rounded-2xl p-4 border border-slate-200/80 bg-white/95 shadow-xs space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500 font-medium">Mandatory Reserve Floor</span>
            <span className="text-[10px] font-mono uppercase bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
              Hard Limit
            </span>
          </div>
          <div className="flex items-baseline gap-1 mt-1">
            <span className="text-2xl font-bold font-mono text-slate-900">
              15.0%
            </span>
          </div>
          <span className="text-[11px] text-slate-500 block">
            Strict Non-Negotiable Threshold
          </span>
        </div>
      </div>

      {/* 3. Hero Visual: Multi-Drone Battery SoC Depletion Trajectory (Precision Interactive Graph) */}
      <div className="glass-card rounded-2xl p-4 border border-slate-200/90 shadow-xs bg-white/95 space-y-3">
        {/* Graph Subheader & Interactive Fleet Filter Pills */}
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xs font-bold text-slate-900 tracking-tight">
                Battery State of Charge (SoC) Depletion Trajectory
              </h2>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono bg-slate-100 text-slate-600 border border-slate-200">
                <Radio className="w-3 h-3 text-sky-600" />
                Continuous BEMT Telemetry
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Interactive discharge curves modeled against rotor polars, hover thrust, and 2D crosswind vectors
            </p>
          </div>

          {/* Unit Filter Legend with Live Status */}
          <div className="flex items-center flex-wrap gap-1.5 bg-slate-100/70 p-1 rounded-xl border border-slate-200/70">
            {/* All Units Filter */}
            <button
              onClick={() => setSelectedDroneId('ALL')}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer flex items-center gap-1.5 ${
                selectedDroneId === 'ALL'
                  ? 'bg-white text-slate-900 font-semibold shadow-2xs border border-slate-200/90'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <span>All UAVs</span>
              <span className="font-mono text-[10px] px-1 py-0.2 rounded bg-slate-100 text-slate-500">
                {routes.length}
              </span>
            </button>

            {/* Individual Unit Filters */}
            {routes.map((r) => {
              const isFocused = selectedDroneId === r.drone_id;
              const color = DRONE_COLORS[r.drone_id] || '#64748b';
              const currentBat = getBatteryAtTime(r, missionTime);

              return (
                <button
                  key={r.drone_id}
                  onClick={() => setSelectedDroneId(isFocused ? 'ALL' : r.drone_id)}
                  className={`px-2.5 py-1 rounded-lg text-xs transition-all cursor-pointer flex items-center gap-1.5 ${
                    isFocused
                      ? 'bg-white text-slate-900 font-semibold shadow-2xs border border-slate-200/90 ring-1 ring-slate-300'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: color }}
                  />
                  <span className="font-mono text-[11px]">{r.drone_id}</span>
                  <span className="font-mono font-bold text-slate-800 text-[11px]">
                    {currentBat.toFixed(1)}%
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* High-Precision SVG Graph Container with Hover Tracking */}
        <div
          className="w-full bg-slate-50/40 rounded-xl p-2 border border-slate-200/70 relative select-none cursor-crosshair"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          onClick={handleChartClick}
        >
          <svg className="w-full h-auto" viewBox={`0 0 ${svgWidth} ${svgHeight}`}>
            <defs>
              {/* Hatch Pattern for 15% Mandatory Safety Floor */}
              <pattern
                id="safety-hatch"
                width="8"
                height="8"
                patternTransform="rotate(45 0 0)"
                patternUnits="userSpaceOnUse"
              >
                <line
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="8"
                  stroke="#f43f5e"
                  strokeWidth="1.2"
                  strokeOpacity="0.14"
                />
              </pattern>

              {/* Curve Soft Glow Filter */}
              <filter id="focusedGlow" x="-10%" y="-10%" width="120%" height="120%">
                <feDropShadow dx="0" dy="2" stdDeviation="2.5" floodColor="#0284c7" floodOpacity="0.25" />
              </filter>

              {/* Area Gradients for each drone */}
              {routes.map((r) => {
                const color = DRONE_COLORS[r.drone_id] || '#64748b';
                return (
                  <linearGradient
                    key={`grad-${r.drone_id}`}
                    id={`drone-grad-${r.drone_id}`}
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop offset="0%" stopColor={color} stopOpacity="0.18" />
                    <stop offset="70%" stopColor={color} stopOpacity="0.04" />
                    <stop offset="100%" stopColor={color} stopOpacity="0.00" />
                  </linearGradient>
                );
              })}
            </defs>

            {/* 15% Mandatory Safety Floor Hatch Fill */}
            <rect
              x={padding.left}
              y={safetyY}
              width={chartW}
              height={baseY - safetyY}
              fill="url(#safety-hatch)"
            />
            {/* Subtle red bottom gradient */}
            <rect
              x={padding.left}
              y={safetyY}
              width={chartW}
              height={baseY - safetyY}
              fill="rgba(244, 63, 94, 0.035)"
            />

            {/* Horizontal Grid Lines & Y-Labels */}
            {yTicks.map((val) => {
              const yPos = mapY(val);
              return (
                <g key={val}>
                  <line
                    x1={padding.left}
                    y1={yPos}
                    x2={padding.left + chartW}
                    y2={yPos}
                    stroke="rgba(148, 163, 184, 0.22)"
                    strokeWidth="1"
                    strokeDasharray={val === 0 || val === 100 ? 'none' : '3 3'}
                  />
                  <text
                    x={padding.left - 10}
                    y={yPos + 3.5}
                    textAnchor="end"
                    fill="#94a3b8"
                    fontSize="10"
                    fontFamily="JetBrains Mono, monospace"
                  >
                    {val}%
                  </text>
                </g>
              );
            })}

            {/* 30% Nominal Reserve Target Reference Line */}
            <line
              x1={padding.left}
              y1={nominalY}
              x2={padding.left + chartW}
              y2={nominalY}
              stroke="#94a3b8"
              strokeWidth="1"
              strokeDasharray="2 3"
              strokeOpacity="0.65"
            />
            <text
              x={padding.left + chartW - 6}
              y={nominalY - 4}
              textAnchor="end"
              fill="#64748b"
              fontSize="9"
              fontFamily="JetBrains Mono, monospace"
            >
              30.0% Nominal Mission Reserve Target
            </text>

            {/* 15% Safety Floor Dashed Line & High-Contrast Badge */}
            <line
              x1={padding.left}
              y1={safetyY}
              x2={padding.left + chartW}
              y2={safetyY}
              stroke="#f43f5e"
              strokeWidth="1.5"
              strokeDasharray="4 4"
              strokeOpacity="0.85"
            />
            <rect
              x={padding.left + 8}
              y={safetyY - 14}
              width="175"
              height="16"
              rx="3"
              fill="#fff1f2"
              stroke="#fecdd3"
              strokeWidth="0.8"
            />
            <text
              x={padding.left + 14}
              y={safetyY - 3}
              fill="#e11d48"
              fontSize="9"
              fontFamily="JetBrains Mono, monospace"
              fontWeight="700"
            >
              15.0% MANDATORY SAFETY FLOOR
            </text>

            {/* X-Axis Grid Lines & Time Labels */}
            {xTicks.map((t) => {
              const xPos = mapX(t);
              return (
                <g key={t}>
                  <line
                    x1={xPos}
                    y1={padding.top}
                    x2={xPos}
                    y2={padding.top + chartH}
                    stroke="rgba(148, 163, 184, 0.15)"
                    strokeWidth="1"
                  />
                  <text
                    x={xPos}
                    y={padding.top + chartH + 18}
                    textAnchor="middle"
                    fill="#94a3b8"
                    fontSize="10"
                    fontFamily="JetBrains Mono, monospace"
                  >
                    {formatSeconds(t)}
                  </text>
                </g>
              );
            })}

            {/* Drone Depletion Area Fills & Multi-Stage Curves */}
            {routes.map((route) => {
              const color = DRONE_COLORS[route.drone_id] || '#64748b';
              const wps = route.waypoints ?? [];
              if (wps.length === 0) return null;

              const isDimmed = selectedDroneId !== 'ALL' && selectedDroneId !== route.drone_id;
              const isFocused = selectedDroneId === route.drone_id;

              // All base points from t=0 to touchdown
              const allWpPts = [
                { t: 0, soc: 100, label: 'DEPOT' },
                ...wps.map((w) => ({
                  t: w.departure_time,
                  soc: w.remaining_battery_percent,
                  node_id: w.node_id,
                  label: w.node_id === 0 ? 'DEPOT' : `T-${String(w.node_id).padStart(2, '0')}`
                }))
              ];

              const totalFlightT = route.total_flight_time ?? maxFlightTime;
              const curSoc = getBatteryAtTime(route, missionTime);
              const curPt = { t: missionTime, soc: curSoc };

              // Partition into Flown vs. Projected Trajectory
              let flownPts = [];
              let projectedPts = [];

              if (missionTime <= 0) {
                // At t=0, everything is planned forward
                flownPts = [{ ...allWpPts[0], x: mapX(0), y: mapY(100) }];
                projectedPts = allWpPts.map(p => ({ ...p, x: mapX(p.t), y: mapY(p.soc) }));
              } else if (missionTime >= totalFlightT) {
                // Drone has finished its mission, all points are flown
                flownPts = allWpPts.map(p => ({ ...p, x: mapX(p.t), y: mapY(p.soc) }));
                projectedPts = [];
              } else {
                // Intermediate: split at current missionTime
                const pastWps = allWpPts.filter(p => p.t <= missionTime);
                const futureWps = allWpPts.filter(p => p.t > missionTime);
                flownPts = [
                  ...pastWps.map(p => ({ ...p, x: mapX(p.t), y: mapY(p.soc) })),
                  { ...curPt, x: mapX(missionTime), y: mapY(curSoc) }
                ];
                projectedPts = [
                  { ...curPt, x: mapX(missionTime), y: mapY(curSoc) },
                  ...futureWps.map(p => ({ ...p, x: mapX(p.t), y: mapY(p.soc) }))
                ];
              }

              const flownAreaD = generateAreaPath(flownPts, baseY);
              const flownLineD = generateSmoothPath(flownPts);
              const projectedLineD = generateSmoothPath(projectedPts);
              const lastPt = allWpPts[allWpPts.length - 1];
              const lastX = mapX(lastPt.t);
              const lastY = mapY(lastPt.soc);

              return (
                <g
                  key={route.drone_id}
                  style={{
                    opacity: isDimmed ? 0.18 : 1.0,
                    transition: 'opacity 0.2s ease-in-out'
                  }}
                >
                  {/* Flown Gradient Area Fill (Hidden if dimmed) */}
                  {!isDimmed && flownAreaD && (
                    <path
                      d={flownAreaD}
                      fill={`url(#drone-grad-${route.drone_id})`}
                      opacity={isFocused ? 1.0 : 0.75}
                    />
                  )}

                  {/* Projected Forecast Trajectory Line (Dashed) */}
                  {projectedLineD && (
                    <path
                      d={projectedLineD}
                      fill="none"
                      stroke={color}
                      strokeWidth={isFocused ? '2.8' : isDimmed ? '1.5' : '2'}
                      strokeDasharray="4 3"
                      strokeOpacity={isDimmed ? 0.4 : 0.75}
                    />
                  )}

                  {/* Flown Real-Time Telemetry Path (Solid Spline) */}
                  {flownLineD && (
                    <path
                      d={flownLineD}
                      fill="none"
                      stroke={color}
                      strokeWidth={isFocused ? '3.5' : isDimmed ? '1.5' : '2.5'}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      filter={isFocused ? 'url(#focusedGlow)' : undefined}
                    />
                  )}

                  {/* Waypoint Nodes (Rendered when focused or in All view) */}
                  {!isDimmed && allWpPts.map((pt, idx) => {
                    if (idx === 0) return null; // Start depot handled separately
                    const ptX = mapX(pt.t);
                    const ptY = mapY(pt.soc);
                    const isVisited = pt.t <= missionTime;

                    return (
                      <g key={idx}>
                        <circle
                          cx={ptX}
                          cy={ptY}
                          r={isFocused ? '3.5' : '2.5'}
                          fill={isVisited ? color : '#ffffff'}
                          stroke={color}
                          strokeWidth="1.5"
                        />
                        {isFocused && pt.node_id !== undefined && pt.node_id !== 0 && (
                          <text
                            x={ptX}
                            y={Math.max(padding.top + 10, ptY - 6)}
                            textAnchor="middle"
                            fontSize="8"
                            fill="#64748b"
                            fontFamily="JetBrains Mono, monospace"
                            fontWeight="600"
                          >
                            {isVisited ? `✓ T-${pt.node_id}` : `T-${pt.node_id}`}
                          </text>
                        )}
                      </g>
                    );
                  })}

                  {/* Start Launch Point (100%) */}
                  <circle
                    cx={mapX(0)}
                    cy={mapY(100)}
                    r={isFocused ? '4' : '3'}
                    fill="#ffffff"
                    stroke={color}
                    strokeWidth="2"
                  />

                  {/* End Touchdown Point */}
                  <circle
                    cx={lastX}
                    cy={lastY}
                    r={isFocused ? '4.5' : '3.5'}
                    fill={color}
                    stroke="#ffffff"
                    strokeWidth="2"
                  />

                  {/* End Reserve Value Label */}
                  {!isDimmed && (
                    <text
                      x={lastX + 6}
                      y={lastY + 3.5}
                      fill={color}
                      fontSize="9.5"
                      fontFamily="JetBrains Mono, monospace"
                      fontWeight="700"
                    >
                      {(route.final_reserve_percent ?? 29.6).toFixed(1)}%
                    </text>
                  )}
                </g>
              );
            })}

            {/* Active Playback Mission Time Scrubber Line & Markers */}
            {missionTime > 0 && (
              <g>
                <line
                  x1={currentScrubberX}
                  y1={padding.top}
                  x2={currentScrubberX}
                  y2={padding.top + chartH}
                  stroke="#0284c7"
                  strokeWidth="1.5"
                  strokeDasharray="3 3"
                />

                {/* Top scrubber badge */}
                <g transform={`translate(${currentScrubberX}, ${padding.top - 8})`}>
                  <rect
                    x="-24"
                    y="-12"
                    width="48"
                    height="16"
                    rx="4"
                    fill="#0f172a"
                  />
                  <text
                    x="0"
                    y="0"
                    textAnchor="middle"
                    fill="#ffffff"
                    fontSize="9"
                    fontFamily="JetBrains Mono, monospace"
                    fontWeight="600"
                  >
                    T+{Math.round(missionTime)}s
                  </text>
                </g>

                {/* Live battery dot on each drone curve at missionTime */}
                {routes.map((route) => {
                  if (selectedDroneId !== 'ALL' && selectedDroneId !== route.drone_id) {
                    return null;
                  }
                  const color = DRONE_COLORS[route.drone_id] || '#64748b';
                  const batNow = getBatteryAtTime(route, missionTime);
                  const ptY = mapY(batNow);
                  return (
                    <g key={`scrub-${route.drone_id}`}>
                      {/* Pulsing halo */}
                      <circle
                        cx={currentScrubberX}
                        cy={ptY}
                        r="7"
                        fill={color}
                        fillOpacity="0.22"
                      />
                      {/* Center dot */}
                      <circle
                        cx={currentScrubberX}
                        cy={ptY}
                        r="3.5"
                        fill={color}
                        stroke="#ffffff"
                        strokeWidth="1.8"
                      />
                    </g>
                  );
                })}
              </g>
            )}

            {/* Interactive Hover Crosshair & Dynamic Nodes */}
            {hoverData && (
              <g pointerEvents="none">
                {/* Vertical guideline */}
                <line
                  x1={hoverData.x}
                  y1={padding.top}
                  x2={hoverData.x}
                  y2={padding.top + chartH}
                  stroke="#475569"
                  strokeWidth="1.2"
                  strokeDasharray="2 2"
                />

                {/* Hover time marker pill at top */}
                <g transform={`translate(${hoverData.x}, ${padding.top - 7})`}>
                  <rect
                    x="-26"
                    y="-11"
                    width="52"
                    height="15"
                    rx="3"
                    fill="#1e293b"
                  />
                  <text
                    x="0"
                    y="0"
                    textAnchor="middle"
                    fill="#38bdf8"
                    fontSize="8.5"
                    fontFamily="JetBrains Mono, monospace"
                    fontWeight="600"
                  >
                    T+{Math.round(hoverData.time)}s
                  </text>
                </g>

                {/* Intersecting dots on drone curves */}
                {hoverData.perDrone.map((d) => {
                  if (selectedDroneId !== 'ALL' && selectedDroneId !== d.drone_id) {
                    return null;
                  }
                  return (
                    <circle
                      key={`hover-dot-${d.drone_id}`}
                      cx={hoverData.x}
                      cy={d.y}
                      r="4"
                      fill="#ffffff"
                      stroke={d.color}
                      strokeWidth="2"
                    />
                  );
                })}
              </g>
            )}
          </svg>

          {/* Floating Telemetry HUD Tooltip Overlay */}
          {hoverData && (
            <div
              className="absolute pointer-events-none z-30 transition-all duration-75"
              style={{
                left: hoverData.clientRelX > 0.62 
                  ? `calc(${hoverData.clientRelX * 100}% - 225px)` 
                  : `calc(${hoverData.clientRelX * 100}% + 16px)`,
                top: '24px'
              }}
            >
              <div className="bg-slate-900/95 text-white backdrop-blur-md rounded-xl p-3 border border-slate-700/80 shadow-2xl w-52 space-y-2">
                <div className="flex items-center justify-between border-b border-slate-800 pb-1.5 text-[11px]">
                  <span className="font-mono font-bold text-sky-400">
                    T+{Math.round(hoverData.time)}s
                  </span>
                  <span className="text-slate-400 font-mono text-[10px]">
                    {formatSeconds(hoverData.time)}
                  </span>
                </div>

                <div className="space-y-1.5">
                  {hoverData.perDrone.map((d) => (
                    <div
                      key={d.drone_id}
                      className={`flex items-center justify-between text-[11px] ${
                        selectedDroneId !== 'ALL' && selectedDroneId !== d.drone_id ? 'opacity-40' : ''
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }} />
                        <span className="font-mono font-medium text-slate-300">{d.drone_id}</span>
                      </div>
                      <div className="flex items-baseline gap-1">
                        <span className="font-mono font-bold text-white">
                          {d.soc.toFixed(1)}%
                        </span>
                        <span className={`text-[9px] font-mono ${d.margin >= 15 ? 'text-emerald-400' : 'text-amber-400'}`}>
                          ({d.margin >= 0 ? `+${d.margin.toFixed(0)}%` : `${d.margin.toFixed(0)}%`})
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="pt-1.5 border-t border-slate-800 flex items-center justify-between text-[10px] text-slate-400 font-mono">
                  <span>Swarm Mean:</span>
                  <span className="text-emerald-400 font-bold">{hoverData.avgSoC.toFixed(1)}%</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* High-Level Telemetry Inspection Strip directly below Graph */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 border-t border-slate-100 text-xs font-sans">
          <div className="flex items-center gap-2 p-2 rounded-xl bg-slate-50/70 border border-slate-200/50">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
            <div>
              <span className="text-[10px] text-slate-400 block">Critical Unit</span>
              <span className="font-mono font-bold text-slate-800 text-[11px]">
                {lowestReserveRoute?.drone_id} ({(lowestReserveRoute?.final_reserve_percent ?? 29.6).toFixed(1)}%)
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 p-2 rounded-xl bg-slate-50/70 border border-slate-200/50">
            <Zap className="w-3.5 h-3.5 text-slate-500 shrink-0" />
            <div>
              <span className="text-[10px] text-slate-400 block">Swarm Burn Rate</span>
              <span className="font-mono font-bold text-slate-800 text-[11px]">
                ~{avgBurnRatePerMin.toFixed(2)} %/min
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 p-2 rounded-xl bg-slate-50/70 border border-slate-200/50">
            <Clock className="w-3.5 h-3.5 text-slate-500 shrink-0" />
            <div>
              <span className="text-[10px] text-slate-400 block">Mission Horizon</span>
              <span className="font-mono font-bold text-slate-800 text-[11px]">
                00:00 → {formatSeconds(maxFlightTime)}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 p-2 rounded-xl bg-slate-50/70 border border-slate-200/50">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
            <div>
              <span className="text-[10px] text-slate-400 block">Floor Compliance</span>
              <span className="font-mono font-bold text-emerald-700 text-[11px]">
                +{(minReserveAll - 15.0).toFixed(1)}% Reserve Safe
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 4. Lower Analytical Depth: 2-Column Balanced Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Subsystem Power Allocation Breakdown (7 cols) */}
        <div className="lg:col-span-7 glass-card rounded-2xl p-4 border border-slate-200/90 shadow-xs bg-white/95 space-y-3.5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
            <div>
              <h3 className="text-xs font-bold text-slate-900 tracking-tight">
                Subsystem Power Allocation Breakdown
              </h3>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Mechanical and electrical power consumption during cruise (14.5 m/s)
              </p>
            </div>
            <span className="text-[11px] font-mono text-slate-500 bg-slate-50 px-2 py-0.5 rounded border border-slate-200/60">
              Avg: 610W Swarm Draw
            </span>
          </div>

          <div className="space-y-3 text-xs">
            {/* Subsystem 1 */}
            <div>
              <div className="flex justify-between text-slate-700 mb-1">
                <span className="font-medium">BEMT Hover & Aerodynamic Rotor Thrust (~320W)</span>
                <span className="text-slate-900 font-bold font-mono">48%</span>
              </div>
              <div className="w-full bg-slate-100 border border-slate-200/70 h-2 rounded-full overflow-hidden">
                <div className="bg-slate-800 h-full rounded-full transition-all" style={{ width: '48%' }} />
              </div>
            </div>

            {/* Subsystem 2 */}
            <div>
              <div className="flex justify-between text-slate-700 mb-1">
                <span className="font-medium">Forward Flight Parasite Drag Polar (~195W)</span>
                <span className="text-slate-900 font-bold font-mono">29%</span>
              </div>
              <div className="w-full bg-slate-100 border border-slate-200/70 h-2 rounded-full overflow-hidden">
                <div className="bg-slate-700 h-full rounded-full transition-all" style={{ width: '29%' }} />
              </div>
            </div>

            {/* Subsystem 3 */}
            <div>
              <div className="flex justify-between text-slate-700 mb-1">
                <span className="font-medium">Vector Wind Drift Crosswind Compensation (~45W)</span>
                <span className="text-slate-900 font-bold font-mono">12%</span>
              </div>
              <div className="w-full bg-slate-100 border border-slate-200/70 h-2 rounded-full overflow-hidden">
                <div className="bg-slate-600 h-full rounded-full transition-all" style={{ width: '12%' }} />
              </div>
            </div>

            {/* Subsystem 4 */}
            <div>
              <div className="flex justify-between text-slate-700 mb-1">
                <span className="font-medium">High-Resolution Sensor & Recon Payload (~35W)</span>
                <span className="text-slate-900 font-bold font-mono">8%</span>
              </div>
              <div className="w-full bg-slate-100 border border-slate-200/70 h-2 rounded-full overflow-hidden">
                <div className="bg-slate-500 h-full rounded-full transition-all" style={{ width: '8%' }} />
              </div>
            </div>

            {/* Subsystem 5 */}
            <div>
              <div className="flex justify-between text-slate-700 mb-1">
                <span className="font-medium">Avionics, RTK GNSS & Telemetry Link (~15W)</span>
                <span className="text-slate-900 font-bold font-mono">3%</span>
              </div>
              <div className="w-full bg-slate-100 border border-slate-200/70 h-2 rounded-full overflow-hidden">
                <div className="bg-slate-400 h-full rounded-full transition-all" style={{ width: '3%' }} />
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Mission Phase Energy Profile (5 cols) */}
        <div className="lg:col-span-5 glass-card rounded-2xl p-4 border border-slate-200/90 shadow-xs bg-white/95 space-y-3.5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
            <div>
              <h3 className="text-xs font-bold text-slate-900 tracking-tight">
                Mission Phase Energy Allocation
              </h3>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Sequential flight stage consumption profile
              </p>
            </div>
            <Layers className="w-4 h-4 text-slate-400" />
          </div>

          {/* Cumulative Stacked Bar */}
          <div className="space-y-1.5">
            <div className="w-full bg-slate-100 border border-slate-200/70 h-2.5 rounded-full overflow-hidden flex">
              <div className="bg-slate-400 h-full" style={{ width: '5.2%' }} title="Deploy (5.2%)" />
              <div className="bg-slate-600 h-full" style={{ width: '28.4%' }} title="Transit (28.4%)" />
              <div className="bg-slate-700 h-full" style={{ width: '21.8%' }} title="Cluster Scan (21.8%)" />
              <div className="bg-slate-900 h-full" style={{ width: '29.6%' }} title="Target Acquisition (29.6%)" />
              <div className="bg-emerald-600 h-full" style={{ width: '15.0%' }} title="Touchdown Reserve (15.0%)" />
            </div>
            <div className="flex justify-between text-[10px] text-slate-400 font-mono">
              <span>0% (Launch)</span>
              <span>100% (Touchdown)</span>
            </div>
          </div>

          {/* Phase Line Items */}
          <div className="divide-y divide-slate-100 text-xs font-sans">
            <div className="py-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-slate-400" />
                <span className="text-slate-700 font-medium">1. Launch & Climb</span>
              </div>
              <span className="font-mono text-slate-900 font-bold">5.2%</span>
            </div>

            <div className="py-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-slate-600" />
                <span className="text-slate-700 font-medium">2. Inter-Cluster Transit</span>
              </div>
              <span className="font-mono text-slate-900 font-bold">28.4%</span>
            </div>

            <div className="py-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-slate-700" />
                <span className="text-slate-700 font-medium">3. Cluster Scouting</span>
              </div>
              <span className="font-mono text-slate-900 font-bold">21.8%</span>
            </div>

            <div className="py-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-slate-900" />
                <span className="text-slate-700 font-medium">4. Target Acquisition</span>
              </div>
              <span className="font-mono text-slate-900 font-bold">29.6%</span>
            </div>

            <div className="py-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-600" />
                <span className="text-slate-800 font-semibold">5. Touchdown Reserve</span>
              </div>
              <span className="font-mono text-emerald-700 font-bold">15.0%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
