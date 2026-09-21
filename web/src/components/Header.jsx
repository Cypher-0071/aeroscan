import React, { useState, useEffect } from 'react';
import { Clock } from 'lucide-react';

export default function Header({ 
  instance, 
  schedule, 
  isSolving,
}) {
  const [currentTime, setCurrentTime] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(
        now.toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const status = isSolving ? 'SOLVING' : (schedule?.status ?? 'READY');

  return (
    <header className="h-14 border-b border-slate-200/80 bg-white/70 backdrop-blur-2xl px-6 flex items-center justify-between sticky top-0 z-40 transition-colors">
      {/* Brand & Mission Scenario */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${isSolving ? 'bg-amber-400' : 'bg-emerald-400'} opacity-75`}></span>
            <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${isSolving ? 'bg-amber-500' : 'bg-emerald-500'}`}></span>
          </span>
          <span className="font-semibold text-xs text-slate-900 tracking-tight">AeroScan Tac-Ops</span>
        </div>

        <span className="text-slate-300">/</span>

        <span className="text-xs font-medium text-slate-700">
          {instance?.instance_name ?? 'Chao Set 64'}
        </span>
      </div>

      {/* Clean Status & Clock */}
      <div className="flex items-center gap-3 text-xs">
        {/* Solver Status Badge */}
        <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border transition-all ${
          isSolving 
            ? 'bg-amber-50 text-amber-700 border-amber-200 animate-pulse'
            : schedule?.validation_passed 
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200/80' 
              : 'bg-slate-100 text-slate-700 border-slate-200'
        }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${isSolving ? 'bg-amber-500' : 'bg-emerald-500'}`}></span>
          <span>{status}</span>
        </div>

        <div className="h-4 w-px bg-slate-200"></div>

        {/* Current Local Clock */}
        <div 
          className="flex items-center gap-1.5 text-xs font-mono text-slate-600 bg-slate-100/80 px-2.5 py-1 rounded-md border border-slate-200/60"
          title={new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
        >
          <Clock className="w-3.5 h-3.5 text-slate-500" />
          <span className="font-medium tracking-tight">{currentTime || '--:--:--'}</span>
        </div>
      </div>
    </header>
  );
}

