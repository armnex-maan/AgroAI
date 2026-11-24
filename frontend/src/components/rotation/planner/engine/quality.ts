/** Graphics quality profiles of the AgroAI Farm Engine, with automatic choice per device. */
export type QualityLevel = "high" | "medium" | "battery";
export type QualityChoice = QualityLevel | "auto";

export interface QualityProfile {
  level: QualityLevel; label: string;
  dpr: [number, number]; shadowMap: number; ao: boolean; grass: number; trees: number; terrainSegments: number;
  wind: boolean; plantShadows: boolean; frameloop: "always" | "demand";
  plants: number; plantLod: number; // plant budget for the whole scene; beyond plantLod metres crops use the far model
  shrubs: number; herbs: number;    // scenery bushes and herb clumps around the farm (CC0 photoscans)
}

export const PROFILES: Record<QualityLevel, QualityProfile> = {
  high: { level: "high", label: "Alta", dpr: [1, 2], shadowMap: 2048, ao: true, grass: 30000, trees: 1700, terrainSegments: 256,
    wind: true, plantShadows: true, frameloop: "always", plants: 4500, plantLod: 75, shrubs: 110, herbs: 160 },
  medium: { level: "medium", label: "Media", dpr: [1, 1.5], shadowMap: 1024, ao: false, grass: 12000, trees: 850, terrainSegments: 160,
    wind: true, plantShadows: false, frameloop: "always", plants: 3500, plantLod: 60, shrubs: 60, herbs: 0 },
  battery: { level: "battery", label: "Risparmio batteria", dpr: [1, 1], shadowMap: 0, ao: false, grass: 0, trees: 380, terrainSegments: 96,
    wind: false, plantShadows: false, frameloop: "demand", plants: 1800, plantLod: 40, shrubs: 0, herbs: 0 },
};

/** First guess from the device; the performance monitor can then step down. */
export function detectQuality(): QualityLevel {
  if (typeof window === "undefined") return "medium";
  const coarse = window.matchMedia?.("(pointer: coarse)").matches;
  const cores = navigator.hardwareConcurrency ?? 4;
  const mem = (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 4;
  if (coarse) return cores >= 8 && mem >= 6 ? "medium" : "battery";
  return cores >= 6 ? "high" : "medium";
}

const KEY = "agroai.planner.quality";
export function loadQuality(): QualityChoice {
  try { const v = localStorage.getItem(KEY); return v === "high" || v === "medium" || v === "battery" || v === "auto" ? v : "auto"; }
  catch { return "auto"; }
}
export function storeQuality(q: QualityChoice) { try { localStorage.setItem(KEY, q); } catch { /* private mode: keep in memory only */ } }

export const lower = (q: QualityLevel): QualityLevel => (q === "high" ? "medium" : "battery");
