/** Graphics quality profiles of the AgroAI Farm Engine, with automatic choice per device. */
export type QualityLevel = "ultra" | "high" | "medium" | "battery";
export type QualityChoice = QualityLevel | "auto";

export interface QualityProfile {
  level: QualityLevel; label: string;
  dpr: [number, number]; shadowMap: number; ao: boolean; grass: number; trees: number; terrainSegments: number;
  wind: boolean; plantShadows: boolean; frameloop: "always" | "demand";
  plants: number; plantLod: number; // plant budget for the whole scene; beyond plantLod metres crops use the far model
  shrubs: number; herbs: number;    // scenery bushes and herb clumps around the farm (CC0 photoscans)
  landcover: number;                // size (px) of the painted countryside texture around the farm
  cropImpostors: number;            // plant budget for crops baked as impostors (one quad each)
}

export const PROFILES: Record<QualityLevel, QualityProfile> = {
  ultra: { level: "ultra", label: "Ultra", dpr: [1, 2], shadowMap: 4096, ao: true, grass: 70000, trees: 26000, terrainSegments: 384,
    wind: true, plantShadows: true, frameloop: "always", plants: 9000, plantLod: 85, shrubs: 220, herbs: 320, landcover: 4096, cropImpostors: 3600 },
  high: { level: "high", label: "Alta", dpr: [1, 1.5], shadowMap: 2048, ao: true, grass: 30000, trees: 12000, terrainSegments: 256,
    wind: true, plantShadows: true, frameloop: "always", plants: 6000, plantLod: 80, shrubs: 110, herbs: 160, landcover: 4096, cropImpostors: 3000 },
  medium: { level: "medium", label: "Media", dpr: [1, 1.25], shadowMap: 1024, ao: false, grass: 12000, trees: 6000, terrainSegments: 160,
    wind: true, plantShadows: false, frameloop: "always", plants: 3500, plantLod: 60, shrubs: 60, herbs: 0, landcover: 2048, cropImpostors: 2200 },
  battery: { level: "battery", label: "Risparmio batteria", dpr: [1, 1], shadowMap: 0, ao: false, grass: 0, trees: 2500, terrainSegments: 96,
    wind: false, plantShadows: false, frameloop: "demand", plants: 1800, plantLod: 40, shrubs: 0, herbs: 0, landcover: 1024, cropImpostors: 1400 },
};

/** Graphics card class from the WebGL renderer string: discrete (NVIDIA, AMD Radeon RX/Pro, Apple M Pro/Max, Intel Arc),
 *  integrated (Intel UHD/Iris/HD, AMD Vega/Radeon Graphics, software) or unknown. */
function gpuClass(): "strong" | "integrated" | "unknown" {
  try {
    const gl = document.createElement("canvas").getContext("webgl2");
    if (!gl) return "integrated";
    const ext = gl.getExtension("WEBGL_debug_renderer_info");
    const name = String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    if (/swiftshader|llvmpipe|software|microsoft basic/i.test(name)) return "integrated";
    if (/nvidia|geforce|rtx|quadro|radeon (rx|pro)|rx \d{3,4}|apple m\d (pro|max|ultra)|arc\(tm\) a/i.test(name)) return "strong";
    if (/intel|uhd|iris|radeon\(tm\) graphics|radeon graphics|vega|mali|adreno|powervr|apple (m\d|gpu)/i.test(name)) return "integrated";
    return "unknown";
  } catch { return "unknown"; }
}

/** First guess from the device; the performance monitor can then step down. */
export function detectQuality(): QualityLevel {
  if (typeof window === "undefined") return "medium";
  const coarse = window.matchMedia?.("(pointer: coarse)").matches;
  const cores = navigator.hardwareConcurrency ?? 4;
  const mem = (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 4;
  if (coarse) return cores >= 8 && mem >= 6 ? "medium" : "battery";
  const gpu = gpuClass();
  if (gpu === "strong") return "ultra";
  if (gpu === "integrated") return "medium";
  return cores >= 6 ? "high" : "medium";
}

const KEY = "agroai.planner.quality";
const CHOICES = ["ultra", "high", "medium", "battery", "auto"];
export function loadQuality(): QualityChoice {
  try { const v = localStorage.getItem(KEY); return v && CHOICES.includes(v) ? v as QualityChoice : "auto"; }
  catch { return "auto"; }
}
export function storeQuality(q: QualityChoice) { try { localStorage.setItem(KEY, q); } catch { /* private mode: keep in memory only */ } }

export const lower = (q: QualityLevel): QualityLevel => (q === "ultra" ? "high" : q === "high" ? "medium" : "battery");
