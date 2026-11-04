"use client";

import React, { useRef, useEffect } from "react";
import { MountLogMessage } from "@/types/telescope";
import { Terminal, Trash2 } from "lucide-react";

interface ConsoleLogProps {
  logs: MountLogMessage[];
  nightMode: boolean;
  onClear: () => void;
}

export const ConsoleLog: React.FC<ConsoleLogProps> = ({ logs, nightMode, onClear }) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const cardBg = nightMode ? "bg-[#080101] border-[#2E0505]" : "bg-[#161B22] border-[#30363D]";

  const getLevelColor = (level: string) => {
    switch (level) {
      case "ERROR":
        return nightMode ? "text-[#FF2222]" : "text-red-400";
      case "WARNING":
        return nightMode ? "text-[#FFCC66]" : "text-amber-400";
      case "COMMAND":
        return nightMode ? "text-[#FFAAAA]" : "text-[#58A6FF]";
      case "INFO":
      default:
        return nightMode ? "text-[#FF4D4D]" : "text-[#8CD68C]";
    }
  };

  return (
    <div className={`p-4 rounded-lg border ${cardBg} shadow-sm space-y-2`}>
      <div className="flex justify-between items-center border-b pb-2 border-inherit">
        <div className="flex items-center gap-2">
          <Terminal className={`w-4 h-4 ${nightMode ? "text-[#FF4D4D]" : "text-[#58A6FF]"}`} />
          <h3 className={`text-xs font-bold uppercase tracking-wider ${nightMode ? "text-[#FF6666]" : "text-gray-200"}`}>
            Activity Console &amp; Hardware Logs
          </h3>
        </div>
        <button
          onClick={onClear}
          className={`flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded border transition-colors ${
            nightMode ? "bg-[#1A0303] border-[#4D0A0A] text-[#AA2222] hover:text-[#FF6666]" : "bg-[#21262D] border-[#30363D] text-gray-400 hover:text-white"
          }`}
          title="Clear Console"
        >
          <Trash2 className="w-3 h-3" />
          <span>Clear</span>
        </button>
      </div>

      <div
        ref={scrollRef}
        className={`h-32 sm:h-36 overflow-y-auto p-2.5 rounded border font-mono text-[11px] space-y-1 select-text ${
          nightMode ? "bg-[#040000] border-[#240404]" : "bg-[#0D1117] border-[#30363D]"
        }`}
      >
        {logs.length === 0 ? (
          <div className={nightMode ? "text-[#4D0D0D]" : "text-gray-600"}>
            Console ready. Hardware commands and telemetry will appear here...
          </div>
        ) : (
          logs.map((log) => (
            <div key={log.id} className="leading-tight">
              <span className={nightMode ? "text-[#661111]" : "text-gray-500"}>
                [{log.timestamp}]
              </span>{" "}
              <span className={`font-bold ${getLevelColor(log.level)}`}>
                [{log.level}]
              </span>{" "}
              <span className={nightMode ? "text-[#CC3333]" : "text-gray-300"}>
                {log.text}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
