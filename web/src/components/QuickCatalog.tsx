"use client";

import React, { useState } from "react";
import { CURATED_CATALOG } from "@/lib/catalog";
import { CatalogTarget } from "@/types/telescope";
import { Telescope, Navigation, Sparkles, AlertTriangle } from "lucide-react";

interface QuickCatalogProps {
  nightMode: boolean;
  onSlewToTarget: (name: string, az: number, alt: number) => void;
}

export const QuickCatalog: React.FC<QuickCatalogProps> = ({ nightMode, onSlewToTarget }) => {
  const [filter, setFilter] = useState<string>("All");
  const [customAz, setCustomAz] = useState<string>("180.0");
  const [customAlt, setCustomAlt] = useState<string>("45.0");
  const [customName, setCustomName] = useState<string>("Custom Point");

  const categories = ["All", "Solar System", "Deep Sky", "Stars", "Manual Coords"];

  const filteredTargets = CURATED_CATALOG.filter((t) => {
    if (filter === "Solar System") return t.type === "Planet" || t.type === "Moon";
    if (filter === "Deep Sky") return t.type === "Nebula" || t.type === "Galaxy" || t.type === "Cluster";
    if (filter === "Stars") return t.type === "Double Star";
    return true;
  });

  const cardBg = nightMode ? "bg-[#080101] border-[#2E0505]" : "bg-[#161B22] border-[#30363D]";
  const itemBg = nightMode ? "bg-[#100202] border-[#2E0505]" : "bg-[#0D1117] border-[#30363D]";

  const handleManualSlew = (e: React.FormEvent) => {
    e.preventDefault();
    const az = parseFloat(customAz);
    const alt = parseFloat(customAlt);
    if (!isNaN(az) && !isNaN(alt)) {
      onSlewToTarget(customName || "Manual Slew", az, Math.max(0, Math.min(85, alt)));
    }
  };

  return (
    <div className={`p-4 rounded-lg border ${cardBg} shadow-sm space-y-4`}>
      <div className="border-b pb-2 border-inherit flex justify-between items-center">
        <div className="flex items-center gap-2">
          <Telescope className={`w-4 h-4 ${nightMode ? "text-[#FF4D4D]" : "text-[#58A6FF]"}`} />
          <h3 className={`text-xs font-bold uppercase tracking-wider ${nightMode ? "text-[#FF6666]" : "text-gray-200"}`}>
            Tonight&apos;s Best &amp; GoTo Catalog
          </h3>
        </div>
        <span className={`text-[11px] font-mono ${nightMode ? "text-[#AA2222]" : "text-gray-400"}`}>
          Curated Targets
        </span>
      </div>

      {/* Category Pills */}
      <div className="flex flex-wrap gap-1.5 font-mono text-xs">
        {categories.map((c) => (
          <button
            key={c}
            onClick={() => setFilter(c)}
            className={`py-1 px-2.5 rounded border transition-colors ${
              filter === c
                ? (nightMode ? "bg-[#5C0B0B] border-[#991414] text-[#FFAAAA] font-bold" : "bg-[#1F6FEB] border-[#388BFD] text-white font-bold")
                : (nightMode ? "bg-[#0E0101] border-[#240404] text-[#AA2222] hover:text-[#FF4D4D]" : "bg-[#0D1117] border-[#30363D] text-gray-400 hover:text-white")
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      {/* Manual Coordinates Form */}
      {filter === "Manual Coords" ? (
        <form onSubmit={handleManualSlew} className="space-y-3 pt-1 text-xs font-mono">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className={`block mb-1 ${nightMode ? "text-[#AA2222]" : "text-gray-400"}`}>Azimuth (0° - 360°)</label>
              <input
                type="number"
                step="0.1"
                min="0"
                max="360"
                value={customAz}
                onChange={(e) => setCustomAz(e.target.value)}
                className={`w-full p-2 rounded border ${
                  nightMode ? "bg-[#050000] border-[#4D0A0A] text-[#FF4D4D]" : "bg-[#0D1117] border-[#30363D] text-white"
                }`}
              />
            </div>
            <div>
              <label className={`block mb-1 ${nightMode ? "text-[#AA2222]" : "text-gray-400"}`}>Altitude (0° - 85°)</label>
              <input
                type="number"
                step="0.1"
                min="0"
                max="85"
                value={customAlt}
                onChange={(e) => setCustomAlt(e.target.value)}
                className={`w-full p-2 rounded border ${
                  nightMode ? "bg-[#050000] border-[#4D0A0A] text-[#FF4D4D]" : "bg-[#0D1117] border-[#30363D] text-white"
                }`}
              />
            </div>
          </div>
          <div>
            <label className={`block mb-1 ${nightMode ? "text-[#AA2222]" : "text-gray-400"}`}>Target Label</label>
            <input
              type="text"
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              className={`w-full p-2 rounded border ${
                nightMode ? "bg-[#050000] border-[#4D0A0A] text-[#FF4D4D]" : "bg-[#0D1117] border-[#30363D] text-white"
              }`}
            />
          </div>
          <button
            type="submit"
            className={`w-full py-2 rounded border font-bold flex items-center justify-center gap-2 transition-all active:scale-98 ${
              nightMode
                ? "bg-[#5C0B0B] hover:bg-[#7A1212] border-[#991414] text-[#FFAAAA]"
                : "bg-[#238636] hover:bg-[#2EA043] border-[#2EA043] text-white"
            }`}
          >
            <Navigation className="w-4 h-4" />
            <span>Slew GoTo Coordinates</span>
          </button>
        </form>
      ) : (
        /* Target Cards List */
        <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
          {filteredTargets.map((t) => {
            // Simulated visible coordinates for preview slewing
            const simAz = (t.ra_hours * 15 + 45) % 360;
            const simAlt = Math.max(15, Math.min(80, 50 + t.dec_deg * 0.4));

            return (
              <div
                key={t.id}
                className={`p-3 rounded border transition-colors flex items-center justify-between gap-2 ${itemBg}`}
              >
                <div className="space-y-0.5 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`font-mono font-bold text-xs ${nightMode ? "text-[#FF4D4D]" : "text-white"}`}>
                      {t.name}
                    </span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono ${
                      nightMode ? "bg-[#1A0303] border-[#380808] text-[#AA2222]" : "bg-[#161B22] border-[#30363D] text-gray-400"
                    }`}>
                      {t.type}
                    </span>
                    <span className={`text-[10px] font-mono ${nightMode ? "text-[#881B1B]" : "text-gray-400"}`}>
                      Mag: {t.mag}
                    </span>
                  </div>
                  <p className={`text-[11px] truncate ${nightMode ? "text-[#881B1B]" : "text-gray-400"}`}>
                    {t.desc}
                  </p>
                </div>

                <button
                  onClick={() => onSlewToTarget(t.name, simAz, simAlt)}
                  className={`shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-bold rounded border transition-all active:scale-95 ${
                    nightMode
                      ? "bg-[#5C0B0B] hover:bg-[#7A1212] border-[#991414] text-[#FFAAAA]"
                      : "bg-[#238636] hover:bg-[#2EA043] border-[#2EA043] text-white"
                  }`}
                  title={`GoTo ${t.name}`}
                >
                  <Navigation className="w-3.5 h-3.5" />
                  <span>GoTo</span>
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
