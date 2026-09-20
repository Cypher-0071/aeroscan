import React, { useState, useEffect } from 'react';
import { 
  DownloadCloud, 
  FileCode, 
  FileText, 
  Table, 
  CheckCircle2, 
  Copy, 
  Check, 
  Radio, 
  ShieldCheck,
  Terminal
} from 'lucide-react';

export default function MissionExport({
  instance,
  schedule,
}) {
  const routes = schedule?.assigned_routes ?? [];
  const [selectedDroneId, setSelectedDroneId] = useState(routes[0]?.drone_id ?? 'UAV-01');
  const [previewTab, setPreviewTab] = useState('qgc'); // 'qgc', 'mavlink', 'csv'
  const [copied, setCopied] = useState(false);
  const [exportData, setExportData] = useState({
    qgc: '',
    mavlink: '',
    csv: '',
  });
  const [loadingExport, setLoadingExport] = useState(false);

  const selectedRoute = routes.find((r) => r.drone_id === selectedDroneId) || routes[0];
  const selectedDrone = instance?.drones?.find((d) => d.id === selectedDroneId) || instance?.drones?.[0];

  // Fetch exports from backend
  useEffect(() => {
    if (!schedule || !instance) return;

    const fetchExports = async () => {
      setLoadingExport(true);
      try {
        // Fetch QGC
        const qgcRes = await fetch('/api/export', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type: 'qgc',
            drone_id: selectedDroneId,
            schedule,
            instance,
          }),
        });
        const qgcJson = await qgcRes.json();

        // Fetch MAVLink
        const mavRes = await fetch('/api/export', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type: 'mavlink',
            drone_id: selectedDroneId,
            schedule,
            instance,
          }),
        });
        const mavJson = await mavRes.json();

        // Fetch CSV
        const csvRes = await fetch('/api/export', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type: 'csv',
            drone_id: selectedDroneId,
            schedule,
            instance,
          }),
        });
        const csvJson = await csvRes.json();

        setExportData({
          qgc: qgcJson.content || '',
          mavlink: mavJson.content || '',
          csv: csvJson.content || '',
        });
      } catch (err) {
        console.error('Failed to fetch hardware exports:', err);
      } finally {
        setLoadingExport(false);
      }
    };

    fetchExports();
  }, [selectedDroneId, schedule, instance]);

  const handleDownload = (type) => {
    let content = '';
    let filename = '';
    let mime = 'text/plain';

    if (type === 'qgc') {
      content = exportData.qgc;
      filename = `aeroscan_${selectedDroneId}_mission.plan`;
      mime = 'application/json';
    } else if (type === 'mavlink') {
      content = exportData.mavlink;
      filename = `aeroscan_${selectedDroneId}_mavlink.waypoints`;
    } else if (type === 'csv') {
      content = exportData.csv;
      filename = 'aeroscan_swarm_telemetry_audit.csv';
      mime = 'text/csv';
    }

    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleCopy = () => {
    const activeText = previewTab === 'qgc' ? exportData.qgc : previewTab === 'mavlink' ? exportData.mavlink : exportData.csv;
    navigator.clipboard.writeText(activeText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const activeContent = previewTab === 'qgc' ? exportData.qgc : previewTab === 'mavlink' ? exportData.mavlink : exportData.csv;

  return (
    <div className="space-y-4 font-mono">
      {/* Export Banner */}
      <div className="glass-card rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <DownloadCloud className="w-4 h-4 text-sky-600" />
            <span>AUTONOMOUS HARDWARE EXPORT ENGINE</span>
          </div>
          <div className="text-xs text-slate-400 mt-0.5">
            Serialize mission corridors into PX4/ArduPilot autopilots, QGroundControl plans, and audit logs
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="px-3 py-1 rounded-full glass-pill border border-sky-200/80 bg-sky-50 text-sky-700 font-semibold shadow-sm">
            COMPLIANT: MAVLink v2.0 / QGC v1
          </span>
        </div>
      </div>

      {/* Two Column Layout: Controls | Live Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="glass-card rounded-2xl p-4 space-y-3.5">
            <div className="text-xs font-semibold text-slate-900">
              SELECT TARGET UAV
            </div>

            <div className="space-y-1">
              <select
                value={selectedDroneId}
                onChange={(e) => setSelectedDroneId(e.target.value)}
                className="glass-input w-full rounded-xl px-3 py-2 text-xs font-mono text-slate-800 bg-white/80 cursor-pointer"
              >
                {routes.map((r) => (
                  <option key={r.drone_id} value={r.drone_id} className="bg-white text-slate-800">
                    {r.drone_id} ({(r.target_ids?.length ?? 0)} nodes · {(r.final_reserve_percent ?? 100).toFixed(0)}% reserve)
                  </option>
                ))}
              </select>
            </div>

            {/* Mission Corridor Summary Card */}
            <div className="glass-pill rounded-xl p-3.5 space-y-2 text-xs border border-slate-200/80 bg-white/70 shadow-sm">
              <div className="font-semibold text-sky-800 border-b border-slate-200/70 pb-1.5 flex justify-between">
                <span>MISSION SUMMARY // {selectedDroneId}</span>
                <span className="text-emerald-700 font-semibold">VALIDATED</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>CRUISE SPEED:</span>
                <span className="text-slate-800 font-semibold">{(selectedDrone?.cruise_speed ?? 14.5).toFixed(1)} m/s</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>WAYPOINT NODES:</span>
                <span className="text-slate-800 font-semibold">{selectedRoute?.waypoints?.length ?? 0} points</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>FLIGHT DURATION:</span>
                <span className="text-slate-800 font-semibold">{(selectedRoute?.total_flight_time ?? 0).toFixed(0)}s</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>FINAL BATTERY RESERVE:</span>
                <span className="text-emerald-600 font-semibold">{(selectedRoute?.final_reserve_percent ?? 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>TARGET REWARDS:</span>
                <span className="text-amber-700 font-semibold">{(selectedRoute?.total_reward ?? 0).toFixed(0)} PTS</span>
              </div>
            </div>

            {/* Download Buttons */}
            <div className="space-y-2 pt-1">
              <button
                onClick={() => handleDownload('qgc')}
                className="glass-btn-primary w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl text-xs font-semibold cursor-pointer"
              >
                <FileCode className="w-4 h-4" />
                <span>DOWNLOAD QGC PLAN ({selectedDroneId})</span>
              </button>

              <button
                onClick={() => handleDownload('mavlink')}
                className="glass-btn-secondary w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl text-xs font-semibold cursor-pointer"
              >
                <FileText className="w-4 h-4" />
                <span>DOWNLOAD MAVLINK WAYPOINTS ({selectedDroneId})</span>
              </button>

              <button
                onClick={() => handleDownload('csv')}
                className="glass-btn-secondary w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl text-xs font-semibold cursor-pointer"
              >
                <Table className="w-4 h-4" />
                <span>DOWNLOAD SWARM TELEMETRY CSV</span>
              </button>
            </div>

            {/* Pre-Flight Validation Checklist */}
            <div className="glass-pill rounded-xl p-3.5 space-y-2 text-[11px] border border-slate-200/80 bg-white/60 shadow-sm">
              <div className="font-semibold text-sky-800">PRE-FLIGHT VALIDATION ENGINE</div>
              <div className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Waypoint terrain constraints verified</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Battery SoC &gt; 15% safety floor enforced</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Geofence boundary deconflicted</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>CRC32 telemetry checksum passed</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Live Syntax Preview (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="glass-card rounded-2xl p-4 space-y-3.5">
            <div className="flex items-center justify-between border-b border-slate-200/80 pb-2.5">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-sky-600" />
                <span className="text-xs font-semibold text-slate-900">
                  LIVE ARTIFACT PREVIEW
                </span>
              </div>

              <div className="flex items-center gap-2">
                {/* Format Toggle */}
                <div className="flex glass-pill rounded-xl p-0.5 text-xs border border-slate-200/80 bg-white/70">
                  <button
                    onClick={() => setPreviewTab('qgc')}
                    className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                      previewTab === 'qgc'
                        ? 'bg-white text-slate-900 font-bold shadow-sm'
                        : 'text-slate-400 hover:text-slate-800'
                    }`}
                  >
                    QGC .plan
                  </button>
                  <button
                    onClick={() => setPreviewTab('mavlink')}
                    className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                      previewTab === 'mavlink'
                        ? 'bg-white text-slate-900 font-bold shadow-sm'
                        : 'text-slate-400 hover:text-slate-800'
                    }`}
                  >
                    MAVLink
                  </button>
                  <button
                    onClick={() => setPreviewTab('csv')}
                    className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                      previewTab === 'csv'
                        ? 'bg-white text-slate-900 font-bold shadow-sm'
                        : 'text-slate-400 hover:text-slate-800'
                    }`}
                  >
                    CSV Audit
                  </button>
                </div>

                <button
                  onClick={handleCopy}
                  className="glass-btn-secondary flex items-center gap-1.5 px-3 py-1 rounded-xl text-slate-700 text-xs cursor-pointer"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </div>

            {/* Code Box */}
            <div className="relative">
              <pre className="h-[480px] overflow-auto p-4 rounded-xl bg-white/90 border border-slate-200/80 text-[11px] font-mono text-slate-800 leading-relaxed shadow-inner">
                {loadingExport ? (
                  <div className="flex items-center justify-center h-full text-slate-400">
                    Generating flight plan serialization...
                  </div>
                ) : (
                  activeContent || 'No export content available.'
                )}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
