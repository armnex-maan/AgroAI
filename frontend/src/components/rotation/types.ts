import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

export type Kind = "bed" | "path" | "access" | "water" | "no_crop" | "shade" | "greenhouse";
/** Sections where crops grow: open-field beds and greenhouses. */
export const isGrowing = (k: string) => k === "bed" || k === "greenhouse";
export interface Section {
  id?: string; name: string; kind: Kind; x: number; y: number; w: number; h: number; area_m2?: number;
  /** rows declared by the farmer (empty = not declared) */
  row_spacing_m?: number | null; plant_spacing_m?: number | null; row_dir?: "x" | "y" | null; rows?: number;
}
export interface Source { id: string; title: string; url: string; year: number | null; type: string; region: string }
export interface Reason { effect: "good" | "warn" | "bad"; text: string; rule: boolean; level: string; source: Source | null }
export interface HistoryRow {
  id: string; year: number; status: "crop" | "rest" | "cover" | "unknown"; crop: string; name: string; family: string | null;
  section_id: string | null; area_m2: number | null; diseases: string | null; treatments: string | null; notes: string | null;
}
export interface Assignment {
  section_id: string | null; section: string; crop: string; name: string; family: string; area_m2: number;
  verdict: "ok" | "care" | "no"; reasons?: Reason[]; calendar?: Record<string, number[]> | null; status?: string; manual?: boolean;
}
export interface Plot {
  id: string; name: string; area_m2: number | null; shape: "rectangle" | "square" | "irregular";
  width_m: number | null; length_m: number | null; orientation_deg: number; exposure: string | null;
  outline: number[][] | null; profile: Record<string, any>; sections: Section[]; history: HistoryRow[];
  polygon?: { type: string; coordinates: number[][][]; origin?: number[]; k?: number[] } | null;
  plans: { year: number; assignments: Assignment[]; goals: any; status: string; updated_at: string }[];
}
export interface RCrop { key: string; name: string; family: string; group: string; gap: number; season: string; height_m?: number[] | null }
export interface Coverage {
  region: string | null; name?: string; level: "crops" | "general" | "none"; text: string;
  documents?: Source[]; general_rule?: { text: string; source: Source } | null;
}
export interface FarmData {
  id: string; name: string; region: string | null; province: string | null; municipality: string | null;
  latitude: number | null; longitude: number | null; coverage: Coverage; season_year: number;
  plots: Plot[]; crops: RCrop[]; families: Record<string, string>;
  height_source?: { id: string; title: string; url: string; year: number };
}
export interface PlanYear { year: number; assignments: Assignment[]; unplaced: { crop: string; name: string; why: string }[];
  area_by_crop: Record<string, number> }
export interface PlanResult {
  plot_id: string; region: string | null; coverage: Coverage; season_year: number; years: PlanYear[];
  beds: { id: string | null; name: string; area_m2: number }[]; current: { year: number; assignments: Assignment[] };
  notes: string[]; general_rule: { text: string; source: Source } | null;
}

export const useFarmData = () =>
  useQuery({ queryKey: ["rotation-farm"], queryFn: () => api.get<FarmData>("/api/v1/rotation/farm"),
             refetchInterval: false, staleTime: 30000 });

export const FAMILY_COLOR: Record<string, string> = {
  solanacee: "#e5533d", cucurbitacee: "#f0a020", crucifere: "#2f9e6e", leguminose: "#7b5cd6", liliacee: "#c46fb0",
  ombrellifere: "#f07f3c", composite: "#5fae3e", chenopodiacee: "#b5476a", graminacee: "#c9a227", rosacee: "#e0607e",
  lamiacee: "#3aa39a",
};
export const GROUP_ICON: Record<string, string> = { frutto: "fruit", foglia: "leaf", radice: "root", legume: "pod", cereale: "grain" };
export const KIND_LABEL: Record<Kind, string> = {
  bed: "Aiuola", path: "Sentiero", access: "Accesso", water: "Punto d'acqua", no_crop: "Zona non coltivabile", shade: "Zona d'ombra", greenhouse: "Serra",
};
export const LEVEL: Record<string, { label: string; cls: string }> = {
  obbligatoria: { label: "Obbligatoria", cls: "lv-law" },
  disciplinare: { label: "Disciplinare", cls: "lv-dpi" },
  buona_pratica: { label: "Buona pratica", cls: "lv-gp" },
  suggerimento: { label: "Suggerimento AI", cls: "lv-ai" },
};
export const VERDICT = {
  ok: { label: "Va bene", cls: "ok", icon: "check" },
  care: { label: "Con attenzione", cls: "warn", icon: "alert" },
  no: { label: "Meglio di no", cls: "bad", icon: "ban" },
} as const;
export const MONTHS = ["G", "F", "M", "A", "M", "G", "L", "A", "S", "O", "N", "D"];

/** A stable colour per crop: the family colour, shifted a little per crop so neighbours differ. */
// field crops of the same family (cereals) get clearly different colours, so a farm map reads at a glance
const CROP_COLOR: Record<string, string> = {
  wheat: "#f08a24", durum_wheat: "#d9731a", barley: "#e8c547", maize: "#8e4fb8", sorghum: "#a0522d",
  rapeseed: "#3b82c4", sunflower: "#f2c230", soybean: "#5f9e45", alfalfa: "#2e8b57", sugar_beet: "#b5476a",
};
export function cropColor(key: string, family: string): string {
  if (CROP_COLOR[key]) return CROP_COLOR[key];
  const base = FAMILY_COLOR[family] ?? "#8aa095";
  let h = 0;
  for (const ch of key) h = (h * 31 + ch.charCodeAt(0)) % 360;
  const shift = (h % 3) - 1; // -1, 0, +1
  return shift === 0 ? base : mix(base, shift > 0 ? "#ffffff" : "#000000", 0.16);
}
function mix(a: string, b: string, t: number) {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  return "#" + pa.map((v, i) => Math.round(v + (pb[i] - v) * t).toString(16).padStart(2, "0")).join("");
}
export const shortName = (n: string) => n.split(" (")[0];
export const fmtArea = (m2: number | null | undefined) =>
  m2 == null ? "—" : m2 >= 10000 ? `${(m2 / 10000).toLocaleString("it-IT", { maximumFractionDigits: 2 })} ha`
    : `${Math.round(m2).toLocaleString("it-IT")} m²`;
