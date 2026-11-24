/**
 * AgroAI crop library: GLB models (public/planner/crops, built by scripts/build-crop-models.mjs or replaced by
 * artist models with the same node names) -> instancing-ready parts per level of detail, plus growth stages
 * from the indicative crop calendar of the rotation engine.
 */
import { useMemo } from "react";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import manifest from "./crops/manifest.json";
import { windMaterial } from "./engine/Landscape";
import { farModel, plantModel } from "./plants";
import { withLeafDetail } from "./leafDetail";
import { CARDS, cardsFromLeaves, LeafKit, styleFor, useLeafKit } from "./photoLeaves";

export type Stage = "young" | "growing" | "mature" | "none" | "harvested";
export interface CropPart { kind: string; geo: THREE.BufferGeometry; mat: THREE.Material }
export interface CropModel { key: string; width: number; dedicated: boolean; lods: Record<string, CropPart[]>; tris: number[] }

type Entry = { file: string; width: number; tris: Record<string, number> };
type Manifest = { crops: Record<string, Entry>; trees: Record<string, Entry>; aliases: Record<string, string> };
const M = manifest as unknown as Manifest;

/** Wind clock shared by crop leaves (advanced by the engine when wind is enabled). */
export const CROP_WIND = { uTime: { value: 0 } };

export function glbKey(crop: string): string | null {
  if (M.crops[crop]) return crop;
  const a = M.aliases[crop];
  return a && M.crops[a] ? a : null;
}
export const glbUrl = (key: string) => `/planner/crops/${M.crops[key].file}`;
export const dedicatedCrops = () => Object.keys(M.crops);

const ROUGH: Record<string, number> = { fruit: 0.35, flower: 0.6, cob: 0.6, head: 0.7, root: 0.6 };
const DOUBLE = new Set(["leaves", "head", "flower"]);
const matCache = new Map<string, THREE.Material>();
function partMaterial(crop: string, kind: string, color?: string) {
  const k = `${crop}:${kind}:${color ?? ""}`;
  let m = matCache.get(k);
  if (!m) {
    const base = new THREE.MeshStandardMaterial({ vertexColors: !color, color: color ?? "#ffffff", roughness: ROUGH[kind] ?? 0.85,
      side: DOUBLE.has(kind) ? THREE.DoubleSide : THREE.FrontSide });
    m = kind === "leaves" || kind === "ear" || kind === "tassel" ? windMaterial(base, CROP_WIND, 0.035) : base;
    if (kind === "leaves" || kind === "head") m = withLeafDetail(m, kind === "head" ? 4 : 6);   // photo leaf texture (triplanar)
    matCache.set(k, m);
  }
  return m;
}

const modelCache = new Map<string, CropModel>();

/** Near levels of detail: the "leaves" mesh becomes photographic leaf cards laid on its own surface. */
function withPhotoLeaves(lods: Record<string, CropPart[]>, key: string, isTree: boolean, kit: LeafKit) {
  const style = styleFor(key, isTree);
  if (!style) return lods;
  const out: Record<string, CropPart[]> = { ...lods };
  for (const [lod, count] of Object.entries(CARDS)) {
    if (!lods[lod]) continue;
    out[lod] = lods[lod].map((p, i) => p.kind !== "leaves" ? p
      : { kind: "leaves", geo: cardsFromLeaves(p.geo, style, isTree ? count * 2 : count, key.length * 31 + i, isTree ? 0.9 : 1), mat: kit[style] });
  }
  return out;
}

/** Models for a set of crops: GLB when the library has one, otherwise the procedural fallback (plants.ts). */
export function useCropModels(crops: { key: string; group: string }[]): Record<string, CropModel> {
  const files = useMemo(() => [...new Set(crops.map((c) => glbKey(c.key)).filter(Boolean) as string[])].sort(), [crops]);
  const gltfs = useGLTF(files.length ? files.map(glbUrl) : ["/planner/crops/lettuce.glb"]) as unknown as { scene: THREE.Group }[];
  const kit = useLeafKit(CROP_WIND);
  return useMemo(() => {
    const out: Record<string, CropModel> = {};
    const byFile: Record<string, { scene: THREE.Group }> = {};
    files.forEach((f, i) => { byFile[f] = gltfs[i]; });
    for (const c of crops) {
      const g = glbKey(c.key);
      const cacheKey = `${c.key}:${g ?? "proc"}`;
      const hit = modelCache.get(cacheKey);
      if (hit) { out[c.key] = hit; continue; }
      let model: CropModel;
      if (g && byFile[g]) {
        const lods: Record<string, CropPart[]> = {};
        byFile[g].scene.traverse((o) => {
          if (!/^LOD\d/.test(o.name)) return;
          lods[o.name] = o.children.filter((m) => (m as THREE.Mesh).isMesh).map((m) => ({
            kind: m.name.replace(/_\d+$/, ""), geo: (m as THREE.Mesh).geometry, mat: partMaterial(g, m.name.replace(/_\d+$/, "")) }));
        });
        const tri = (l: CropPart[] = []) => l.reduce((a, p) => a + (p.geo.index ? p.geo.index.count : p.geo.attributes.position.count) / 3, 0);
        const photo = withPhotoLeaves(lods, g, false, kit);
        model = { key: c.key, width: M.crops[g].width, dedicated: true, lods: photo, tris: [tri(photo.LOD0), tri(photo.LOD1), tri(photo.LOD2)] };
      } else {
        const near = plantModel(c.key, c.group), far = farModel(c.key, c.group);
        const parts = (pm: typeof near) => pm.parts.map((p, i) => ({ kind: i === 0 ? "leaves" : i === 1 && c.group === "frutto" ? "fruit" : `part${i}`,
          geo: p.geo, mat: partMaterial(c.key, `p${i}${pm === far ? "far" : ""}`, p.color) }));
        model = { key: c.key, width: near.width, dedicated: false, lods: { LOD0: parts(near), LOD1: parts(near), LOD2: parts(far) },
          tris: [near.tris ?? 0, near.tris ?? 0, far.tris ?? 0] };
      }
      modelCache.set(cacheKey, model);
      out[c.key] = model;
    }
    return out;
  }, [crops, files, gltfs, kit]);
}

/** GLB scene -> parts per level of detail. */
function toParts(scene: THREE.Group, matKey: string): Record<string, CropPart[]> {
  const lods: Record<string, CropPart[]> = {};
  scene.traverse((o) => {
    if (!/^LOD\d/.test(o.name)) return;
    lods[o.name] = o.children.filter((m) => (m as THREE.Mesh).isMesh).map((m) => {
      const kind = m.name.replace(/_\d+$/, "");
      return { kind, geo: (m as THREE.Mesh).geometry, mat: partMaterial(matKey, kind) };
    });
  });
  return lods;
}

export const treeKeys = () => Object.keys(M.trees);
const treeCache = new Map<string, CropModel>();
/** Fruit trees and vines (orchards, vineyards) from public/planner/trees. */
export function useTreeModels(keys: string[]): Record<string, CropModel> {
  const files = useMemo(() => [...new Set(keys.filter((k) => M.trees[k]))].sort(), [keys]);
  const gltfs = useGLTF(files.length ? files.map((k) => `/planner/trees/${M.trees[k].file}`) : ["/planner/trees/apple.glb"]) as unknown as { scene: THREE.Group }[];
  const kit = useLeafKit(CROP_WIND);
  return useMemo(() => {
    const out: Record<string, CropModel> = {};
    files.forEach((k, i) => {
      let m = treeCache.get(k);
      if (!m) {
        const lods = withPhotoLeaves(toParts(gltfs[i].scene, `tree-${k}`), k, true, kit);
        const tri = (l: CropPart[] = []) => l.reduce((a, p) => a + (p.geo.index ? p.geo.index.count : p.geo.attributes.position.count) / 3, 0);
        m = { key: k, width: M.trees[k].width, dedicated: true, lods, tris: [tri(lods.LOD0), tri(lods.LOD1), tri(lods.LOD2)] };
        treeCache.set(k, m);
      }
      out[k] = m;
    });
    return out;
  }, [files, gltfs, kit]);
}

// ------------------------------------------------------------------ growth stages
export interface Calendar { semina?: number[]; trapianto?: number[]; raccolta?: number[] }
const cyc = (a: number, b: number) => (b - a + 12) % 12;

/** Stage of a crop in a month (1-12) from the indicative calendar; month 0 = full season (mature). */
export function stageFor(cal: Calendar | undefined, month: number): Stage {
  if (!month || !cal?.raccolta?.length) return "mature";
  const start = (cal.trapianto?.length ? cal.trapianto : cal.semina ?? [])[0];
  if (!start) return "mature";
  const hs = cal.raccolta[0], he = cal.raccolta[cal.raccolta.length - 1];
  const span = cyc(start, he), pos = cyc(start, month);
  if (pos > span) return cyc(he, month) <= 2 ? "harvested" : "none";
  if (pos >= cyc(start, hs)) return "mature";
  return pos / Math.max(1, cyc(start, hs)) < 0.45 ? "young" : "growing";
}

export const STAGE_SCALE: Record<Stage, number> = { young: 0.35, growing: 0.75, mature: 1, none: 0, harvested: 0 };
export const STAGE_LABEL: Record<Stage, string> = { young: "Piantina", growing: "In crescita", mature: "Maturazione / raccolta",
  none: "Non in campo", harvested: "Già raccolta" };
const HIDE: Record<Stage, Set<string>> = {
  young: new Set(["fruit", "flower", "ear", "cob", "silk", "tassel"]),
  growing: new Set(["fruit", "cob", "silk"]),
  mature: new Set(), none: new Set(), harvested: new Set(),
};

/** Parts to draw for a level of detail and a stage (cereals switch to the green variant before ripening). */
export function partsFor(model: CropModel, lod: 0 | 1 | 2, stage: Stage): CropPart[] {
  const green = stage !== "mature" && model.lods[`LOD${lod}_green`];
  const list = (green || model.lods[`LOD${lod}`] || model.lods.LOD0 || []) as CropPart[];
  return list.filter((p) => !HIDE[stage].has(p.kind));
}
