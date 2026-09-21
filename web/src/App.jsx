import React, { useState, useEffect, useRef, useCallback } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import OperationsMap from './components/OperationsMap';
import FleetTelemetry from './components/FleetTelemetry';
import OptimizationLab from './components/OptimizationLab';
import EnergyBattery from './components/EnergyBattery';
import MissionExport from './components/MissionExport';
import IntroCinematic from './components/IntroCinematic';

export default function App() {
  const [activeTab, setActiveTab] = useState('map');
  const [scenario, setScenario] = useState('Chao Set 64 (Clustered SAR)');
  const [fleetSize, setFleetSize] = useState(3);
  const [windSpeed, setWindSpeed] = useState(3.5);
  const [windDir, setWindDir] = useState(45.0);

  // Cinematic Intro Animation & Depot Landing State
  const [showIntro, setShowIntro] = useState(true);
  const [triggerLandingAnim, setTriggerLandingAnim] = useState(false);

  const [instance, setInstance] = useState(null);
  const [schedule, setSchedule] = useState(null);
  const [graspSchedule, setGraspSchedule] = useState(null);
  const [maxMissionTime, setMaxMissionTime] = useState(600.0);
  const [missionTime, setMissionTime] = useState(0.0);
  const [isPlaying, setIsPlaying] = useState(false);

  const [telemetry, setTelemetry] = useState([]);
  const [securedTargets, setSecuredTargets] = useState([]);
  const [isSolving, setIsSolving] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);

  const handleIntroComplete = useCallback(() => {
    setShowIntro(false);
    setActiveTab('map');
    // Trigger the drone squadron flying in from top and landing onto the depot immediately
    setTriggerLandingAnim(true);
  }, []);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // Initial Boot: Load Mock Schedule or Canonical Instance
  useEffect(() => {
    const bootInit = async () => {
      try {
        const res = await fetch(`/api/mock?fleet_size=${fleetSize}`);
        if (res.ok) {
          const data = await res.json();
          setInstance(data.instance);
          setSchedule(data.schedule);
          setGraspSchedule(data.grasp_schedule);
          setMaxMissionTime(data.max_mission_time || 600.0);
          setTelemetry(data.telemetry_init || []);
          setSecuredTargets(data.secured_targets_init || []);
          showToast(`Mission initialized: ${data.instance.instance_name}`);
        } else {
          // Fallback to solving
          handleRunOptimizer();
        }
      } catch (err) {
        console.warn('API mock init failed, running solver:', err);
        handleRunOptimizer();
      }
    };
    bootInit();
  }, []);

  // Solve Optimizer
  const handleRunOptimizer = async (overrideParams = {}) => {
    setIsSolving(true);
    const runFleetSize = overrideParams.fleetSize ?? fleetSize;
    const runScenario = overrideParams.scenario ?? scenario;
    const runWindSpeed = overrideParams.windSpeed ?? windSpeed;
    const runWindDir = overrideParams.windDir ?? windDir;

    try {
      const res = await fetch('/api/solve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario: runScenario,
          fleet_size: runFleetSize,
          wind_speed: runWindSpeed,
          wind_dir: runWindDir,
          max_iterations: 200,
          time_limit_sec: 1.2,
        }),
      });

      if (!res.ok) throw new Error('Solver failed');
      const data = await res.json();
      setInstance(data.instance);
      setSchedule(data.schedule);
      setGraspSchedule(data.grasp_schedule);
      setMaxMissionTime(data.max_mission_time || 600.0);
      setTelemetry(data.telemetry_init || []);
      setSecuredTargets(data.secured_targets_init || []);
      setMissionTime(0.0);
      setIsPlaying(false);
      const activeCount = data.schedule?.assigned_routes?.length || 0;
      showToast(`Fleet deployed: ${activeCount} UAVs scouting ${data.schedule.cumulative_reward.toFixed(0)} pts in ${data.schedule.solve_time_seconds.toFixed(2)}s`);
    } catch (err) {
      console.error('Error running optimizer:', err);
      showToast('Solver execution failed. Check backend service.');
    } finally {
      setIsSolving(false);
    }
  };

  // Debounced auto-solve on slider/preset changes
  const isInitialBootRef = useRef(true);
  useEffect(() => {
    if (isInitialBootRef.current) {
      isInitialBootRef.current = false;
      return;
    }
    const timer = setTimeout(() => {
      handleRunOptimizer({ fleetSize, scenario, windSpeed, windDir });
    }, 450);
    return () => clearTimeout(timer);
  }, [fleetSize, scenario, windSpeed, windDir]);

  // Load Mock Fixture
  const handleLoadMock = async () => {
    try {
      const res = await fetch('/api/mock');
      if (!res.ok) throw new Error('Failed to load mock');
      const data = await res.json();
      setInstance(data.instance);
      setSchedule(data.schedule);
      setGraspSchedule(data.grasp_schedule);
      setMaxMissionTime(data.max_mission_time || 600.0);
      setTelemetry(data.telemetry_init || []);
      setSecuredTargets(data.secured_targets_init || []);
      setMissionTime(0.0);
      setIsPlaying(false);
      showToast('Loaded benchmark mock mission fixture');
    } catch (err) {
      console.error('Error loading mock:', err);
      showToast('Could not load mock fixture');
    }
  };

  // Real-time telemetry updates during scrubbing or playback
  const lastTelemReqRef = useRef(0);
  useEffect(() => {
    if (!schedule || !instance) return;

    const now = performance.now();
    // Throttle network requests to ~10Hz max (100ms)
    if (now - lastTelemReqRef.current < 80) return;
    lastTelemReqRef.current = now;

    const fetchTelem = async () => {
      try {
        const res = await fetch('/api/telemetry', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            t_sec: missionTime,
            schedule,
            instance,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          setTelemetry(data.telemetry || []);
          setSecuredTargets(data.secured_targets || []);
        }
      } catch (err) {
        // Silently skip if interrupted
      }
    };

    fetchTelem();
  }, [missionTime, schedule, instance]);

  return (
    <div className="relative flex h-screen bg-[#f6f8fc] text-slate-900 overflow-hidden font-sans select-none">
      {/* Ambient Radial Mesh Gradient Orbs (True Glass Refraction Engine) */}
      <div className="ambient-glow-bg" aria-hidden="true">
        <div className="ambient-orb-1" />
        <div className="ambient-orb-2" />
        <div className="ambient-orb-3" />
      </div>

      {/* Glass Sidebar Navigation */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        scenario={scenario}
        setScenario={setScenario}
        fleetSize={fleetSize}
        setFleetSize={setFleetSize}
        windSpeed={windSpeed}
        setWindSpeed={setWindSpeed}
        windDir={windDir}
        setWindDir={setWindDir}
        onRunOptimizer={handleRunOptimizer}
        onLoadMock={handleLoadMock}
        isSolving={isSolving}
        instance={instance}
        schedule={schedule}
      />

      {/* Main Mission Operations Viewport */}
      <div className="relative z-10 flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Command Bar */}
        <Header
          instance={instance}
          schedule={schedule}
          isSolving={isSolving}
          windSpeed={windSpeed}
          windDir={windDir}
          fleetSize={fleetSize}
        />

        {/* Content Area */}
        <main className="flex-1 overflow-y-auto p-5 space-y-4">
          {activeTab === 'map' && (
            <OperationsMap
              instance={instance}
              schedule={schedule}
              graspSchedule={graspSchedule}
              maxMissionTime={maxMissionTime}
              missionTime={missionTime}
              setMissionTime={setMissionTime}
              isPlaying={isPlaying}
              setIsPlaying={setIsPlaying}
              telemetry={telemetry}
              securedTargets={securedTargets}
              windSpeed={windSpeed}
              windDir={windDir}
              fleetSize={fleetSize}
              isSolving={isSolving}
              introActive={showIntro}
              triggerLandingAnim={triggerLandingAnim}
              onLandingAnimDone={() => setTriggerLandingAnim(false)}
            />
          )}

          {activeTab === 'telemetry' && (
            <FleetTelemetry
              instance={instance}
              schedule={schedule}
              telemetry={telemetry}
              missionTime={missionTime}
              windSpeed={windSpeed}
              windDir={windDir}
              fleetSize={fleetSize}
            />
          )}

          {activeTab === 'arena' && (
            <OptimizationLab
              instance={instance}
              schedule={schedule}
              graspSchedule={graspSchedule}
            />
          )}

          {activeTab === 'energy' && (
            <EnergyBattery
              instance={instance}
              schedule={schedule}
              missionTime={missionTime}
              windSpeed={windSpeed}
              windDir={windDir}
              fleetSize={fleetSize}
            />
          )}

          {activeTab === 'export' && (
            <MissionExport
              instance={instance}
              schedule={schedule}
            />
          )}
        </main>
      </div>

      {/* Floating Minimal Glass Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-2.5 rounded-2xl glass-card text-xs font-mono shadow-xl flex items-center gap-2.5 border border-black/[0.06] animate-fade-in">
          <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"></span>
          <span className="text-slate-800 font-medium">{toastMessage}</span>
        </div>
      )}

      {/* Realistic Drone Intro Animation & Mission Launch Sequence */}
      {showIntro && <IntroCinematic onComplete={handleIntroComplete} />}
    </div>
  );
}
