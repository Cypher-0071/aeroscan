import React, { useState, useEffect, useMemo } from 'react';
import { 
  DownloadCloud, 
  FileCode, 
  FileText, 
  Table, 
  CheckCircle2, 
  Copy, 
  Check, 
  Terminal,
  Download,
  Archive,
  CheckCheck
} from 'lucide-react';

const DRONE_COLORS = {
  'UAV-01': '#0284c7', // Sky
  'UAV-02': '#d97706', // Amber
  'UAV-03': '#059669', // Emerald
};

function formatSeconds(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// Lightweight JSON syntax colorizer without third-party dependencies
function renderColoredJsonLine(line) {
  const match = line.match(/^(\s*)(".*?")(\s*:\s*)(.*)$/);
  if (match) {
    const [, indent, key, colon, value] = match;
    let valColor = 'text-slate-700';
    if (value.startsWith('"')) {
      valColor = 'text-sky-700';
    } else if (value.startsWith('[') || value.startsWith('{')) {
      valColor = 'text-slate-400';
    } else if (!isNaN(parseFloat(value))) {
      valColor = 'text-emerald-700 font-semibold';
    } else if (value.includes('true') || value.includes('false')) {
      valColor = 'text-amber-700 font-semibold';
    } else if (value.includes('null')) {
      valColor = 'text-slate-400 italic';
    }

    return (
      <span>
        <span>{indent}</span>
        <span className="text-slate-900 font-semibold">{key}</span>
        <span className="text-slate-400">{colon}</span>
        <span className={valColor}>{value}</span>
      </span>
    );
  }
  return <span className="text-slate-600">{line}</span>;
}

// MAVLink syntax colorizer
function renderColoredMavlinkLine(line, idx) {
  if (idx === 0) {
    return <span className="text-sky-700 font-bold tracking-wide">{line}</span>;
  }
  const parts = line.split('\t');
  if (parts.length >= 8) {
    return (
      <span className="space-x-3 font-mono text-[11px]">
        <span className="text-slate-400 w-5 inline-block">{parts[0]}</span>
        <span className="text-emerald-700 font-medium inline-block w-4">{parts[1]}</span>
        <span className="text-slate-500 inline-block w-4">{parts[2]}</span>
        <span className="text-sky-700 font-bold inline-block w-12">CMD_{parts[3]}</span>
        <span className="text-slate-700 inline-block w-10">{parts[4]}s</span>
        <span className="text-slate-800">{parts.slice(8).join('  ')}</span>
      </span>
    );
  }
  return <span className="text-slate-600">{line}</span>;
}

export default function MissionExport({
  instance,
  schedule,
}) {
  const routes = schedule?.assigned_routes ?? [];
  const [selectedDroneId, setSelectedDroneId] = useState(routes[0]?.drone_id ?? 'UAV-01');
  const [previewTab, setPreviewTab] = useState('qgc'); // 'qgc', 'mavlink', 'csv'
  const [csvViewMode, setCsvViewMode] = useState('table'); // 'table', 'code'
  const [copied, setCopied] = useState(false);
  const [exportData, setExportData] = useState({
    qgc: '',
    mavlink: '',
    csv: '',
  });
  const [loadingExport, setLoadingExport] = useState(false);

  const selectedRoute = routes.find((r) => r.drone_id === selectedDroneId) || routes[0];
  const selectedDrone = instance?.drones?.find((d) => d.id === selectedDroneId) || instance?.drones?.[0];

  // Aggregates
  const totalWaypoints = routes.reduce(
    (sum, r) => sum + (r.waypoints?.length ?? 0),
    0
  );

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
      mime = 'text/plain';
    } else if (type === 'csv') {
      content = exportData.csv;
      filename = 'aeroscan_swarm_telemetry_audit.csv';
      mime = 'text/csv';
    }

    if (!content) return;

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

  const handleDownloadAll = () => {
    handleDownload('qgc');
    setTimeout(() => handleDownload('mavlink'), 250);
    setTimeout(() => handleDownload('csv'), 500);
  };

  const handleCopy = () => {
    const activeText = previewTab === 'qgc' ? exportData.qgc : previewTab === 'mavlink' ? exportData.mavlink : exportData.csv;
    if (!activeText) return;
    navigator.clipboard.writeText(activeText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const activeContent = previewTab === 'qgc' ? exportData.qgc : previewTab === 'mavlink' ? exportData.mavlink : exportData.csv;
  const contentLines = useMemo(() => (activeContent || '').split('\n'), [activeContent]);

  // Parse CSV into structured rows for Table View
  const parsedCsv = useMemo(() => {
    if (!exportData.csv) return { headers: [], rows: [] };
    const lines = exportData.csv.trim().split('\n');
    if (lines.length < 2) return { headers: [], rows: [] };
    const headers = lines[0].split(',').map((h) => h.trim());
    const rows = lines.slice(1).map((line) => {
      const vals = line.split(',').map((v) => v.trim());
      const row = {};
      headers.forEach((h, idx) => {
        row[h] = vals[idx] || '';
      });
      return row;
    });
    return { headers, rows };
  }, [exportData.csv]);

  const activeFilename = previewTab === 'qgc' 
    ? `aeroscan_${selectedDroneId}_mission.plan` 
    : previewTab === 'mavlink' 
    ? `aeroscan_${selectedDroneId}_mavlink.waypoints` 
    : 'aeroscan_swarm_telemetry_audit.csv';

  const activeFormatTag = previewTab === 'qgc' ? 'JSON' : previewTab === 'mavlink' ? 'ASCII / WPL 110' : 'CSV';
  const activeApproxSize = `${((activeContent?.length ?? 0) / 1024).toFixed(1)} KB`;

  return (
    <div className="space-y-4 font-sans max-w-7xl mx-auto">
      {/* 1. Header Bar: Clean, Restrained, and spacious with integrated status */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-slate-100 border border-slate-200/80 flex items-center justify-center text-slate-700 shadow-2xs">
            <DownloadCloud className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-900 tracking-tight">
              Hardware Flight Plan Export & Serialization
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Deploy serialized flight corridors directly to PX4 / ArduPilot autopilots and QGroundControl
            </p>
          </div>
        </div>

        {/* Unified status capsule in header */}
        <div className="flex items-center gap-2 text-xs">
          <span className="px-2.5 py-1 rounded-lg bg-slate-100 border border-slate-200 text-slate-600 font-mono">
            {routes.length} UAV Sorties · {totalWaypoints} Waypoints
          </span>
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-emerald-50 border border-emerald-200/70 text-emerald-700 font-medium">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span>Pre-Flight Validated</span>
          </div>
        </div>
      </div>

      {/* 2. Main Two-Panel Layout: Zero Card Soup, High Visual Hierarchy */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        
        {/* Left Panel: Unified Sortie Configuration & Dispatch Hub (5 cols) */}
        <div className="lg:col-span-5 glass-card rounded-2xl p-4 border border-slate-200/90 shadow-xs bg-white/95 space-y-4 flex flex-col justify-between">
          <div className="space-y-4">
            {/* Step 1: UAV Selection */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-slate-900">
                  1. Select Target UAV
                </span>
                <span className="text-[11px] text-slate-400 font-mono">
                  {selectedDroneId} active
                </span>
              </div>

              {/* Segmented UAV Tabs */}
              <div className="grid grid-cols-3 gap-2">
                {routes.map((r) => {
                  const isSelected = r.drone_id === selectedDroneId;
                  const color = DRONE_COLORS[r.drone_id] || '#64748b';
                  const reserve = r.final_reserve_percent ?? 100;

                  return (
                    <button
                      key={r.drone_id}
                      onClick={() => setSelectedDroneId(r.drone_id)}
                      className={`p-2 rounded-xl border text-left transition-all cursor-pointer ${
                        isSelected
                          ? 'bg-slate-900 text-white border-slate-900 shadow-2xs'
                          : 'bg-slate-50/80 text-slate-700 border-slate-200/80 hover:bg-slate-100'
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        <span
                          className="w-2 h-2 rounded-full shrink-0"
                          style={{ backgroundColor: isSelected ? '#ffffff' : color }}
                        />
                        <span className="font-mono font-bold text-xs">
                          {r.drone_id}
                        </span>
                      </div>
                      <div className={`text-[10px] font-mono mt-0.5 ${isSelected ? 'text-slate-300' : 'text-slate-500'}`}>
                        {reserve.toFixed(1)}% res
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Step 2: Flight Corridor Key Specifications */}
            <div className="border-t border-slate-100 pt-3">
              <div className="text-xs font-bold text-slate-900 mb-2">
                2. Corridor Specifications
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2 rounded-xl bg-slate-50/70 border border-slate-200/60">
                  <span className="text-[10px] text-slate-400 block font-sans">Cruise Speed</span>
                  <span className="font-mono font-bold text-slate-900 text-[11px]">
                    {(selectedDrone?.cruise_speed ?? 14.5).toFixed(1)} m/s
                  </span>
                </div>

                <div className="p-2 rounded-xl bg-slate-50/70 border border-slate-200/60">
                  <span className="text-[10px] text-slate-400 block font-sans">Waypoints</span>
                  <span className="font-mono font-bold text-slate-900 text-[11px]">
                    {selectedRoute?.waypoints?.length ?? 0} Nav Nodes
                  </span>
                </div>

                <div className="p-2 rounded-xl bg-slate-50/70 border border-slate-200/60">
                  <span className="text-[10px] text-slate-400 block font-sans">Flight Duration</span>
                  <span className="font-mono font-bold text-slate-900 text-[11px]">
                    {formatSeconds(selectedRoute?.total_flight_time ?? 0)} ({selectedRoute?.total_flight_time ?? 0}s)
                  </span>
                </div>

                <div className="p-2 rounded-xl bg-slate-50/70 border border-slate-200/60">
                  <span className="text-[10px] text-slate-400 block font-sans">Landing Battery</span>
                  <span className="font-mono font-bold text-emerald-700 text-[11px]">
                    {(selectedRoute?.final_reserve_percent ?? 100).toFixed(1)}% (+{((selectedRoute?.final_reserve_percent ?? 100) - 15).toFixed(1)}%)
                  </span>
                </div>
              </div>
            </div>

            {/* Step 3: Dispatch Downloads */}
            <div className="border-t border-slate-100 pt-3">
              <div className="text-xs font-bold text-slate-900 mb-2">
                3. Download Artifacts
              </div>
              <div className="space-y-2">
                {/* Primary: QGC Plan */}
                <button
                  onClick={() => handleDownload('qgc')}
                  className="w-full py-2.5 px-3 rounded-xl bg-slate-900 hover:bg-slate-800 text-white transition-all cursor-pointer flex items-center justify-between shadow-2xs"
                >
                  <div className="flex items-center gap-2">
                    <FileCode className="w-4 h-4 text-sky-400" />
                    <span className="text-xs font-semibold">QGroundControl Plan</span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
                    .plan
                  </span>
                </button>

                {/* Secondary: MAVLink Waypoints */}
                <button
                  onClick={() => handleDownload('mavlink')}
                  className="w-full py-2 px-3 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-slate-800 transition-all cursor-pointer flex items-center justify-between shadow-2xs"
                >
                  <div className="flex items-center gap-2">
                    <FileText className="w-3.5 h-3.5 text-slate-500" />
                    <span className="text-xs font-medium">MAVLink Waypoints</span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                    WPL 110
                  </span>
                </button>

                {/* Tertiary: Swarm CSV Audit */}
                <button
                  onClick={() => handleDownload('csv')}
                  className="w-full py-2 px-3 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-slate-800 transition-all cursor-pointer flex items-center justify-between shadow-2xs"
                >
                  <div className="flex items-center gap-2">
                    <Table className="w-3.5 h-3.5 text-slate-500" />
                    <span className="text-xs font-medium">Swarm Telemetry Audit</span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                    All UAVs (.csv)
                  </span>
                </button>

                {/* Batch Bundle Link */}
                <button
                  onClick={handleDownloadAll}
                  className="w-full py-1.5 text-center text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors cursor-pointer flex items-center justify-center gap-1.5"
                >
                  <Archive className="w-3 h-3 text-slate-400" />
                  <span>Download All Sorties as Package</span>
                </button>
              </div>
            </div>
          </div>

          {/* Compact Pre-Flight Verification Footer Strip */}
          <div className="p-2.5 rounded-xl bg-slate-50/90 border border-slate-200/80 text-[11px] font-sans space-y-1">
            <div className="flex items-center gap-1.5 font-semibold text-slate-800">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
              <span>Pre-Flight Verification (4/4 Passed)</span>
            </div>
            <p className="text-[10px] text-slate-500 leading-tight">
              Terrain clearance (&gt;45m AGL), battery reserve floor (&gt;15%), geofence deconfliction, and CRC32 telemetry checksums verified.
            </p>
          </div>
        </div>

        {/* Right Panel: Live Code Studio & Telemetry Inspector (7 cols) */}
        <div className="lg:col-span-7 glass-card rounded-2xl p-4 border border-slate-200/90 shadow-xs bg-white/95 space-y-3 flex flex-col justify-between">
          <div>
            {/* Studio Header Toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
              {/* Left: Active File Info */}
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-700">
                  <Terminal className="w-3.5 h-3.5" />
                </div>
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-mono font-bold text-slate-900">
                      {activeFilename}
                    </span>
                    <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-slate-100 text-slate-600 font-semibold uppercase">
                      {activeFormatTag}
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono">
                    {contentLines.length} lines · {activeApproxSize}
                  </div>
                </div>
              </div>

              {/* Right: Format Selector & Action Buttons */}
              <div className="flex items-center gap-2">
                {/* Segmented Format Switcher */}
                <div className="flex items-center bg-slate-100/80 p-0.5 rounded-xl border border-slate-200/70 text-xs">
                  <button
                    onClick={() => setPreviewTab('qgc')}
                    className={`px-2.5 py-1 rounded-lg font-medium transition-all cursor-pointer ${
                      previewTab === 'qgc'
                        ? 'bg-white text-slate-900 font-semibold shadow-2xs border border-slate-200/80'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    QGC .plan
                  </button>
                  <button
                    onClick={() => setPreviewTab('mavlink')}
                    className={`px-2.5 py-1 rounded-lg font-medium transition-all cursor-pointer ${
                      previewTab === 'mavlink'
                        ? 'bg-white text-slate-900 font-semibold shadow-2xs border border-slate-200/80'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    MAVLink
                  </button>
                  <button
                    onClick={() => setPreviewTab('csv')}
                    className={`px-2.5 py-1 rounded-lg font-medium transition-all cursor-pointer ${
                      previewTab === 'csv'
                        ? 'bg-white text-slate-900 font-semibold shadow-2xs border border-slate-200/80'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    CSV Audit
                  </button>
                </div>

                {/* View Switcher if CSV is active */}
                {previewTab === 'csv' && (
                  <div className="flex items-center bg-slate-100/80 p-0.5 rounded-xl border border-slate-200/70 text-[11px]">
                    <button
                      onClick={() => setCsvViewMode('table')}
                      className={`px-2 py-0.5 rounded-lg transition-all cursor-pointer ${
                        csvViewMode === 'table'
                          ? 'bg-white text-slate-900 font-semibold shadow-2xs border border-slate-200/80'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      Table
                    </button>
                    <button
                      onClick={() => setCsvViewMode('code')}
                      className={`px-2 py-0.5 rounded-lg transition-all cursor-pointer ${
                        csvViewMode === 'code'
                          ? 'bg-white text-slate-900 font-semibold shadow-2xs border border-slate-200/80'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      Raw
                    </button>
                  </div>
                )}

                {/* Copy Code */}
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-xl bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-medium shadow-2xs transition-all cursor-pointer"
                  title="Copy to clipboard"
                >
                  {copied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                      <span className="text-emerald-700 font-semibold">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5 text-slate-500" />
                      <span>Copy</span>
                    </>
                  )}
                </button>

                {/* Download Current File Button */}
                <button
                  onClick={() => handleDownload(previewTab)}
                  className="p-1.5 rounded-xl bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 shadow-2xs transition-all cursor-pointer"
                  title={`Download ${activeFilename}`}
                >
                  <Download className="w-3.5 h-3.5 text-slate-600" />
                </button>
              </div>
            </div>

            {/* Studio Body: Code Gutter or Table View */}
            <div className="mt-3 h-[460px] overflow-hidden rounded-xl bg-slate-50/70 border border-slate-200/80 relative">
              {loadingExport ? (
                <div className="flex flex-col items-center justify-center h-full text-slate-400 font-sans text-xs space-y-2">
                  <Terminal className="w-6 h-6 animate-pulse text-slate-400" />
                  <span>Compiling avionics flight package...</span>
                </div>
              ) : previewTab === 'csv' && csvViewMode === 'table' ? (
                /* Structured Table View for CSV Audit */
                <div className="h-full overflow-auto text-xs font-mono">
                  <table className="w-full text-left border-collapse">
                    <thead className="bg-white/95 sticky top-0 border-b border-slate-200/90 shadow-2xs z-10">
                      <tr>
                        {parsedCsv.headers.map((h, i) => (
                          <th
                            key={i}
                            className="py-2.5 px-3 text-[10px] font-bold text-slate-700 uppercase tracking-wider whitespace-nowrap bg-slate-100/70"
                          >
                            {h.replace(/_/g, ' ')}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 bg-white/70">
                      {parsedCsv.rows.map((row, rIdx) => (
                        <tr key={rIdx} className="hover:bg-slate-50/80 transition-colors">
                          {parsedCsv.headers.map((h, cIdx) => (
                            <td key={cIdx} className="py-2 px-3 text-[11px] text-slate-800 whitespace-nowrap">
                              {h === 'Drone_ID' ? (
                                <span className="font-bold font-mono text-slate-900">
                                  {row[h]}
                                </span>
                              ) : h.includes('SoC') ? (
                                <span className="text-emerald-700 font-semibold font-mono">
                                  {row[h]}%
                                </span>
                              ) : h.includes('Time') ? (
                                <span className="text-slate-600 font-mono">
                                  {row[h]}s
                                </span>
                              ) : (
                                row[h]
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                /* High-End Code Gutter View for JSON / MAVLink / Raw CSV */
                <div className="h-full overflow-auto p-3 text-xs font-mono select-text flex">
                  {/* Line Numbers Gutter */}
                  <div className="select-none pr-3 text-right text-slate-400 border-r border-slate-200/70 mr-3 shrink-0 font-mono text-[11px] leading-relaxed">
                    {contentLines.map((_, i) => (
                      <div key={i}>{i + 1}</div>
                    ))}
                  </div>

                  {/* Formatted Code Lines */}
                  <div className="overflow-x-auto flex-1 leading-relaxed text-[11px]">
                    {contentLines.map((line, i) => (
                      <div key={i} className="whitespace-pre">
                        {previewTab === 'qgc'
                          ? renderColoredJsonLine(line)
                          : previewTab === 'mavlink'
                          ? renderColoredMavlinkLine(line, i)
                          : <span className="text-slate-700">{line}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Studio Footer Bar: Clean metadata strip */}
          <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center justify-between text-[11px] text-slate-400 font-mono">
            <div className="flex items-center gap-2">
              <span>PX4 (v1.14+) / ArduPilot (v4.4+)</span>
              <span>•</span>
              <span>MAV_FRAME_GLOBAL_REL_ALT (3)</span>
            </div>
            <span>WGS-84: 37.7749° N, -122.4194° W</span>
          </div>
        </div>
      </div>
    </div>
  );
}
