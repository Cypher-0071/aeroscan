import React, { useState, useEffect } from 'react';

const PREPARATION_STEPS = [
  'Initializing fleet telemetry & GPS lock...',
  'Analyzing atmospheric wind field & drag limits...',
  'Calculating collision-free flight corridors...',
  'Optimizing multi-UAV reconnaissance routes...',
  'Pre-flight checks verified. Ready for launch.',
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

      </div>

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
            2. PRECISION SUSPENSION RIGGING
            ========================================================================= */}
        <div className="relative w-[440px] h-[52px] pointer-events-none -mt-7 z-20">
          <svg viewBox="0 0 440 52" className="w-full h-full overflow-visible">
            <defs>
              <linearGradient id="cableSteel" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#475569" />
                <stop offset="50%" stopColor="#94a3b8" />
                <stop offset="100%" stopColor="#64748b" />
              </linearGradient>
            </defs>

            {/* Left Suspension Cable */}
            <circle cx="145" cy="4" r="3" fill="#1e293b" stroke="#64748b" strokeWidth="1" />
            <line x1="145" y1="6" x2="160" y2="48" stroke="url(#cableSteel)" strokeWidth="1.6" />
            <circle cx="160" cy="48" r="2.5" fill="#334155" />

            {/* Right Suspension Cable */}
            <circle cx="295" cy="4" r="3" fill="#1e293b" stroke="#64748b" strokeWidth="1" />
            <line x1="295" y1="6" x2="280" y2="48" stroke="url(#cableSteel)" strokeWidth="1.6" />
            <circle cx="280" cy="48" r="2.5" fill="#334155" />
          </svg>
        </div>

        {/* =========================================================================
            3. MINIMAL PHYSICAL BOARD (HUMAN-CRAFTED DESIGN)
            ========================================================================= */}
        <div className="animate-board-swing origin-top w-[440px] max-w-[92vw]">
          <div className="relative rounded-2xl bg-white/95 backdrop-blur-xl border border-slate-200/90 px-8 py-6 shadow-[0_22px_45px_-12px_rgba(15,23,42,0.11),0_2px_6px_rgba(15,23,42,0.03)] text-slate-800">
            {/* Top Suspension Eyelets */}
            <div className="absolute -top-2 left-[calc(50%-60px)] -translate-x-1/2 w-3.5 h-3.5 rounded-full border-2 border-slate-400 bg-white shadow-xs flex items-center justify-center">
              <div className="w-1.5 h-1.5 rounded-full bg-slate-600" />
            </div>
            <div className="absolute -top-2 left-[calc(50%+60px)] -translate-x-1/2 w-3.5 h-3.5 rounded-full border-2 border-slate-400 bg-white shadow-xs flex items-center justify-center">
              <div className="w-1.5 h-1.5 rounded-full bg-slate-600" />
            </div>

            {/* Brand Header */}
            <div className="flex flex-col items-center text-center">
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-slate-100 border border-slate-200/70 mb-2">
                <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse" />
                <span className="text-[10px] font-mono tracking-wider uppercase text-slate-600 font-semibold">
                  Pre-Flight Calibration
                </span>
              </div>
              <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 font-sans">
                AeroScan
              </h1>
              <p className="text-xs text-slate-500 mt-0.5 font-medium">
                Autonomous Aerial Mission Operations
              </p>
            </div>

            {/* Loader Section */}
            <div className="mt-6 space-y-2.5">
              {/* Clean continuous progress line */}
              <div className="w-full h-1.5 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className="h-full bg-slate-900 rounded-full transition-all duration-200 ease-out"
                  style={{ width: `${progress}%` }}
                />
              </div>

              {/* Dynamic Status Text & Percentage */}
              <div className="flex items-center justify-between text-xs font-mono pt-1">
                <span className="text-slate-600 font-medium truncate pr-2">
                  {currentStep}
                </span>
                <span className="text-slate-900 font-bold shrink-0">
                  {progress}%
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
