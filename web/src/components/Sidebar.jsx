import React from 'react';
import { 
  Compass, 
  Activity, 
  GitCompare, 
  BatteryCharging, 
  DownloadCloud, 
  Play, 
  RefreshCw, 
  Radio, 
  Shield, 
  Cpu
} from 'lucide-react';

const WORKSPACE_TABS = [
  { id: 'map', label: '01 Operations Map', icon: Compass },
  { id: 'telemetry', label: '02 Fleet Telemetry', icon: Activity },
  { id: 'arena', label: '03 Optimization Lab', icon: GitCompare },
  { id: 'energy', label: '04 Energy & Battery', icon: BatteryCharging },
  { id: 'export', label: '05 Mission Export', icon: DownloadCloud },
];

const SCENARIOS = [
  { id: 'Chao Set 64 (Clustered SAR)', label: 'Chao Set 64 (Clustered SAR)' },
  { id: 'Chao Set 66 (Diamond Perimeter)', label: 'Chao Set 66 (Diamond Perimeter)' },
  { id: 'Chao Set 100 (Concentric Grid)', label: 'Chao Set 100 (Concentric Grid)' },
  { id: 'Chao Set 102 (Uniform Scatter)', label: 'Chao Set 102 (Uniform Scatter)' },
  { id: 'Sample Mountain SAR', label: 'Sample Mountain SAR' },
];

export default function Sidebar({
  activeTab,
  setActiveTab,
  scenario,
  setScenario,
  fleetSize,
  setFleetSize,
  windSpeed,
  setWindSpeed,
  windDir,
  setWindDir,
  onRunOptimizer,
  onLoadMock,
  isSolving,
  instance,
  schedule,
}) {
  const totalTargets = instance?.target_nodes?.length ?? 0;
  const visitedTargets = (schedule?.assigned_routes ?? []).reduce(
    (acc, r) => acc + (r.target_ids?.length ?? 0), 
    0
  );
  const coveragePct = totalTargets > 0 ? (visitedTargets / totalTargets) * 100 : 0;
  const activeDronesCount = instance?.drones?.length ?? fleetSize;

  return (
    <aside className="w-72 border-r border-slate-800/80 bg-slate-950/90 flex flex-col justify-between shrink-0 select-none overflow-y-auto h-screen sticky top-0">
      <div className="p-4 space-y-5">
        {/* Brand Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800/70">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polygon points="12 2 15 9 22 12 15 15 12 22 9 15 2 12 9 9 12 2" />
              </svg>
            </div>
            <div>
              <div className="font-mono text-sm font-bold tracking-wider text-slate-100 flex items-center gap-1.5">
                AEROSCAN
                <span className="text-[10px] text-sky-400 bg-sky-950/80 px-1 py-0.2 border border-sky-800/40 rounded">
                  REACT
                </span>
              </div>
              <div className="text-[10px] font-mono text-slate-400 tracking-wider">
                MISSION OPERATIONS
              </div>
            </div>
          </div>
          <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
            v2.0
          </span>
        </div>

        {/* Navigation Workspace Rail */}
        <div>
          <div className="text-[10px] font-mono font-semibold text-slate-400 uppercase tracking-wider mb-2 px-1">
            Workspace
          </div>
          <nav className="space-y-1">
            {WORKSPACE_TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-mono transition-all text-left ${
                    isActive
                      ? 'bg-sky-500/15 text-sky-300 border border-sky-500/30 font-semibold shadow-sm shadow-sky-900/30'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/50 border border-transparent'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-sky-400' : 'text-slate-500'}`} />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Active Mission Context Card */}
        <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-2.5">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="font-bold text-slate-200 truncate max-w-[140px]">
              {instance?.instance_name ?? 'ACTIVE SCENARIO'}
            </span>
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 font-bold">
              ACTIVE
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2 pt-1 border-t border-slate-800/60 text-center font-mono">
            <div>
              <div className="text-[9px] text-slate-400">FLEET</div>
              <div className="text-xs font-bold text-slate-100">{activeDronesCount} UAVs</div>
            </div>
            <div>
              <div className="text-[9px] text-slate-400">TARGETS</div>
              <div className="text-xs font-bold text-slate-100">{totalTargets}</div>
            </div>
            <div>
              <div className="text-[9px] text-slate-400">COVERAGE</div>
              <div className="text-xs font-bold text-sky-400">{coveragePct.toFixed(0)}%</div>
            </div>
          </div>
        </div>

        {/* Mission Setup Controls */}
        <div className="space-y-3 pt-1">
          <div className="text-[10px] font-mono font-semibold text-slate-400 uppercase tracking-wider px-1">
            Mission Setup
          </div>

          {/* Scenario Selector */}
          <div className="space-y-1">
            <label className="text-[11px] font-mono text-slate-300">Scenario</label>
            <select
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-sky-500 transition-colors"
            >
              {SCENARIOS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>

          {/* Fleet Size Slider */}
          <div className="space-y-1">
            <div className="flex justify-between text-[11px] font-mono">
              <span className="text-slate-300">Fleet Size</span>
              <span className="text-sky-400 font-bold">{fleetSize} UAVs</span>
            </div>
            <input
              type="range"
              min="2"
              max="8"
              step="1"
              value={fleetSize}
              onChange={(e) => setFleetSize(Number(e.target.value))}
              className="w-full accent-sky-500 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          {/* Wind Speed Slider */}
          <div className="space-y-1">
            <div className="flex justify-between text-[11px] font-mono">
              <span className="text-slate-300">Wind Speed</span>
              <span className="text-sky-400 font-bold">{windSpeed.toFixed(1)} m/s</span>
            </div>
            <input
              type="range"
              min="0.0"
              max="15.0"
              step="0.5"
              value={windSpeed}
              onChange={(e) => setWindSpeed(Number(e.target.value))}
              className="w-full accent-sky-500 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          {/* Wind Direction Slider */}
          <div className="space-y-1">
            <div className="flex justify-between text-[11px] font-mono">
              <span className="text-slate-300">Wind Direction</span>
              <span className="text-sky-400 font-bold">{windDir.toFixed(0)}°</span>
            </div>
            <input
              type="range"
              min="0"
              max="360"
              step="15"
              value={windDir}
              onChange={(e) => setWindDir(Number(e.target.value))}
              className="w-full accent-sky-500 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer"
            />
          </div>

          {/* Action Buttons */}
          <div className="pt-2 grid grid-cols-5 gap-2">
            <button
              onClick={onRunOptimizer}
              disabled={isSolving}
              className="col-span-3 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-sky-600 hover:bg-sky-500 active:bg-sky-700 text-white font-mono text-xs font-semibold shadow-md shadow-sky-600/30 transition-all disabled:opacity-50 cursor-pointer"
            >
              {isSolving ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Optimizing...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Run Optimizer</span>
                </>
              )}
            </button>

            <button
              onClick={onLoadMock}
              disabled={isSolving}
              className="col-span-2 flex items-center justify-center py-2 px-2 rounded-lg bg-slate-800 hover:bg-slate-700 active:bg-slate-900 text-slate-300 font-mono text-xs border border-slate-700 transition-all disabled:opacity-50 cursor-pointer"
            >
              <span>Load Mock</span>
            </button>
          </div>
        </div>
      </div>

      {/* System Hardware Status Footer */}
      <div className="p-4 border-t border-slate-800/80 bg-slate-950">
        <div className="grid grid-cols-3 gap-1.5 text-center font-mono text-[10px]">
          <div className="flex items-center justify-center gap-1 py-1 px-1.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
            <Radio className="w-2.5 h-2.5 text-emerald-400" />
            <span>RTK LOCK</span>
          </div>
          <div className="flex items-center justify-center gap-1 py-1 px-1.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
            <Shield className="w-2.5 h-2.5 text-sky-400" />
            <span>AES-256</span>
          </div>
          <div className="flex items-center justify-center gap-1 py-1 px-1.5 rounded bg-slate-900 border border-slate-800 text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>DECONFL</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
