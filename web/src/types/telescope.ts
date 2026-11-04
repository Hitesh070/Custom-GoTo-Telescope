export type SlewState = "IDLE" | "SLEWING" | "TRACKING" | "PARKED";
export type TrackingRate = "Sidereal" | "King" | "Lunar" | "Solar";
export type CableStatus = "OK" | "CAUTION" | "STRAIN";

export interface TelescopeTelemetry {
  connected: boolean;
  simulated: boolean;
  slew_state: SlewState;
  tracking: boolean;
  tracking_rate: TrackingRate;
  az_deg: number;
  alt_deg: number;
  ra_j2000_hours: number;
  dec_j2000_deg: number;
  target_name: string;
  target_type: string;
  target_ra_hours: number | null;
  target_dec_deg: number | null;
  target_az_deg: number | null;
  target_alt_deg: number | null;
  sun_sep_deg: number;
  solar_filter_confirmed: boolean;
  cable_turns: number;
  cable_status: CableStatus;
  focus_pos: number;
  data_rate_hz: number;
  weather?: {
    condition: string;
    cloud_cover: number;
    temp_c: number;
    humidity: number;
    wind_kmh: number;
    obs_status: string;
  };
}

export interface CatalogTarget {
  id: string;
  name: string;
  type: "Planet" | "Moon" | "Nebula" | "Galaxy" | "Cluster" | "Double Star" | "Sun";
  ra_hours: number;
  dec_deg: number;
  mag: number | string;
  desc: string;
  constellation: string;
}

export interface MountLogMessage {
  id: string;
  timestamp: string;
  level: "INFO" | "WARNING" | "ERROR" | "COMMAND";
  text: string;
}

export interface ConnectionConfig {
  apiUrl: string;
  authToken: string;
  simulatedMode: boolean;
  refreshIntervalMs: number;
}
