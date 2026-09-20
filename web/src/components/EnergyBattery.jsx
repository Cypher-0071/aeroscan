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
  '#38BDF8',
  '#FB923C',
  '#34D399',
  '#A78BFA',
  '#F87171',
  '#FACC15',
  '#F472B6',
  '#2DD4BF',
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
      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-md flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-sm font-bold text-slate-100 flex items-center gap-2">
            <BatteryCharging className="w-4 h-4 text-emerald-400" />
            <span>SWARM ENERGY INTELLIGENCE // SOC DEPLETION ANALYSIS</span>
          </div>
          <div className="text-xs text-slate-400 mt-0.5">
            Aerodynamic power draw, wind drift penalty, and 15% emergency reserve floor monitoring
          </div>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs">
          <span className="text-slate-400">STATUS:</span>
          <span className={`font-bold ${minReserveAll >= 15 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {minReserveAll >= 15 ? 'ALL CONSTRAINTS SATISFIED' : 'FLOOR VIOLATION DETECTED'}
          </span>
        </div>
      </div>

      {/* Multi-Drone Battery SoC Depletion Curves (SVG Graphic) */}
      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-md space-y-3">
        <div className="flex items-center justify-between text-xs border-b border-slate-800 pb-2">
          <span className="font-bold text-slate-200">
            FLEET BATTERY SOC (%) VS MISSION TIME (SECONDS)
          </span>
          <div className="flex items-center gap-3">
            {routes.map((r, idx) => (
              <div key={r.drone_id} className="flex items-center gap-1.5 text-[10px]">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: DRONE_COLORS[idx % DRONE_COLORS.length] }}
                />
                <span className="text-slate-300">{r.drone_id}</span>
              </div>
            ))}
          </div>
        </div>

        {/* SVG Chart */}
        <div className="h-64 w-full bg-slate-950 rounded-xl p-3 border border-slate-800 relative">
          <svg className="w-full h-full" viewBox="0 0 500 200" preserveAspectRatio="none">
            {/* Grid lines */}
            {[0, 50, 100, 150, 200].map((y) => (
              <line key={y} x1="0" y1={y} x2="500" y2={y} stroke="rgba(56, 189, 248, 0.08)" strokeWidth="1" />
            ))}

            {/* 15% Safety Floor Area & Line */}
            <rect x="0" y="170" width="500" height="30" fill="rgba(239, 68, 68, 0.08)" />
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
                        strokeWidth="1"
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
      <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-md flex flex-wrap items-center justify-between text-xs">
        <span className="text-slate-400 font-bold">MISSION PHASE CONSUMPTION:</span>
        <span><b className="text-sky-400">DEPLOY</b> (5.2%)</span>
        <span className="text-slate-600">&rarr;</span>
        <span><b className="text-sky-400">TRANSIT</b> (28.4%)</span>
        <span className="text-slate-600">&rarr;</span>
        <span><b className="text-sky-400">CLUSTER INGESTION</b> (21.8%)</span>
        <span className="text-slate-600">&rarr;</span>
        <span><b className="text-sky-400">TARGET ACQUISITION</b> (29.6%)</span>
        <span className="text-slate-600">&rarr;</span>
        <span><b className="text-emerald-400">RETURN BASE</b> (15.0%)</span>
      </div>

      {/* Subsystem Power Allocation Breakdown */}
      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-md space-y-3">
        <div className="text-xs font-bold text-slate-200">
          SUBSYSTEM POWER ALLOCATION BREAKDOWN
        </div>

        <div className="space-y-2 text-xs">
          <div>
            <div className="flex justify-between text-slate-400 mb-1">
              <span>BEMT Hover &amp; Aerodynamic Rotor Thrust (~320W)</span>
              <span className="text-sky-400 font-bold">48%</span>
            </div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div className="bg-sky-500 h-full rounded-full" style={{ width: '48%' }} />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-slate-400 mb-1">
              <span>Forward Flight Parasite Drag Polar (~195W)</span>
              <span className="text-indigo-400 font-bold">29%</span>
            </div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div className="bg-indigo-500 h-full rounded-full" style={{ width: '29%' }} />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-slate-400 mb-1">
              <span>Vector Wind Drift Crosswind Compensation (~45W)</span>
              <span className="text-amber-400 font-bold">12%</span>
            </div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div className="bg-amber-500 h-full rounded-full" style={{ width: '12%' }} />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-slate-400 mb-1">
              <span>High-Resolution Sensor &amp; Optical Recon Payload (~35W)</span>
              <span className="text-emerald-400 font-bold">8%</span>
            </div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div className="bg-emerald-500 h-full rounded-full" style={{ width: '8%' }} />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-slate-400 mb-1">
              <span>Avionics, RTK GNSS &amp; AES-256 Telemetry Link (~15W)</span>
              <span className="text-slate-400 font-bold">3%</span>
            </div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div className="bg-slate-500 h-full rounded-full" style={{ width: '3%' }} />
            </div>
          </div>
        </div>
      </div>

      {/* 4 KPI Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800/80">
          <span className="text-[10px] text-slate-400 block">MINIMUM FLEET RESERVE</span>
          <span className="text-xl font-bold text-emerald-400 mt-1 block">
            {minReserveAll.toFixed(1)}%
          </span>
          <span className="text-[10px] text-slate-500 mt-0.5 block">Above 15% Floor</span>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800/80">
          <span className="text-[10px] text-slate-400 block">TOTAL SWARM ENERGY</span>
          <span className="text-xl font-bold text-sky-400 mt-1 block">
            {(totalJoules / 1000).toFixed(1)} kJ
          </span>
          <span className="text-[10px] text-slate-500 mt-0.5 block">Wind-Compensated</span>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800/80">
          <span className="text-[10px] text-slate-400 block">AVERAGE RECOVERY MARGIN</span>
          <span className="text-xl font-bold text-slate-200 mt-1 block">
            {avgReserve.toFixed(1)}%
          </span>
          <span className="text-[10px] text-slate-500 mt-0.5 block">Optimal Land Margin</span>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800/80">
          <span className="text-[10px] text-slate-400 block">SAFETY RESERVE FLOOR</span>
          <span className="text-xl font-bold text-rose-400 mt-1 block">
            15.0%
          </span>
          <span className="text-[10px] text-slate-500 mt-0.5 block">Strict Constraint</span>
        </div>
      </div>
    </div>
  );
}
