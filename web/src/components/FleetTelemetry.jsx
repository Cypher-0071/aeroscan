import React, { useState, useMemo } from 'react';
import { 
  Activity, 
  Radio, 
  BatteryCharging, 
  Navigation, 
  ShieldCheck, 
  Cpu, 
  Compass, 
  Zap,
  ArrowUpRight
} from 'lucide-react';

export default function FleetTelemetry({
  instance,
  schedule,
  telemetry,
  missionTime,
}) {
  const drones = instance?.drones ?? [];
  const [selectedDroneId, setSelectedDroneId] = useState(drones[0]?.id ?? 'UAV-01');

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
  };

  // Fleet overview aggregates
  const avgBat = telemetryList.length > 0
    ? telemetryList.reduce((sum, t) => sum + (t.battery_percent ?? 100), 0) / telemetryList.length
    : 100;
  const activeCount = telemetryList.filter((t) => t.flight_phase !== 'RECOVERED' && t.flight_phase !== 'STANDBY').length;
  const standbyCount = telemetryList.length - activeCount;
  const totalDistKm = (schedule?.assigned_routes ?? []).reduce(
    (acc, r) => acc + ((r.total_flight_time ?? 0) * 14.5) / 1000,
    0
  );

  // Selected route waypoints for profile chart
  const selectedRoute = (schedule?.assigned_routes ?? []).find(
    (r) => r.drone_id === selectedDroneId
  );
  const waypoints = selectedRoute?.waypoints ?? [];

  return (
    <div className="space-y-4">
      {/* Overview Banner */}
      <div className="glass-card rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-sky-50 border border-sky-200/80 flex items-center justify-center text-sky-600">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-900 font-sans tracking-tight">
              Swarm Telemetry & Kinematics
            </h2>
            <div className="text-xs text-slate-500 font-sans mt-0.5">
              Multi-parameter state vectors, aerodynamic power draw, and real-time avionics
            </div>
          </div>
        </div>

        {/* Grouped Telemetry Strip */}
        <div className="flex items-center gap-3 px-3 py-1.5 rounded-xl bg-white/70 border border-slate-200/80 shadow-sm text-xs font-sans">
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500">Active:</span>
            <span className="font-mono font-semibold text-slate-900">{activeCount.toString().padStart(2, '0')}</span>
          </div>
          <div className="h-3.5 w-px bg-slate-200" />
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500">Standby:</span>
            <span className="font-mono font-semibold text-slate-700">{standbyCount.toString().padStart(2, '0')}</span>
          </div>
          <div className="h-3.5 w-px bg-slate-200" />
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500">Avg Battery:</span>
            <span className="font-mono font-semibold text-emerald-600">{avgBat.toFixed(1)}%</span>
          </div>
          <div className="h-3.5 w-px bg-slate-200" />
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500">Total Distance:</span>
            <span className="font-mono font-semibold text-sky-700">{totalDistKm.toFixed(1)} km</span>
          </div>
        </div>
      </div>

      {/* 3-Column Layout: Fleet List | Kinematics Charts | Avionics HUD */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Fleet List (3 cols) */}
        <div className="lg:col-span-3 space-y-2">
          <div className="text-xs font-semibold text-slate-900 font-sans px-1 flex items-center justify-between">
            <span>Fleet Roster</span>
            <span className="text-[11px] font-mono font-normal text-slate-400">{drones.length} UAVs</span>
          </div>

          <div className="space-y-2">
            {drones.map((drone) => {
              const telem = telemMap[drone.id] || {};
              const isSelected = drone.id === selectedDroneId;
              const soc = telem.battery_percent ?? 100;
              const phase = telem.flight_phase ?? 'CRUISE';
              const isCruising = phase === 'CRUISE' || phase === 'TRANSIT_CRUISE';

              return (
                <button
                  key={drone.id}
                  onClick={() => setSelectedDroneId(drone.id)}
                  className={`w-full text-left p-3.5 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? 'glass-card border-sky-300 shadow-sm bg-white/95 ring-1 ring-sky-200'
                      : 'border-slate-200/70 bg-white/60 hover:bg-white/90 hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-sm text-slate-900">{drone.id}</span>
                    <span className={`text-[10px] font-sans px-2 py-0.5 rounded-md font-medium ${
                      isCruising
                        ? 'bg-sky-50 text-sky-700 border border-sky-200/80'
                        : 'bg-slate-100 text-slate-500 border border-slate-200/70'
                    }`}>
                      {phase}
                    </span>
                  </div>

                  <div className="mt-2.5 space-y-1.5 text-xs">
                    <div className="flex justify-between font-sans text-[11px] text-slate-500">
                      <span>Battery SoC</span>
                      <span className={`font-mono font-semibold ${soc >= 15 ? 'text-emerald-600' : 'text-rose-600'}`}>
                        {soc.toFixed(0)}%
                      </span>
                    </div>
                    <div className="w-full bg-slate-100 border border-slate-200/60 h-1.5 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          soc >= 15 ? 'bg-emerald-500' : 'bg-rose-500'
                        }`}
                        style={{ width: `${Math.max(0, Math.min(100, soc))}%` }}
                      />
                    </div>

                    <div className="flex justify-between text-slate-500 pt-1 font-mono text-[10px]">
                      <span>Alt: {(telem.z ?? 60).toFixed(0)}m</span>
                      <span>Spd: {(telem.speed_mps ?? 14.5).toFixed(1)}m/s</span>
                      <span>Hdg: {(telem.heading_deg ?? 0).toFixed(0)}°</span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Center Column: Kinematics Profile Charts (6 cols) */}
        <div className="lg:col-span-6 space-y-4">
          <div className="glass-card rounded-2xl p-4 space-y-3.5">
            <div className="flex items-center justify-between border-b border-slate-200/80 pb-2.5">
              <div className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-md bg-sky-50 border border-sky-200/80 flex items-center justify-center text-sky-600">
                  <Zap className="w-3 h-3" />
                </div>
                <span className="text-xs font-semibold text-slate-900 font-sans">
                  Kinematics Profile:
                </span>
                <span className="font-mono text-xs font-bold text-sky-700">{selectedDroneId}</span>
              </div>
              <span className="text-[11px] text-slate-400 font-mono">
                Time: T+{missionTime.toFixed(0)}s
              </span>
            </div>

            {/* Battery SoC Curve (SVG Visualizer) */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-sans text-slate-500">
                <span>Battery State of Charge (%)</span>
                <span className="text-emerald-600 font-semibold font-mono">
                  {(activeDroneTelem.battery_percent ?? 100).toFixed(1)}%
                </span>
              </div>
              <div className="h-32 w-full bg-white/80 rounded-xl p-2.5 border border-slate-200/80 shadow-inner relative">
                <svg className="w-full h-full" viewBox="0 0 400 100" preserveAspectRatio="none">
                  {/* 15% Safety Floor Line */}
                  <line x1="0" y1="85" x2="400" y2="85" stroke="#ef4444" strokeWidth="1" strokeDasharray="4 4" strokeOpacity="0.7" />
                  <text x="5" y="81" fill="#ef4444" fontSize="8" fontFamily="Inter, sans-serif" fontWeight="500">15% SAFETY FLOOR</text>

                  {/* Battery Curve */}
                  {waypoints.length > 1 && (() => {
                    const maxT = Math.max(...waypoints.map((w) => w.departure_time), 600);
                    const points = waypoints.map((w) => {
                      const px = (w.departure_time / maxT) * 400;
                      const py = 100 - (w.remaining_battery_percent / 100) * 90;
                      return `${px},${py}`;
                    }).join(' ');

                    return (
                      <>
                        <polyline fill="none" stroke="#059669" strokeWidth="2.5" points={points} />
                        {/* Current Time Marker */}
                        {(() => {
                          const cx = Math.min(400, Math.max(0, (missionTime / maxT) * 400));
                          const cy = 100 - ((activeDroneTelem.battery_percent ?? 100) / 100) * 90;
                          return (
                            <>
                              <line x1={cx} y1="0" x2={cx} y2="100" stroke="#0284c7" strokeWidth="1.5" strokeDasharray="3 3" />
                              <circle cx={cx} cy={cy} r="4" fill="#0284c7" stroke="#ffffff" strokeWidth="2" />
                            </>
                          );
                        })()}
                      </>
                    );
                  })()}
                </svg>
              </div>
            </div>

            {/* Altitude Profile Curve */}
            <div className="space-y-1.5 pt-1">
              <div className="flex justify-between text-xs font-sans text-slate-500">
                <span>Flight Altitude (m AGL)</span>
                <span className="text-sky-700 font-semibold font-mono">{(activeDroneTelem.z ?? 60).toFixed(0)} m</span>
              </div>
              <div className="h-28 w-full bg-white/80 rounded-xl p-2.5 border border-slate-200/80 shadow-inner relative">
                <svg className="w-full h-full" viewBox="0 0 400 100" preserveAspectRatio="none">
                  {/* Ground Level */}
                  <line x1="0" y1="95" x2="400" y2="95" stroke="rgba(15,23,42,0.12)" strokeWidth="1" />
                  
                  {/* Altitude Bar Profile */}
                  {waypoints.length > 0 && (() => {
                    const maxT = Math.max(...waypoints.map((w) => w.departure_time), 600);
                    const points = [
                      '0,95',
                      ...waypoints.map((w) => {
                        const px = (w.departure_time / maxT) * 400;
                        const py = 95 - Math.min(80, (w.node_id === 0 ? 10 : 65));
                        return `${px},${py}`;
                      }),
                      '400,95',
                    ].join(' ');

                    return (
                      <>
                        <polygon fill="rgba(2, 132, 199, 0.08)" stroke="#0284c7" strokeWidth="2" points={points} />
                        {(() => {
                          const cx = Math.min(400, Math.max(0, (missionTime / maxT) * 400));
                          return (
                            <line x1={cx} y1="0" x2={cx} y2="100" stroke="#d97706" strokeWidth="1.5" strokeDasharray="3 3" />
                          );
                        })()}
                      </>
                    );
                  })()}
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Avionics HUD Card (3 cols) */}
        <div className="lg:col-span-3 space-y-3">
          <div className="glass-card rounded-2xl p-4 space-y-3">
            <div className="font-sans text-xs font-semibold text-slate-900 border-b border-slate-200/80 pb-2 flex items-center justify-between">
              <span>Avionics HUD</span>
              <span className="text-sky-700 font-mono font-bold">{selectedDroneId}</span>
            </div>

            {/* Avionics Instrument Readout Rows */}
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-200/60 font-sans">
                <span className="text-slate-500">Callsign</span>
                <span className="text-slate-900 font-mono font-semibold">{selectedDroneId}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200/60 font-sans">
                <span className="text-slate-500">Flight Phase</span>
                <span className="text-sky-700 font-medium">{activeDroneTelem.flight_phase}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200/60 font-sans">
                <span className="text-slate-500">Groundspeed</span>
                <span className="text-slate-900 font-mono font-semibold">{(activeDroneTelem.speed_mps ?? 14.5).toFixed(1)} m/s</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200/60 font-sans">
                <span className="text-slate-500">Altitude (AGL)</span>
                <span className="text-slate-900 font-mono font-semibold">{(activeDroneTelem.z ?? 60).toFixed(0)} m</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200/60 font-sans">
                <span className="text-slate-500">Heading Azimuth</span>
                <span className="text-sky-700 font-mono font-semibold">{(activeDroneTelem.heading_deg ?? 0).toFixed(0)}°</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200/60 font-sans">
                <span className="text-slate-500">Current Target</span>
                <span className="text-amber-700 font-medium">{activeDroneTelem.target_name ?? 'DEPOT'}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200/60 font-sans">
                <span className="text-slate-500">Comm Link RSSI</span>
                <span className="text-emerald-600 font-mono font-semibold">99.8%</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200/60 font-sans">
                <span className="text-slate-500">Geofence Status</span>
                <span className="text-emerald-600 font-medium">Clear</span>
              </div>
            </div>

            {/* Tactical Compass Visualizer */}
            <div className="pt-2 flex flex-col items-center justify-center">
              <div className="relative w-20 h-20 rounded-full border border-slate-200/90 flex items-center justify-center bg-white/90 shadow-inner">
                <span className="absolute top-1 text-[8px] font-sans font-bold text-slate-400">N</span>
                <span className="absolute right-1 text-[8px] font-sans font-bold text-slate-400">E</span>
                <span className="absolute bottom-1 text-[8px] font-sans font-bold text-slate-400">S</span>
                <span className="absolute left-1 text-[8px] font-sans font-bold text-slate-400">W</span>
                
                {/* Needle */}
                <div
                  className="w-1 h-14 bg-gradient-to-b from-sky-600 via-transparent to-slate-400 transition-transform duration-200 rounded"
                  style={{ transform: `rotate(${activeDroneTelem.heading_deg ?? 0}deg)` }}
                />
                <div className="w-2 h-2 rounded-full bg-sky-600 z-10" />
              </div>
              <div className="text-[11px] font-sans text-slate-500 mt-2 flex items-center gap-1.5">
                <span>Azimuth:</span>
                <span className="font-mono font-semibold text-slate-800">{(activeDroneTelem.heading_deg ?? 0).toFixed(0)}°</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Detailed Fleet Kinematics Table */}
      <div className="glass-card rounded-2xl p-4 space-y-3.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-900 font-sans">
            Fleet Kinematics State Vectors (10Hz)
          </span>
          <span className="text-xs text-slate-400 font-sans">{telemetryList.length} sorties monitored</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse font-sans">
            <thead>
              <tr className="border-b border-slate-200/80 text-slate-400 text-[11px] font-medium">
                <th className="py-2.5 px-3">Callsign</th>
                <th className="py-2.5 px-3">Coordinates (X, Y)</th>
                <th className="py-2.5 px-3">Alt Z (m)</th>
                <th className="py-2.5 px-3">Battery SoC</th>
                <th className="py-2.5 px-3">Groundspeed</th>
                <th className="py-2.5 px-3">Wind Resistance</th>
                <th className="py-2.5 px-3">Aero Power</th>
                <th className="py-2.5 px-3">Flight Phase</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200/60 font-mono">
              {telemetryList.map((t) => {
                const soc = t.battery_percent ?? 100;
                const gSpeed = (t.ground_speed_mps ?? t.speed_mps ?? 14.5).toFixed(1);
                const windComp = (t.wind_along_mps ?? 0).toFixed(1);
                const isTail = (t.wind_along_mps ?? 0) > 0.5;
                const isHead = (t.wind_along_mps ?? 0) < -0.5;

                return (
                  <tr key={t.drone_id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-2.5 px-3 font-semibold text-sky-700">{t.drone_id}</td>
                    <td className="py-2.5 px-3 text-slate-700">
                      ({(t.x ?? 0).toFixed(0)}, {(t.y ?? 0).toFixed(0)})
                    </td>
                    <td className="py-2.5 px-3 text-slate-700">{(t.z ?? 60).toFixed(0)}</td>
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-2">
                        <div className="w-14 bg-slate-100 border border-slate-200/60 h-1.5 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${soc >= 15 ? 'bg-emerald-500' : 'bg-rose-500'}`}
                            style={{ width: `${Math.max(0, Math.min(100, soc))}%` }}
                          />
                        </div>
                        <span className={`font-semibold ${soc >= 15 ? 'text-emerald-600' : 'text-rose-600'}`}>
                          {soc.toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-slate-900">{gSpeed} m/s</td>
                    <td className="py-2.5 px-3">
                      <span className={`px-2 py-0.5 rounded-md text-[10px] font-sans font-medium border ${
                        isTail 
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200/80' 
                          : isHead 
                            ? 'bg-amber-50 text-amber-700 border-amber-200/80' 
                            : 'bg-slate-50 text-slate-600 border-slate-200/70'
                      }`}>
                        {t.wind_effect ?? 'Nominal'} ({windComp >= 0 ? '+' : ''}{windComp} m/s)
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-amber-700 font-semibold">
                      {(t.power_watts ?? 180).toFixed(0)} W
                    </td>
                    <td className="py-2.5 px-3 font-sans">
                      <span className="px-2.5 py-0.5 rounded-md text-[10px] font-medium bg-sky-50 text-sky-700 border border-sky-200/80">
                        {t.flight_phase ?? 'CRUISE'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
