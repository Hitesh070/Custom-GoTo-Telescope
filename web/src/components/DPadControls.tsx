"use client";

import React, { useState } from "react";
import { ArrowUp, ArrowDown, ArrowLeft, ArrowRight, ShieldAlert, Crosshair, Home, Anchor } from "lucide-react";

interface DPadControlsProps {
  nightMode: boolean;
  onJog: (axis: "az" | "alt", dir: 1 | -1, deg: number) => void;
  onStop: () => void;
  onSync: () => void;
  onHome: (axis: "az" | "alt") => void;
  onPark: () => void;
}

export const DPadControls: React.FC<DPadControlsProps> = ({
  nightMode,
  onJog,
  onStop,
  onSync,
  onHome,
  onPark,
}) => {
  const [jogSpeed, setJogSpeed] = useState<number>(0.50); // Default medium

  const speeds = [
    { label: "Fine (0.05°)", val: 0.05 },
    { label: "Medium (0.50°)", val: 0.50 },
    { label: "Coarse (3.00°)", val: 3.00 },
  ];

  const cardBg = nightMode ? "bg-[#080101] border-[#2E0505]" : "bg-[#161B22] border-[#30363D]";
  const btnDpad = nightMode
    ? "bg-[#1A0303] hover:bg-[#300606] active:bg-[#4D0A0A] border-[#4D0A0A] text-[#FF4D4D]"
    : "bg-[#21262D] hover:bg-[#30363D] active:bg-[#161B22] border-[#30363D] text-gray-200";

  return (
    <div className={`p-4 rounded-lg border ${cardBg} shadow-sm space-y-4`}>
      <div className="border-b pb-2 border-inherit flex justify-between items-center">
        <h3 className={`text-xs font-bold uppercase tracking-wider ${nightMode ? "text-[#FF6666]" : "text-gray-200"}`}>
          Manual Motion Controls
        </h3>
        <span className={`text-[11px] font-mono ${nightMode ? "text-[#AA2222]" : "text-gray-400"}`}>
          Eyepiece Nudge
        </span>
      </div>

      {/* D-Pad 3x3 Grid */}
      <div className="flex flex-col items-center justify-center pt-2">
        <div className="grid grid-cols-3 gap-2 w-56 sm:w-64">
          {/* Top Row: empty, ALT +, empty */}
          <div />
          <button
            onClick={() => onJog("alt", 1, jogSpeed)}
            className={`h-12 flex flex-col items-center justify-center rounded border font-mono font-bold text-xs shadow-sm transition-all active:scale-95 ${btnDpad}`}
            title="Altitude Up"
          >
            <ArrowUp className="w-5 h-5 mb-0.5" />
            <span>ALT +</span>
          </button>
          <div />

          {/* Middle Row: AZ -, STOP, AZ + */}
          <button
            onClick={() => onJog("az", -1, jogSpeed)}
            className={`h-12 flex flex-col items-center justify-center rounded border font-mono font-bold text-xs shadow-sm transition-all active:scale-95 ${btnDpad}`}
            title="Azimuth West / Decrement"
          >
            <ArrowLeft className="w-5 h-5 mb-0.5" />
            <span>AZ -</span>
          </button>

          <button
            onClick={onStop}
            className="h-12 flex flex-col items-center justify-center rounded border border-[#B31D1D] bg-[#8A1B1B] hover:bg-[#B31D1D] active:scale-95 text-white font-mono font-bold text-xs shadow-md transition-all"
            title="Instant Slew Abort"
          >
            <ShieldAlert className="w-5 h-5 mb-0.5 text-white" />
            <span>STOP</span>
          </button>

          <button
            onClick={() => onJog("az", 1, jogSpeed)}
            className={`h-12 flex flex-col items-center justify-center rounded border font-mono font-bold text-xs shadow-sm transition-all active:scale-95 ${btnDpad}`}
            title="Azimuth East / Increment"
          >
            <ArrowRight className="w-5 h-5 mb-0.5" />
            <span>AZ +</span>
          </button>

          {/* Bottom Row: empty, ALT -, empty */}
          <div />
          <button
            onClick={() => onJog("alt", -1, jogSpeed)}
            className={`h-12 flex flex-col items-center justify-center rounded border font-mono font-bold text-xs shadow-sm transition-all active:scale-95 ${btnDpad}`}
            title="Altitude Down"
          >
            <ArrowDown className="w-5 h-5 mb-0.5" />
            <span>ALT -</span>
          </button>
          <div />
        </div>
      </div>

      {/* Speed Selector */}
      <div className="pt-2">
        <div className={`text-[10px] font-mono uppercase mb-1.5 ${nightMode ? "text-[#AA2222]" : "text-gray-400"}`}>
          Jog Step Increment
        </div>
        <div className="grid grid-cols-3 gap-1.5 font-mono">
          {speeds.map((s) => (
            <button
              key={s.val}
              onClick={() => setJogSpeed(s.val)}
              className={`py-1.5 px-2 text-xs rounded border transition-all ${
                jogSpeed === s.val
                  ? (nightMode ? "bg-[#5C0B0B] border-[#991414] text-[#FFAAAA] font-bold" : "bg-[#1F6FEB] border-[#388BFD] text-white font-bold")
                  : (nightMode ? "bg-[#100202] border-[#2E0505] text-[#AA2222] hover:text-[#FF4D4D]" : "bg-[#0D1117] border-[#30363D] text-gray-300 hover:bg-[#21262D]")
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Alignment Actions Strip */}
      <div className="pt-2 border-t border-inherit space-y-2">
        <div className={`text-[10px] font-mono uppercase ${nightMode ? "text-[#AA2222]" : "text-gray-400"}`}>
          Mount Alignment & Homing
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs font-mono">
          <button
            onClick={onSync}
            className={`flex items-center justify-center gap-1.5 py-1.5 px-2 rounded border transition-colors ${
              nightMode ? "bg-[#1A0303] border-[#4D0A0A] text-[#FF4D4D] hover:bg-[#2E0505]" : "bg-[#21262D] border-[#30363D] text-gray-200 hover:bg-[#30363D]"
            }`}
          >
            <Crosshair className="w-3.5 h-3.5" />
            <span>Sync Target</span>
          </button>

          <button
            onClick={onPark}
            className={`flex items-center justify-center gap-1.5 py-1.5 px-2 rounded border transition-colors ${
              nightMode ? "bg-[#1A0303] border-[#4D0A0A] text-[#FF4D4D] hover:bg-[#2E0505]" : "bg-[#21262D] border-[#30363D] text-gray-200 hover:bg-[#30363D]"
            }`}
          >
            <Anchor className="w-3.5 h-3.5" />
            <span>Park (0, 0)</span>
          </button>

          <button
            onClick={() => onHome("alt")}
            className={`flex items-center justify-center gap-1.5 py-1.5 px-2 rounded border transition-colors ${
              nightMode ? "bg-[#100202] border-[#2E0505] text-[#AA2222] hover:text-[#FF4D4D]" : "bg-[#0D1117] border-[#30363D] text-gray-400 hover:text-white"
            }`}
          >
            <Home className="w-3.5 h-3.5" />
            <span>Home Alt</span>
          </button>

          <button
            onClick={() => onHome("az")}
            className={`flex items-center justify-center gap-1.5 py-1.5 px-2 rounded border transition-colors ${
              nightMode ? "bg-[#100202] border-[#2E0505] text-[#AA2222] hover:text-[#FF4D4D]" : "bg-[#0D1117] border-[#30363D] text-gray-400 hover:text-white"
            }`}
          >
            <Home className="w-3.5 h-3.5" />
            <span>Home Az</span>
          </button>
        </div>
      </div>
    </div>
  );
};
