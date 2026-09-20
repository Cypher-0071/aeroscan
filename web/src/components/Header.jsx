import React, { useState, useEffect } from 'react';
import { Radio, Wind, BatteryCharging, Clock, ShieldCheck, Activity } from 'lucide-react';

export default function Header({ 
  instance, 
  schedule, 
  isSolving,
  windSpeed,
  windDir,
  fleetSize,
  onReplayIntro,
}) {
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

  const windSpd = (instance?.ambient_wind?.speed_mps ?? (windSpeed ?? 3.5)).toFixed(1);
  const activeWindDir = instance?.ambient_wind?.direction_deg ?? (windDir ?? 45);
  const routes = schedule?.assigned_routes ?? [];
  const activeFleetCount = routes.length || (fleetSize ?? 3);
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
          <span className="font-semibold text-slate-900 font-mono">{activeFleetCount} UAVs</span>
        </div>

        <div className="h-3.5 w-px bg-slate-200"></div>

        {/* Atmospheric Wind with Dynamic Directional Arrow */}
        <div className="flex items-center gap-1.5 text-slate-500">
          <div 
            className="w-3.5 h-3.5 flex items-center justify-center text-sky-600 transition-transform duration-300"
            style={{ transform: `rotate(${-activeWindDir}deg)` }}
            title={`Wind vector: ${windSpd} m/s towards ${activeWindDir}°`}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </div>
          <span className="text-slate-500 font-medium">Wind:</span>
          <span className="font-semibold text-slate-800 font-mono">{windSpd} m/s <span className="text-slate-400">·</span> {Math.round(activeWindDir)}°</span>
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

        {onReplayIntro && (
          <>
            <div className="h-3.5 w-px bg-slate-200"></div>
            <button
              onClick={onReplayIntro}
              type="button"
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium text-slate-700 hover:text-slate-900 bg-slate-100/90 hover:bg-slate-200/80 border border-slate-200/90 transition-all cursor-pointer shadow-2xs active:scale-95"
              title="Replay cinematic drone intro animation"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="text-sky-600">
                <circle cx="12" cy="12" r="10" />
                <polygon points="12 2 15 9 22 12 15 15 12 22 9 15 2 12 9 9 12 2" />
              </svg>
              <span>Replay Intro</span>
            </button>
          </>
        )}
      </div>
    </header>
  );
}
