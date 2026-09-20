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
    <header className="h-14 border-b border-black/[0.06] bg-white/60 backdrop-blur-2xl px-6 flex items-center justify-between sticky top-0 z-40 transition-colors">
      {/* Callsign & Mission Brand */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-3 py-1 rounded-full glass-pill shadow-xs">
          <span className="relative flex h-2 w-2">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${isSolving ? 'bg-amber-400' : 'bg-emerald-400'} opacity-75`}></span>
            <span className={`relative inline-flex rounded-full h-2 w-2 ${isSolving ? 'bg-amber-500' : 'bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.6)]'}`}></span>
          </span>
          <span className="font-mono text-[11px] font-semibold tracking-wider text-slate-800">AEROSCAN // TAC-OPS</span>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-slate-700 font-medium px-2.5 py-0.5 rounded-full bg-white/70 border border-black/[0.06] shadow-xs">
            {instance?.instance_name?.toUpperCase() ?? 'CHAO SET 64'}
          </span>
          <span className="text-[10px] uppercase font-mono tracking-wider px-2.5 py-0.5 rounded-full bg-slate-900 text-white font-medium shadow-xs">
            TOP-DC CLUSTERED SAR
          </span>
        </div>
      </div>

      {/* Real-time Telemetry Bar */}
      <div className="flex items-center gap-2.5">
        {/* Fleet Sorties */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-full glass-pill">
          <Activity className="w-3.5 h-3.5 text-slate-600" />
          <div className="text-[11px] font-mono">
            <span className="text-slate-400 mr-1 font-normal">FLEET:</span>
            <span className="text-slate-900 font-semibold">{routes.length.toString().padStart(2, '0')}</span>
            <span className="text-[9px] text-slate-400 ml-1">SORTIES</span>
          </div>
        </div>

        {/* Atmospheric Wind Vector */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-full glass-pill">
          <Wind className="w-3.5 h-3.5 text-slate-500" />
          <div className="text-[11px] font-mono">
            <span className="text-slate-400 mr-1 font-normal">WIND:</span>
            <span className="text-slate-800 font-medium">{windSpd} m/s</span>
            <span className="text-slate-900 ml-1 font-semibold">@{windDir.toString().padStart(3, '0')}°</span>
          </div>
        </div>

        {/* Energy Floor Guard */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-full glass-pill">
          <BatteryCharging className={`w-3.5 h-3.5 ${minReserve >= 15 ? 'text-emerald-600' : 'text-rose-500'}`} />
          <div className="text-[11px] font-mono">
            <span className="text-slate-400 mr-1 font-normal">FLOOR:</span>
            <span className={`font-semibold ${minReserve >= 15 ? 'text-emerald-600' : 'text-rose-600'}`}>
              {minReserve.toFixed(1)}%
            </span>
            <span className="text-[9px] text-slate-400 ml-1">MIN</span>
          </div>
        </div>

        {/* Solver Status Badge */}
        <div className={`px-3 py-1 rounded-full text-[11px] font-mono font-medium flex items-center gap-1.5 border shadow-xs transition-all ${
          isSolving 
            ? 'bg-amber-50 text-amber-700 border-amber-300 animate-pulse'
            : schedule?.validation_passed 
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200' 
              : 'bg-slate-100 text-slate-700 border-slate-200'
        }`}>
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>{status}</span>
        </div>

        {/* UTC Clock */}
        <div className="flex items-center gap-1.5 text-xs font-mono text-slate-500 pl-3 border-l border-black/[0.08]">
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-slate-700 font-medium">{utcTime || '00:00:00 UTC'}</span>
        </div>
      </div>
    </header>
  );
}
