import React from 'react';
import { 
  BatteryCharging, 
  Zap, 
  ShieldAlert, 
  Wind, 
  Activity,
  CheckCircle,
  Gauge
} from 'lucide-react';

const DRONE_COLORS = [
  '#0284C7',
  '#EA580C',
  '#059669',
  '#7C3AED',
  '#DC2626',
  '#D97706',
  '#DB2777',
  '#0D9488',
];

export default function EnergyBattery({
  instance,
  schedule,
  missionTime,
}) {
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

  const maxFlightTime = Math.max(
    ...routes.map((r) => r.total_flight_time ?? 0),
    600
  );

  return (
    <div className="space-y-4 font-mono">
      {/* Energy Banner */}
      <div className="glass-card rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <BatteryCharging className="w-4 h-4 text-emerald-600" />
            <span>SWARM ENERGY INTELLIGENCE // SOC DEPLETION ANALYSIS</span>
          </div>
          <div className="text-xs text-slate-400 mt-0.5">
            Aerodynamic power draw, wind drift penalty, and 15% emergency reserve floor monitoring
          </div>
        </div>

        <div className="flex items-center gap-2 px-3 py-1 rounded-full glass-pill text-xs border border-emerald-200/80 bg-emerald-50">
          <span className="text-slate-400 font-normal">STATUS:</span>
          <span className={`font-semibold ${minReserveAll >= 15 ? 'text-emerald-700' : 'text-rose-600'}`}>
            {minReserveAll >= 15 ? 'ALL CONSTRAINTS SATISFIED' : 'FLOOR VIOLATION DETECTED'}
          </span>
        </div>
      </div>

      {/* Multi-Drone Battery SoC Depletion Curves (SVG Graphic) */}
      <div className="glass-card rounded-2xl p-4 space-y-3.5">
        <div className="flex items-center justify-between text-xs border-b border-slate-200/80 pb-2.5">
          <span className="font-semibold text-slate-900">
            FLEET BATTERY SOC (%) VS MISSION TIME (SECONDS)
          </span>
          <div className="flex items-center gap-3">
            {routes.map((r, idx) => (
              <div key={r.drone_id} className="flex items-center gap-1.5 text-[10px]">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: DRONE_COLORS[idx % DRONE_COLORS.length] }}
                />
                <span className="text-slate-700 font-medium">{r.drone_id}</span>
              </div>
            ))}
          </div>
        </div>

        {/* SVG Chart */}
        <div className="h-64 w-full bg-white/80 rounded-xl p-3 border border-slate-200/80 shadow-inner relative">
          <svg className="w-full h-full" viewBox="0 0 500 200" preserveAspectRatio="none">
            {/* Grid lines */}
            {[0, 50, 100, 150, 200].map((y) => (
              <line key={y} x1="0" y1={y} x2="500" y2={y} stroke="rgba(15, 23, 42, 0.05)" strokeWidth="1" />
            ))}

            {/* 15% Safety Floor Area & Line */}
            <rect x="0" y="170" width="500" height="30" fill="rgba(239, 68, 68, 0.06)" />
            <line x1="0" y1="170" x2="500" y2="170" stroke="#ef4444" strokeWidth="1.5" strokeDasharray="5 5" />
            <text x="10" y="165" fill="#ef4444" fontSize="9" fontWeight="bold">
              15% MANDATORY SAFETY FLOOR
            </text>

            {/* Drone Depletion Paths */}
            {routes.map((route, rIdx) => {
              const color = DRONE_COLORS[rIdx % DRONE_COLORS.length];
              const wps = route.waypoints ?? [];
              if (wps.length === 0) return null;

              const points = wps.map((w) => {
                const px = (w.departure_time / maxFlightTime) * 500;
                const py = 200 - (w.remaining_battery_percent / 100) * 190;
                return `${px},${py}`;
              }).join(' ');

              return (
                <g key={route.drone_id}>
                  <polyline
                    fill="none"
                    stroke={color}
                    strokeWidth="2.5"
                    points={points}
                    className="transition-all"
                  />
                  {wps.map((w, wIdx) => {
                    const px = (w.departure_time / maxFlightTime) * 500;
                    const py = 200 - (w.remaining_battery_percent / 100) * 190;
                    return (
                      <circle
                        key={wIdx}
                        cx={px}
                        cy={py}
                        r="3"
                        fill={color}
                        stroke="#ffffff"
                        strokeWidth="1.5"
                      />
                    );
                  })}
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {/* Mission Phase Consumption Progression Strip */}
      <div className="glass-pill rounded-xl p-3 flex flex-wrap items-center justify-between text-xs border border-slate-200/80 bg-white/60">
        <span className="text-slate-400 font-semibold">MISSION PHASE CONSUMPTION:</span>
        <span><b className="text-sky-700">DEPLOY</b> (5.2%)</span>
        <span className="text-slate-400">&rarr;</span>
        <span><b className="text-sky-700">TRANSIT</b> (28.4%)</span>
        <span className="text-slate-400">&rarr;</span>
        <span><b className="text-sky-700">CLUSTER INGESTION</b> (21.8%)</span>
        <span className="text-slate-400">&rarr;</span>
        <span><b className="text-sky-700">TARGET ACQUISITION</b> (29.6%)</span>
        <span className="text-slate-400">&rarr;</span>
        <span><b className="text-emerald-600">RETURN BASE</b> (15.0%)</span>
      </div>

      {/* Subsystem Power Allocation Breakdown */}
      <div className="glass-card rounded-2xl p-4 space-y-3.5">
        <div className="text-xs font-semibold text-slate-900">
          SUBSYSTEM POWER ALLOCATION BREAKDOWN
        </div>

        <div className="space-y-2.5 text-xs">
          <div>
            <div className="flex justify-between text-slate-600 mb-1">
              <span>BEMT Hover &amp; Aerodynamic Rotor Thrust (~320W)</span>
              <span className="text-sky-700 font-semibold">48%</span>
            </div>
            <div className="w-full bg-slate-100 border border-slate-200/60 h-1.5 rounded-full overflow-hidden">
              <div className="bg-sky-500 h-full rounded-full" style={{ width: '48%' }} />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-slate-600 mb-1">
              <span>Forward Flight Parasite Drag Polar (~195W)</span>
              <span className="text-indigo-700 font-semibold">29%</span>
            </div>
            <div className="w-full bg-slate-100 border border-slate-200/60 h-1.5 rounded-full overflow-hidden">
              <div className="bg-indigo-500 h-full rounded-full" style={{ width: '29%' }} />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-slate-600 mb-1">
              <span>Vector Wind Drift Crosswind Compensation (~45W)</span>
              <span className="text-amber-700 font-semibold">12%</span>
            </div>
            <div className="w-full bg-slate-100 border border-slate-200/60 h-1.5 rounded-full overflow-hidden">
              <div className="bg-amber-500 h-full rounded-full" style={{ width: '12%' }} />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-slate-600 mb-1">
              <span>High-Resolution Sensor &amp; Optical Recon Payload (~35W)</span>
              <span className="text-emerald-700 font-semibold">8%</span>
            </div>
            <div className="w-full bg-slate-100 border border-slate-200/60 h-1.5 rounded-full overflow-hidden">
              <div className="bg-emerald-500 h-full rounded-full" style={{ width: '8%' }} />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-slate-600 mb-1">
              <span>Avionics, RTK GNSS &amp; AES-256 Telemetry Link (~15W)</span>
              <span className="text-slate-600 font-semibold">3%</span>
            </div>
            <div className="w-full bg-slate-100 border border-slate-200/60 h-1.5 rounded-full overflow-hidden">
              <div className="bg-slate-400 h-full rounded-full" style={{ width: '3%' }} />
            </div>
          </div>
        </div>
      </div>

      {/* 4 KPI Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="glass-card-interactive rounded-2xl p-4 space-y-1">
          <span className="text-[10px] text-slate-400 block font-medium">MINIMUM FLEET RESERVE</span>
          <span className="text-xl font-bold text-emerald-600 mt-1 block">
            {minReserveAll.toFixed(1)}%
          </span>
          <span className="text-[10px] text-slate-400 mt-0.5 block">Above 15% Floor</span>
        </div>

        <div className="glass-card-interactive rounded-2xl p-4 space-y-1">
          <span className="text-[10px] text-slate-400 block font-medium">TOTAL SWARM ENERGY</span>
          <span className="text-xl font-bold text-sky-700 mt-1 block">
            {(totalJoules / 1000).toFixed(1)} kJ
          </span>
          <span className="text-[10px] text-slate-400 mt-0.5 block">Wind-Compensated</span>
        </div>

        <div className="glass-card-interactive rounded-2xl p-4 space-y-1">
          <span className="text-[10px] text-slate-400 block font-medium">AVERAGE RECOVERY MARGIN</span>
          <span className="text-xl font-bold text-slate-900 mt-1 block">
            {avgReserve.toFixed(1)}%
          </span>
          <span className="text-[10px] text-slate-400 mt-0.5 block">Optimal Land Margin</span>
        </div>

        <div className="glass-card-interactive rounded-2xl p-4 space-y-1">
          <span className="text-[10px] text-slate-400 block font-medium">SAFETY RESERVE FLOOR</span>
          <span className="text-xl font-bold text-rose-600 mt-1 block">
            15.0%
          </span>
          <span className="text-[10px] text-slate-400 mt-0.5 block">Strict Constraint</span>
        </div>
      </div>
    </div>
  );
}
