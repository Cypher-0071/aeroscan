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
  Cpu,
  Wind
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

const getCardinal = (deg) => {
  const normalized = ((deg % 360) + 360) % 360;
  if (normalized >= 337.5 || normalized < 22.5) return 'East (0°)';
  if (normalized >= 22.5 && normalized < 67.5) return 'NE (45°)';
  if (normalized >= 67.5 && normalized < 112.5) return 'North (90°)';
  if (normalized >= 112.5 && normalized < 157.5) return 'NW (135°)';
  if (normalized >= 157.5 && normalized < 202.5) return 'West (180°)';
  if (normalized >= 202.5 && normalized < 247.5) return 'SW (225°)';
  if (normalized >= 247.5 && normalized < 292.5) return 'South (270°)';
  return 'SE (315°)';
};

const getWindCategory = (spd) => {
  if (spd < 2.0) return 'Light Air';
  if (spd < 6.0) return 'Moderate Breeze';
  if (spd < 10.0) return 'Strong Wind';
  return 'High Wind Warning';
};

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
  const activeDronesCount = instance?.drones?.length ?? 3;
  const activeWindSpd = instance?.ambient_wind?.speed_mps ?? 3.5;
  const activeWindDir = instance?.ambient_wind?.direction_deg ?? 45;

  const isParamsChanged =
    fleetSize !== activeDronesCount ||
    Math.abs(windSpeed - activeWindSpd) > 0.1 ||
    Math.abs(windDir - activeWindDir) > 1;

  const cardinalDir = getCardinal(windDir);
  const windRating = getWindCategory(windSpeed);
  const minGroundspeed = Math.max(1.0, 14.5 - windSpeed).toFixed(1);
  const maxGroundspeed = (14.5 + windSpeed).toFixed(1);
  const energyImpactPct = ((Math.pow((14.5 + windSpeed * 0.5) / 14.5, 2) - 1) * 100).toFixed(0);

  const fleetCapacityLabel = 
    fleetSize === 2 
      ? 'Recon Pair ~40%' 
      : fleetSize <= 4 
        ? 'Balanced ~70%' 
        : 'Full Swarm ~95%';

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

        {/* Mission Setup Controls */}
        <div className="space-y-4 pt-2">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-1">
            Mission Parameters
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

          {/* Dynamic Execution Dependence Impact Card */}
          <div className="rounded-xl p-3 bg-slate-50/90 border border-slate-200/80 space-y-2 text-xs">
            <div className="flex items-center justify-between font-medium text-slate-700">
              <span className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-900">
                <Wind className="w-3.5 h-3.5 text-sky-600" />
                <span>Execution Dynamics</span>
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-md bg-sky-100 text-sky-800 font-semibold">
                {cardinalDir} · {windRating}
              </span>
            </div>

            <div className="space-y-1 text-[11px] pt-1.5 border-t border-slate-200/70">
              <div className="flex justify-between">
                <span className="text-slate-500">Fleet Capacity:</span>
                <span className="font-mono text-slate-800 font-semibold">
                  {fleetSize} UAVs ({fleetCapacityLabel})
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Headwind Speed:</span>
                <span className="font-mono font-semibold text-amber-700">
                  {minGroundspeed} m/s <span className="text-slate-400 font-normal">(-{windSpeed.toFixed(1)})</span>
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Tailwind Speed:</span>
                <span className="font-mono font-semibold text-emerald-600">
                  {maxGroundspeed} m/s <span className="text-slate-400 font-normal">(+{windSpeed.toFixed(1)})</span>
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Upwind Energy Drag:</span>
                <span className="font-mono font-semibold text-rose-600">
                  +{energyImpactPct}% Watts
                </span>
              </div>
            </div>

            {isParamsChanged && (
              <div className="pt-1.5 border-t border-amber-200/70 flex items-center gap-1.5 text-[10px] text-amber-800 font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-ping"></span>
                <span>Modified • Click Run Optimizer to solve</span>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="pt-1 grid grid-cols-5 gap-2">
            <button
              onClick={onRunOptimizer}
              disabled={isSolving}
              className={`col-span-3 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-medium cursor-pointer disabled:opacity-50 transition-all ${
                isParamsChanged 
                  ? 'btn-primary ring-2 ring-sky-500 ring-offset-1 shadow-md' 
                  : 'btn-primary'
              }`}
            >
              {isSolving ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Optimizing...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>{isParamsChanged ? 'Re-solve Swarm' : 'Run Optimizer'}</span>
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
