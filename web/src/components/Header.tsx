"use client";

import React from "react";
import { TelescopeTelemetry, SlewState } from "@/types/telescope";
import { ShieldAlert, Moon, Sun, Settings as SettingsIcon } from "lucide-react";

interface HeaderProps {
  telemetry: TelescopeTelemetry;
  nightMode: boolean;
  onToggleNightMode: () => void;
  onEmergencyStop: () => void;
  onOpenSettings: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  telemetry,
  nightMode,
  onToggleNightMode,
  onEmergencyStop,
  onOpenSettings,
}) => {
  const isSim = telemetry.simulated;
  const isConn = telemetry.connected;

  const getHardwareBadge = () => {
    if (isConn) {
      if (isSim) {
        return {
          text: "ARDUINO: SIMULATED",
          bg: nightMode ? "bg-[#4A1020] text-[#FFAAAA] border-[#801830]" : "bg-[#1E4472] text-white border-[#2B6496]",
        };
      }
      return {
        text: "ARDUINO: CONNECTED",
        bg: nightMode ? "bg-[#5C0B0B] text-[#FFAAAA] border-[#991414]" : "bg-[#1E7E34] text-white border-[#28A745]",
      };
    }
    return {
      text: "ARDUINO: DISCONNECTED",
      bg: nightMode ? "bg-[#1A0303] text-[#AA2222] border-[#4D0A0A]" : "bg-[#8A1B1B] text-white border-[#B31D1D]",
    };
  };

  const getSlewBadge = (state: SlewState) => {
    switch (state) {
      case "SLEWING":
        return nightMode ? "bg-[#7A1515] text-[#FFEEEE] animate-pulse border-[#B32424]" : "bg-[#B45309] text-white animate-pulse border-[#D97706]";
      case "TRACKING":
        return nightMode ? "bg-[#4D0E18] text-[#FFAAAA] border-[#801830]" : "bg-[#1E7E34] text-white border-[#28A745]";
      case "PARKED":
        return nightMode ? "bg-[#1A0303] text-[#AA2222] border-[#4D0A0A]" : "bg-[#374151] text-gray-200 border-[#4B5563]";
      case "IDLE":
      default:
        return nightMode ? "bg-[#140202] text-[#881B1B] border-[#2E0505]" : "bg-[#1F2937] text-gray-300 border-[#374151]";
    }
  };

  const hw = getHardwareBadge();

  return (
    <header className={`w-full border-b transition-colors duration-200 ${
      nightMode ? "bg-[#050000] border-[#2E0505]" : "bg-[#0D1117] border-[#30363D]"
    }`}>
      <div className="max-w-7xl mx-auto px-4 py-2.5 flex flex-wrap items-center justify-between gap-2.5">
        
        {/* Brand & Hardware Status */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${isConn ? (nightMode ? "bg-red-500 animate-ping" : "bg-emerald-400 animate-ping") : "bg-red-700"}`} />
            <h1 className={`text-base font-bold tracking-wider uppercase ${nightMode ? "text-[#FF4D4D]" : "text-white"}`}>
              Custom GoTo
            </h1>
          </div>

          <span className={`px-2.5 py-1 text-xs font-mono font-bold rounded border ${hw.bg}`}>
            {hw.text}
          </span>

          <span className={`px-2.5 py-1 text-xs font-mono font-bold rounded border ${getSlewBadge(telemetry.slew_state)}`}>
            {telemetry.slew_state}
          </span>
        </div>

        {/* Global Controls & Emergency Stop */}
        <div className="flex items-center gap-2">
          {/* Emergency Stop Button */}
          <button
            onClick={onEmergencyStop}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-[#8A1B1B] hover:bg-[#B31D1D] active:scale-95 text-white font-mono font-bold text-xs rounded border border-[#B31D1D] shadow-md transition-transform"
            title="Emergency Abort All Motors"
          >
            <ShieldAlert className="w-4 h-4 text-white" />
            <span>STOP</span>
          </button>

          {/* Night Vision Toggle */}
          <button
            onClick={onToggleNightMode}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded border transition-colors ${
              nightMode
                ? "bg-[#5C0B0B] border-[#991414] text-[#FFAAAA] hover:bg-[#7A1212]"
                : "bg-[#21262D] border-[#30363D] text-[#C9D1D9] hover:bg-[#30363D]"
            }`}
            title="Toggle Red Night-Vision Mode"
          >
            {nightMode ? <Moon className="w-3.5 h-3.5 text-[#FFAAAA]" /> : <Sun className="w-3.5 h-3.5 text-amber-400" />}
            <span>{nightMode ? "Night: ON" : "Night: OFF"}</span>
          </button>

          {/* Settings Button */}
          <button
            onClick={onOpenSettings}
            className={`p-1.5 text-xs rounded border transition-colors ${
              nightMode
                ? "bg-[#1A0303] border-[#4D0A0A] text-[#FF6666] hover:bg-[#2E0505]"
                : "bg-[#21262D] border-[#30363D] text-[#C9D1D9] hover:bg-[#30363D]"
            }`}
            title="Connection Settings"
          >
            <SettingsIcon className="w-4 h-4" />
          </button>
        </div>

      </div>
    </header>
  );
};
