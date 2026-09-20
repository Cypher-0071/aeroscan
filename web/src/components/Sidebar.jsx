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
  { id: 'map', label: 'Operations Map', icon: Compass },
  { id: 'telemetry', label: 'Fleet Telemetry', icon: Activity },
  { id: 'arena', label: 'Optimization Lab', icon: GitCompare },
  { id: 'energy', label: 'Energy & Battery', icon: BatteryCharging },
  { id: 'export', label: 'Mission Export', icon: DownloadCloud },
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
    <aside className="w-68 border-r border-slate-200/80 bg-white/70 backdrop-blur-2xl flex flex-col justify-between shrink-0 select-none overflow-y-auto h-screen sticky top-0 z-30 transition-colors font-sans">
      <div className="p-4 space-y-5">
        {/* Brand Header */}
        <div className="flex items-center justify-between pb-3.5 border-b border-slate-200/80">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-slate-900 flex items-center justify-center text-white shadow-xs">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polygon points="12 2 15 9 22 12 15 15 12 22 9 15 2 12 9 9 12 2" />
              </svg>
            </div>
            <div>
              <div className="text-xs font-semibold text-slate-900 tracking-tight flex items-center gap-1.5">
                AeroScan
                <span className="text-[9px] text-sky-700 bg-sky-50 px-1.5 py-0.2 border border-sky-200/70 rounded-full font-medium">
                  v2.0
                </span>
              </div>
              <div className="text-[11px] text-slate-400 font-normal">
                Swarm Mission Ops
              </div>
            </div>
          </div>
        </div>

        {/* Navigation Workspace Rail */}
        <div>
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2 px-1">
            Workspaces
          </div>
          <nav className="space-y-1">
            {WORKSPACE_TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all text-left cursor-pointer ${
                    isActive
                      ? 'bg-white text-slate-900 border border-slate-200/80 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/60 border border-transparent'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-sky-600' : 'text-slate-400'}`} />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Active Mission Context Card */}
        <div className="glass-card rounded-xl p-3.5 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-slate-900 truncate max-w-[140px]">
              {instance?.instance_name ?? 'Active Scenario'}
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/80 font-medium">
              Live
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-200/70 text-center">
            <div>
              <div className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Fleet</div>
              <div className="text-xs font-semibold text-slate-800 font-mono mt-0.5">{activeDronesCount} UAVs</div>
            </div>
            <div>
              <div className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Targets</div>
              <div className="text-xs font-semibold text-slate-800 font-mono mt-0.5">{totalTargets}</div>
            </div>
            <div>
              <div className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Coverage</div>
              <div className="text-xs font-semibold text-sky-600 font-mono mt-0.5">{coveragePct.toFixed(0)}%</div>
            </div>
          </div>
        </div>

        {/* Mission Setup Controls */}
        <div className="space-y-3.5 pt-1">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-1">
            Parameters
          </div>

          {/* Scenario Selector */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-600">Scenario Preset</label>
            <select
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
              className="glass-input w-full rounded-lg px-2.5 py-1.5 text-xs text-slate-800 cursor-pointer bg-white/80"
            >
              {SCENARIOS.map((s) => (
                <option key={s.id} value={s.id} className="bg-white text-slate-800">
                  {s.label}
                </option>
              ))}
            </select>
          </div>

          {/* Fleet Size Slider */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="text-slate-600 font-medium">Fleet Size</span>
              <span className="text-slate-900 font-semibold font-mono">{fleetSize} UAVs</span>
            </div>
            <input
              type="range"
              min="2"
              max="8"
              step="1"
              value={fleetSize}
              onChange={(e) => setFleetSize(Number(e.target.value))}
              className="w-full cursor-pointer"
            />
          </div>

          {/* Wind Speed Slider */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="text-slate-600 font-medium">Wind Speed</span>
              <span className="text-slate-900 font-semibold font-mono">{windSpeed.toFixed(1)} m/s</span>
            </div>
            <input
              type="range"
              min="0.0"
              max="15.0"
              step="0.5"
              value={windSpeed}
              onChange={(e) => setWindSpeed(Number(e.target.value))}
              className="w-full cursor-pointer"
            />
          </div>

          {/* Wind Direction Slider */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <span className="text-slate-600 font-medium">Wind Direction</span>
              <span className="text-slate-900 font-semibold font-mono">{windDir.toFixed(0)}°</span>
            </div>
            <input
              type="range"
              min="0"
              max="360"
              step="15"
              value={windDir}
              onChange={(e) => setWindDir(Number(e.target.value))}
              className="w-full cursor-pointer"
            />
          </div>

          {/* Action Buttons */}
          <div className="pt-2 grid grid-cols-5 gap-2">
            <button
              onClick={onRunOptimizer}
              disabled={isSolving}
              className="btn-primary col-span-3 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-medium cursor-pointer disabled:opacity-50"
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
              className="btn-secondary col-span-2 flex items-center justify-center py-2 px-2 rounded-lg text-xs font-medium cursor-pointer disabled:opacity-50"
            >
              <span>Load Mock</span>
            </button>
          </div>
        </div>
      </div>

      {/* System Hardware Status Footer */}
      <div className="p-3.5 border-t border-slate-200/80 bg-white/40">
        <div className="grid grid-cols-3 gap-1.5 text-center text-[10px] font-sans">
          <div className="glass-pill flex items-center justify-center gap-1 py-1 px-1.5 rounded-md text-slate-600 font-medium">
            <Radio className="w-2.5 h-2.5 text-emerald-600" />
            <span>RTK Lock</span>
          </div>
          <div className="glass-pill flex items-center justify-center gap-1 py-1 px-1.5 rounded-md text-slate-600 font-medium">
            <Shield className="w-2.5 h-2.5 text-sky-600" />
            <span>AES-256</span>
          </div>
          <div className="glass-pill flex items-center justify-center gap-1 py-1 px-1.5 rounded-md text-emerald-700 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>Deconflict</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
