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
import CustomSelect from './CustomSelect';

const WORKSPACE_TABS = [
  { id: 'map', label: 'Operations Map', icon: Compass },
  { id: 'telemetry', label: 'Fleet Telemetry', icon: Activity },
  { id: 'arena', label: 'Optimization Lab', icon: GitCompare },
  { id: 'energy', label: 'Energy & Battery', icon: BatteryCharging },
  { id: 'export', label: 'Mission Export', icon: DownloadCloud },
];

const SCENARIOS = [
  { value: 'Chao Set 64 (Clustered SAR)', label: 'Chao Set 64 (Clustered SAR)', badge: '64 nodes' },
  { value: 'Chao Set 66 (Diamond Perimeter)', label: 'Chao Set 66 (Diamond Perimeter)', badge: '66 nodes' },
  { value: 'Chao Set 100 (Concentric Grid)', label: 'Chao Set 100 (Concentric Grid)', badge: '100 nodes' },
  { value: 'Chao Set 102 (Uniform Scatter)', label: 'Chao Set 102 (Uniform Scatter)', badge: '102 nodes' },
  { value: 'Sample Mountain SAR', label: 'Sample Mountain SAR', badge: 'GeoJSON' },
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
            <CustomSelect
              value={scenario}
              onChange={(val) => setScenario(val)}
              options={SCENARIOS}
            />
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

          {/* Clean Atmospheric Impact Summary */}
          <div className="rounded-xl p-2.5 bg-slate-50/80 border border-slate-200/70 space-y-1.5 text-xs">
            <div className="flex items-center justify-between text-[11px] text-slate-600">
              <span className="flex items-center gap-1 font-medium">
                <Wind className="w-3 h-3 text-sky-600" />
                <span>Atmosphere</span>
              </span>
              <span className="font-mono text-slate-800 font-semibold">
                {windSpeed.toFixed(1)} m/s · {cardinalDir}
              </span>
            </div>

            <div className="flex justify-between text-[11px] pt-1 border-t border-slate-200/60">
              <span className="text-slate-500">Groundspeed:</span>
              <span className="font-mono font-medium text-slate-700">
                {minGroundspeed} – {maxGroundspeed} m/s
              </span>
            </div>
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

      {/* System Status Footer */}
      <div className="p-3 border-t border-slate-200/70 bg-white/40">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-slate-500">System Status</span>
          <span className="text-emerald-700 font-medium flex items-center gap-1.5 font-mono text-[10px]">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            Ready
          </span>
        </div>
      </div>
    </aside>
  );
}
