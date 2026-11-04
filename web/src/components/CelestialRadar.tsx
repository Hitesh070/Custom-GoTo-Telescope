"use client";

import React from "react";
import { TelescopeTelemetry } from "@/types/telescope";

interface CelestialRadarProps {
  telemetry: TelescopeTelemetry;
  nightMode: boolean;
}

export const CelestialRadar: React.FC<CelestialRadarProps> = ({ telemetry, nightMode }) => {
  const size = 320;
  const center = size / 2;
  const radius = size / 2 - 25;

  // Converts Alt/Az to Cartesian SVG (x, y) coordinates
  // Zenith (Alt 90) is at center, Horizon (Alt 0) is at outer radius
  // Azimuth 0 is North (top), 90 is East (right), 180 is South (bottom), 270 is West (left)
  const altAzToXY = (azDeg: number, altDeg: number) => {
    const clampedAlt = Math.max(0, Math.min(90, altDeg));
    const r = radius * ((90 - clampedAlt) / 90.0);
    const radAz = (azDeg - 90) * (Math.PI / 180);
    return {
      x: center + r * Math.cos(radAz),
      y: center + r * Math.sin(radAz),
    };
  };

  const mountPos = altAzToXY(telemetry.az_deg, telemetry.alt_deg);
  const targetPos = telemetry.target_az_deg !== null && telemetry.target_alt_deg !== null
    ? altAzToXY(telemetry.target_az_deg, telemetry.target_alt_deg)
    : null;

  const strokeColor = nightMode ? "#2E0505" : "#30363D";
  const labelColor = nightMode ? "#881B1B" : "#8B949E";
  const crosshairColor = nightMode ? "#200303" : "#21262D";
  const reticleColor = nightMode ? "#FF3333" : "#58A6FF";
  const targetReticleColor = nightMode ? "#FFAAAA" : "#2EA043";

  return (
    <div className={`p-4 rounded-lg border flex flex-col items-center justify-center ${
      nightMode ? "bg-[#080101] border-[#2E0505]" : "bg-[#161B22] border-[#30363D]"
    }`}>
      <div className="w-full flex justify-between items-center mb-2 border-b pb-1 border-inherit">
        <h3 className={`text-xs font-bold uppercase tracking-wider ${nightMode ? "text-[#FF6666]" : "text-gray-200"}`}>
          Celestial Sky Radar (Alt / Az)
        </h3>
        <span className={`text-[11px] font-mono ${nightMode ? "text-[#AA2222]" : "text-gray-400"}`}>
          Polar Projection
        </span>
      </div>

      <div className="relative">
        <svg width={size} height={size} className="select-none overflow-visible">
          {/* Background circular sky mask */}
          <circle cx={center} cy={center} r={radius} fill={nightMode ? "#040000" : "#0D1117"} stroke={strokeColor} strokeWidth="1.5" />

          {/* Concentric Altitude Rings */}
          {[15, 30, 45, 60, 75].map((alt) => {
            const r = radius * ((90 - alt) / 90.0);
            return (
              <circle
                key={alt}
                cx={center}
                cy={center}
                r={r}
                fill="none"
                stroke={strokeColor}
                strokeWidth="1"
                strokeDasharray="2,3"
              />
            );
          })}

          {/* Crosshairs: North-South & East-West */}
          <line x1={center} y1={center - radius} x2={center} y2={center + radius} stroke={crosshairColor} strokeWidth="1" />
          <line x1={center - radius} y1={center} x2={center + radius} y2={center} stroke={crosshairColor} strokeWidth="1" />

          {/* Cardinal Directions */}
          <text x={center} y={center - radius - 8} textAnchor="middle" className="text-[11px] font-mono font-bold" fill={labelColor}>N</text>
          <text x={center + radius + 10} y={center + 4} textAnchor="middle" className="text-[11px] font-mono font-bold" fill={labelColor}>E</text>
          <text x={center} y={center + radius + 16} textAnchor="middle" className="text-[11px] font-mono font-bold" fill={labelColor}>S</text>
          <text x={center - radius - 10} y={center + 4} textAnchor="middle" className="text-[11px] font-mono font-bold" fill={labelColor}>W</text>

          {/* Altitude labels (along North radial line) */}
          {[30, 60].map((alt) => {
            const r = radius * ((90 - alt) / 90.0);
            return (
              <text key={alt} x={center + 4} y={center - r + 3} className="text-[9px] font-mono" fill={labelColor}>
                {alt}°
              </text>
            );
          })}

          {/* Target Reticle (Dotted circle with center cross) */}
          {targetPos && (
            <g transform={`translate(${targetPos.x}, ${targetPos.y})`}>
              <circle r="9" fill="none" stroke={targetReticleColor} strokeWidth="1.5" strokeDasharray="3,2" />
              <line x1="-12" y1="0" x2="12" y2="0" stroke={targetReticleColor} strokeWidth="1" />
              <line x1="0" y1="-12" x2="0" y2="12" stroke={targetReticleColor} strokeWidth="1" />
              <text x="12" y="-6" className="text-[10px] font-mono font-bold" fill={targetReticleColor}>
                {telemetry.target_name || "Target"}
              </text>
            </g>
          )}

          {/* Active Telescope Mount Reticle (Solid double reticle) */}
          <g transform={`translate(${mountPos.x}, ${mountPos.y})`}>
            <circle r="7" fill="none" stroke={reticleColor} strokeWidth="2" />
            <circle r="2" fill={reticleColor} />
            <line x1="-11" y1="0" x2="11" y2="0" stroke={reticleColor} strokeWidth="1.5" />
            <line x1="0" y1="-11" x2="0" y2="11" stroke={reticleColor} strokeWidth="1.5" />
          </g>
        </svg>
      </div>

      <div className="w-full flex justify-between text-[11px] font-mono mt-2 pt-1 border-t border-inherit">
        <span className="flex items-center gap-1.5">
          <span className={`w-2.5 h-2.5 rounded-full inline-block border ${nightMode ? "border-[#FF3333] bg-[#5C0B0B]" : "border-[#58A6FF] bg-[#1F6FEB]"}`} />
          <span className={labelColor}>Mount Scope</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className={`w-2.5 h-2.5 rounded-full inline-block border border-dashed ${nightMode ? "border-[#FFAAAA]" : "border-emerald-400"}`} />
          <span className={labelColor}>Stellarium Target</span>
        </span>
      </div>
    </div>
  );
};
