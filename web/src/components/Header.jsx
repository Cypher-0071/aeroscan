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
    <header className="h-14 border-b border-slate-200/80 bg-white/70 backdrop-blur-2xl px-6 flex items-center justify-between sticky top-0 z-40 transition-colors">
      {/* Brand & Mission Status */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${isSolving ? 'bg-amber-400' : 'bg-emerald-400'} opacity-75`}></span>
            <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${isSolving ? 'bg-amber-500' : 'bg-emerald-500'}`}></span>
          </span>
          <span className="font-semibold text-xs text-slate-900 tracking-tight">AeroScan Tac-Ops</span>
        </div>

        <span className="text-slate-300">/</span>

        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-700">
            {instance?.instance_name ?? 'Chao Set 64'}
          </span>
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200/80">
            Clustered SAR
          </span>
        </div>
      </div>

      {/* Unified Telemetry Status Strip */}
      <div className="flex items-center gap-4 text-xs font-sans">
        {/* Fleet Sorties */}
        <div className="flex items-center gap-1.5 text-slate-500">
          <Activity className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-slate-500 font-medium">Fleet:</span>
          <span className="font-semibold text-slate-900 font-mono">{routes.length || 3} UAVs</span>
        </div>

        <div className="h-3.5 w-px bg-slate-200"></div>

        {/* Atmospheric Wind */}
        <div className="flex items-center gap-1.5 text-slate-500">
          <Wind className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-slate-500 font-medium">Wind:</span>
          <span className="font-semibold text-slate-800 font-mono">{windSpd} m/s <span className="text-slate-400">·</span> {windDir}°</span>
        </div>

        <div className="h-3.5 w-px bg-slate-200"></div>

        {/* Reserve Floor */}
        <div className="flex items-center gap-1.5 text-slate-500">
          <BatteryCharging className={`w-3.5 h-3.5 ${minReserve >= 15 ? 'text-emerald-500' : 'text-rose-500'}`} />
          <span className="text-slate-500 font-medium">Floor:</span>
          <span className={`font-semibold font-mono ${minReserve >= 15 ? 'text-emerald-600' : 'text-rose-600'}`}>
            {minReserve.toFixed(1)}%
          </span>
        </div>

        <div className="h-3.5 w-px bg-slate-200"></div>

        {/* Solver Status Badge */}
        <div className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border transition-all ${
          isSolving 
            ? 'bg-amber-50 text-amber-700 border-amber-200 animate-pulse'
            : schedule?.validation_passed 
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200/80' 
              : 'bg-slate-100 text-slate-700 border-slate-200'
        }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${isSolving ? 'bg-amber-500' : 'bg-emerald-500'}`}></span>
          <span>{status}</span>
        </div>

        <div className="h-3.5 w-px bg-slate-200"></div>

        {/* UTC Clock */}
        <div className="flex items-center gap-1.5 text-xs font-mono text-slate-500">
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          <span>{utcTime || '00:00:00 UTC'}</span>
        </div>
      </div>
    </header>
  );
}
