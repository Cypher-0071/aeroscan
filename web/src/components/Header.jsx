import React, { useState, useEffect } from 'react';
import { Radio, Wind, BatteryCharging, Clock, ShieldCheck, Activity } from 'lucide-react';

export default function Header({ instance, schedule, isSolving }) {
  const [utcTime, setUtcTime] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setUtcTime(now.toUTCString().split(' ')[4] + ' UTC');
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const windSpd = instance?.ambient_wind?.speed_mps?.toFixed(1) ?? '3.5';
  const windDir = instance?.ambient_wind?.direction_deg ?? 45;
  const routes = schedule?.assigned_routes ?? [];
  const minReserve = routes.length > 0 
    ? Math.min(...routes.map(r => r.final_reserve_percent ?? 100))
    : 100;
  const status = isSolving ? 'SOLVING...' : (schedule?.status ?? 'READY');

  return (
    <header className="h-16 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-40">
      {/* Callsign & Mission Brand */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-sky-950/50 border border-sky-500/20 shadow-inner">
          <span className="relative flex h-2.5 w-2.5">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${isSolving ? 'bg-amber-400' : 'bg-sky-400'} opacity-75`}></span>
            <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${isSolving ? 'bg-amber-500' : 'bg-sky-500'}`}></span>
          </span>
          <span className="font-mono text-xs font-bold tracking-wider text-sky-300">AEROSCAN // TAC-OPS</span>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-slate-300 font-semibold px-2 py-0.5 rounded bg-slate-800/60 border border-slate-700/50">
            {instance?.instance_name?.toUpperCase() ?? 'CHAO SET 64'}
          </span>
          <span className="text-[10px] uppercase font-mono tracking-wider px-2 py-0.5 rounded bg-cyan-950/60 text-cyan-400 border border-cyan-800/40">
            TOP-DC CLUSTERED SAR
          </span>
        </div>
      </div>

      {/* Real-time Telemetry Bar */}
      <div className="flex items-center gap-5">
        {/* Fleet Sorties */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-slate-900/60 border border-slate-800/60">
          <Activity className="w-3.5 h-3.5 text-sky-400" />
          <div className="text-[11px] font-mono">
            <span className="text-slate-400 mr-1.5">FLEET:</span>
            <span className="text-slate-100 font-bold">{routes.length.toString().padStart(2, '0')}</span>
            <span className="text-[9px] text-slate-500 ml-1">SORTIES</span>
          </div>
        </div>

        {/* Atmospheric Wind Vector */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-slate-900/60 border border-slate-800/60">
          <Wind className="w-3.5 h-3.5 text-slate-400" />
          <div className="text-[11px] font-mono">
            <span className="text-slate-400 mr-1.5">WIND:</span>
            <span className="text-slate-200 font-semibold">{windSpd} m/s</span>
            <span className="text-sky-400 ml-1 font-bold">@{windDir.toString().padStart(3, '0')}°</span>
          </div>
        </div>

        {/* Energy Floor Guard */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-slate-900/60 border border-slate-800/60">
          <BatteryCharging className={`w-3.5 h-3.5 ${minReserve >= 15 ? 'text-emerald-400' : 'text-rose-400'}`} />
          <div className="text-[11px] font-mono">
            <span className="text-slate-400 mr-1.5">FLOOR:</span>
            <span className={`font-bold ${minReserve >= 15 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {minReserve.toFixed(1)}%
            </span>
            <span className="text-[9px] text-slate-500 ml-1">MIN</span>
          </div>
        </div>

        {/* Solver Status Badge */}
        <div className={`px-2.5 py-1 rounded text-[11px] font-mono font-bold flex items-center gap-1.5 border ${
          isSolving 
            ? 'bg-amber-950/40 text-amber-300 border-amber-500/40 animate-pulse'
            : schedule?.validation_passed 
              ? 'bg-emerald-950/40 text-emerald-300 border-emerald-500/40' 
              : 'bg-sky-950/40 text-sky-300 border-sky-500/40'
        }`}>
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>{status}</span>
        </div>

        {/* UTC Clock */}
        <div className="flex items-center gap-1.5 text-xs font-mono text-slate-400 pl-2 border-l border-slate-800">
          <Clock className="w-3.5 h-3.5 text-slate-500" />
          <span className="text-slate-300 font-medium">{utcTime || '00:00:00 UTC'}</span>
        </div>
      </div>
    </header>
  );
}
