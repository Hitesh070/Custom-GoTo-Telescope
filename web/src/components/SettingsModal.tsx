"use client";

import React, { useState } from "react";
import { ConnectionConfig } from "@/types/telescope";
import { X, Check, Server, Key, Sliders, Info } from "lucide-react";

interface SettingsModalProps {
  isOpen: boolean;
  config: ConnectionConfig;
  nightMode: boolean;
  onClose: () => void;
  onSave: (newConfig: ConnectionConfig) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  config,
  nightMode,
  onClose,
  onSave,
}) => {
  const [apiUrl, setApiUrl] = useState(config.apiUrl);
  const [authToken, setAuthToken] = useState(config.authToken);
  const [simulated, setSimulated] = useState(config.simulatedMode);
  const [refreshMs, setRefreshMs] = useState(config.refreshIntervalMs);

  if (!isOpen) return null;

  const handleSave = () => {
    onSave({
      apiUrl,
      authToken,
      simulatedMode: simulated,
      refreshIntervalMs: refreshMs,
    });
    onClose();
  };

  const cardBg = nightMode ? "bg-[#0A0101] border-[#4D0A0A] text-[#FF4D4D]" : "bg-[#161B22] border-[#30363D] text-gray-200";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xs">
      <div className={`w-full max-w-md p-5 rounded-lg border shadow-xl space-y-4 ${cardBg}`}>
        {/* Header */}
        <div className="flex justify-between items-center border-b pb-2 border-inherit">
          <div className="flex items-center gap-2">
            <Server className={`w-4 h-4 ${nightMode ? "text-[#FF4D4D]" : "text-[#58A6FF]"}`} />
            <h3 className={`text-sm font-bold uppercase tracking-wider ${nightMode ? "text-[#FF6666]" : "text-white"}`}>
              Connection &amp; Bridge Settings
            </h3>
          </div>
          <button
            onClick={onClose}
            className={`p-1 rounded hover:bg-white/10 transition-colors ${nightMode ? "text-[#AA2222]" : "text-gray-400"}`}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <div className="space-y-3.5 text-xs font-mono">
          {/* Simulated Mode Toggle */}
          <div className={`p-3 rounded border flex items-center justify-between ${
            nightMode ? "bg-[#140202] border-[#2E0505]" : "bg-[#0D1117] border-[#30363D]"
          }`}>
            <div>
              <div className="font-bold">Virtual Mount Simulator</div>
              <div className={`text-[11px] ${nightMode ? "text-[#881B1B]" : "text-gray-400"}`}>
                Run without physical telescope connected
              </div>
            </div>
            <button
              onClick={() => setSimulated(!simulated)}
              className={`px-3 py-1.5 rounded font-bold border transition-colors ${
                simulated
                  ? (nightMode ? "bg-[#5C0B0B] border-[#991414] text-[#FFAAAA]" : "bg-[#1E7E34] border-[#28A745] text-white")
                  : (nightMode ? "bg-[#1A0303] border-[#4D0A0A] text-[#AA2222]" : "bg-[#21262D] border-[#30363D] text-gray-400")
              }`}
            >
              {simulated ? "ENABLED" : "DISABLED"}
            </button>
          </div>

          {/* Bridge API URL */}
          <div className="space-y-1">
            <label className="flex items-center gap-1.5 font-bold">
              <Server className="w-3.5 h-3.5" />
              <span>Telescope Bridge URL / Endpoint</span>
            </label>
            <input
              type="text"
              value={apiUrl}
              disabled={simulated}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="http://localhost:8080 or https://telescope.yourdomain.com"
              className={`w-full p-2 rounded border transition-colors ${
                nightMode
                  ? "bg-[#050000] border-[#4D0A0A] text-[#FF4D4D] disabled:opacity-50"
                  : "bg-[#0D1117] border-[#30363D] text-white disabled:opacity-50"
              }`}
            />
            <p className={`text-[10px] ${nightMode ? "text-[#881B1B]" : "text-gray-400"}`}>
              Local Wi-Fi IP or secure Cloudflare Tunnel address.
            </p>
          </div>

          {/* Secret Auth Token */}
          <div className="space-y-1">
            <label className="flex items-center gap-1.5 font-bold">
              <Key className="w-3.5 h-3.5" />
              <span>Secret Access PIN / Bearer Token</span>
            </label>
            <input
              type="password"
              value={authToken}
              disabled={simulated}
              onChange={(e) => setAuthToken(e.target.value)}
              placeholder="Optional security secret"
              className={`w-full p-2 rounded border ${
                nightMode
                  ? "bg-[#050000] border-[#4D0A0A] text-[#FF4D4D] disabled:opacity-50"
                  : "bg-[#0D1117] border-[#30363D] text-white disabled:opacity-50"
              }`}
            />
          </div>

          {/* Refresh Interval */}
          <div className="space-y-1">
            <label className="flex items-center gap-1.5 font-bold">
              <Sliders className="w-3.5 h-3.5" />
              <span>Telemetry Polling Rate ({refreshMs} ms)</span>
            </label>
            <input
              type="range"
              min="100"
              max="1000"
              step="50"
              value={refreshMs}
              onChange={(e) => setRefreshMs(parseInt(e.target.value, 10))}
              className="w-full accent-red-600"
            />
          </div>

          <div className={`p-2.5 rounded border text-[11px] flex gap-2 ${
            nightMode ? "bg-[#140202] border-[#2E0505] text-[#AA2222]" : "bg-[#0D1117] border-[#30363D] text-gray-400"
          }`}>
            <Info className="w-4 h-4 shrink-0 mt-0.5" />
            <span>
              Settings are saved locally in your browser and used whenever you access this Vercel deployment.
            </span>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex justify-end gap-2 pt-2 border-t border-inherit">
          <button
            onClick={onClose}
            className={`px-3 py-1.5 rounded border text-xs font-mono transition-colors ${
              nightMode ? "bg-[#1A0303] border-[#4D0A0A] text-[#AA2222] hover:text-[#FF4D4D]" : "bg-[#21262D] border-[#30363D] text-gray-300 hover:text-white"
            }`}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded border text-xs font-mono font-bold transition-all ${
              nightMode
                ? "bg-[#5C0B0B] hover:bg-[#7A1212] border-[#991414] text-[#FFAAAA]"
                : "bg-[#238636] hover:bg-[#2EA043] border-[#2EA043] text-white"
            }`}
          >
            <Check className="w-3.5 h-3.5" />
            <span>Save Settings</span>
          </button>
        </div>
      </div>
    </div>
  );
};
