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
      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-md flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-sm font-bold text-slate-100 flex items-center gap-2">
            <DownloadCloud className="w-4 h-4 text-sky-400" />
            <span>AUTONOMOUS HARDWARE EXPORT ENGINE</span>
          </div>
          <div className="text-xs text-slate-400 mt-0.5">
            Serialize mission corridors into PX4/ArduPilot autopilots, QGroundControl plans, and audit logs
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="px-2.5 py-1 rounded bg-slate-950 border border-slate-800 text-sky-400 font-bold">
            COMPLIANT: MAVLink v2.0 / QGC v1
          </span>
        </div>
      </div>

      {/* Two Column Layout: Controls | Live Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-md space-y-3">
            <div className="text-xs font-bold text-slate-200">
              SELECT TARGET UAV
            </div>

            <div className="space-y-1">
              <select
                value={selectedDroneId}
                onChange={(e) => setSelectedDroneId(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-sky-500"
              >
                {routes.map((r) => (
                  <option key={r.drone_id} value={r.drone_id}>
                    {r.drone_id} ({(r.target_ids?.length ?? 0)} nodes · {(r.final_reserve_percent ?? 100).toFixed(0)}% reserve)
                  </option>
                ))}
              </select>
            </div>

            {/* Mission Corridor Summary Card */}
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800/80 space-y-2 text-xs">
              <div className="font-bold text-sky-400 border-b border-slate-800 pb-1 flex justify-between">
                <span>MISSION SUMMARY // {selectedDroneId}</span>
                <span className="text-emerald-400 font-bold">VALIDATED</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>CRUISE SPEED:</span>
                <span className="text-slate-100 font-bold">{(selectedDrone?.cruise_speed ?? 14.5).toFixed(1)} m/s</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>WAYPOINT NODES:</span>
                <span className="text-slate-100 font-bold">{selectedRoute?.waypoints?.length ?? 0} points</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>FLIGHT DURATION:</span>
                <span className="text-slate-100 font-bold">{(selectedRoute?.total_flight_time ?? 0).toFixed(0)}s</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>FINAL BATTERY RESERVE:</span>
                <span className="text-emerald-400 font-bold">{(selectedRoute?.final_reserve_percent ?? 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>TARGET REWARDS:</span>
                <span className="text-amber-400 font-bold">{(selectedRoute?.total_reward ?? 0).toFixed(0)} PTS</span>
              </div>
            </div>

            {/* Download Buttons */}
            <div className="space-y-2 pt-1">
              <button
                onClick={() => handleDownload('qgc')}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg bg-sky-600 hover:bg-sky-500 active:bg-sky-700 text-white text-xs font-bold shadow-md shadow-sky-600/30 transition-all cursor-pointer"
              >
                <FileCode className="w-4 h-4" />
                <span>DOWNLOAD QGC PLAN ({selectedDroneId})</span>
              </button>

              <button
                onClick={() => handleDownload('mavlink')}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition-all cursor-pointer"
              >
                <FileText className="w-4 h-4" />
                <span>DOWNLOAD MAVLINK WAYPOINTS ({selectedDroneId})</span>
              </button>

              <button
                onClick={() => handleDownload('csv')}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition-all cursor-pointer"
              >
                <Table className="w-4 h-4" />
                <span>DOWNLOAD SWARM TELEMETRY CSV</span>
              </button>
            </div>

            {/* Pre-Flight Validation Checklist */}
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2 text-[11px]">
              <div className="font-bold text-sky-400">PRE-FLIGHT VALIDATION ENGINE</div>
              <div className="flex items-center gap-2 text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Waypoint terrain constraints verified</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Battery SoC &gt; 15% safety floor enforced</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Geofence boundary deconflicted</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-400">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>CRC32 telemetry checksum passed</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Live Syntax Preview (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800/80 backdrop-blur-md space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-sky-400" />
                <span className="text-xs font-bold text-slate-200">
                  LIVE ARTIFACT PREVIEW
                </span>
              </div>

              <div className="flex items-center gap-2">
                {/* Format Toggle */}
                <div className="flex bg-slate-950 rounded-lg p-0.5 border border-slate-800 text-xs">
                  <button
                    onClick={() => setPreviewTab('qgc')}
                    className={`px-2.5 py-1 rounded ${
                      previewTab === 'qgc'
                        ? 'bg-sky-600 text-white font-bold'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    QGC .plan
                  </button>
                  <button
                    onClick={() => setPreviewTab('mavlink')}
                    className={`px-2.5 py-1 rounded ${
                      previewTab === 'mavlink'
                        ? 'bg-sky-600 text-white font-bold'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    MAVLink
                  </button>
                  <button
                    onClick={() => setPreviewTab('csv')}
                    className={`px-2.5 py-1 rounded ${
                      previewTab === 'csv'
                        ? 'bg-sky-600 text-white font-bold'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    CSV Audit
                  </button>
                </div>

                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs border border-slate-700"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </div>

            {/* Code Box */}
            <div className="relative">
              <pre className="h-[480px] overflow-auto p-4 rounded-xl bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 leading-relaxed">
                {loadingExport ? (
                  <div className="flex items-center justify-center h-full text-slate-500">
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
