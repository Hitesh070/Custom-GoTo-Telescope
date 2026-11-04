"use client";

import React, { useState, useEffect, useCallback } from "react";
import { TelescopeTelemetry, ConnectionConfig, MountLogMessage, TrackingRate } from "@/types/telescope";
import { DEFAULT_CONFIG, fetchTelemetry, sendCommand } from "@/lib/api";
import { Header } from "@/components/Header";
import { TelemetryCard } from "@/components/TelemetryCard";
import { CelestialRadar } from "@/components/CelestialRadar";
import { DPadControls } from "@/components/DPadControls";
import { QuickCatalog } from "@/components/QuickCatalog";
import { FocusController } from "@/components/FocusController";
import { ConsoleLog } from "@/components/ConsoleLog";
import { SettingsModal } from "@/components/SettingsModal";
import { AlertOctagon } from "lucide-react";

export default function TelescopeControlPage() {
  const [telemetry, setTelemetry] = useState<TelescopeTelemetry>({
    connected: true,
    simulated: true,
    slew_state: "IDLE",
    tracking: false,
    tracking_rate: "Sidereal",
    az_deg: 0.0,
    alt_deg: 0.0,
    ra_j2000_hours: 2.53,
    dec_j2000_deg: 89.26,
    target_name: "Polaris",
    target_type: "Alignment Star",
    target_ra_hours: 2.53,
    target_dec_deg: 89.26,
    target_az_deg: 0.0,
    target_alt_deg: 13.0,
    sun_sep_deg: 110.5,
    solar_filter_confirmed: false,
    cable_turns: 0.0,
    cable_status: "OK",
    focus_pos: 0,
    data_rate_hz: 4,
    weather: {
      condition: "Clear Sky",
      cloud_cover: 8,
      temp_c: 24.5,
      humidity: 58,
      wind_kmh: 6.2,
      obs_status: "Excellent Seeing",
    },
  });

  const [nightMode, setNightMode] = useState<boolean>(true);
  const [config, setConfig] = useState<ConnectionConfig>(DEFAULT_CONFIG);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [logs, setLogs] = useState<MountLogMessage[]>([]);

  // Load saved preferences on mount
  useEffect(() => {
    try {
      const savedNm = localStorage.getItem("custom_goto_night_mode");
      if (savedNm !== null) setNightMode(savedNm === "true");

      const savedCfg = localStorage.getItem("custom_goto_config");
      if (savedCfg) setConfig({ ...DEFAULT_CONFIG, ...JSON.parse(savedCfg) });
    } catch {
      // localStorage may fail in strict private modes
    }
  }, []);

  const addLog = useCallback((level: "INFO" | "WARNING" | "ERROR" | "COMMAND", text: string) => {
    const now = new Date();
    const timeStr = `${now.getHours().toString().padStart(2, "0")}:${now.getMinutes().toString().padStart(2, "0")}:${now.getSeconds().toString().padStart(2, "0")}`;
    setLogs((prev) => [
      ...prev.slice(-99),
      {
        id: Math.random().toString(36).substring(2, 9),
        timestamp: timeStr,
        level,
        text,
      },
    ]);
  }, []);

  // Polling loop for mount telemetry
  useEffect(() => {
    let isMounted = true;
    const interval = setInterval(async () => {
      const data = await fetchTelemetry(config);
      if (isMounted) {
        setTelemetry(data);
      }
    }, config.refreshIntervalMs);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [config]);

  // Slew arrival detection & logger
  const [prevSlewState, setPrevSlewState] = useState<string>("IDLE");
  useEffect(() => {
    if (prevSlewState === "SLEWING" && (telemetry.slew_state === "TRACKING" || telemetry.slew_state === "IDLE")) {
      addLog("INFO", `Slew completed. Arrived at target ${telemetry.target_name || "position"}`);
    }
    setPrevSlewState(telemetry.slew_state);
  }, [telemetry.slew_state, telemetry.target_name, prevSlewState, addLog]);

  // Handlers
  const handleToggleNightMode = () => {
    const next = !nightMode;
    setNightMode(next);
    try {
      localStorage.setItem("custom_goto_night_mode", String(next));
    } catch {}
  };

  const handleSaveConfig = (newConfig: ConnectionConfig) => {
    setConfig(newConfig);
    try {
      localStorage.setItem("custom_goto_config", JSON.stringify(newConfig));
    } catch {}
    addLog("INFO", `Config updated: Mode=${newConfig.simulatedMode ? "Simulated" : "Live"}, URL=${newConfig.apiUrl}`);
  };

  const handleEmergencyStop = async () => {
    addLog("COMMAND", "EXECUTING EMERGENCY STOP");
    const res = await sendCommand("stop", {}, config);
    if (res.success) {
      addLog("WARNING", res.message);
    } else {
      addLog("ERROR", res.message);
    }
  };

  const handleJog = async (axis: "az" | "alt", dir: 1 | -1, deg: number) => {
    addLog("COMMAND", `NUDGE ${axis.toUpperCase()} ${dir > 0 ? "+" : "-"}${deg}°`);
    const res = await sendCommand("jog", { axis, dir, deg }, config);
    if (!res.success) addLog("ERROR", res.message);
  };

  const handleSlewToTarget = async (name: string, az: number, alt: number) => {
    addLog("COMMAND", `GOTO -> ${name} (Az ${az.toFixed(1)}°, Alt ${alt.toFixed(1)}°)`);
    const res = await sendCommand("goto", { name, az, alt }, config);
    if (res.success) {
      addLog("INFO", res.message);
    } else {
      addLog("ERROR", res.message);
    }
  };

  const handleToggleTracking = async (rate?: TrackingRate) => {
    const nextRate = rate || telemetry.tracking_rate;
    const nextEnabled = rate ? true : !telemetry.tracking;
    addLog("COMMAND", `SET TRACKING: ${nextEnabled ? "ON (" + nextRate + ")" : "OFF"}`);
    const res = await sendCommand("tracking", { enabled: nextEnabled, rate: nextRate }, config);
    if (res.success) addLog("INFO", res.message);
  };

  const handleUnwindCable = async () => {
    addLog("COMMAND", "UNWIND CABLE TO AZIMUTH 0°");
    const res = await sendCommand("unwind", {}, config);
    if (res.success) addLog("INFO", res.message);
  };

  const handleFocusNudge = async (steps: number) => {
    addLog("COMMAND", `FOCUS NUDGE: ${steps > 0 ? "+" : ""}${steps} steps`);
    const res = await sendCommand("focus", { steps }, config);
    if (res.success) addLog("INFO", res.message);
  };

  const handleZeroFocus = async () => {
    addLog("COMMAND", "ZERO FOCUS POSITION");
    const res = await sendCommand("focus", { steps: -telemetry.focus_pos }, config);
    if (res.success) addLog("INFO", "Focus position zeroed");
  };

  const handleSync = async () => {
    addLog("COMMAND", "SYNC TARGET TO OPTICAL POSITION");
    const res = await sendCommand("sync", { name: telemetry.target_name }, config);
    if (res.success) addLog("INFO", res.message);
  };

  const handleHome = async (axis: "az" | "alt") => {
    addLog("COMMAND", `HOME ${axis.toUpperCase()} AXIS`);
    const res = await sendCommand("home", { axis }, config);
    if (res.success) addLog("INFO", res.message);
  };

  const handlePark = async () => {
    addLog("COMMAND", "PARK TELESCOPE (0°, 0°)");
    const res = await sendCommand("park", {}, config);
    if (res.success) addLog("INFO", res.message);
  };

  return (
    <div className={`min-h-screen transition-colors duration-200 ${
      nightMode ? "bg-[#000000] text-[#FF3333]" : "bg-[#0D1117] text-[#E6EDF3]"
    }`}>
      {/* 1. Header Bar */}
      <Header
        telemetry={telemetry}
        nightMode={nightMode}
        onToggleNightMode={handleToggleNightMode}
        onEmergencyStop={handleEmergencyStop}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      {/* 2. Solar Safety Warning Strip */}
      <div className={`w-full py-1.5 px-4 text-center font-mono text-xs font-bold border-b flex items-center justify-center gap-2 ${
        nightMode ? "bg-[#1A0303] text-[#FFAAAA] border-[#4D0A0A]" : "bg-[#380D0D] text-[#FFB4B4] border-[#5E1717]"
      }`}>
        <AlertOctagon className="w-3.5 h-3.5 text-red-500" />
        <span>CAUTION: NEVER POINT TELESCOPE AT OR NEAR THE SUN WITHOUT A CERTIFIED SOLAR FILTER</span>
      </div>

      {/* 3. Main Workspace Container */}
      <main className="max-w-7xl mx-auto p-3 sm:p-4 md:p-6 space-y-4">
        {/* Responsive Grid: 3 columns on large screens, stacked on mobile */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          
          {/* Column 1: Sky Radar & Motorized Focus */}
          <div className="space-y-4">
            <CelestialRadar telemetry={telemetry} nightMode={nightMode} />
            <FocusController
              focusPos={telemetry.focus_pos}
              nightMode={nightMode}
              onFocusNudge={handleFocusNudge}
              onZeroFocus={handleZeroFocus}
            />
          </div>

          {/* Column 2: Mount Telemetry & GoTo Catalog */}
          <div className="space-y-4">
            <TelemetryCard
              telemetry={telemetry}
              nightMode={nightMode}
              onToggleTracking={handleToggleTracking}
              onUnwindCable={handleUnwindCable}
            />
            <QuickCatalog
              nightMode={nightMode}
              onSlewToTarget={handleSlewToTarget}
            />
          </div>

          {/* Column 3: D-Pad Controls & Activity Console */}
          <div className="space-y-4">
            <DPadControls
              nightMode={nightMode}
              onJog={handleJog}
              onStop={handleEmergencyStop}
              onSync={handleSync}
              onHome={handleHome}
              onPark={handlePark}
            />
            <ConsoleLog
              logs={logs}
              nightMode={nightMode}
              onClear={() => setLogs([])}
            />
          </div>

        </div>
      </main>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        config={config}
        nightMode={nightMode}
        onClose={() => setIsSettingsOpen(false)}
        onSave={handleSaveConfig}
      />
    </div>
  );
}
