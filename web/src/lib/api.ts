import { TelescopeTelemetry, ConnectionConfig, SlewState, TrackingRate } from "@/types/telescope";

export const DEFAULT_CONFIG: ConnectionConfig = {
  apiUrl: "http://localhost:8080",
  authToken: "",
  simulatedMode: true,
  refreshIntervalMs: 250,
};

// Initial simulated state matching desktop bridge defaults
let simState: TelescopeTelemetry = {
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
};

let simSlewTarget: { az: number; alt: number; name: string } | null = null;

// Background simulated slewing & tracking loop
if (typeof window !== "undefined") {
  setInterval(() => {
    if (simSlewTarget) {
      simState.slew_state = "SLEWING";
      const dAz = simSlewTarget.az - simState.az_deg;
      const dAlt = simSlewTarget.alt - simState.alt_deg;
      const step = 2.5; // slew speed deg/sec / 4

      if (Math.abs(dAz) <= step && Math.abs(dAlt) <= step) {
        simState.az_deg = simSlewTarget.az;
        simState.alt_deg = simSlewTarget.alt;
        simState.slew_state = simState.tracking ? "TRACKING" : "IDLE";
        simSlewTarget = null;
      } else {
        simState.az_deg += Math.sign(dAz) * Math.min(step, Math.abs(dAz));
        simState.alt_deg += Math.sign(dAlt) * Math.min(step, Math.abs(dAlt));
        simState.cable_turns = simState.az_deg / 360.0;
        if (Math.abs(simState.cable_turns) >= 1.0) {
          simState.cable_status = "STRAIN";
        } else if (Math.abs(simState.cable_turns) >= 0.75) {
          simState.cable_status = "CAUTION";
        } else {
          simState.cable_status = "OK";
        }
      }
    } else if (simState.tracking) {
      // Small sidereal motion simulation
      simState.az_deg = (simState.az_deg + 0.002) % 360.0;
      simState.cable_turns = simState.az_deg / 360.0;
    }
  }, 250);
}

export async function fetchTelemetry(config: ConnectionConfig): Promise<TelescopeTelemetry> {
  if (config.simulatedMode) {
    return { ...simState };
  }

  try {
    const res = await fetch(`${config.apiUrl}/api/telemetry`, {
      headers: {
        "Authorization": `Bearer ${config.authToken}`,
        "Accept": "application/json",
      },
      signal: AbortSignal.timeout(3000),
    });

    if (!res.ok) {
      throw new Error(`HTTP error ${res.status}`);
    }

    const data = await res.json();
    return data;
  } catch {
    // If live connection fails and user isn't strictly in real-only mode, report disconnected
    return {
      ...simState,
      connected: false,
      simulated: false,
      slew_state: "IDLE",
    };
  }
}

export async function sendCommand(
  action: string,
  params: Record<string, any> = {},
  config: ConnectionConfig
): Promise<{ success: boolean; message: string }> {
  if (config.simulatedMode) {
    switch (action) {
      case "goto":
        simSlewTarget = {
          az: params.az ?? simState.az_deg,
          alt: params.alt ?? simState.alt_deg,
          name: params.name ?? "Custom Target",
        };
        simState.target_name = params.name ?? "Custom Target";
        simState.target_az_deg = params.az;
        simState.target_alt_deg = params.alt;
        simState.slew_state = "SLEWING";
        return { success: true, message: `Slewing to ${params.name || "Target"} (${params.az?.toFixed(1)}°, ${params.alt?.toFixed(1)}°)` };

      case "stop":
        simSlewTarget = null;
        simState.slew_state = "IDLE";
        simState.tracking = false;
        return { success: true, message: "EMERGENCY STOP executed. Motors halted." };

      case "jog":
        const axis = params.axis; // "az" | "alt"
        const dir = params.dir; // +1 | -1
        const deg = params.deg || 0.5;
        if (axis === "az") {
          simState.az_deg = (simState.az_deg + dir * deg + 360) % 360;
          simState.cable_turns = simState.az_deg / 360.0;
        } else if (axis === "alt") {
          simState.alt_deg = Math.max(0, Math.min(85, simState.alt_deg + dir * deg));
        }
        return { success: true, message: `Jogged ${axis.toUpperCase()} by ${dir > 0 ? "+" : "-"}${deg}°` };

      case "tracking":
        simState.tracking = params.enabled ?? !simState.tracking;
        if (params.rate) simState.tracking_rate = params.rate;
        simState.slew_state = simState.tracking ? "TRACKING" : "IDLE";
        return { success: true, message: `Tracking ${simState.tracking ? "ON (" + simState.tracking_rate + ")" : "OFF"}` };

      case "unwind":
        simSlewTarget = { az: 0.0, alt: simState.alt_deg, name: "North True (Unwind)" };
        simState.slew_state = "SLEWING";
        return { success: true, message: "Unwinding cable to Azimuth 0.0°" };

      case "park":
        simSlewTarget = { az: 0.0, alt: 0.0, name: "Park Position" };
        simState.slew_state = "PARKED";
        simState.tracking = false;
        return { success: true, message: "Parking telescope at (0°, 0°)" };

      case "focus":
        const steps = params.steps || 0;
        simState.focus_pos += steps;
        return { success: true, message: `Focus moved by ${steps > 0 ? "+" : ""}${steps} steps (Pos: ${simState.focus_pos})` };

      case "sync":
        simState.target_name = params.name || simState.target_name;
        return { success: true, message: "Target synchronized with current optical position." };

      default:
        return { success: false, message: `Unknown action: ${action}` };
    }
  }

  // Live real network command
  try {
    const res = await fetch(`${config.apiUrl}/api/mount/${action}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${config.authToken}`,
      },
      body: JSON.stringify(params),
      signal: AbortSignal.timeout(4000),
    });

    const data = await res.json();
    return data;
  } catch (err: any) {
    return { success: false, message: `Command failed: ${err.message}` };
  }
}
