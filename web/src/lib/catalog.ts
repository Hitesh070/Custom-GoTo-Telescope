import { CatalogTarget } from "@/types/telescope";

export const CURATED_CATALOG: CatalogTarget[] = [
  // Solar System
  { id: "moon", name: "Moon", type: "Moon", ra_hours: 0, dec_deg: 0, mag: -12.7, desc: "Earth natural satellite; craters, rilles and maria.", constellation: "Dynamic" },
  { id: "jupiter", name: "Jupiter", type: "Planet", ra_hours: 4.85, dec_deg: 21.8, mag: -2.6, desc: "Gas giant showing equatorial bands, Great Red Spot, and 4 Galilean moons.", constellation: "Taurus" },
  { id: "saturn", name: "Saturn", type: "Planet", ra_hours: 23.1, dec_deg: -8.5, mag: 0.6, desc: "The Ringed Planet; prominent Cassini Division and Titan.", constellation: "Aquarius" },
  { id: "mars", name: "Mars", type: "Planet", ra_hours: 7.9, dec_deg: 22.3, mag: -0.4, desc: "The Red Planet; dark albedo regions and polar ice caps.", constellation: "Gemini" },
  { id: "venus", name: "Venus", type: "Planet", ra_hours: 18.2, dec_deg: -24.1, mag: -4.2, desc: "Bright morning/evening star; brilliant crescent or gibbous phases.", constellation: "Sagittarius" },

  // Deep Sky Objects (Messier & Caldwell)
  { id: "m42", name: "M42 Orion Nebula", type: "Nebula", ra_hours: 5.59, dec_deg: -5.39, mag: 4.0, desc: "Great stellar nursery; striking glowing ionization fronts and Trapezium cluster.", constellation: "Orion" },
  { id: "m31", name: "M31 Andromeda Galaxy", type: "Galaxy", ra_hours: 0.71, dec_deg: 41.27, mag: 3.4, desc: "Nearest major spiral galaxy; distinct dust lanes and satellite M32.", constellation: "Andromeda" },
  { id: "m45", name: "M45 Pleiades", type: "Cluster", ra_hours: 3.79, dec_deg: 24.11, mag: 1.6, desc: "The Seven Sisters; sparkling open star cluster immersed in blue reflection nebulosity.", constellation: "Taurus" },
  { id: "m13", name: "M13 Great Hercules Cluster", type: "Cluster", ra_hours: 16.69, dec_deg: 36.46, mag: 5.8, desc: "Massive globular cluster of ~300,000 ancient stars resolved to the core.", constellation: "Hercules" },
  { id: "m57", name: "M57 Ring Nebula", type: "Nebula", ra_hours: 18.89, dec_deg: 33.03, mag: 8.8, desc: "Classic smoky smoke-ring planetary nebula expelled by white dwarf.", constellation: "Lyra" },
  { id: "m8", name: "M8 Lagoon Nebula", type: "Nebula", ra_hours: 18.06, dec_deg: -24.38, mag: 6.0, desc: "Giant interstellar emission nebula with open cluster NGC 6530.", constellation: "Sagittarius" },
  { id: "m27", name: "M27 Dumbbell Nebula", type: "Nebula", ra_hours: 19.99, dec_deg: 22.72, mag: 7.5, desc: "Large bi-polar apple-core planetary nebula in Vulpecula.", constellation: "Vulpecula" },
  { id: "m51", name: "M51 Whirlpool Galaxy", type: "Galaxy", ra_hours: 13.50, dec_deg: 47.20, mag: 8.4, desc: "Spectacular interacting face-on grand design spiral galaxy.", constellation: "Canes Venatici" },
  { id: "m81", name: "M81 Bode's Galaxy", type: "Galaxy", ra_hours: 9.93, dec_deg: 69.07, mag: 6.9, desc: "Bright grand-design spiral galaxy in Ursa Major.", constellation: "Ursa Major" },

  // Double Stars & Calibration
  { id: "albireo", name: "Albireo (Beta Cygni)", type: "Double Star", ra_hours: 19.51, dec_deg: 27.96, mag: 3.1, desc: "Finest color-contrast double star in the sky: golden topaz and sapphire blue.", constellation: "Cygnus" },
  { id: "mizar", name: "Mizar & Alcor", type: "Double Star", ra_hours: 13.40, dec_deg: 54.92, mag: 2.2, desc: "Famous naked-eye visual double in Ursa Major handle.", constellation: "Ursa Major" },
  { id: "polaris", name: "Polaris (Alpha UMi)", type: "Double Star", ra_hours: 2.53, dec_deg: 89.26, mag: 2.0, desc: "North Star alignment standard; close white-yellow primary and 9th-mag companion.", constellation: "Ursa Minor" }
];

export function formatRa(hours: number): string {
  const h = Math.floor(hours);
  const m = Math.floor((hours - h) * 60);
  const s = ((hours - h) * 60 - m) * 60;
  return `${h.toString().padStart(2, "0")}h ${m.toString().padStart(2, "0")}m ${s.toFixed(1).padStart(4, "0")}s`;
}

export function formatDec(deg: number): string {
  const sign = deg >= 0 ? "+" : "-";
  const abs = Math.abs(deg);
  const d = Math.floor(abs);
  const m = Math.floor((abs - d) * 60);
  const s = ((abs - d) * 60 - m) * 60;
  return `${sign}${d.toString().padStart(2, "0")}° ${m.toString().padStart(2, "0")}' ${s.toFixed(1).padStart(4, "0")}"`;
}

export function formatDegMinSec(deg: number): string {
  const sign = deg >= 0 ? "+" : "-";
  const abs = Math.abs(deg);
  const d = Math.floor(abs);
  const m = Math.floor((abs - d) * 60);
  const s = ((abs - d) * 60 - m) * 60;
  return `${sign}${d.toString().padStart(2, "0")}° ${m.toString().padStart(2, "0")}' ${s.toFixed(1).padStart(4, "0")}"`;
}
