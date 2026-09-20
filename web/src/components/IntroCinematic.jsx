import React, { useState, useEffect } from 'react';
import { Shield, Zap, CheckCircle2, ChevronRight, X, Radio, Activity } from 'lucide-react';

const PREPARATION_STEPS = [
  {
    step: '01/05',
    subsystem: 'NAVIGATION & GNSS',
    text: 'Dual RTK-GNSS carrier phase locked · 18 satellites · Sub-centimeter fix',
    tag: 'RTK: FIX',
  },
  {
    step: '02/05',
    subsystem: 'ATMOSPHERIC SOUNDING',
    text: 'Ambient boundary wind 3.5 m/s @ 045° · Aerodynamic drag envelope verified',
    tag: 'WIND: NOMINAL',
  },
  {
    step: '03/05',
    subsystem: 'SPATIAL DECONFLICTION',
    text: 'Corridor sector allocation complete · Radial separation buffers enforced',
    tag: 'SECTOR: ISOLATED',
  },
  {
    step: '04/05',
    subsystem: 'ALNS MATHEURISTIC',
    text: 'Synthesizing energy-feasible trajectories · Battery reserve bounds satisfied',
    tag: 'ALNS: CONVERGED',
  },
  {
    step: '05/05',
    subsystem: 'OR-TOOLS CP-SAT',
    text: 'Exact set packing validated: 0 corridor clashes across fleet · Sortie authorized',
    tag: 'CP-SAT: VERIFIED',
  },
];

export default function IntroCinematic({ onComplete }) {
  const [progress, setProgress] = useState(0);
  const [logIndex, setLogIndex] = useState(0);
  const [phase, setPhase] = useState('hovering'); // 'hovering' | 'spooling' | 'lifting' | 'exiting'

  // Animate progress and log lines
  useEffect(() => {
    const startTime = performance.now();
    const duration = 4000; // 4.0s total preparation sequence

    const interval = setInterval(() => {
      const elapsed = performance.now() - startTime;
      const pct = Math.min(100, Math.floor((elapsed / duration) * 100));
      setProgress(pct);

      if (pct < 20) setLogIndex(0);
      else if (pct < 45) setLogIndex(1);
      else if (pct < 70) setLogIndex(2);
      else if (pct < 90) setLogIndex(3);
      else setLogIndex(4);

      if (elapsed >= duration) {
        clearInterval(interval);
        setProgress(100);
        // Phase 1: Spool up motors, pitch forward into aerodynamic climb
        setPhase('spooling');
        setTimeout(() => {
          // Phase 2: Slower, realistic vertical flight climb (2.2s flight)
          setPhase('lifting');
          setTimeout(() => {
            // Phase 3: Screen fade-out and seamless handoff to dashboard
            setPhase('exiting');
            setTimeout(() => {
              onComplete();
            }, 600);
          }, 1800);
        }, 600);
      }
    }, 35);

    return () => clearInterval(interval);
  }, [onComplete]);

  // Keyboard shortcut Esc to skip
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onComplete();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onComplete]);

  const isLifting = phase === 'lifting';
  const isExiting = phase === 'exiting';
  const isSpooling = phase === 'spooling' || phase === 'lifting';
  const currentStep = PREPARATION_STEPS[logIndex] || PREPARATION_STEPS[0];

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-[#f8fafc]/96 backdrop-blur-3xl transition-opacity duration-700 select-none overflow-hidden ${
        isExiting ? 'opacity-0 pointer-events-none' : 'opacity-100'
      }`}
    >
      {/* Light Ambient Aerospace Sky Atmosphere */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        {/* Soft daylight sky diffusion */}
        <div className="absolute top-1/6 left-1/2 -translate-x-1/2 w-[1000px] h-[700px] bg-radial from-sky-200/40 via-slate-100/30 to-transparent blur-3xl" />
        <div className="absolute -bottom-20 left-1/2 -translate-x-1/2 w-[700px] h-[350px] bg-radial from-indigo-100/30 to-transparent blur-2xl" />

        {/* Clean, subtle coordinate micro-grid */}
        <div
          className="absolute inset-0 opacity-[0.035]"
          style={{
            backgroundImage:
              'linear-gradient(to right, #0f172a 1px, transparent 1px), linear-gradient(to bottom, #0f172a 1px, transparent 1px)',
            backgroundSize: '48px 48px',
          }}
        />

        {/* Aerospace Watermark */}
        <div className="absolute top-6 left-8 font-mono text-[10px] text-slate-400 tracking-wider">
          AEROSCAN // MISSION PREPARATION · PLATFORM UAV-01
        </div>
        <div className="absolute bottom-6 left-8 font-mono text-[10px] text-slate-400 tracking-wider">
          LAT 37°46&apos;29&quot;N · LON 122°25&apos;10&quot;W · ELEV 14M · WIND 3.5 M/S @ 045°
        </div>
      </div>

      {/* Minimal Skip Button */}
      <button
        onClick={onComplete}
        className="absolute top-6 right-6 z-50 flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-white/80 hover:bg-white text-slate-600 hover:text-slate-900 text-xs font-mono tracking-wider backdrop-blur-md border border-slate-200/90 transition-all cursor-pointer shadow-xs hover:shadow-sm hover:scale-105"
      >
        <span>SKIP INTRO</span>
        <span className="px-1.5 py-0.5 rounded bg-slate-100 text-[10px] text-slate-500 font-semibold">
          ESC
        </span>
      </button>

      {/* Main Assembly: Industrial Drone + High-Tensile Rigging + Minimal Frosted Glass Slate */}
      <div
        className={`relative flex flex-col items-center transition-all duration-[2200ms] ease-[cubic-bezier(0.33,1,0.68,1)] ${
          isLifting
            ? '-translate-y-[150vh] scale-95 opacity-90'
            : isSpooling
            ? 'animate-pulse'
            : 'animate-drone-hover'
        }`}
      >
        {/* =========================================================================
            1. REALISTIC INDUSTRIAL QUADCOPTER (UAV-01 "AEROSCAN TITAN")
            ========================================================================= */}
        <div className="relative w-[440px] h-[210px] flex items-center justify-center">
          {/* Subtle Atmospheric Downwash Air Distortion */}
          <div className="absolute top-[90px] left-1/2 -translate-x-1/2 w-[400px] h-[240px] pointer-events-none opacity-20 animate-searchlight z-0">
            <svg viewBox="0 0 400 240" className="w-full h-full overflow-visible">
              <defs>
                <linearGradient id="daylightDownwash" x1="50%" y1="0%" x2="50%" y2="100%">
                  <stop offset="0%" stopColor="#0284c7" stopOpacity="0.2" />
                  <stop offset="60%" stopColor="#0284c7" stopOpacity="0.04" />
                  <stop offset="100%" stopColor="#0284c7" stopOpacity="0" />
                </linearGradient>
              </defs>
              <polygon points="180,0 30,240 210,240" fill="url(#daylightDownwash)" />
              <polygon points="220,0 190,240 370,240" fill="url(#daylightDownwash)" />
            </svg>
          </div>

          {/* High-Fidelity Drone SVG Model */}
          <svg
            viewBox="0 0 440 210"
            className="w-full h-full relative z-10 drop-shadow-[0_16px_28px_rgba(15,23,42,0.18)]"
          >
            <defs>
              {/* Carbon Fiber Composite Fuselage Gradient */}
              <linearGradient id="fuselageCarbon" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#334155" />
                <stop offset="30%" stopColor="#1e293b" />
                <stop offset="70%" stopColor="#0f172a" />
                <stop offset="100%" stopColor="#020617" />
              </linearGradient>

              {/* Titanium Arm Strut Gradient */}
              <linearGradient id="strutTitanium" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#64748b" />
                <stop offset="40%" stopColor="#475569" />
                <stop offset="80%" stopColor="#1e293b" />
                <stop offset="100%" stopColor="#0f172a" />
              </linearGradient>

              {/* Motor Nacelle Metallic Gradient */}
              <linearGradient id="nacelleBell" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#1e293b" />
                <stop offset="50%" stopColor="#475569" />
                <stop offset="100%" stopColor="#0f172a" />
              </linearGradient>

              {/* High-Speed Spinning Propeller Motion Blur */}
              <radialGradient id="rotorBlurLight">
                <stop offset="0%" stopColor="#0284c7" stopOpacity="0.25" />
                <stop offset="55%" stopColor="#0284c7" stopOpacity="0.12" />
                <stop offset="88%" stopColor="#64748b" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#0284c7" stopOpacity="0" />
              </radialGradient>

              {/* Optical Lens Anti-Reflective Coating */}
              <radialGradient id="opticReflect" cx="35%" cy="35%" r="65%">
                <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.95" />
                <stop offset="45%" stopColor="#0284c7" stopOpacity="0.75" />
                <stop offset="80%" stopColor="#1e1b4b" stopOpacity="0.95" />
                <stop offset="100%" stopColor="#020617" />
              </radialGradient>
            </defs>

            {/* --- 1. Carbon Fiber Structural Cross-Arms --- */}
            <g stroke="url(#strutTitanium)" strokeWidth="7" strokeLinecap="round">
              {/* Front-Left to Rear-Right Arm */}
              <line x1="60" y1="58" x2="220" y2="105" />
              <line x1="220" y1="105" x2="380" y2="152" />
              {/* Front-Right to Rear-Left Arm */}
              <line x1="380" y1="58" x2="220" y2="105" />
              <line x1="220" y1="105" x2="60" y2="152" />
            </g>

            {/* Central Arm Clamps with Hex Fasteners */}
            <path
              d="M 175 105 L 220 78 L 265 105 L 220 132 Z"
              fill="#0f172a"
              stroke="#334155"
              strokeWidth="1.5"
            />

            {/* --- 2. Landing Skids Assembly --- */}
            <g stroke="#94a3b8" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none">
              {/* Left Landing Gear Leg & Longitudinal Skid Tube */}
              <path d="M 160 118 L 145 168 L 110 168" />
              <path d="M 195 118 L 180 168 L 270 168" />
              <path d="M 100 170 L 205 170" stroke="#64748b" strokeWidth="4" />
              {/* Left Skid Rubber Damper Bushings */}
              <rect x="115" y="167" width="10" height="6" rx="2" fill="#0f172a" />
              <rect x="180" y="167" width="10" height="6" rx="2" fill="#0f172a" />

              {/* Right Landing Gear Leg & Skid Tube */}
              <path d="M 245 118 L 260 168 L 330 168" />
              <path d="M 280 118 L 295 168" />
              <path d="M 235 170 L 340 170" stroke="#64748b" strokeWidth="4" />
              {/* Right Skid Rubber Damper Bushings */}
              <rect x="250" y="167" width="10" height="6" rx="2" fill="#0f172a" />
              <rect x="315" y="167" width="10" height="6" rx="2" fill="#0f172a" />
            </g>

            {/* Heavy-Lift Winch Shackles (Anchor Points for Cables) */}
            <g>
              <circle cx="145" cy="170" r="4" fill="#334155" stroke="#cbd5e1" strokeWidth="1.5" />
              <circle cx="145" cy="170" r="1.8" fill="#ffffff" />

              <circle cx="295" cy="170" r="4" fill="#334155" stroke="#cbd5e1" strokeWidth="1.5" />
              <circle cx="295" cy="170" r="1.8" fill="#ffffff" />
            </g>

            {/* --- 3. Sculpted Central Aerodynamic Fuselage --- */}
            {/* Lower Hull Section */}
            <ellipse
              cx="220"
              cy="105"
              rx="54"
              ry="27"
              fill="url(#fuselageCarbon)"
              stroke="#475569"
              strokeWidth="2"
            />

            {/* Upper Avionics Stealth Cowling */}
            <path
              d="M 180 102 C 180 84, 260 84, 260 102 C 260 115, 180 115, 180 102 Z"
              fill="#0f172a"
              stroke="#38bdf8"
              strokeWidth="1.2"
            />

            {/* Cooling Louvers */}
            <g stroke="#334155" strokeWidth="1.2" strokeLinecap="round">
              <line x1="205" y1="92" x2="235" y2="92" />
              <line x1="208" y1="96" x2="232" y2="96" />
              <line x1="212" y1="100" x2="228" y2="100" />
            </g>

            {/* Dual RTK-GNSS Helical Masts */}
            <g>
              <rect x="192" y="74" width="3" height="12" rx="1.5" fill="#64748b" />
              <ellipse cx="193.5" cy="74" rx="4" ry="2.5" fill="#ffffff" stroke="#0f172a" strokeWidth="1" />
              <rect x="245" y="74" width="3" height="12" rx="1.5" fill="#64748b" />
              <ellipse cx="246.5" cy="74" rx="4" ry="2.5" fill="#ffffff" stroke="#0f172a" strokeWidth="1" />
            </g>

            {/* Center AeroScan Drone Emblem */}
            <g transform="translate(220, 107)">
              <circle cx="0" cy="0" r="6" fill="#0284c7" />
              <polygon points="0,-3.5 2.5,2.5 -2.5,2.5" fill="#ffffff" />
            </g>

            {/* --- 4. Brushless Motor Nacelles --- */}
            {/* Motor 1: Front Left */}
            <rect x="44" y="48" width="32" height="20" rx="5" fill="url(#nacelleBell)" stroke="#64748b" strokeWidth="1.5" />
            <line x1="50" y1="58" x2="70" y2="58" stroke="#d97706" strokeWidth="1.5" opacity="0.8" />
            {/* Motor 2: Front Right */}
            <rect x="364" y="48" width="32" height="20" rx="5" fill="url(#nacelleBell)" stroke="#64748b" strokeWidth="1.5" />
            <line x1="370" y1="58" x2="390" y2="58" stroke="#d97706" strokeWidth="1.5" opacity="0.8" />
            {/* Motor 3: Rear Left */}
            <rect x="44" y="142" width="32" height="20" rx="5" fill="url(#nacelleBell)" stroke="#64748b" strokeWidth="1.5" />
            <line x1="50" y1="152" x2="70" y2="152" stroke="#d97706" strokeWidth="1.5" opacity="0.8" />
            {/* Motor 4: Rear Right */}
            <rect x="364" y="142" width="32" height="20" rx="5" fill="url(#nacelleBell)" stroke="#64748b" strokeWidth="1.5" />
            <line x1="370" y1="152" x2="390" y2="152" stroke="#d97706" strokeWidth="1.5" opacity="0.8" />

            {/* --- 5. High-Velocity Spinning Rotor Blur Discs --- */}
            {/* Rotor 1 (Front Left) */}
            <g transform="translate(60, 46)">
              <ellipse cx="0" cy="0" rx="56" ry="15" fill="url(#rotorBlurLight)" />
              <g className="animate-rotor-fast" style={{ transformOrigin: '0px 0px' }}>
                <line x1="-54" y1="0" x2="54" y2="0" stroke="#0f172a" strokeWidth="3" opacity="0.8" strokeLinecap="round" />
                <line x1="0" y1="-12" x2="0" y2="12" stroke="#475569" strokeWidth="2.2" opacity="0.6" strokeLinecap="round" />
                {/* Propeller High-Visibility Orange Safety Tips */}
                <line x1="-54" y1="0" x2="-44" y2="0" stroke="#ea580c" strokeWidth="3.5" strokeLinecap="round" />
                <line x1="44" y1="0" x2="54" y2="0" stroke="#ea580c" strokeWidth="3.5" strokeLinecap="round" />
              </g>
              <circle cx="0" cy="0" r="4.5" fill="#f8fafc" stroke="#0f172a" strokeWidth="1.5" />
            </g>

            {/* Rotor 2 (Front Right) */}
            <g transform="translate(380, 46)">
              <ellipse cx="0" cy="0" rx="56" ry="15" fill="url(#rotorBlurLight)" />
              <g className="animate-rotor-fast" style={{ transformOrigin: '0px 0px' }}>
                <line x1="-54" y1="0" x2="54" y2="0" stroke="#0f172a" strokeWidth="3" opacity="0.8" strokeLinecap="round" />
                <line x1="0" y1="-12" x2="0" y2="12" stroke="#475569" strokeWidth="2.2" opacity="0.6" strokeLinecap="round" />
                <line x1="-54" y1="0" x2="-44" y2="0" stroke="#ea580c" strokeWidth="3.5" strokeLinecap="round" />
                <line x1="44" y1="0" x2="54" y2="0" stroke="#ea580c" strokeWidth="3.5" strokeLinecap="round" />
              </g>
              <circle cx="0" cy="0" r="4.5" fill="#f8fafc" stroke="#0f172a" strokeWidth="1.5" />
            </g>

            {/* Rotor 3 (Rear Left) */}
            <g transform="translate(60, 140)">
              <ellipse cx="0" cy="0" rx="56" ry="15" fill="url(#rotorBlurLight)" />
              <g className="animate-rotor-fast" style={{ transformOrigin: '0px 0px' }}>
                <line x1="-54" y1="0" x2="54" y2="0" stroke="#0f172a" strokeWidth="3" opacity="0.8" strokeLinecap="round" />
                <line x1="0" y1="-12" x2="0" y2="12" stroke="#475569" strokeWidth="2.2" opacity="0.6" strokeLinecap="round" />
                <line x1="-54" y1="0" x2="-44" y2="0" stroke="#ea580c" strokeWidth="3.5" strokeLinecap="round" />
                <line x1="44" y1="0" x2="54" y2="0" stroke="#ea580c" strokeWidth="3.5" strokeLinecap="round" />
              </g>
              <circle cx="0" cy="0" r="4.5" fill="#f8fafc" stroke="#0f172a" strokeWidth="1.5" />
            </g>

            {/* Rotor 4 (Rear Right) */}
            <g transform="translate(380, 140)">
              <ellipse cx="0" cy="0" rx="56" ry="15" fill="url(#rotorBlurLight)" />
              <g className="animate-rotor-fast" style={{ transformOrigin: '0px 0px' }}>
                <line x1="-54" y1="0" x2="54" y2="0" stroke="#0f172a" strokeWidth="3" opacity="0.8" strokeLinecap="round" />
                <line x1="0" y1="-12" x2="0" y2="12" stroke="#475569" strokeWidth="2.2" opacity="0.6" strokeLinecap="round" />
                <line x1="-54" y1="0" x2="-44" y2="0" stroke="#ea580c" strokeWidth="3.5" strokeLinecap="round" />
                <line x1="44" y1="0" x2="54" y2="0" stroke="#ea580c" strokeWidth="3.5" strokeLinecap="round" />
              </g>
              <circle cx="0" cy="0" r="4.5" fill="#f8fafc" stroke="#0f172a" strokeWidth="1.5" />
            </g>

            {/* --- 6. FAA Certified Navigation Beacons --- */}
            <circle cx="42" cy="48" r="3.5" fill="#ef4444" className="animate-strobe-red" />
            <circle cx="42" cy="142" r="3.5" fill="#ef4444" className="animate-strobe-red" />

            <circle cx="398" cy="48" r="3.5" fill="#10b981" className="animate-strobe-green" />
            <circle cx="398" cy="142" r="3.5" fill="#10b981" className="animate-strobe-green" />

            <circle cx="220" cy="132" r="3.5" fill="#0284c7" className="animate-strobe-white" />

            {/* --- 7. 3-Axis Gyro Camera Gimbal --- */}
            <g transform="translate(220, 126)">
              <rect x="-6" y="0" width="12" height="6" rx="2" fill="#334155" />
              <ellipse cx="0" cy="8" rx="10" ry="10" fill="#090d16" stroke="#475569" strokeWidth="1.5" />
              <circle cx="0" cy="8" r="6" fill="url(#opticReflect)" />
              <circle cx="-2" cy="6" r="1.8" fill="#ffffff" opacity="0.9" />
            </g>
          </svg>
        </div>

        {/* =========================================================================
            2. BRAIDED STEEL RIGGING TETHERS
            ========================================================================= */}
        <div className="relative w-[440px] h-[60px] flex justify-between px-[142px] pointer-events-none -mt-4">
          {/* Left Tether */}
          <div className="relative w-[2px] h-full bg-gradient-to-b from-slate-400 via-slate-500 to-slate-400 origin-top transform rotate-[3.5deg]">
            <div className="absolute -top-1 -left-[3px] w-2 h-2 rounded-full border border-slate-400 bg-slate-200" />
            <div className="absolute -bottom-1 -left-[3px] w-2 h-2.5 rounded-xs border border-slate-400 bg-slate-300" />
          </div>

          {/* Right Tether */}
          <div className="relative w-[2px] h-full bg-gradient-to-b from-slate-400 via-slate-500 to-slate-400 origin-top transform -rotate-[3.5deg]">
            <div className="absolute -top-1 -left-[3px] w-2 h-2 rounded-full border border-slate-400 bg-slate-200" />
            <div className="absolute -bottom-1 -left-[3px] w-2 h-2.5 rounded-xs border border-slate-400 bg-slate-300" />
          </div>
        </div>

        {/* =========================================================================
            3. MINIMAL FROSTED WHITE GLASS SLATE (SWISS / LINEAR STANDARD)
            ========================================================================= */}
        <div className="animate-board-swing origin-top w-[540px] max-w-[94vw]">
          <div className="relative rounded-2xl bg-white/90 backdrop-blur-2xl border border-slate-200/95 p-7 shadow-[0_20px_50px_-10px_rgba(15,23,42,0.12),0_1px_3px_rgba(15,23,42,0.04)] text-slate-800">
            {/* Minimal Titanium Fasteners */}
            <div className="absolute top-3 left-3 w-2 h-2 rounded-full border border-slate-300 bg-slate-100 flex items-center justify-center">
              <div className="w-1 h-[0.5px] bg-slate-400" />
            </div>
            <div className="absolute top-3 right-3 w-2 h-2 rounded-full border border-slate-300 bg-slate-100 flex items-center justify-center">
              <div className="w-1 h-[0.5px] bg-slate-400" />
            </div>
            <div className="absolute bottom-3 left-3 w-2 h-2 rounded-full border border-slate-300 bg-slate-100 flex items-center justify-center">
              <div className="w-1 h-[0.5px] bg-slate-400" />
            </div>
            <div className="absolute bottom-3 right-3 w-2 h-2 rounded-full border border-slate-300 bg-slate-100 flex items-center justify-center">
              <div className="w-1 h-[0.5px] bg-slate-400" />
            </div>

            {/* Mounting Brackets at Top Cable Connection */}
            <div className="absolute -top-3 left-[140px] w-3.5 h-3.5 rounded-full border-2 border-slate-300 bg-white shadow-xs flex items-center justify-center">
              <div className="w-1.5 h-1.5 rounded-full bg-slate-400" />
            </div>
            <div className="absolute -top-3 right-[140px] w-3.5 h-3.5 rounded-full border-2 border-slate-300 bg-white shadow-xs flex items-center justify-center">
              <div className="w-1.5 h-1.5 rounded-full bg-slate-400" />
            </div>

            {/* Header: Pure Minimal Branding */}
            <div className="flex flex-col items-center text-center space-y-1">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-slate-100 border border-slate-200/80 flex items-center justify-center text-slate-700 shadow-2xs">
                  <Activity className="w-4 h-4 text-sky-600" />
                </div>
                <h1 className="text-3xl font-extrabold tracking-[0.2em] text-slate-900 font-sans">
                  AEROSCAN
                </h1>
              </div>
              <p className="text-[10.5px] font-mono tracking-widest text-slate-500 uppercase font-medium">
                Autonomous Swarm Reconnaissance Intelligence
              </p>
            </div>

            {/* Minimal Divider */}
            <div className="my-4 h-px bg-slate-200/80" />

            {/* Clean Telemetry Verification Container */}
            <div className="bg-slate-50/90 rounded-xl border border-slate-200/80 p-3.5 space-y-2.5 font-mono">
              <div className="flex items-center justify-between text-[11px] text-slate-500 border-b border-slate-200/70 pb-2">
                <span className="flex items-center gap-2 text-slate-700 font-semibold">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse inline-block" />
                  PRE-FLIGHT TELEMETRY
                </span>
                <span className="px-2 py-0.5 rounded-md bg-white border border-slate-200 text-[10px] text-slate-600 font-medium">
                  {currentStep.subsystem}
                </span>
              </div>

              {/* Dynamic Line Showing Current Pre-Flight Step */}
              <div className="min-h-[42px] flex items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="text-sky-600 font-bold shrink-0">
                    [{currentStep.step}]
                  </span>
                  <span className="text-slate-700 tracking-tight leading-snug truncate font-medium">
                    {currentStep.text}
                  </span>
                </div>
                <span className="px-2 py-0.5 rounded-md bg-sky-50 border border-sky-200/80 text-[10px] text-sky-700 shrink-0 font-semibold">
                  {currentStep.tag}
                </span>
              </div>
            </div>

            {/* Calibrated Minimal Progress Gauge */}
            <div className="mt-4 space-y-2">
              <div className="flex justify-between items-center text-xs font-mono">
                <span className="text-slate-500 flex items-center gap-1.5 font-medium">
                  <Zap className={`w-3.5 h-3.5 ${progress < 100 ? 'text-amber-500' : 'text-emerald-500'}`} />
                  <span>
                    {progress < 100
                      ? 'CALIBRATING SWARM TRAJECTORIES...'
                      : 'ALL SYSTEMS GREEN · SORTIE AUTHORIZED'}
                  </span>
                </span>
                <span className="text-slate-900 font-bold text-sm tracking-wider">
                  {progress}%
                </span>
              </div>

              {/* Segmented Readiness Gauge */}
              <div className="w-full h-2.5 rounded-full bg-slate-100 p-0.5 border border-slate-200/90 overflow-hidden flex gap-1">
                {Array.from({ length: 10 }).map((_, idx) => {
                  const filled = progress >= (idx + 1) * 10;
                  return (
                    <div
                      key={idx}
                      className={`flex-1 h-full rounded-xs transition-colors duration-150 ${
                        filled
                          ? 'bg-slate-900'
                          : 'bg-slate-200/70'
                      }`}
                    />
                  );
                })}
              </div>
            </div>

            {/* Minimal Footer */}
            <div className="mt-4 flex items-center justify-between text-[10px] font-mono text-slate-500 pt-2.5 border-t border-slate-200/80">
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                <span>DECONFLICTED DEPLOYMENT</span>
              </span>
              <span className="text-slate-400">TIER-2 CP-SAT MATHEURISTIC</span>
              <span className="text-slate-700 font-semibold">UAV-01 READY</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
