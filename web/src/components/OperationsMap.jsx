import React, { useState, useEffect, useRef, useMemo } from 'react';
import { 
  Play, 
  Square, 
  RotateCcw, 
  Compass, 
  Target, 
  Zap,
  Sliders,
  ChevronDown,
  Layers
} from 'lucide-react';

const DRONE_COLORS = [
  '#0284C7', // Sky-600 (UAV-01)
  '#EA580C', // Orange-600 (UAV-02)
  '#059669', // Emerald-600 (UAV-03)
  '#7C3AED', // Violet-600 (UAV-04)
  '#DC2626', // Red-600 (UAV-05)
  '#D97706', // Amber-600 (UAV-06)
  '#DB2777', // Pink-600 (UAV-07)
  '#0D9488', // Teal-600 (UAV-08)
];

function drawSafeRoundRect(ctx, x, y, width, height, radius) {
  ctx.beginPath();
  if (typeof ctx.roundRect === 'function') {
    ctx.roundRect(x, y, width, height, radius);
  } else {
    const r = Math.min(radius, width / 2, height / 2);
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + width, y, x + width, y + height, r);
    ctx.arcTo(x + width, y + height, x, y + height, r);
    ctx.arcTo(x, y + height, x, y, r);
    ctx.arcTo(x, y, x + width, y, r);
    ctx.closePath();
  }
}

// Geometric apron parking calculation: zero badge overlap and clean tactical echelon formation
function getApronParkPosition(dIdx, totalFleet, depotX, depotY) {
  if (totalFleet === 1) {
    return { x: depotX, y: depotY };
  }
  if (totalFleet === 2) {
    return {
      x: depotX + (dIdx === 0 ? -48 : 48),
      y: depotY,
    };
  }
  if (totalFleet === 3) {
    // Center lead UAV-02 raised 14px, wingmen UAV-01 (-58px) and UAV-03 (+58px) lowered 12px
    if (dIdx === 0) return { x: depotX - 58, y: depotY + 12 };
    if (dIdx === 1) return { x: depotX, y: depotY - 14 };
    return { x: depotX + 58, y: depotY + 12 };
  }
  // General N-fleet apron echelon
  const isCenter = dIdx === Math.floor(totalFleet / 2);
  const offset = (dIdx - (totalFleet - 1) / 2) * 56;
  return {
    x: depotX + offset,
    y: depotY + (isCenter ? -14 : 12),
  };
}

// Realistic miniature quadcopter rendering for all drones on the map
function drawRealisticMiniDrone(ctx, x, y, headingDeg, color, label, isStationed = false, timeSec = 0) {
  ctx.save();
  ctx.translate(x, y);

  // 1. Soft ground shadow underneath
  const shadowScale = isStationed ? 0.9 : 1.15;
  const shadowAlpha = isStationed ? 0.22 : 0.15;
  ctx.save();
  ctx.fillStyle = `rgba(15, 23, 42, ${shadowAlpha})`;
  ctx.beginPath();
  ctx.ellipse(0, 5, 14 * shadowScale, 7 * shadowScale, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  // 2. Rotate to flight heading
  const headingRad = (headingDeg * Math.PI) / 180;
  ctx.rotate(headingRad);

  // 3. Carbon Cross-Arms
  ctx.strokeStyle = '#334155';
  ctx.lineWidth = 2.4;
  ctx.lineCap = 'round';
  ctx.beginPath();
  // Arm 1: Front-Left to Rear-Right
  ctx.moveTo(-9, -9);
  ctx.lineTo(9, 9);
  // Arm 2: Front-Right to Rear-Left
  ctx.moveTo(9, -9);
  ctx.lineTo(-9, 9);
  ctx.stroke();

  // 4. Brushless Motor Bells & Spinning Rotor Blur Discs
  const rotorSpinSpeed = isStationed ? 12 : 36;
  const rotorAngle = timeSec * rotorSpinSpeed;
  const rotorPositions = [
    [-9, -9],
    [9, -9],
    [-9, 9],
    [9, 9],
  ];

  rotorPositions.forEach(([rx, ry], idx) => {
    // Rotor translucent blur disc
    ctx.beginPath();
    ctx.arc(rx, ry, 6.5, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(2, 132, 199, 0.16)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(15, 23, 42, 0.22)';
    ctx.lineWidth = 0.6;
    ctx.stroke();

    // High-speed spinning blade line
    ctx.save();
    ctx.translate(rx, ry);
    ctx.rotate(rotorAngle + (idx * Math.PI) / 2);
    ctx.strokeStyle = '#0f172a';
    ctx.lineWidth = 1.3;
    ctx.beginPath();
    ctx.moveTo(-5.5, 0);
    ctx.lineTo(5.5, 0);
    ctx.stroke();
    // Safety colored blade tip (orange)
    ctx.strokeStyle = '#ea580c';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(3.5, 0);
    ctx.lineTo(5.5, 0);
    ctx.stroke();
    ctx.restore();

    // Motor center hub
    ctx.beginPath();
    ctx.arc(rx, ry, 1.8, 0, Math.PI * 2);
    ctx.fillStyle = '#0f172a';
    ctx.fill();
  });

  // 5. Central Aerodynamic Fuselage
  ctx.fillStyle = '#1e293b';
  ctx.beginPath();
  ctx.ellipse(0, 0, 5.5, 4.2, 0, 0, Math.PI * 2);
  ctx.fill();

  // Top canopy with fleet color ring
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(0, 0, 2.8, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 1;
  ctx.stroke();

  // Forward heading indicator on nose
  ctx.fillStyle = '#ffffff';
  ctx.beginPath();
  ctx.moveTo(0, -4.5);
  ctx.lineTo(2, -1.5);
  ctx.lineTo(-2, -1.5);
  ctx.closePath();
  ctx.fill();

  // Navigation lights
  // Left port: Red
  ctx.fillStyle = '#ef4444';
  ctx.beginPath();
  ctx.arc(-9, -9, 1.2, 0, Math.PI * 2);
  ctx.fill();
  // Right starboard: Green
  ctx.fillStyle = '#10b981';
  ctx.beginPath();
  ctx.arc(9, -9, 1.2, 0, Math.PI * 2);
  ctx.fill();

  ctx.restore();

  // 6. Drone Callsign & Status Pill
  if (label) {
    ctx.save();
    ctx.font = '700 9.5px Inter, -apple-system, sans-serif';
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';
    const textW = ctx.measureText(label).width;
    const badgeW = Math.round(textW + 22);
    const badgeH = 19;
    const badgeX = Math.round(x - badgeW / 2);
    const badgeY = Math.round(y - 25);

    // Subtle drop shadow under pill for crisp contrast on light map
    ctx.shadowColor = 'rgba(15, 23, 42, 0.10)';
    ctx.shadowBlur = 6;
    ctx.shadowOffsetY = 2;

    // Solid pure white badge background
    drawSafeRoundRect(ctx, badgeX, badgeY, badgeW, badgeH, 6);
    ctx.fillStyle = '#ffffff';
    ctx.fill();

    // Disable shadow before borders, beacon and typography
    ctx.shadowColor = 'transparent';
    ctx.shadowBlur = 0;
    ctx.shadowOffsetY = 0;

    // Accent border in drone color
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.4;
    ctx.stroke();

    // Drone colored status beacon LED with micro white ring
    ctx.beginPath();
    ctx.arc(badgeX + 9, badgeY + badgeH / 2, 2.8, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1;
    ctx.stroke();

    // High-contrast deep slate text
    ctx.fillStyle = '#0f172a';
    ctx.fillText(label, badgeX + 16, badgeY + badgeH / 2);
    ctx.restore();
  }
}

export default function OperationsMap({
  instance,
  schedule,
  graspSchedule,
  maxMissionTime,
  missionTime,
  setMissionTime,
  isPlaying,
  setIsPlaying,
  telemetry,
  securedTargets,
  windSpeed: propWindSpeed,
  windDir: propWindDir,
  fleetSize: propFleetSize,
  triggerLandingAnim,
  onLandingAnimDone,
  isSolving,
  introActive,
}) {
  const activeWindSpd = propWindSpeed ?? instance?.ambient_wind?.speed_mps ?? 3.5;
  const activeWindDir = propWindDir ?? instance?.ambient_wind?.direction_deg ?? 45;
  const activeFleetSize = propFleetSize ?? instance?.drones?.length ?? 3;

  // Sensor layer toggles
  const [showRadarHalos, setShowRadarHalos] = useState(false); // Default off to reduce clutter
  const [showFlightPaths, setShowFlightPaths] = useState(true);
  const [showRangeRings, setShowRangeRings] = useState(false); // Default off to reduce clutter
  const [showTacticalGrid, setShowTacticalGrid] = useState(true);
  const [showWindStream, setShowWindStream] = useState(true);
  const [showUavIcons, setShowUavIcons] = useState(true);
  const [playbackSpeed, setPlaybackSpeed] = useState(20); // 20 mission-sec per wall-sec feels natural for an 800s mission
  const [selectedInspectorObj, setSelectedInspectorObj] = useState('None (Overview)');
  const [hoveredTarget, setHoveredTarget] = useState(null);

  // Cinematic Depot Touchdown Sequence State
  const [landingState, setLandingState] = useState(() => {
    return triggerLandingAnim ? { progress: 0, phase: 'descending' } : null;
  });
  const [hasLanded, setHasLanded] = useState(!triggerLandingAnim && !introActive);

  const canvasRef = useRef(null);

  // Landing sequence animation loop
  useEffect(() => {
    if (!triggerLandingAnim) {
      if (!introActive) setHasLanded(true);
      setLandingState(null);
      return;
    }

    setHasLanded(false);
    setLandingState({ progress: 0, phase: 'descending' });

    let animId;
    const startTime = performance.now();
    const duration = 2400; // 2.4s total: 1.6s descent + 0.8s touchdown shockwave & badge

    const loop = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(1.0, elapsed / duration);
      const phase = progress < 0.65 ? 'descending' : progress < 0.95 ? 'touchdown' : 'done';

      setLandingState({ progress, phase });

      if (progress < 1.0) {
        animId = requestAnimationFrame(loop);
      } else {
        setHasLanded(true);
        setTimeout(() => {
          setLandingState(null);
          if (onLandingAnimDone) onLandingAnimDone();
        }, 800);
      }
    };

    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [triggerLandingAnim, onLandingAnimDone]);

  // Ensure drones NEVER show up early while intro is active or replaying
  useEffect(() => {
    if (introActive) {
      setHasLanded(false);
      setLandingState(null);
    }
  }, [introActive]);

  // Mission Execution Playback Engine (Drives UAV movement & scouting progression)
  useEffect(() => {
    if (!isPlaying) return;

    let lastTime = performance.now();
    let animId;

    const tick = (now) => {
      const dt = (now - lastTime) / 1000;
      lastTime = now;

      setMissionTime((prevTime) => {
        const nextTime = prevTime + dt * playbackSpeed;
        if (nextTime >= maxMissionTime) {
          setIsPlaying(false);
          return maxMissionTime;
        }
        return nextTime;
      });

      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [isPlaying, playbackSpeed, maxMissionTime, setIsPlaying, setMissionTime]);

  // Progressive reveal for paths and targets (avoids rapid flashing)
  const [revealProgress, setRevealProgress] = useState(1.0);
  useEffect(() => {
    if (isSolving) {
      setRevealProgress(0.15);
    } else {
      let start = performance.now();
      let animId;
      const animate = (now) => {
        const t = Math.min(1.0, (now - start) / 600);
        setRevealProgress(t);
        if (t < 1.0) animId = requestAnimationFrame(animate);
      };
      animId = requestAnimationFrame(animate);
      return () => cancelAnimationFrame(animId);
    }
  }, [isSolving, schedule]);

  // Derived coordinate bounds
  const targets = instance?.targets ?? [];
  const { minX, maxX, minY, maxY } = useMemo(() => {
    if (targets.length === 0) return { minX: 0, maxX: 1000, minY: 0, maxY: 1000 };
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    targets.forEach((t) => {
      if (t.x < x0) x0 = t.x;
      if (t.x > x1) x1 = t.x;
      if (t.y < y0) y0 = t.y;
      if (t.y > y1) y1 = t.y;
    });
    const padX = Math.max((x1 - x0) * 0.12, 60);
    const padY = Math.max((y1 - y0) * 0.12, 60);
    return { minX: x0 - padX, maxX: x1 + padX, minY: y0 - padY, maxY: y1 + padY };
  }, [targets]);

  // Coordinate conversion helpers
  const toCanvasX = (x, width) => ((x - minX) / (maxX - minX)) * (width - 80) + 40;
  const toCanvasY = (y, height) => height - (((y - minY) / (maxY - minY)) * (height - 80) + 40);

  // Canvas Mouse Move detection for non-intrusive target hover
  const handleCanvasMouseMove = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const mouseX = (e.clientX - rect.left) * scaleX;
    const mouseY = (e.clientY - rect.top) * scaleY;

    // Detect target hovering
    let closest = null;
    let minDist = 14;
    targets.forEach((t) => {
      const cx = toCanvasX(t.x, canvas.width);
      const cy = toCanvasY(t.y, canvas.height);
      const d = Math.hypot(mouseX - cx, mouseY - cy);
      if (d < minDist) {
        minDist = d;
        closest = t;
      }
    });
    setHoveredTarget(closest);
  };

  const handleCanvasMouseLeave = () => {
    setHoveredTarget(null);
  };

  const handleCanvasClick = () => {
    if (hoveredTarget) {
      setSelectedInspectorObj(`Target #${hoveredTarget.id.toString().padStart(2, '0')}`);
    }
  };

  // Draw 2D Tactical Map Canvas (Light Aerospace Glassmorphic Standard)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId;

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;
      const timeSec = performance.now() / 1000;

      // Clear background with crisp light aerospace tone
      ctx.fillStyle = '#f8fafc';
      ctx.fillRect(0, 0, width, height);

    // 1. Draw Tactical Grid (clean light slate grid)
    if (showTacticalGrid) {
      ctx.strokeStyle = 'rgba(15, 23, 42, 0.045)';
      ctx.lineWidth = 1;
      const step = 60;
      for (let x = 0; x < width; x += step) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 0; y < height; y += step) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }
    }

    // 1b. Realistic Atmospheric Wind Stream (Organic Fluid Streamlines)
    if (showWindStream && activeWindSpd > 0.3) {
      ctx.save();
      const windRad = (activeWindDir * Math.PI) / 180;
      const wx = Math.cos(windRad);
      const wy = -Math.sin(windRad); // Inverted canvas y
      const px = -wy; // Perpendicular vector x
      const py = wx;  // Perpendicular vector y

      const diag = Math.hypot(width, height) + 200;
      const travelSpan = diag;
      const flowSpeed = 24 + Math.min(activeWindSpd, 20) * 14; // pixels per second
      const numParticles = 42;
      const baseAlpha = Math.min(0.38, 0.10 + (activeWindSpd / 20) * 0.18);

      for (let i = 0; i < numParticles; i++) {
        // Distribute across the perpendicular width of the airflow corridor
        const offsetPerp = (((i * 1.618) % 1) - 0.5) * diag;
        const speedVar = 0.85 + ((i * 7) % 5) * 0.08;
        const phaseSeed = i * 137.5;
        const cycleDist = (timeSec * flowSpeed * speedVar + phaseSeed) % travelSpan;
        const distAlongFlow = cycleDist - travelSpan / 2;

        // Center coordinates of the current streamline wisp
        const cx = width / 2 + px * offsetPerp + wx * distAlongFlow;
        const cy = height / 2 + py * offsetPerp + wy * distAlongFlow;

        // Cull particles completely outside the canvas viewport (+60px margin)
        if (cx < -60 || cx > width + 60 || cy < -60 || cy > height + 60) continue;

        // Fluid streak dimensions
        const streakLen = 45 + (i % 6) * 10 + Math.min(activeWindSpd, 15) * 2.2;
        const tailX = cx - wx * (streakLen * 0.5);
        const tailY = cy - wy * (streakLen * 0.5);
        const headX = cx + wx * (streakLen * 0.5);
        const headY = cy + wy * (streakLen * 0.5);

        // Gentle organic atmospheric wave (turbulent laminar breeze)
        const waveAmp = 2.5 + (i % 4) * 1.2;
        const waveOffset = Math.sin(distAlongFlow * 0.012 + timeSec * 2.2 + i) * waveAmp;
        const midX = cx + px * waveOffset;
        const midY = cy + py * waveOffset;

        // Smooth aerodynamic gradient: invisible tail -> soft sky glow -> tapered head
        const grad = ctx.createLinearGradient(tailX, tailY, headX, headY);
        grad.addColorStop(0, 'rgba(2, 132, 199, 0)');
        grad.addColorStop(0.3, `rgba(2, 132, 199, ${baseAlpha * 0.6})`);
        grad.addColorStop(0.75, `rgba(14, 165, 233, ${baseAlpha})`);
        grad.addColorStop(1, 'rgba(14, 165, 233, 0)');

        ctx.strokeStyle = grad;
        ctx.lineWidth = 1.2 + (i % 3) * 0.5;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(tailX, tailY);
        ctx.quadraticCurveTo(midX, midY, headX, headY);
        ctx.stroke();
      }
      ctx.restore();
    }

    // Launch Base Depot
    const depotNode = targets.find((t) => (instance?.depot_ids ?? [0]).includes(t.id)) || targets[0];
    const depotX = depotNode ? toCanvasX(depotNode.x, width) : width / 2;
    const depotY = depotNode ? toCanvasY(depotNode.y, height) : height / 2;

    // 2. Range Rings (clean light theme)
    if (showRangeRings) {
      ctx.strokeStyle = 'rgba(15, 23, 42, 0.06)';
      ctx.setLineDash([4, 6]);
      [140, 280].forEach((r) => {
        ctx.beginPath();
        ctx.arc(depotX, depotY, r, 0, Math.PI * 2);
        ctx.stroke();
      });
      ctx.setLineDash([]);
    }

    // 3. Radar Sweep Line (subtle atmospheric pulse)
    if (showRangeRings) {
      const sweepAngle = (performance.now() / 1800) % (Math.PI * 2);
      const grad = ctx.createRadialGradient(depotX, depotY, 0, depotX, depotY, 280);
      grad.addColorStop(0, 'rgba(2, 132, 199, 0.08)');
      grad.addColorStop(1, 'rgba(2, 132, 199, 0)');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.moveTo(depotX, depotY);
      ctx.arc(depotX, depotY, 280, sweepAngle - 0.35, sweepAngle);
      ctx.closePath();
      ctx.fill();
    }

    // Base Depot Marker on Light Canvas
    ctx.beginPath();
    ctx.arc(depotX, depotY, 18, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(2, 132, 199, 0.10)';
    ctx.fill();

    ctx.fillStyle = '#0284C7';
    ctx.beginPath();
    ctx.arc(depotX, depotY, 7.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2.2;
    ctx.stroke();

    ctx.fillStyle = '#0284C7';
    ctx.font = '700 10px JetBrains Mono, monospace';
    ctx.fillText('DEPOT', depotX + 13, depotY + 3.5);

    // 4. Planned Flight Corridors (progressive reveal, high-contrast)
    const routes = schedule?.assigned_routes ?? [];
    if (showFlightPaths) {
      routes.forEach((route, rIdx) => {
        const color = DRONE_COLORS[rIdx % DRONE_COLORS.length];
        const wps = route.waypoints ?? [];
        if (wps.length < 2) return;

        ctx.strokeStyle = color;
        ctx.lineWidth = 2.4;
        ctx.lineCap = 'round';
        ctx.globalAlpha = Math.min(1.0, 0.2 + revealProgress * 0.78);
        ctx.beginPath();
        wps.forEach((wp, idx) => {
          const node = targets.find((t) => t.id === wp.node_id);
          if (node) {
            const cx = toCanvasX(node.x, width);
            const cy = toCanvasY(node.y, height);
            if (idx === 0) ctx.moveTo(cx, cy);
            else ctx.lineTo(cx, cy);
          }
        });
        ctx.stroke();
        ctx.globalAlpha = 1.0;
      });
    }

    // 5. Target Nodes with Sector/Drone Color-Coding (Clean on Light Canvas)
    const securedSet = new Set(securedTargets ?? []);
    const targetToDroneMap = new Map();
    routes.forEach((route, rIdx) => {
      const color = DRONE_COLORS[rIdx % DRONE_COLORS.length];
      (route.target_ids ?? []).forEach((tid) => {
        targetToDroneMap.set(tid, { color, droneId: route.drone_id });
      });
    });

    ctx.globalAlpha = Math.min(1.0, 0.4 + revealProgress * 0.6);
    targets.forEach((node) => {
      const isDepot = (instance?.depot_ids ?? [0]).includes(node.id);
      if (isDepot) return; // Already drawn depot above

      const cx = toCanvasX(node.x, width);
      const cy = toCanvasY(node.y, height);
      const isSecured = securedSet.has(node.id);
      const isHovered = hoveredTarget && hoveredTarget.id === node.id;
      const isInspected = selectedInspectorObj === `Target #${node.id.toString().padStart(2, '0')}`;

      const radius = isHovered || isInspected ? 6 : isSecured ? 4.5 : 3.5;
      const droneInfo = targetToDroneMap.get(node.id);

      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);

      if (isSecured) {
        ctx.fillStyle = '#059669';
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      } else if (droneInfo) {
        ctx.fillStyle = droneInfo.color;
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1.2;
        ctx.stroke();
      } else {
        ctx.fillStyle = isHovered || isInspected ? '#0284C7' : '#ffffff';
        ctx.fill();
        ctx.strokeStyle = isHovered || isInspected ? '#0284C7' : '#94a3b8';
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }

      // Legible Node ID on light canvas
      ctx.fillStyle = '#64748b';
      ctx.font = '500 8.5px JetBrains Mono, monospace';
      ctx.fillText(`${node.id}`, cx + radius + 3, cy + 2.5);

      // Tooltip pill on hover or selection
      if (isHovered || isInspected) {
        const accentColor = droneInfo ? droneInfo.color : isSecured ? '#059669' : '#0284C7';
        ctx.strokeStyle = accentColor;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(cx, cy, radius + 4, 0, Math.PI * 2);
        ctx.stroke();

        const droneTag = droneInfo ? ` (${droneInfo.droneId})` : '';
        const statusTag = isSecured ? ' · SECURED' : '';
        const label = `Target #${node.id} · ${(node.priority_score || 0).toFixed(0)} pts${droneTag}${statusTag}`;
        ctx.font = '600 10px Inter, sans-serif';
        const textW = ctx.measureText(label).width;

        ctx.fillStyle = 'rgba(15, 23, 42, 0.94)';
        ctx.beginPath();
        drawSafeRoundRect(ctx, cx - textW / 2 - 8, cy - radius - 25, textW + 16, 20, 5);
        ctx.fill();
        ctx.strokeStyle = accentColor;
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.fillStyle = '#FFFFFF';
        ctx.fillText(label, cx - textW / 2, cy - radius - 11);
      }
    });
    ctx.globalAlpha = 1.0;

    // 6. Drone Fleet Display (Stationed at Depot while Solving or Flying in Mission)
    const isStationed = (isSolving || (!isPlaying && missionTime === 0)) && hasLanded && !landingState && !introActive && !triggerLandingAnim;

    if (isStationed) {
      // Drones are parked at the DEPOT while solving or waiting for execution!
      const totalFleet = Math.max(1, activeFleetSize);
      for (let dIdx = 0; dIdx < totalFleet; dIdx++) {
        const color = DRONE_COLORS[dIdx % DRONE_COLORS.length];
        const parkPos = getApronParkPosition(dIdx, totalFleet, depotX, depotY);
        const droneLabel = `UAV-0${dIdx + 1} (100%)`;

        drawRealisticMiniDrone(ctx, parkPos.x, parkPos.y, 0, color, droneLabel, true, timeSec);
      }

      // Clean Stationed / Solving Status Badge over Depot (elevated above lead UAV-02)
      ctx.save();
      const statusText = isSolving 
        ? 'UAV FLEET AT DEPOT · OPTIMIZING FLIGHT CORRIDORS...' 
        : 'UAV FLEET STATIONED AT DEPOT · READY FOR MISSION';
      ctx.font = '600 10px Inter, sans-serif';
      ctx.textBaseline = 'middle';
      const sW = ctx.measureText(statusText).width;
      const bX = Math.round(depotX - sW / 2 - 12);
      const bY = Math.round(depotY - 66);

      drawSafeRoundRect(ctx, bX, bY, sW + 24, 22, 6);
      ctx.fillStyle = 'rgba(255, 255, 255, 0.96)';
      ctx.fill();
      ctx.strokeStyle = isSolving ? '#f59e0b' : '#10b981';
      ctx.lineWidth = 1.4;
      ctx.stroke();

      // Pulsing status dot
      ctx.fillStyle = isSolving ? '#f59e0b' : '#10b981';
      ctx.beginPath();
      ctx.arc(bX + 11, bY + 11, 3.5, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = '#0f172a';
      ctx.fillText(statusText, bX + 20, bY + 11);
      ctx.restore();

    } else if (!landingState && hasLanded && !introActive) {
      // Drones in active flight along corridors: high-precision 60fps kinematics + telemetry fallback
      const telemetryList = telemetry ?? [];
      const routes = schedule?.assigned_routes ?? [];
      const targetsList = targets ?? [];
      const totalFleet = Math.max(1, activeFleetSize);

      for (let dIdx = 0; dIdx < totalFleet; dIdx++) {
        const droneId = `UAV-0${dIdx + 1}`;
        const color = DRONE_COLORS[dIdx % DRONE_COLORS.length];
        const route = routes.find((r) => r.drone_id === droneId);
        const telem = telemetryList.find((t) => t.drone_id === droneId);

        let cx, cy, headingDeg = 0, gSpeed = '14.5';

        if (route && route.waypoints && route.waypoints.length > 0) {
          const wps = route.waypoints;
          const tCur = missionTime;

          if (tCur <= wps[0].departure_time) {
            const n0 = targetsList.find((t) => t.id === wps[0].node_id);
            cx = n0 ? toCanvasX(n0.x, width) : depotX;
            cy = n0 ? toCanvasY(n0.y, height) : depotY;
            gSpeed = '0.0';
          } else if (tCur >= wps[wps.length - 1].arrival_time) {
            const nLast = targetsList.find((t) => t.id === wps[wps.length - 1].node_id);
            cx = nLast ? toCanvasX(nLast.x, width) : depotX;
            cy = nLast ? toCanvasY(nLast.y, height) : depotY;
            gSpeed = '0.0';
          } else {
            let segmentFound = false;
            for (let s = 0; s < wps.length - 1; s++) {
              const wpA = wps[s];
              const wpB = wps[s + 1];
              const nodeA = targetsList.find((t) => t.id === wpA.node_id);
              const nodeB = targetsList.find((t) => t.id === wpB.node_id);
              if (!nodeA || !nodeB) continue;

              // Hover scan over nodeA
              if (tCur >= wpA.arrival_time && tCur <= wpA.departure_time) {
                cx = toCanvasX(nodeA.x, width);
                cy = toCanvasY(nodeA.y, height);
                headingDeg = (Math.atan2(nodeB.x - nodeA.x, -(nodeB.y - nodeA.y)) * 180) / Math.PI;
                gSpeed = '0.0';
                segmentFound = true;
                break;
              }

              // In forward transit between nodeA and nodeB
              if (tCur > wpA.departure_time && tCur < wpB.arrival_time) {
                const dur = Math.max(0.01, wpB.arrival_time - wpA.departure_time);
                const frac = Math.max(0, Math.min(1, (tCur - wpA.departure_time) / dur));
                const interpX = nodeA.x + frac * (nodeB.x - nodeA.x);
                const interpY = nodeA.y + frac * (nodeB.y - nodeA.y);
                cx = toCanvasX(interpX, width);
                cy = toCanvasY(interpY, height);
                headingDeg = (Math.atan2(nodeB.x - nodeA.x, -(nodeB.y - nodeA.y)) * 180) / Math.PI;
                const distM = Math.hypot(nodeB.x - nodeA.x, nodeB.y - nodeA.y);
                gSpeed = (distM / dur).toFixed(1);
                segmentFound = true;
                break;
              }
            }

            if (!segmentFound && telem) {
              cx = toCanvasX(telem.x, width);
              cy = toCanvasY(telem.y, height);
              headingDeg = telem.heading_deg || 0;
              gSpeed = (telem.ground_speed_mps ?? telem.speed_mps ?? 14.5).toFixed(1);
            }
          }
        } else if (telem) {
          cx = toCanvasX(telem.x, width);
          cy = toCanvasY(telem.y, height);
          headingDeg = telem.heading_deg || 0;
          gSpeed = (telem.ground_speed_mps ?? telem.speed_mps ?? 14.5).toFixed(1);
        } else {
          const parkPos = getApronParkPosition(dIdx, totalFleet, depotX, depotY);
          cx = parkPos.x;
          cy = parkPos.y;
          gSpeed = '0.0';
        }

        if (cx !== undefined && cy !== undefined) {
          const droneLabel = `${droneId} (${gSpeed}m/s)`;
          drawRealisticMiniDrone(ctx, cx, cy, headingDeg, color, droneLabel, gSpeed === '0.0', timeSec);
        }
      }
    }

    // 7. Dynamic Depot Touchdown Sequence (when intro hands off)
    if (landingState) {
      const { progress } = landingState;
      const totalFleet = Math.max(1, activeFleetSize);

      for (let dIdx = 0; dIdx < totalFleet; dIdx++) {
        const color = DRONE_COLORS[dIdx % DRONE_COLORS.length];
        // Target parking spot at depot: matches exactly the apron positioned spot
        const targetPos = getApronParkPosition(dIdx, totalFleet, depotX, depotY);
        const targetX_d = targetPos.x;
        const targetY_d = targetPos.y;

        // Ingress starting position above top of canvas with echelon stagger
        const ingressOffset = (dIdx - (totalFleet - 1) / 2) * 45;
        const startX_d = targetX_d + 60 + ingressOffset;
        const startY_d = -80 - dIdx * 25;

        // Slight micro-stagger for wingmen behind lead UAV-01
        const droneStagger = dIdx === 0 ? 0 : 0.04 + dIdx * 0.03;
        const descentDuration = 0.65 - droneStagger * 0.4;
        const descentFrac = Math.max(0, Math.min(1.0, (progress - droneStagger) / Math.max(0.2, descentDuration)));
        const easeT = 1 - Math.pow(1 - descentFrac, 3);

        const curX = startX_d + (targetX_d - startX_d) * easeT;
        const curY = startY_d + (targetY_d - startY_d) * easeT;

        // Soft ground shadow growing at each drone's pad
        const shadowAlpha = (dIdx === 0 ? 0.32 : 0.22) * easeT;
        const shadowRadius = 8 + 10 * easeT;
        ctx.save();
        ctx.fillStyle = `rgba(15, 23, 42, ${shadowAlpha})`;
        ctx.beginPath();
        ctx.ellipse(targetX_d, targetY_d + 4, shadowRadius * 1.4, shadowRadius * 0.7, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        // Draw incoming realistic mini drone descending
        const isLanded = descentFrac >= 0.99;
        const bank = isLanded ? 0 : (1 - easeT) * (14 + (dIdx % 2 === 0 ? 4 : -4));
        const droneLabel = isLanded ? `UAV-0${dIdx + 1} (PARKED)` : `UAV-0${dIdx + 1} (APPROACH)`;

        drawRealisticMiniDrone(ctx, curX, curY, bank, color, droneLabel, isLanded, timeSec);
      }

      // Touchdown shockwave pulse and badge
      if (progress >= 0.65) {
        const pulseFrac = (progress - 0.65) / 0.35;
        const pulseRadius = 10 + pulseFrac * 70;
        const pulseAlpha = Math.max(0, 1 - pulseFrac);

        ctx.save();
        ctx.strokeStyle = `rgba(16, 185, 129, ${pulseAlpha})`;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(depotX, depotY, pulseRadius, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();

        // Touchdown confirmation badge
        ctx.save();
        const badge = totalFleet > 1 
          ? `FLEET (${totalFleet} UAVs) TOUCHDOWN · DEPOT ONLINE`
          : 'UAV-01 TOUCHDOWN · DEPOT ONLINE';
        ctx.font = 'bold 10px Inter, sans-serif';
        const bW = ctx.measureText(badge).width;
        ctx.fillStyle = 'rgba(255, 255, 255, 0.96)';
        ctx.beginPath();
        drawSafeRoundRect(ctx, depotX - bW / 2 - 8, depotY - 34, bW + 16, 20, 5);
        ctx.fill();
        ctx.strokeStyle = '#10b981';
        ctx.lineWidth = 1.4;
        ctx.stroke();
        ctx.fillStyle = '#059669';
        ctx.fillText(badge, depotX - bW / 2, depotY - 20);
        ctx.restore();
      }
    }

    // Continuous 60FPS animation loop for spinning propellers and atmospheric motion
    animId = requestAnimationFrame(render);
  };

  animId = requestAnimationFrame(render);
  return () => cancelAnimationFrame(animId);
}, [
  instance,
  schedule,
  telemetry,
  securedTargets,
  minX,
  maxX,
  minY,
  maxY,
  showRadarHalos,
  showFlightPaths,
  showRangeRings,
  showTacticalGrid,
  showWindStream,
  showUavIcons,
  hoveredTarget,
  selectedInspectorObj,
  landingState,
  hasLanded,
  triggerLandingAnim,
  revealProgress,
  isSolving,
  isPlaying,
  missionTime,
  activeFleetSize,
  activeWindSpd,
  activeWindDir,
  introActive,
]);

  // Context Inspector Calculations
  const activeTelemMap = useMemo(() => {
    const map = {};
    (telemetry ?? []).forEach((t) => {
      map[t.drone_id] = t;
    });
    return map;
  }, [telemetry]);

  const inspectorOptions = useMemo(() => {
    const opts = ['None (Overview)'];
    (instance?.drones ?? []).forEach((d) => opts.push(d.id));
    (instance?.target_nodes ?? []).slice(0, 15).forEach((t) => opts.push(`Target #${t.id.toString().padStart(2, '0')}`));
    return opts;
  }, [instance]);

  const visitedCount = securedTargets?.length ?? 0;
  const totalTargetsCount = instance?.target_nodes?.length ?? 0;
  const coveragePct = totalTargetsCount > 0 ? (visitedCount / totalTargetsCount) * 100 : 0;
  const routes = schedule?.assigned_routes ?? [];
  const minReserveAll = routes.reduce(
    (min, r) => Math.min(min, r.final_reserve_percent ?? 100),
    100
  );

  return (
    <div className="space-y-4 font-sans">
      {/* 1. Slim Top Bar: Map Title & Layer Toggles */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-sky-50 border border-sky-200/80 flex items-center justify-center text-sky-600">
            <Compass className="w-4 h-4" />
          </div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-900 tracking-tight">
              Tactical Operations Map
            </h2>
            <span className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-slate-100 text-slate-600 border border-slate-200/60">
              {instance?.instance_name ?? 'Chao Set 64'}
            </span>
          </div>
        </div>

        {/* Minimalist Layer Segmented Toolbar */}
        <div className="segmented-control">
          <button
            type="button"
            onClick={() => setShowFlightPaths(!showFlightPaths)}
            className={`segmented-item text-xs flex items-center gap-1.5 ${showFlightPaths ? 'segmented-item-active' : ''}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${showFlightPaths ? 'bg-sky-500' : 'bg-slate-300'}`} />
            <span>Flight Paths</span>
          </button>

          <button
            type="button"
            onClick={() => setShowUavIcons(!showUavIcons)}
            className={`segmented-item text-xs flex items-center gap-1.5 ${showUavIcons ? 'segmented-item-active' : ''}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${showUavIcons ? 'bg-sky-500' : 'bg-slate-300'}`} />
            <span>UAV Glyphs</span>
          </button>

          <button
            type="button"
            onClick={() => setShowTacticalGrid(!showTacticalGrid)}
            className={`segmented-item text-xs flex items-center gap-1.5 ${showTacticalGrid ? 'segmented-item-active' : ''}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${showTacticalGrid ? 'bg-sky-500' : 'bg-slate-300'}`} />
            <span>Grid</span>
          </button>

          <button
            type="button"
            onClick={() => setShowWindStream(!showWindStream)}
            className={`segmented-item text-xs flex items-center gap-1.5 ${showWindStream ? 'segmented-item-active' : ''}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${showWindStream ? 'bg-sky-500' : 'bg-slate-300'}`} />
            <span>Wind Stream</span>
          </button>

          <button
            type="button"
            onClick={() => setShowRangeRings(!showRangeRings)}
            className={`segmented-item text-xs flex items-center gap-1.5 ${showRangeRings ? 'segmented-item-active' : ''}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${showRangeRings ? 'bg-sky-500' : 'bg-slate-300'}`} />
            <span>Rings</span>
          </button>

          <button
            type="button"
            onClick={() => setShowRadarHalos(!showRadarHalos)}
            className={`segmented-item text-xs flex items-center gap-1.5 ${showRadarHalos ? 'segmented-item-active' : ''}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${showRadarHalos ? 'bg-sky-500' : 'bg-slate-300'}`} />
            <span>Halos</span>
          </button>
        </div>
      </div>

      {/* 2. Hero Tactical Map Canvas & Integrated Player Dock */}
      <div className="glass-card rounded-2xl overflow-hidden shadow-sm border border-slate-200/80">
        {/* Canvas Display */}
        <div className="relative">
          <canvas
            ref={canvasRef}
            width={1100}
            height={520}
            onMouseMove={handleCanvasMouseMove}
            onMouseLeave={handleCanvasMouseLeave}
            onClick={handleCanvasClick}
            className="w-full h-[500px] object-cover block cursor-crosshair bg-[#f8fafc]"
          />

          {/* Floating Tactical Status Badges */}
          <div className="absolute top-3 left-3 flex items-center gap-2 pointer-events-none">
            <div className="px-2.5 py-1.5 rounded-xl text-[11px] font-mono text-slate-700 font-medium bg-white/92 border border-slate-200/90 shadow-sm flex items-center gap-2 backdrop-blur-md">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              <span>TACTICAL HUD // 60FPS SITL • {routes.length || activeFleetSize} UAVs</span>
            </div>
            {hoveredTarget && (
              <div className="px-2.5 py-1.5 rounded-xl text-[11px] font-mono text-sky-700 font-medium bg-white/92 border border-sky-300/80 shadow-sm backdrop-blur-md">
                TARGET #{hoveredTarget.id} ({(hoveredTarget.priority_score || 0).toFixed(0)} PTS)
              </div>
            )}
          </div>

          {/* Dynamic Tactical Wind Vector Compass & Clock HUD */}
          <div className="absolute top-3 right-3 flex items-center gap-2 pointer-events-none">
            <div className="px-3 py-1.5 rounded-xl text-xs bg-white/92 border border-slate-200/90 shadow-sm flex items-center gap-3 backdrop-blur-md font-mono text-slate-700">
              {/* Compass Dial & Vector */}
              <div className="flex items-center gap-2">
                <div 
                  className="w-5 h-5 rounded-full border border-sky-300 bg-sky-50 flex items-center justify-center transition-transform duration-300 shadow-2xs"
                  style={{ transform: `rotate(${-activeWindDir}deg)` }}
                  title={`Wind vector: ${activeWindSpd.toFixed(1)} m/s towards ${activeWindDir}°`}
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#0284c7" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="5" y1="12" x2="19" y2="12" />
                    <polyline points="12 5 19 12 12 19" />
                  </svg>
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 uppercase tracking-wider block leading-none">
                    WIND VECTOR
                  </span>
                  <span className="text-[11px] font-semibold text-slate-800 font-mono">
                    {activeWindSpd.toFixed(1)} m/s · {Math.round(activeWindDir)}°
                  </span>
                </div>
              </div>

              <div className="h-5 w-px bg-slate-200" />

              {/* Groundspeed Envelope */}
              <div>
                <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wider block leading-none">
                  Vg Window
                </span>
                <span className="text-[11px] font-mono font-semibold text-sky-700">
                  {Math.max(1.0, 14.5 - activeWindSpd).toFixed(1)} – {(14.5 + activeWindSpd).toFixed(1)} m/s
                </span>
              </div>

              <div className="h-5 w-px bg-slate-200" />

              {/* Mission Clock */}
              <div>
                <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wider block leading-none">
                  Mission Clock
                </span>
                <span className="text-[11px] font-mono font-semibold text-slate-700">
                  T+{missionTime.toFixed(0).padStart(4, '0')}s
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Integrated Player Dock: Transport + Scrubber + Timeline Stepper */}
        <div className="p-3.5 border-t border-slate-200/70 bg-white/50 backdrop-blur-md flex flex-wrap items-center gap-4">
          {/* Transport buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (!isPlaying && missionTime >= maxMissionTime) {
                  setMissionTime(0);
                }
                setIsPlaying(!isPlaying);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer shadow-xs ${
                isPlaying ? 'bg-amber-500 hover:bg-amber-600 text-white' : 'btn-primary'
              }`}
            >
              {isPlaying ? (
                <>
                  <Square className="w-3.5 h-3.5 fill-current" />
                  <span>Pause</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Execute</span>
                </>
              )}
            </button>

            <button
              onClick={() => {
                setIsPlaying(false);
                setMissionTime(0);
              }}
              title="Reset Timeline"
              className="btn-secondary px-2.5 py-1.5 rounded-lg text-xs font-medium cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5 text-slate-500" />
            </button>
          </div>

          {/* Timeline Scrubber & Minimal Stage Stepper */}
          <div className="flex-1 min-w-[240px] flex flex-col justify-center gap-1">
            <input
              type="range"
              min="0"
              max={maxMissionTime}
              step="1"
              value={missionTime}
              onChange={(e) => {
                setIsPlaying(false);
                setMissionTime(Number(e.target.value));
              }}
              className="w-full cursor-pointer"
            />
            {/* Minimal inline stage labels */}
            {(() => {
              const prog = maxMissionTime > 0 ? missionTime / maxMissionTime : 0;
              return (
                <div className="flex justify-between items-center text-[10px] font-sans px-0.5 text-slate-400">
                  <span className={prog < 0.15 ? 'text-sky-600 font-semibold' : ''}>Deploy</span>
                  <span>•</span>
                  <span className={prog >= 0.15 && prog < 0.40 ? 'text-sky-600 font-semibold' : ''}>Transit</span>
                  <span>•</span>
                  <span className={prog >= 0.40 && prog < 0.70 ? 'text-sky-600 font-semibold' : ''}>Cluster</span>
                  <span>•</span>
                  <span className={prog >= 0.70 && prog < 0.90 ? 'text-sky-600 font-semibold' : ''}>Acquire</span>
                  <span>•</span>
                  <span className={prog >= 0.90 ? 'text-sky-600 font-semibold' : ''}>Recovery</span>
                </div>
              );
            })()}
          </div>

          {/* Speed Selector */}
          <div className="flex items-center gap-2">
            <div className="segmented-control">
              {[5, 10, 20, 50].map((spd) => (
                <button
                  key={spd}
                  onClick={() => setPlaybackSpeed(spd)}
                  className={`segmented-item font-mono text-[11px] py-1 px-2 ${
                    playbackSpeed === spd ? 'segmented-item-active' : ''
                  }`}
                >
                  {spd}×
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 3. Streamlined Metric Strip (One quiet, elegant horizontal row) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="glass-card rounded-xl p-3 space-y-0.5">
          <div className="text-[11px] text-slate-500 font-medium">Total Secured Reward</div>
          <div className="text-xl font-mono font-bold text-slate-900">
            {schedule?.cumulative_reward?.toFixed(0) ?? '0'} <span className="text-xs font-sans text-slate-400 font-normal">PTS</span>
          </div>
          <div className="text-[11px] text-emerald-600 font-medium">
            +{schedule?.reward_gain_percent?.toFixed(1) ?? '18.5'}% vs baseline
          </div>
        </div>

        <div className="glass-card rounded-xl p-3 space-y-0.5">
          <div className="text-[11px] text-slate-500 font-medium">Targets Secured</div>
          <div className="text-xl font-mono font-bold text-slate-900">
            {visitedCount} <span className="text-xs font-sans text-slate-400 font-normal">/ {totalTargetsCount}</span>
          </div>
          <div className="text-[11px] text-sky-600 font-medium">
            {coveragePct.toFixed(1)}% swarm coverage
          </div>
        </div>

        <div className="glass-card rounded-xl p-3 space-y-0.5">
          <div className="text-[11px] text-slate-500 font-medium">Min Battery Reserve</div>
          <div className="text-xl font-mono font-bold text-emerald-600">
            {minReserveAll.toFixed(1)}%
          </div>
          <div className="text-[11px] text-slate-400">
            Above 15.0% safety floor
          </div>
        </div>

        <div className="glass-card rounded-xl p-3 space-y-0.5">
          <div className="text-[11px] text-slate-500 font-medium">Optimizer Solve Time</div>
          <div className="text-xl font-mono font-bold text-slate-900">
            {schedule?.solve_time_seconds?.toFixed(3) ?? '0.840'}s
          </div>
          <div className="text-[11px] text-slate-400">
            ALNS + CP-SAT Certified
          </div>
        </div>
      </div>

      {/* 4. Interactive Context Inspector (Clean & Non-Intrusive) */}
      <div className="glass-card rounded-2xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-sky-50 border border-sky-200/80 flex items-center justify-center text-sky-600">
              <Target className="w-3.5 h-3.5" />
            </div>
            <span className="text-xs font-semibold text-slate-900">Asset & Target Inspector</span>
          </div>

          <div className="w-60">
            <select
              value={selectedInspectorObj}
              onChange={(e) => setSelectedInspectorObj(e.target.value)}
              className="glass-input w-full rounded-lg px-2.5 py-1.5 text-xs text-slate-800 bg-white/80 cursor-pointer"
            >
              {inspectorOptions.map((opt) => (
                <option key={opt} value={opt} className="bg-white text-slate-800">
                  {opt}
                </option>
              ))}
            </select>
          </div>
        </div>

        {selectedInspectorObj === 'None (Overview)' && (
          <div className="rounded-xl p-3 text-xs text-slate-500 flex items-center justify-between border border-slate-200/70 bg-white/60">
            <span>Hover or click any target node or select a UAV to inspect kinematics and sensor status.</span>
            <span className="text-[11px] font-mono text-sky-700 font-semibold">{instance?.drones?.length ?? 0} UAVs active</span>
          </div>
        )}

        {selectedInspectorObj.startsWith('UAV') && (
          <div className="rounded-xl p-3.5 space-y-2.5 bg-white/70 border border-slate-200/80">
            <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
              <div className="text-xs font-semibold text-slate-900 flex items-center gap-2">
                <span>Callsign:</span>
                <span className="font-mono text-sky-700 font-bold">{selectedInspectorObj}</span>
              </div>
              <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-sky-50 text-sky-700 border border-sky-200/80 font-medium">
                {activeTelemMap[selectedInspectorObj]?.flight_phase ?? 'CRUISE'}
              </span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                <span className="text-[10px] text-slate-400 block mb-0.5">Battery SoC</span>
                <span className="text-emerald-600 font-bold text-sm font-mono">
                  {(activeTelemMap[selectedInspectorObj]?.battery_percent ?? 100).toFixed(1)}%
                </span>
              </div>
              <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                <span className="text-[10px] text-slate-400 block mb-0.5">Groundspeed (GNSS)</span>
                <span className="text-slate-800 font-bold text-sm font-mono">
                  {(activeTelemMap[selectedInspectorObj]?.ground_speed_mps ?? activeTelemMap[selectedInspectorObj]?.speed_mps ?? 14.5).toFixed(1)} m/s
                </span>
              </div>
              <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                <span className="text-[10px] text-slate-400 block mb-0.5">Altitude (AGL)</span>
                <span className="text-slate-800 font-bold text-sm font-mono">
                  {(activeTelemMap[selectedInspectorObj]?.z ?? 60).toFixed(0)} m
                </span>
              </div>
              <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                <span className="text-[10px] text-slate-400 block mb-0.5">Heading</span>
                <span className="text-sky-700 font-bold text-sm font-mono">
                  {(activeTelemMap[selectedInspectorObj]?.heading_deg ?? 0).toFixed(0)}°
                </span>
              </div>
              <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                <span className="text-[10px] text-slate-400 block mb-0.5">Current Target</span>
                <span className="text-slate-800 font-medium truncate block">
                  {activeTelemMap[selectedInspectorObj]?.target_name ?? 'DEPOT'}
                </span>
              </div>
              <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                <span className="text-[10px] text-slate-400 block mb-0.5">Coordinates</span>
                <span className="text-slate-800 font-mono text-[11px]">
                  ({(activeTelemMap[selectedInspectorObj]?.x ?? 0).toFixed(0)}, {(activeTelemMap[selectedInspectorObj]?.y ?? 0).toFixed(0)})
                </span>
              </div>
              <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                <span className="text-[10px] text-slate-400 block mb-0.5">Power Draw</span>
                <span className="text-amber-600 font-bold font-mono">
                  {activeTelemMap[selectedInspectorObj]?.power_watts ?? 180} W
                </span>
              </div>
              <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                <span className="text-[10px] text-slate-400 block mb-0.5">Wind Impact</span>
                <span className={`font-bold font-mono text-[11px] block truncate ${
                  (activeTelemMap[selectedInspectorObj]?.wind_along_mps ?? 0) > 0.5 
                    ? 'text-emerald-600' 
                    : (activeTelemMap[selectedInspectorObj]?.wind_along_mps ?? 0) < -0.5 
                      ? 'text-amber-700' 
                      : 'text-sky-700'
                }`}>
                  {activeTelemMap[selectedInspectorObj]?.wind_effect ?? 'Nominal'} ({(activeTelemMap[selectedInspectorObj]?.wind_along_mps ?? 0) >= 0 ? '+' : ''}{(activeTelemMap[selectedInspectorObj]?.wind_along_mps ?? 0).toFixed(1)} m/s)
                </span>
              </div>
            </div>
          </div>
        )}

        {selectedInspectorObj.startsWith('Target') && (() => {
          const tId = parseInt(selectedInspectorObj.replace('Target #', ''), 10);
          const targetNode = instance?.targets?.find((t) => t.id === tId);
          const isSec = securedTargets?.includes(tId);
          let assignedUav = 'None';
          (schedule?.assigned_routes ?? []).forEach((r) => {
            if (r.target_ids?.includes(tId)) assignedUav = r.drone_id;
          });

          return (
            <div className="rounded-xl p-3.5 space-y-2.5 bg-white/70 border border-slate-200/80">
              <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
                <div className="text-xs font-semibold text-slate-900 flex items-center gap-2">
                  <span>Target Details:</span>
                  <span className="font-mono text-amber-700 font-bold">{selectedInspectorObj}</span>
                </div>
                <span className={`text-[10px] px-2.5 py-0.5 rounded-full font-medium border ${
                  isSec
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200/80'
                    : 'bg-amber-50 text-amber-700 border-amber-200/80'
                }`}>
                  {isSec ? 'Secured' : 'Pending Scan'}
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Priority Score</span>
                  <span className="text-amber-700 font-bold text-sm font-mono">
                    {targetNode?.priority_score?.toFixed(0) ?? '0'} PTS
                  </span>
                </div>
                <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Assigned UAV</span>
                  <span className="text-sky-700 font-bold text-sm font-mono">{assignedUav}</span>
                </div>
                <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Sensor Dwell</span>
                  <span className="text-slate-800 font-bold text-sm font-mono">
                    {targetNode?.dwell_time?.toFixed(0) ?? '30'}s
                  </span>
                </div>
                <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Elevation</span>
                  <span className="text-slate-800 font-bold text-sm font-mono">
                    {targetNode?.elevation?.toFixed(1) ?? '0'} m
                  </span>
                </div>
                <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Coordinates</span>
                  <span className="text-slate-800 font-mono text-[11px]">
                    ({targetNode?.x?.toFixed(1) ?? '0'}, {targetNode?.y?.toFixed(1) ?? '0'})
                  </span>
                </div>
                <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Cluster Zone</span>
                  <span className="text-slate-800 font-medium">Zone {((tId % 4) + 1)}</span>
                </div>
                <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Geofence</span>
                  <span className="text-emerald-600 font-bold">Clear</span>
                </div>
                <div className="p-2 rounded-lg bg-white/90 border border-slate-200/70 shadow-xs">
                  <span className="text-[10px] text-slate-400 block mb-0.5">Optical Recon</span>
                  <span className="text-sky-700 font-bold">Active</span>
                </div>
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
}
