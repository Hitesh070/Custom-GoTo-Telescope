"use client";

import React, { useState } from "react";
import { Sliders, ChevronsLeft, ChevronLeft, ChevronRight, ChevronsRight, RotateCcw } from "lucide-react";

interface FocusControllerProps {
  focusPos: number;
  nightMode: boolean;
  onFocusNudge: (steps: number) => void;
  onZeroFocus: () => void;
}

export const FocusController: React.FC<FocusControllerProps> = ({
  focusPos,
  nightMode,
  onFocusNudge,
  onZeroFocus,
}) => {
  const [customSteps, setCustomSteps] = useState<string>("10");

  const cardBg = nightMode ? "bg-[#080101] border-[#2E0505]" : "bg-[#161B22] border-[#30363D]";
  const btnStep = nightMode
    ? "bg-[#1A0303] hover:bg-[#300606] active:bg-[#4D0A0A] border-[#4D0A0A] text-[#FF4D4D]"
    : "bg-[#21262D] hover:bg-[#30363D] active:bg-[#161B22] border-[#30363D] text-gray-200";

  const handleCustomGo = () => {
    const val = parseInt(customSteps, 10);
    if (!isNaN(val) && val !== 0) {
      onFocusNudge(val);
    }
  };

  return (
    <div className={`p-4 rounded-lg border ${cardBg} shadow-sm space-y-3`}>
      <div className="border-b pb-2 border-inherit flex justify-between items-center">
        <div className="flex items-center gap-2">
          <Sliders className={`w-4 h-4 ${nightMode ? "text-[#FF4D4D]" : "text-[#58A6FF]"}`} />
          <h3 className={`text-xs font-bold uppercase tracking-wider ${nightMode ? "text-[#FF6666]" : "text-gray-200"}`}>
            Motorized Focus Controller
          </h3>
        </div>
        <span className={`text-[11px] font-mono font-bold ${nightMode ? "text-[#FFAAAA]" : "text-emerald-400"}`}>
          Position: {focusPos} steps
        </span>
      </div>

      {/* Preset Stepping Buttons */}
      <div className="grid grid-cols-4 gap-1.5 font-mono text-xs">
        <button
          onClick={() => onFocusNudge(-50)}
          className={`py-2 flex flex-col items-center justify-center rounded border transition-all active:scale-95 ${btnStep}`}
          title="Coarse Inward (-50 steps)"
        >
          <ChevronsLeft className="w-4 h-4" />
          <span className="text-[10px] mt-0.5">&lt;&lt; 50</span>
        </button>

        <button
          onClick={() => onFocusNudge(-5)}
          className={`py-2 flex flex-col items-center justify-center rounded border transition-all active:scale-95 ${btnStep}`}
          title="Fine Inward (-5 steps)"
        >
          <ChevronLeft className="w-4 h-4" />
          <span className="text-[10px] mt-0.5">&lt; 5</span>
        </button>

        <button
          onClick={() => onFocusNudge(5)}
          className={`py-2 flex flex-col items-center justify-center rounded border transition-all active:scale-95 ${btnStep}`}
          title="Fine Outward (+5 steps)"
        >
          <ChevronRight className="w-4 h-4" />
          <span className="text-[10px] mt-0.5">5 &gt;</span>
        </button>

        <button
          onClick={() => onFocusNudge(50)}
          className={`py-2 flex flex-col items-center justify-center rounded border transition-all active:scale-95 ${btnStep}`}
          title="Coarse Outward (+50 steps)"
        >
          <ChevronsRight className="w-4 h-4" />
          <span className="text-[10px] mt-0.5">50 &gt;&gt;</span>
        </button>
      </div>

      {/* Custom Nudge & Zero Focus */}
      <div className="flex items-center gap-2 pt-1 font-mono text-xs">
        <input
          type="number"
          value={customSteps}
          onChange={(e) => setCustomSteps(e.target.value)}
          placeholder="Steps"
          className={`w-24 p-1.5 rounded border text-center ${
            nightMode ? "bg-[#050000] border-[#4D0A0A] text-[#FF4D4D]" : "bg-[#0D1117] border-[#30363D] text-white"
          }`}
        />
        <button
          onClick={handleCustomGo}
          className={`flex-1 py-1.5 rounded border font-bold transition-all ${
            nightMode ? "bg-[#5C0B0B] border-[#991414] text-[#FFAAAA]" : "bg-[#1F6FEB] border-[#388BFD] text-white"
          }`}
        >
          Nudge
        </button>
        <button
          onClick={onZeroFocus}
          className={`px-3 py-1.5 rounded border flex items-center gap-1 transition-colors ${
            nightMode ? "bg-[#1A0303] border-[#4D0A0A] text-[#AA2222] hover:text-[#FF4D4D]" : "bg-[#21262D] border-[#30363D] text-gray-300 hover:text-white"
          }`}
          title="Reset Focus Step Counter to Zero"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Zero</span>
        </button>
      </div>
    </div>
  );
};
