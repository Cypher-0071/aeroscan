import React, { useState, useMemo, useRef } from 'react';
import { 
  Activity, 
  BatteryCharging, 
  Navigation, 
  ShieldCheck, 
  Compass, 
  Zap, 
  ArrowUpRight,
  ChevronDown,
  ChevronUp,
  Clock,
  CheckCircle2,
  Gauge,
  Wind,
  Plane,
  AlertTriangle,
  Radio
} from 'lucide-react';

function formatTime(sec) {
  if (isNaN(sec) || sec < 0) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function getCardinalDirection(deg) {
  const normalized = ((deg % 360) + 360) % 360;
  const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  const index = Math.round(normalized / 45) % 8;
  return directions[index];
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

    // Monotonicity clamping: if p1.y <= p2.y, control points must stay between p1.y and p2.y
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

export default function FleetTelemetry({
  instance,
  schedule,
  telemetry,
  missionTime = 0,
  setMissionTime,
  windSpeed = 0,
  windDir = 0,
}) {
  const drones = instance?.drones ?? [];
  const [selectedDroneId, setSelectedDroneId] = useState(drones[0]?.id ?? 'UAV-01');
  const [showRawTable, setShowRawTable] = useState(false);
  const [hoverData, setHoverData] = useState(null);

  const telemetryList = telemetry ?? [];
  const telemMap = useMemo(() => {
    const map = {};
    telemetryList.forEach((t) => {
      map[t.drone_id] = t;
    });
    return map;
  }, [telemetryList]);

  const activeDroneTelem = telemMap[selectedDroneId] || telemetryList[0] || {
    drone_id: selectedDroneId,
    battery_percent: 100,
    speed_mps: 14.5,
    z: 60,
    heading_deg: 45,
    flight_phase: 'CRUISE',
    target_name: 'DEPOT',
    x: 0,
    y: 0,
    power_watts: 180,
  };

  // Fleet overview aggregates
  const avgBat = telemetryList.length > 0
    ? telemetryList.reduce((sum, t) => sum + (t.battery_percent ?? 100), 0) / telemetryList.length
    : 100;
  const activeCount = telemetryList.filter((t) => t.flight_phase !== 'RECOVERED' && t.flight_phase !== 'STANDBY').length;

  // Total planned distance of full mission
  const totalDistKm = (schedule?.assigned_routes ?? []).reduce(
    (acc, r) => acc + ((r.total_flight_time ?? 0) * 14.5) / 1000,
    0
  );

  // Actual distance covered by fleet up to current missionTime
  const currentDistKm = useMemo(() => {
    const routes = schedule?.assigned_routes ?? [];
    if (routes.length === 0) return 0;
    return routes.reduce((acc, r) => {
      const tFlown = Math.min(missionTime, r.total_flight_time ?? 0);
      return acc + (tFlown * 14.5) / 1000;
    }, 0);
  }, [schedule, missionTime]);

  // Selected route and waypoints
  const selectedRoute = (schedule?.assigned_routes ?? []).find(
    (r) => r.drone_id === selectedDroneId
  );
  const waypoints = selectedRoute?.waypoints ?? [];
  const targets = instance?.targets ?? [];

  // Mission max duration for scaling
  const maxTime = useMemo(() => {
    const allWps = (schedule?.assigned_routes ?? []).flatMap((r) => r.waypoints ?? []);
    const maxDep = allWps.length > 0 ? Math.max(...allWps.map((w) => w.departure_time)) : 600;
    return Math.max(maxDep, 600);
  }, [schedule]);

  // Coordinate scales for 800 x 220 viewBox
  const chartW = 800;
  const chartH = 220;
  const padLeft = 55;
  const padRight = 30;
  const padTop = 20;
  const padBottom = 35;
  const plotW = chartW - padLeft - padRight;
  const plotH = chartH - padTop - padBottom;

  const timeToX = (t) => padLeft + (Math.max(0, Math.min(maxTime, t)) / maxTime) * plotW;
  const socToY = (soc) => padTop + plotH - (Math.max(0, Math.min(100, soc)) / 100) * plotH;
  const altToY = (alt) => padTop + plotH - (Math.max(0, Math.min(80, alt)) / 80) * plotH;

  // Battery points mapped to chart
  const batteryPoints = useMemo(() => {
    if (waypoints.length === 0) {
      return [
        { x: padLeft, y: socToY(100), t: 0, soc: 100 },
        { x: padLeft + plotW, y: socToY(100), t: maxTime, soc: 100 },
      ];
    }
    return waypoints.map((w) => ({
      x: timeToX(w.departure_time),
      y: socToY(w.remaining_battery_percent),
      t: w.departure_time,
      soc: w.remaining_battery_percent,
      node_id: w.node_id,
    }));
  }, [waypoints, maxTime]);

  // Current Live Scrubber Position
  const currentX = timeToX(missionTime);
  const currentSoc = activeDroneTelem.battery_percent ?? 100;
  const currentAlt = activeDroneTelem.z ?? 60;
  const currentSocY = socToY(currentSoc);
  const currentAltY = altToY(currentAlt);

  // Live connecting point on battery chart
  const currentBatPt = useMemo(() => ({
    x: currentX,
    y: currentSocY,
    t: missionTime,
    soc: currentSoc,
  }), [currentX, currentSocY, missionTime, currentSoc]);

  // Split battery trajectory: Flown Telemetry (<= missionTime) vs Planned Ahead (> missionTime)
  const { pastBatteryPoints, futureBatteryPoints } = useMemo(() => {
    if (batteryPoints.length === 0) {
      return { pastBatteryPoints: [], futureBatteryPoints: [] };
    }
    const past = batteryPoints.filter((p) => p.t <= missionTime);
    const future = batteryPoints.filter((p) => p.t > missionTime);

    const fullPast = [...past, currentBatPt];
    const fullFuture = [currentBatPt, ...future];

    return { pastBatteryPoints: fullPast, futureBatteryPoints: fullFuture };
  }, [batteryPoints, missionTime, currentBatPt]);

  const pastBatteryLinePath = useMemo(() => generateSmoothPath(pastBatteryPoints), [pastBatteryPoints]);
  const pastBatteryAreaPath = useMemo(() => generateAreaPath(pastBatteryPoints, padTop + plotH), [pastBatteryPoints]);
  const futureBatteryLinePath = useMemo(() => generateSmoothPath(futureBatteryPoints), [futureBatteryPoints]);

  // Realistic aerodynamic altitude profile
  const altPoints = useMemo(() => {
    if (waypoints.length < 2) {
      return [
        { x: padLeft, y: altToY(0), t: 0, alt: 0 },
        { x: padLeft + plotW, y: altToY(0), t: maxTime, alt: 0 },
      ];
    }
    const tStart = 0;
    const tEnd = waypoints[waypoints.length - 1].departure_time;
    const climbTime = Math.min(22, tEnd * 0.1);
    const descentStart = Math.max(tEnd - Math.min(25, tEnd * 0.12), climbTime + 15);

    const pts = [
      { t: tStart, alt: 0, label: 'DEPOT' },
      { t: climbTime, alt: 60, label: 'CRUISE LEVEL' },
    ];

    for (let i = 1; i < waypoints.length - 1; i++) {
      const wp = waypoints[i];
      pts.push({
        t: wp.departure_time,
        alt: 60,
        label: wp.node_id === 0 ? 'DEPOT' : `T-${wp.node_id.toString().padStart(2, '0')}`,
      });
    }

    if (descentStart > climbTime) {
      pts.push({ t: descentStart, alt: 60, label: 'DESCENT' });
    }
    pts.push({ t: tEnd, alt: 0, label: 'RECOVERY' });

    return pts.map((p) => ({
      x: timeToX(p.t),
      y: altToY(p.alt),
      t: p.t,
      alt: p.alt,
      label: p.label,
    }));
  }, [waypoints, maxTime]);

  // Live connecting point on altitude chart
  const currentAltPt = useMemo(() => ({
    x: currentX,
    y: currentAltY,
    t: missionTime,
    alt: currentAlt,
  }), [currentX, currentAltY, missionTime, currentAlt]);

  // Split altitude trajectory: Flown vs Planned Ahead
  const { pastAltPoints, futureAltPoints } = useMemo(() => {
    if (altPoints.length === 0) {
      return { pastAltPoints: [], futureAltPoints: [] };
    }
    const past = altPoints.filter((p) => p.t <= missionTime);
    const future = altPoints.filter((p) => p.t > missionTime);

    const fullPast = [...past, currentAltPt];
    const fullFuture = [currentAltPt, ...future];

    return { pastAltPoints: fullPast, futureAltPoints: fullFuture };
  }, [altPoints, missionTime, currentAltPt]);

  const pastAltLinePath = useMemo(() => generateSmoothPath(pastAltPoints), [pastAltPoints]);
  const pastAltAreaPath = useMemo(() => generateAreaPath(pastAltPoints, padTop + plotH), [pastAltPoints]);
  const futureAltLinePath = useMemo(() => generateSmoothPath(futureAltPoints), [futureAltPoints]);

  // Time grid ticks (5 intervals)
  const timeTicks = useMemo(() => {
    const step = maxTime / 5;
    return [0, 1, 2, 3, 4, 5].map((i) => {
      const t = i * step;
      return { t, x: timeToX(t), label: formatTime(t) };
    });
  }, [maxTime]);

  // Safety floor Y level (15%)
  const safetyFloorY = socToY(15);

  // Interactive mouse scrubbing
  const handleChartClick = (e) => {
    if (!setMissionTime) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const relX = (e.clientX - rect.left) / rect.width;
    const clickedX = relX * chartW;
    const clampedPlotX = Math.max(padLeft, Math.min(padLeft + plotW, clickedX));
    const targetT = ((clampedPlotX - padLeft) / plotW) * maxTime;
    setMissionTime(targetT);
  };

  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const relX = (e.clientX - rect.left) / rect.width;
    const currentHoverX = relX * chartW;
    if (currentHoverX < padLeft || currentHoverX > padLeft + plotW) {
      setHoverData(null);
      return;
    }
    const hoverT = ((currentHoverX - padLeft) / plotW) * maxTime;

    // Approximate SoC at hoverT
    let projectedSoc = 100;
    if (batteryPoints.length > 1) {
      const nextIdx = batteryPoints.findIndex((p) => p.t >= hoverT);
      if (nextIdx <= 0) {
        projectedSoc = batteryPoints[0].soc;
      } else if (nextIdx >= batteryPoints.length) {
        projectedSoc = batteryPoints[batteryPoints.length - 1].soc;
      } else {
        const pA = batteryPoints[nextIdx - 1];
        const pB = batteryPoints[nextIdx];
        const frac = (hoverT - pA.t) / (pB.t - pA.t || 1);
        projectedSoc = pA.soc + frac * (pB.soc - pA.soc);
      }
    }

    setHoverData({
      x: currentHoverX,
      t: hoverT,
      soc: Math.max(0, Math.min(100, projectedSoc)),
    });
  };

  return (
    <div className="space-y-4">
      {/* 1. Header Bar: Clean, uncluttered, high-impact */}
      <div className="glass-card rounded-2xl px-5 py-3.5 flex flex-wrap items-center justify-between gap-4 border border-slate-200/80 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-sky-50 border border-sky-200/80 flex items-center justify-center text-sky-600 shadow-sm">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-semibold text-slate-900 tracking-tight">Fleet Telemetry</h1>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200/70">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                10Hz Live
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">Real-time kinematics & energy telemetry</p>
          </div>
        </div>

        {/* Minimal Metric Capsules */}
        <div className="flex items-center gap-2 sm:gap-3 text-xs">
          <div className="px-3 py-1.5 rounded-xl bg-white/70 border border-slate-200/80 shadow-xs flex items-center gap-2">
            <span className="text-slate-400">Sorties:</span>
            <span className="font-mono font-semibold text-slate-900">{activeCount} / {drones.length}</span>
          </div>
          <div className="px-3 py-1.5 rounded-xl bg-white/70 border border-slate-200/80 shadow-xs flex items-center gap-2">
            <span className="text-slate-400">Fleet Avg SoC:</span>
            <span className={`font-mono font-semibold ${avgBat >= 25 ? 'text-emerald-600' : 'text-rose-600'}`}>
              {avgBat.toFixed(1)}%
            </span>
          </div>
          <div className="px-3 py-1.5 rounded-xl bg-white/70 border border-slate-200/80 shadow-xs flex items-center gap-2">
            <span className="text-slate-400">Flown / Plan:</span>
            <span className="font-mono font-semibold text-sky-700">
              {currentDistKm.toFixed(1)} <span className="text-slate-400 font-normal">/ {totalDistKm.toFixed(1)} km</span>
            </span>
          </div>
          <div className="px-3 py-1.5 rounded-xl bg-sky-50 border border-sky-200/80 shadow-xs flex items-center gap-2 text-sky-800">
            <Clock className="w-3.5 h-3.5 text-sky-600" />
            <span className="font-mono font-bold">T+{missionTime.toFixed(0)}s</span>
          </div>
        </div>
      </div>

      {/* 2. Interactive UAV Selector Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {drones.map((drone) => {
          const telem = telemMap[drone.id] || {};
          const isSelected = drone.id === selectedDroneId;
          const soc = telem.battery_percent ?? 100;
          const phase = telem.flight_phase ?? 'CRUISE';
          const isCruising = phase === 'CRUISE' || phase === 'TRANSIT_CRUISE';
          const isLowBat = soc < 15;

          return (
            <button
              key={drone.id}
              onClick={() => setSelectedDroneId(drone.id)}
              className={`p-3.5 rounded-2xl border text-left transition-all cursor-pointer relative overflow-hidden group ${
                isSelected
                  ? 'glass-card border-sky-400/90 shadow-md bg-white/95 ring-2 ring-sky-300/40'
                  : 'bg-white/60 border-slate-200/70 hover:bg-white/90 hover:border-slate-300 shadow-xs'
              }`}
            >
              {isSelected && (
                <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-sky-400 to-emerald-400" />
              )}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${isCruising ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`} />
                  <span className="font-mono font-bold text-sm text-slate-900 tracking-tight">{drone.id}</span>
                </div>
                <span className={`text-[10px] font-medium px-2 py-0.5 rounded-md border ${
                  isCruising
                    ? 'bg-sky-50 text-sky-700 border-sky-200/80'
                    : 'bg-slate-100 text-slate-600 border-slate-200/70'
                }`}>
                  {phase}
                </span>
              </div>

              {/* Battery bar */}
              <div className="mt-2.5 space-y-1">
                <div className="flex justify-between text-[11px]">
                  <span className="text-slate-400 font-medium">SoC Level</span>
                  <span className={`font-mono font-bold ${isLowBat ? 'text-rose-600' : 'text-emerald-600'}`}>
                    {soc.toFixed(1)}%
                  </span>
                </div>
                <div className="w-full bg-slate-100 border border-slate-200/60 h-1.5 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      isLowBat ? 'bg-rose-500' : soc < 30 ? 'bg-amber-500' : 'bg-emerald-500'
                    }`}
                    style={{ width: `${Math.max(0, Math.min(100, soc))}%` }}
                  />
                </div>
              </div>

              {/* Quick telemetry metrics */}
              <div className="mt-2.5 pt-2 border-t border-slate-200/60 flex items-center justify-between text-[11px] font-mono text-slate-500">
                <span>Alt: <strong className="text-slate-800 font-semibold">{(telem.z ?? 60).toFixed(0)}m</strong></span>
                <span>Spd: <strong className="text-slate-800 font-semibold">{(telem.speed_mps ?? 14.5).toFixed(1)}m/s</strong></span>
                <span className="text-sky-700 font-semibold font-sans">
                  {telem.target_name ? `→ ${telem.target_name}` : 'DEPOT'}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* 3. Primary Workspace: Graphs Left (8 cols) & Flight Avionics Right (4 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Redesigned Kinematics Profiles (8 cols) */}
        <div className="lg:col-span-8 space-y-4">
          
          {/* Chart 1: Battery State of Charge (%) */}
          <div className="glass-card rounded-2xl p-4 space-y-3 border border-slate-200/80 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/70 pb-2.5">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-lg bg-emerald-50 border border-emerald-200/80 flex items-center justify-center text-emerald-600">
                  <BatteryCharging className="w-3.5 h-3.5" />
                </div>
                <div>
                  <h2 className="text-xs font-semibold text-slate-900 tracking-tight">Battery State of Charge (%)</h2>
                  <div className="flex items-center gap-3 text-[10px] text-slate-500 font-sans mt-0.5">
                    <span className="inline-flex items-center gap-1.5 font-medium text-emerald-700">
                      <span className="w-2.5 h-1 bg-emerald-500 rounded-full" />
                      Flown Telemetry (0s → T+{missionTime.toFixed(0)}s)
                    </span>
                    <span className="inline-flex items-center gap-1.5 font-medium text-sky-700">
                      <span className="w-2.5 h-0.5 border-t-2 border-dashed border-sky-500" />
                      Planned Trajectory Ahead
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 text-xs font-mono">
                <div className="px-2.5 py-1 rounded-lg bg-emerald-50 border border-emerald-200/80 text-emerald-800 font-bold">
                  Current: {currentSoc.toFixed(1)}% SoC
                </div>
                <div className="px-2.5 py-1 rounded-lg bg-slate-50 border border-slate-200/80 text-slate-600 font-medium">
                  Burned: {(100 - currentSoc).toFixed(1)}%
                </div>
                <div className="px-2.5 py-1 rounded-lg bg-slate-50 border border-slate-200/80 text-slate-600 font-medium" title="Projected reserve upon return to depot">
                  Est. Landing: {(selectedRoute?.final_reserve_percent ?? 100).toFixed(1)}%
                </div>
                {(selectedRoute?.final_reserve_percent ?? 100) >= 15 ? (
                  <span className="inline-flex items-center gap-1 text-[10px] text-emerald-600 font-sans font-medium px-2 py-0.5 rounded-md bg-emerald-50/80 border border-emerald-200/60">
                    <CheckCircle2 className="w-3 h-3" />
                    Floor Safe
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[10px] text-rose-600 font-sans font-medium px-2 py-0.5 rounded-md bg-rose-50 border border-rose-200">
                    <AlertTriangle className="w-3 h-3" />
                    Floor Warning
                  </span>
                )}
              </div>
            </div>

            {/* SVG Visualizer with Flown Telemetry vs Planned Trajectory */}
            <div
              className="h-56 w-full bg-gradient-to-b from-white to-slate-50/50 rounded-xl p-2 border border-slate-200/80 shadow-inner relative cursor-crosshair select-none"
              onClick={handleChartClick}
              onMouseMove={handleMouseMove}
              onMouseLeave={() => setHoverData(null)}
            >
              <svg className="w-full h-full" viewBox={`0 0 ${chartW} ${chartH}`} preserveAspectRatio="none">
                <defs>
                  {/* Battery area gradient for flown portion */}
                  <linearGradient id="batteryAreaGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.28" />
                    <stop offset="70%" stopColor="#059669" stopOpacity="0.08" />
                    <stop offset="100%" stopColor="#059669" stopOpacity="0.01" />
                  </linearGradient>

                  {/* Battery line stroke gradient */}
                  <linearGradient id="batteryLineGrad" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#059669" />
                    <stop offset="100%" stopColor="#10b981" />
                  </linearGradient>

                  {/* Safety floor danger zone gradient */}
                  <linearGradient id="dangerZoneGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ef4444" stopOpacity="0.10" />
                    <stop offset="100%" stopColor="#ef4444" stopOpacity="0.02" />
                  </linearGradient>

                  {/* Soft curve glow */}
                  <filter id="curveGlow" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#10b981" floodOpacity="0.35" />
                  </filter>
                </defs>

                {/* 15% Safety Floor Shaded Zone */}
                <rect
                  x={padLeft}
                  y={safetyFloorY}
                  width={plotW}
                  height={padTop + plotH - safetyFloorY}
                  fill="url(#dangerZoneGrad)"
                />

                {/* Horizontal Grid lines and labels */}
                {[100, 75, 50, 25, 0].map((socVal) => {
                  const y = socToY(socVal);
                  return (
                    <g key={socVal}>
                      <line
                        x1={padLeft}
                        y1={y}
                        x2={padLeft + plotW}
                        y2={y}
                        stroke="rgba(148, 163, 184, 0.25)"
                        strokeDasharray={socVal === 0 ? '0' : '3 3'}
                        strokeWidth="1"
                      />
                      <text
                        x={padLeft - 8}
                        y={y + 3.5}
                        textAnchor="end"
                        fontSize="9"
                        fill="#94a3b8"
                        fontFamily="ui-monospace, monospace"
                        fontWeight="500"
                      >
                        {socVal}%
                      </text>
                    </g>
                  );
                })}

                {/* 15% Reserve Safety Floor Line */}
                <line
                  x1={padLeft}
                  y1={safetyFloorY}
                  x2={padLeft + plotW}
                  y2={safetyFloorY}
                  stroke="#ef4444"
                  strokeWidth="1.2"
                  strokeDasharray="4 4"
                />
                <rect
                  x={padLeft + 6}
                  y={safetyFloorY - 14}
                  width="86"
                  height="12"
                  rx="3"
                  fill="#fee2e2"
                  stroke="#fca5a5"
                  strokeWidth="0.8"
                />
                <text
                  x={padLeft + 10}
                  y={safetyFloorY - 5}
                  fill="#b91c1c"
                  fontSize="7.5"
                  fontFamily="Inter, sans-serif"
                  fontWeight="600"
                >
                  15% SAFETY FLOOR
                </text>

                {/* Vertical Time Grid Ticks & Labels */}
                {timeTicks.map((tick) => (
                  <g key={tick.t}>
                    <line
                      x1={tick.x}
                      y1={padTop}
                      x2={tick.x}
                      y2={padTop + plotH}
                      stroke="rgba(148, 163, 184, 0.15)"
                      strokeWidth="1"
                    />
                    <text
                      x={tick.x}
                      y={padTop + plotH + 15}
                      textAnchor="middle"
                      fontSize="9"
                      fill="#94a3b8"
                      fontFamily="ui-monospace, monospace"
                    >
                      {tick.label}
                    </text>
                  </g>
                ))}

                {/* 1. Flown Area Under Curve (Up to missionTime) */}
                {pastBatteryAreaPath && (
                  <path d={pastBatteryAreaPath} fill="url(#batteryAreaGrad)" />
                )}

                {/* 2. Planned Trajectory Path Ahead (Dashed Sky Line) */}
                {futureBatteryLinePath && (
                  <path
                    d={futureBatteryLinePath}
                    fill="none"
                    stroke="#0284c7"
                    strokeWidth="2"
                    strokeDasharray="5 3"
                    strokeOpacity="0.75"
                  />
                )}

                {/* 3. Actual Flown Telemetry Path (Solid Vibrant Emerald Spline) */}
                {pastBatteryLinePath && (
                  <path
                    d={pastBatteryLinePath}
                    fill="none"
                    stroke="url(#batteryLineGrad)"
                    strokeWidth="3.2"
                    strokeLinecap="round"
                    filter="url(#curveGlow)"
                  />
                )}

                {/* Waypoint Nodes on Curve */}
                {batteryPoints.map((pt, idx) => {
                  const isScouted = pt.t <= missionTime;
                  return (
                    <g key={idx}>
                      <circle
                        cx={pt.x}
                        cy={pt.y}
                        r={isScouted ? '3.5' : '3'}
                        fill={isScouted ? '#059669' : '#ffffff'}
                        stroke={isScouted ? '#ffffff' : '#0284c7'}
                        strokeWidth={isScouted ? '2' : '1.5'}
                        strokeDasharray={isScouted ? '0' : '2 2'}
                      />
                      {pt.node_id !== undefined && pt.node_id !== 0 && (
                        <text
                          x={pt.x}
                          y={Math.max(padTop + 10, pt.y - 7)}
                          textAnchor="middle"
                          fontSize="8"
                          fill={isScouted ? '#059669' : '#0369a1'}
                          fontFamily="ui-monospace, monospace"
                          fontWeight="600"
                        >
                          {isScouted ? `✓ T-${pt.node_id}` : `T-${pt.node_id}`}
                        </text>
                      )}
                    </g>
                  );
                })}

                {/* Live Current Time Scrubber Line */}
                <line
                  x1={currentX}
                  y1={padTop}
                  x2={currentX}
                  y2={padTop + plotH}
                  stroke="#0284c7"
                  strokeWidth="1.8"
                  strokeDasharray="4 2"
                />

                {/* Current Live Marker Reticle */}
                <circle
                  cx={currentX}
                  cy={currentSocY}
                  r="7"
                  fill="rgba(2, 132, 199, 0.25)"
                />
                <circle
                  cx={currentX}
                  cy={currentSocY}
                  r="3.5"
                  fill="#0284c7"
                  stroke="#ffffff"
                  strokeWidth="1.8"
                />

                {/* Live Floating Tooltip Capsule */}
                <g transform={`translate(${Math.min(padLeft + plotW - 75, Math.max(padLeft + 5, currentX - 35))}, ${padTop + 6})`}>
                  <rect
                    width="70"
                    height="16"
                    rx="4"
                    fill="rgba(15, 23, 42, 0.85)"
                    backdropFilter="blur(4px)"
                  />
                  <text
                    x="35"
                    y="11.5"
                    textAnchor="middle"
                    fill="#ffffff"
                    fontSize="8.5"
                    fontFamily="ui-monospace, monospace"
                    fontWeight="600"
                  >
                    T+{missionTime.toFixed(0)}s • {currentSoc.toFixed(0)}%
                  </text>
                </g>

                {/* Hover Line & Marker */}
                {hoverData && (
                  <g>
                    <line
                      x1={hoverData.x}
                      y1={padTop}
                      x2={hoverData.x}
                      y2={padTop + plotH}
                      stroke="#64748b"
                      strokeWidth="1"
                      strokeDasharray="2 2"
                    />
                    <circle
                      cx={hoverData.x}
                      cy={socToY(hoverData.soc)}
                      r="4"
                      fill="#6366f1"
                      stroke="#ffffff"
                      strokeWidth="1.5"
                    />
                  </g>
                )}
              </svg>

              {/* Hover Tooltip Overlay */}
              {hoverData && (
                <div
                  className="absolute pointer-events-none -top-1 px-2.5 py-1 rounded-lg bg-slate-900/90 text-white text-[10px] font-mono shadow-lg border border-slate-700/60 backdrop-blur-md transform -translate-x-1/2 flex items-center gap-2 z-20"
                  style={{ left: `${(hoverData.x / chartW) * 100}%` }}
                >
                  <span className="text-slate-300">T+{Math.round(hoverData.t)}s</span>
                  <span className="text-emerald-400 font-bold">{hoverData.soc.toFixed(1)}%</span>
                </div>
              )}
            </div>
          </div>

          {/* Chart 2: Flight Altitude & Elevation Profile (m AGL) */}
          <div className="glass-card rounded-2xl p-4 space-y-3 border border-slate-200/80 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/70 pb-2.5">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-lg bg-sky-50 border border-sky-200/80 flex items-center justify-center text-sky-600">
                  <Plane className="w-3.5 h-3.5" />
                </div>
                <div>
                  <h2 className="text-xs font-semibold text-slate-900 tracking-tight">Flight Altitude Profile (m AGL)</h2>
                  <div className="flex items-center gap-3 text-[10px] text-slate-500 font-sans mt-0.5">
                    <span className="inline-flex items-center gap-1.5 font-medium text-sky-700">
                      <span className="w-2.5 h-1 bg-sky-600 rounded-full" />
                      Flown Altitude
                    </span>
                    <span className="inline-flex items-center gap-1.5 font-medium text-slate-500">
                      <span className="w-2.5 h-0.5 border-t-2 border-dashed border-sky-400" />
                      Planned Flight Envelope
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 text-xs font-mono">
                <span className="px-2.5 py-1 rounded-lg bg-sky-50 border border-sky-200/80 text-sky-800 font-bold">
                  {(activeDroneTelem.z ?? 60).toFixed(0)}m AGL
                </span>
                <span className="text-[11px] text-slate-400 font-sans">Cruise: 60m Nominal</span>
              </div>
            </div>

            {/* Altitude Profile SVG */}
            <div
              className="h-44 w-full bg-gradient-to-b from-white to-sky-50/30 rounded-xl p-2 border border-slate-200/80 shadow-inner relative cursor-crosshair select-none"
              onClick={handleChartClick}
            >
              <svg className="w-full h-full" viewBox={`0 0 ${chartW} ${chartH}`} preserveAspectRatio="none">
                <defs>
                  <linearGradient id="altAreaGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#0284c7" stopOpacity="0.22" />
                    <stop offset="75%" stopColor="#0284c7" stopOpacity="0.06" />
                    <stop offset="100%" stopColor="#0284c7" stopOpacity="0.01" />
                  </linearGradient>

                  <linearGradient id="altLineGrad" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#0284c7" />
                    <stop offset="100%" stopColor="#38bdf8" />
                  </linearGradient>
                </defs>

                {/* Altitude Grid Lines */}
                {[80, 60, 40, 20, 0].map((altVal) => {
                  const y = altToY(altVal);
                  return (
                    <g key={altVal}>
                      <line
                        x1={padLeft}
                        y1={y}
                        x2={padLeft + plotW}
                        y2={y}
                        stroke="rgba(148, 163, 184, 0.25)"
                        strokeDasharray={altVal === 0 ? '0' : '3 3'}
                        strokeWidth={altVal === 0 ? '1.5' : '1'}
                      />
                      <text
                        x={padLeft - 8}
                        y={y + 3.5}
                        textAnchor="end"
                        fontSize="9"
                        fill="#94a3b8"
                        fontFamily="ui-monospace, monospace"
                      >
                        {altVal}m
                      </text>
                    </g>
                  );
                })}

                {/* Nominal Cruise Guideline */}
                <line
                  x1={padLeft}
                  y1={altToY(60)}
                  x2={padLeft + plotW}
                  y2={altToY(60)}
                  stroke="#0284c7"
                  strokeWidth="1"
                  strokeDasharray="4 4"
                  strokeOpacity="0.5"
                />

                {/* Vertical Time Grid Ticks */}
                {timeTicks.map((tick) => (
                  <g key={tick.t}>
                    <line
                      x1={tick.x}
                      y1={padTop}
                      x2={tick.x}
                      y2={padTop + plotH}
                      stroke="rgba(148, 163, 184, 0.15)"
                      strokeWidth="1"
                    />
                    <text
                      x={tick.x}
                      y={padTop + plotH + 15}
                      textAnchor="middle"
                      fontSize="9"
                      fill="#94a3b8"
                      fontFamily="ui-monospace, monospace"
                    >
                      {tick.label}
                    </text>
                  </g>
                ))}

                {/* Filled Altitude Area for flown portion */}
                {pastAltAreaPath && (
                  <path d={pastAltAreaPath} fill="url(#altAreaGrad)" />
                )}

                {/* Planned Altitude Ahead (Dashed) */}
                {futureAltLinePath && (
                  <path
                    d={futureAltLinePath}
                    fill="none"
                    stroke="#0284c7"
                    strokeWidth="1.8"
                    strokeDasharray="4 3"
                    strokeOpacity="0.7"
                  />
                )}

                {/* Flown Altitude Vector (Solid) */}
                {pastAltLinePath && (
                  <path
                    d={pastAltLinePath}
                    fill="none"
                    stroke="url(#altLineGrad)"
                    strokeWidth="2.8"
                    strokeLinecap="round"
                  />
                )}

                {/* Altitude Waypoints */}
                {altPoints.map((pt, idx) => {
                  const isScouted = pt.t <= missionTime;
                  return (
                    <g key={idx}>
                      <circle
                        cx={pt.x}
                        cy={pt.y}
                        r="3"
                        fill={isScouted ? '#0284c7' : '#ffffff'}
                        stroke="#0284c7"
                        strokeWidth="1.8"
                        strokeDasharray={isScouted ? '0' : '2 2'}
                      />
                      {pt.label && pt.alt > 0 && (
                        <text
                          x={pt.x}
                          y={pt.y - 7}
                          textAnchor="middle"
                          fontSize="7.5"
                          fill={isScouted ? '#0284c7' : '#64748b'}
                          fontFamily="ui-monospace, monospace"
                          fontWeight="600"
                        >
                          {pt.label}
                        </text>
                      )}
                    </g>
                  );
                })}

                {/* Live Current Time Scrubber Line */}
                <line
                  x1={currentX}
                  y1={padTop}
                  x2={currentX}
                  y2={padTop + plotH}
                  stroke="#0284c7"
                  strokeWidth="1.8"
                  strokeDasharray="4 2"
                />

                {/* Current Live Marker Reticle */}
                <circle
                  cx={currentX}
                  cy={currentAltY}
                  r="6"
                  fill="rgba(2, 132, 199, 0.25)"
                />
                <circle
                  cx={currentX}
                  cy={currentAltY}
                  r="3"
                  fill="#0284c7"
                  stroke="#ffffff"
                  strokeWidth="1.5"
                />
              </svg>
            </div>
          </div>
        </div>

        {/* Right Column: Active Avionics HUD & Sortie Progression (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          
          {/* Active Avionics Card */}
          <div className="glass-card rounded-2xl p-4 space-y-3.5 border border-slate-200/80 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-200/70 pb-2.5">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-lg bg-sky-50 border border-sky-200/80 flex items-center justify-center text-sky-600">
                  <Compass className="w-3.5 h-3.5" />
                </div>
                <h2 className="text-xs font-semibold text-slate-900 tracking-tight">Avionics & Vector State</h2>
              </div>
              <span className="font-mono text-xs font-bold text-sky-700 bg-sky-50 px-2 py-0.5 rounded-md border border-sky-200/70">
                {selectedDroneId}
              </span>
            </div>

            {/* Tactical Compass Dial */}
            <div className="flex flex-col items-center justify-center py-2">
              <div className="relative w-24 h-24 rounded-full border border-slate-200/90 flex items-center justify-center bg-gradient-to-br from-white to-slate-50/80 shadow-inner">
                {/* Cardinal Points */}
                <span className="absolute top-1 text-[8px] font-sans font-bold text-slate-400">N</span>
                <span className="absolute right-1 text-[8px] font-sans font-bold text-slate-400">E</span>
                <span className="absolute bottom-1 text-[8px] font-sans font-bold text-slate-400">S</span>
                <span className="absolute left-1 text-[8px] font-sans font-bold text-slate-400">W</span>

                {/* Rotating Needle */}
                <div
                  className="w-1 h-18 bg-gradient-to-b from-sky-600 via-transparent to-slate-400 transition-transform duration-200 rounded"
                  style={{ transform: `rotate(${activeDroneTelem.heading_deg ?? 0}deg)` }}
                />
                <div className="w-2.5 h-2.5 rounded-full bg-sky-600 shadow-sm z-10 border border-white" />
              </div>
              
              <div className="text-xs font-mono font-bold text-slate-800 mt-2 flex items-center gap-1.5">
                <span>{(activeDroneTelem.heading_deg ?? 0).toFixed(0)}°</span>
                <span className="text-[11px] font-sans text-sky-700 font-semibold px-1.5 py-0.2 bg-sky-50 rounded border border-sky-200/60">
                  {getCardinalDirection(activeDroneTelem.heading_deg ?? 0)}
                </span>
              </div>
            </div>

            {/* 4 Clean Glass Metric Tiles */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-2xs">
                <span className="text-[11px] text-slate-400 block font-medium">Groundspeed</span>
                <span className="font-mono text-sm font-bold text-slate-900 mt-0.5 block">
                  {(activeDroneTelem.speed_mps ?? 14.5).toFixed(1)} m/s
                </span>
              </div>

              <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-2xs">
                <span className="text-[11px] text-slate-400 block font-medium">Altitude AGL</span>
                <span className="font-mono text-sm font-bold text-slate-900 mt-0.5 block">
                  {(activeDroneTelem.z ?? 60).toFixed(0)} m
                </span>
              </div>

              <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-2xs">
                <span className="text-[11px] text-slate-400 block font-medium">Aero Power</span>
                <span className="font-mono text-sm font-bold text-amber-600 mt-0.5 block">
                  {(activeDroneTelem.power_watts ?? 180).toFixed(0)} W
                </span>
              </div>

              <div className="p-2.5 rounded-xl bg-white/70 border border-slate-200/70 shadow-2xs">
                <span className="text-[11px] text-slate-400 block font-medium">Active Vector</span>
                <span className="font-sans text-xs font-semibold text-sky-700 mt-0.5 block truncate">
                  {activeDroneTelem.target_name ?? 'DEPOT'}
                </span>
              </div>
            </div>

            {/* Comm Link & Geofence Status */}
            <div className="pt-1 flex items-center justify-between text-[11px] font-sans border-t border-slate-200/60 text-slate-500">
              <div className="flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5 text-emerald-600" />
                <span>Link RSSI: <strong className="text-slate-800 font-mono">99.8%</strong></span>
              </div>
              <div className="flex items-center gap-1 text-emerald-600 font-medium">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Geofence Clear</span>
              </div>
            </div>
          </div>

          {/* Sortie Route Progression (Distinguishes Secured vs En Route vs Planned) */}
          <div className="glass-card rounded-2xl p-4 space-y-3 border border-slate-200/80 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-200/70 pb-2">
              <span className="text-xs font-semibold text-slate-900">Sortie Waypoint Sequence</span>
              <span className="text-[11px] text-slate-400 font-mono">{waypoints.length} waypoints</span>
            </div>

            <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
              {waypoints.map((wp, idx) => {
                const isPassed = missionTime >= wp.departure_time;
                const isCurrent = !isPassed && (idx === 0 || missionTime >= waypoints[idx - 1].departure_time);
                const isDepot = wp.node_id === 0;
                const targetNode = targets.find((t) => t.id === wp.node_id);
                const label = isDepot ? (idx === 0 ? 'DEPOT LAUNCH' : 'DEPOT RECOVERY') : (targetNode?.name || `Target #${wp.node_id}`);

                return (
                  <div
                    key={idx}
                    className={`flex items-center justify-between p-2 rounded-xl border text-xs transition-all ${
                      isCurrent
                        ? 'bg-sky-50 border-sky-300 shadow-2xs text-sky-900 ring-1 ring-sky-200'
                        : isPassed
                          ? 'bg-emerald-50/40 border-emerald-200/60 text-slate-700'
                          : 'bg-white/60 border-slate-200/60 text-slate-400'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold ${
                        isPassed
                          ? 'bg-emerald-500 text-white'
                          : isCurrent
                            ? 'bg-sky-600 text-white animate-pulse'
                            : 'bg-slate-100 text-slate-400 border border-slate-200'
                      }`}>
                        {isPassed ? '✓' : idx + 1}
                      </div>
                      <div>
                        <span className="font-semibold block text-slate-800">{label}</span>
                        <span className="text-[10px] text-slate-400 font-sans block">
                          {isPassed ? 'Secured' : isCurrent ? 'Active Recon' : 'Planned Target'}
                        </span>
                      </div>
                    </div>

                    <div className="text-right font-mono text-[11px]">
                      <div className="text-slate-500">T+{wp.departure_time.toFixed(0)}s</div>
                      <div className={`font-semibold text-[10px] ${
                        isPassed 
                          ? 'text-emerald-600' 
                          : isCurrent 
                            ? 'text-sky-700' 
                            : 'text-slate-400'
                      }`}>
                        {isPassed ? `SoC: ${wp.remaining_battery_percent.toFixed(0)}%` : `Est: ${wp.remaining_battery_percent.toFixed(0)}%`}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* 4. Collapsible Detailed 10Hz Kinematics Vectors (Keeps page clean by default) */}
      <div className="glass-card rounded-2xl p-4 border border-slate-200/80 shadow-sm">
        <button
          onClick={() => setShowRawTable(!showRawTable)}
          className="w-full flex items-center justify-between text-xs font-semibold text-slate-700 hover:text-slate-900 cursor-pointer transition-colors"
        >
          <div className="flex items-center gap-2">
            <Gauge className="w-4 h-4 text-slate-500" />
            <span>Raw Kinematics State Vectors (10Hz)</span>
            <span className="text-[11px] font-normal text-slate-400 font-mono">
              ({telemetryList.length} UAVs tracked)
            </span>
          </div>
          <div className="flex items-center gap-1 text-sky-700 text-xs">
            <span>{showRawTable ? 'Hide Table' : 'Show Table'}</span>
            {showRawTable ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </button>

        {showRawTable && (
          <div className="mt-3.5 overflow-x-auto border-t border-slate-200/70 pt-3">
            <table className="w-full text-left text-xs border-collapse font-sans">
              <thead>
                <tr className="border-b border-slate-200/80 text-slate-400 text-[11px] font-medium">
                  <th className="py-2 px-3">Callsign</th>
                  <th className="py-2 px-3">Position (X, Y)</th>
                  <th className="py-2 px-3">Alt (m)</th>
                  <th className="py-2 px-3">Battery SoC</th>
                  <th className="py-2 px-3">Groundspeed</th>
                  <th className="py-2 px-3">Wind Comp</th>
                  <th className="py-2 px-3">Power</th>
                  <th className="py-2 px-3">Phase</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200/60 font-mono text-[11px]">
                {telemetryList.map((t) => {
                  const soc = t.battery_percent ?? 100;
                  const gSpeed = (t.ground_speed_mps ?? t.speed_mps ?? 14.5).toFixed(1);
                  const windComp = (t.wind_along_mps ?? 0).toFixed(1);

                  return (
                    <tr key={t.drone_id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-2 px-3 font-semibold text-sky-700">{t.drone_id}</td>
                      <td className="py-2 px-3 text-slate-700">({(t.x ?? 0).toFixed(0)}, {(t.y ?? 0).toFixed(0)})</td>
                      <td className="py-2 px-3 text-slate-700">{(t.z ?? 60).toFixed(0)}m</td>
                      <td className="py-2 px-3">
                        <span className={`font-semibold ${soc >= 15 ? 'text-emerald-600' : 'text-rose-600'}`}>
                          {soc.toFixed(1)}%
                        </span>
                      </td>
                      <td className="py-2 px-3 font-semibold text-slate-800">{gSpeed} m/s</td>
                      <td className="py-2 px-3 text-slate-600">{windComp >= 0 ? `+${windComp}` : windComp} m/s</td>
                      <td className="py-2 px-3 text-amber-700 font-semibold">{(t.power_watts ?? 180).toFixed(0)}W</td>
                      <td className="py-2 px-3 font-sans">
                        <span className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-sky-50 text-sky-700 border border-sky-200/80">
                          {t.flight_phase ?? 'CRUISE'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
