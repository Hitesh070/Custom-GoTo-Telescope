"use client";

import React from "react";
import { TelescopeTelemetry, TrackingRate } from "@/types/telescope";
import { formatDegMinSec, formatRa, formatDec } from "@/lib/catalog";
import { RotateCcw, Compass, SunMedium } from "lucide-react";

interface TelemetryCardProps {
  telemetry: TelescopeTelemetry;
  nightMode: boolean;
  onToggleTracking: (rate?: TrackingRate) => void;
  onUnwindCable: () => void;
}

export const TelemetryCard: React.FC<TelemetryCardProps> = ({
  telemetry,
  nightMode,
  onToggleTracking,
  onUnwindCable,
}) => {
  const getCableBadgeClass = () => {
    switch (telemetry.cable_status) {
      case "STRAIN":
        return nightMode ? "text-[#FF2222] font-bold" : "text-red-500 font-bold";
      case "CAUTION":
        return nightMode ? "text-[#FFCC66] font-bold" : "text-amber-400 font-bold";
      case "OK":
      default:
        return nightMode ? "text-[#88C0FF] font-semibold" : "text-blue-400 font-semibold";
    }
  };

  const cardBg = nightMode ? "bg-[#080101] border-[#2E0505]" : "bg-[#161B22] border-[#30363D]";
  const keyText = nightMode ? "text-[#AA2222]" : "text-[#8B949E]";
  const valText = nightMode ? "text-[#FF4D4D]" : "text-[#58A6FF]";
  const heroValText = nightMode ? "text-[#FF3333]" : "text-white";

  return (
    <div className={`p-4 rounded-lg border ${cardBg} shadow-sm space-y-4`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-2 border-inherit">
        <div className="flex items-center gap-2">
          <Compass className={`w-4 h-4 ${nightMode ? "text-[#FF4D4D]" : "text-[#58A6FF]"}`} />
          <h2 className={`text-xs font-bold uppercase tracking-wider ${nightMode ? "text-[#FF6666]" : "text-gray-200"}`}>
            Telescope Mount Telemetry
          </h2>
        </div>
        <span className={`text-[11px] font-mono ${nightMode ? "text-[#881B1B]" : "text-gray-400"}`}>
          Rate: {telemetry.data_rate_hz} Hz
        </span>
      </div>

      {/* Main Coordinate Grid */}
      <div className="grid grid-cols-2 gap-3 font-mono">
        {/* Azimuth / Altitude (Current Apparent) */}
        <div className={`p-2.5 rounded border ${nightMode ? "bg-[#100202] border-[#2E0505]" : "bg-[#0D1117] border-[#30363D]"}`}>
          <div className={`text-[10px] uppercase font-bold tracking-wider ${keyText}`}>Azimuth / Altitude</div>
          <div className={`text-base sm:text-lg font-bold tracking-tight ${heroValText}`}>
            {formatDegMinSec(telemetry.az_deg)}
          </div>
          <div className={`text-sm sm:text-base font-semibold ${valText}`}>
            {formatDegMinSec(telemetry.alt_deg)} (app)
          </div>
        </div>

        {/* Equatorial J2000 (RA / Dec) */}
        <div className={`p-2.5 rounded border ${nightMode ? "bg-[#100202] border-[#2E0505]" : "bg-[#0D1117] border-[#30363D]"}`}>
          <div className={`text-[10px] uppercase font-bold tracking-wider ${keyText}`}>RA / Dec (J2000)</div>
          <div className={`text-sm sm:text-base font-bold ${heroValText}`}>
            {formatRa(telemetry.ra_j2000_hours)}
          </div>
          <div className={`text-sm sm:text-base font-semibold ${valText}`}>
            {formatDec(telemetry.dec_j2000_deg)}
          </div>
        </div>
      </div>

      {/* Target & Solar Separation */}
      <div className={`p-3 rounded border text-xs space-y-1.5 ${nightMode ? "bg-[#0E0101] border-[#240404]" : "bg-[#0D1117] border-[#30363D]"}`}>
        <div className="flex justify-between items-center">
          <span className={keyText}>Current Tracked Target:</span>
          <span className={`font-bold font-mono ${nightMode ? "text-[#FFAAAA]" : "text-emerald-400"}`}>
            {telemetry.target_name || "None (Awaiting Slew)"}
          </span>
        </div>
        <div className="flex justify-between items-center text-[11px]">
          <span className={keyText}>Sun Separation:</span>
          <span className={`font-mono font-bold flex items-center gap-1 ${
            telemetry.sun_sep_deg < 15.0
              ? (nightMode ? "text-[#FF2222]" : "text-red-400")
              : (nightMode ? "text-[#FFAAAA]" : "text-emerald-400")
          }`}>
            <SunMedium className="w-3 h-3 inline" />
            {telemetry.sun_sep_deg.toFixed(1)}° {telemetry.sun_sep_deg < 15.0 ? "[CAUTION < 15°]" : ""}
          </span>
        </div>
      </div>

      {/* Cable Wrap & Tracking Controls */}
      <div className="space-y-3 pt-1">
        {/* Cable turns */}
        <div className="flex items-center justify-between text-xs font-mono">
          <div>
            <span className={keyText}>Cable: </span>
            <span className={getCableBadgeClass()}>
              {telemetry.cable_turns >= 0 ? "+" : ""}{telemetry.cable_turns.toFixed(2)} turns [{telemetry.cable_status}]
            </span>
          </div>
          <button
            onClick={onUnwindCable}
            className={`flex items-center gap-1 px-2.5 py-1 text-[11px] rounded border transition-colors ${
              nightMode
                ? "bg-[#1A0303] border-[#4D0A0A] text-[#FFAAAA] hover:bg-[#2E0505]"
                : "bg-[#21262D] border-[#30363D] text-gray-200 hover:bg-[#30363D]"
            }`}
            title="Unwind mount to North 0°"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Unwind (0°)</span>
          </button>
        </div>

        {/* Tracking Rate Toggle Strip */}
        <div className="flex flex-wrap items-center justify-between gap-1.5 pt-1">
          <button
            onClick={() => onToggleTracking()}
            className={`flex-1 px-3 py-1.5 text-xs font-mono font-bold rounded border transition-all ${
              telemetry.tracking
                ? (nightMode ? "bg-[#5C0B0B] border-[#991414] text-[#FFAAAA]" : "bg-[#1E7E34] border-[#28A745] text-white")
                : (nightMode ? "bg-[#1A0303] border-[#4D0A0A] text-[#FF4D4D] hover:bg-[#2E0505]" : "bg-[#21262D] border-[#30363D] text-gray-300 hover:bg-[#30363D]")
            }`}
          >
            Tracking: {telemetry.tracking ? "ON" : "OFF"}
          </button>

          {(["Sidereal", "King", "Lunar", "Solar"] as TrackingRate[]).map((rate) => (
            <button
              key={rate}
              onClick={() => onToggleTracking(rate)}
              className={`px-2 py-1 text-[11px] font-mono rounded border transition-colors ${
                telemetry.tracking_rate === rate
                  ? (nightMode ? "bg-[#4D0E18] border-[#991414] text-[#FFAAAA] font-bold" : "bg-[#1F6FEB] border-[#388BFD] text-white font-bold")
                  : (nightMode ? "bg-[#0E0101] border-[#240404] text-[#AA2222] hover:text-[#FF6666]" : "bg-[#0D1117] border-[#30363D] text-gray-400 hover:text-white")
              }`}
            >
              {rate}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
