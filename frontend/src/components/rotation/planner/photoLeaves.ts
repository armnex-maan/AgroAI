/**
 * Photographic leaves for the near levels of detail (LOD0, LOD1) of crops and fruit trees.
 * The botanical shape stays the one of the model: cards are scattered ON the surface of its "leaves" mesh, facing
 * like that surface, and take its colour (so a lettuce stays lettuce-green, a vine stays vine-green). The card adds
 * only the photographed leaf outline and detail (CC0 Poly Haven leaf atlases, converted to brightness + mask).
 */
import { useMemo } from "react";
import { useTexture } from "@react-three/drei";
import * as THREE from "three";
import { windMaterial } from "./engine/Landscape";
import { rng } from "./engine/noise";

export type LeafStyle = "spray" | "leaf";

/** Broad single leaves for leafy vegetables and cucurbits, leafy twigs for bushes and trees; grasses keep blades. */
const STYLE: Record<string, LeafStyle | null> = {
  lettuce: "leaf", cabbage: "leaf", zucchini: "leaf", pumpkin: "leaf",
  tomato: "spray", pepper: "spray", eggplant: "spray", potato: "spray", bean: "spray", carrot: "spray", pea: "spray",
  wheat: null, barley: null, maize: null,
};
export const styleFor = (modelKey: string, isTree: boolean): LeafStyle | null => (isTree ? "spray" : STYLE[modelKey] ?? null);

interface Region { uv: [number, number, number, number]; aspect: number; base: boolean }
// tree_small_02 atlas: twigs with leaves (centred cards)
const SPRAY: Region[] = [
  { uv: [0.0, 0.5, 0.46, 1.0], aspect: 0.92, base: false },
  { uv: [0.0, 0.0, 0.46, 0.5], aspect: 0.92, base: false },
  { uv: [0.527, 0.326, 0.86, 0.961], aspect: 0.52, base: false },
];
// island_tree_02 atlas: single leaves, stem at the bottom (cards start at the attachment point)
const px = (x0: number, y0: number, x1: number, y1: number): Region =>
  ({ uv: [x0 / 1024, 1 - y1 / 1024, x1 / 1024, 1 - y0 / 1024], aspect: (x1 - x0) / (y1 - y0), base: true });
const SINGLE: Region[] = [px(18, 22, 150, 410), px(170, 22, 345, 400), px(530, 50, 665, 370), px(710, 22, 835, 420),
  px(18, 645, 185, 1000), px(222, 595, 362, 1000), px(432, 620, 575, 1000)];

const FILES = ["/planner/foliage/tree_small_02_leaves_diff_1k.jpg", "/planner/foliage/tree_small_02_leaves_alpha_1k.jpg",
  "/planner/foliage/island_tree_02_leaves_diff_1k.jpg", "/planner/foliage/island_tree_02_leaves_alpha_1k.jpg"];

/** Atlas -> texture holding the leaf brightness (average about 0.9) and the cut-out mask. */
function brightnessMask(diff: HTMLImageElement, alpha: HTMLImageElement) {
  const S = 1024, c = document.createElement("canvas"); c.width = c.height = S;
  const g = c.getContext("2d")!;
  g.drawImage(alpha, 0, 0, S, S); const a = g.getImageData(0, 0, S, S);
  g.drawImage(diff, 0, 0, S, S); const d = g.getImageData(0, 0, S, S);
  let sum = 0, n = 0;
  for (let i = 0; i < d.data.length; i += 4) if (a.data[i] > 128) { sum += d.data[i] * 0.3 + d.data[i + 1] * 0.59 + d.data[i + 2] * 0.11; n++; }
  const mean = sum / Math.max(1, n);
  for (let i = 0; i < d.data.length; i += 4) {
    const l = d.data[i] * 0.3 + d.data[i + 1] * 0.59 + d.data[i + 2] * 0.11;
    const v = Math.max(0, Math.min(225, (l / mean) * 0.9 * 255));   // cap highlights: no white glints
    d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = a.data[i] > 128 ? 255 : 0;
  }
  g.putImageData(d, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.NoColorSpace; t.anisotropy = 4;
  return t;
}

export interface LeafKit { spray: THREE.Material; leaf: THREE.Material }
let kit: LeafKit | null = null;

export function useLeafKit(wind: { uTime: { value: number } }): LeafKit {
  const t = useTexture(FILES);
  return useMemo(() => {
    if (kit) return kit;
    const mk = (map: THREE.Texture) => windMaterial(new THREE.MeshStandardMaterial({ map, alphaTest: 0.5, side: THREE.DoubleSide,
      vertexColors: true, roughness: 0.72 }), wind, 0.035);
    kit = { spray: mk(brightnessMask(t[0].image, t[1].image)), leaf: mk(brightnessMask(t[2].image, t[3].image)) };
    return kit;
  }, [t, wind]);
}

/** Cards spread over the triangles of a leaves mesh (area-weighted), oriented like the surface. */
export function cardsFromLeaves(src: THREE.BufferGeometry, style: LeafStyle, count: number, seed: number, sizeK = 1): THREE.BufferGeometry {
  const g = src.index ? src.toNonIndexed() : src;
  const P = g.attributes.position, C = g.attributes.color as THREE.BufferAttribute | undefined;
  const tris = P.count / 3;
  const area: number[] = [];
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), e1 = new THREE.Vector3(), e2 = new THREE.Vector3();
  let total = 0;
  for (let i = 0; i < tris; i++) {
    a.fromBufferAttribute(P, i * 3); b.fromBufferAttribute(P, i * 3 + 1); c.fromBufferAttribute(P, i * 3 + 2);
    const s = e1.subVectors(b, a).cross(e2.subVectors(c, a)).length() / 2;
    total += s; area.push(total);
  }
  g.computeBoundingBox();
  const bb = g.boundingBox!, H = bb.max.y - bb.min.y || 1, cy = (bb.min.y + bb.max.y) / 2;
  const regions = style === "spray" ? SPRAY : SINGLE;
  const r = rng(seed);
  // card size from the leaf area, but never smaller than a share of the plant (many tiny leaves = sparse cards)
  const size = Math.max(Math.sqrt(total / count) * (style === "spray" ? 2.1 : 1.9), H * (style === "spray" ? 0.17 : 0.13)) * sizeK;
  const pos: number[] = [], nor: number[] = [], uv: number[] = [], col: number[] = [];
  const n = new THREE.Vector3(), up = new THREE.Vector3(), side = new THREE.Vector3(), out = new THREE.Vector3(), p = new THREE.Vector3();
  const colA = new THREE.Color(), colB = new THREE.Color(), colC = new THREE.Color();
  for (let k = 0; k < count && total > 0; k++) {
    const x = r() * total;
    let lo = 0, hi = tris - 1;
    while (lo < hi) { const m = (lo + hi) >> 1; if (area[m] < x) lo = m + 1; else hi = m; }
    const i = lo;
    a.fromBufferAttribute(P, i * 3); b.fromBufferAttribute(P, i * 3 + 1); c.fromBufferAttribute(P, i * 3 + 2);
    let u = r(), v = r(); if (u + v > 1) { u = 1 - u; v = 1 - v; }
    p.copy(a).addScaledVector(e1.subVectors(b, a), u).addScaledVector(e2.subVectors(c, a), v);
    n.subVectors(b, a).cross(e2.subVectors(c, a)).normalize();
    out.set(p.x, 0, p.z); if (out.lengthSq() < 1e-6) out.set(r() - 0.5, 0, r() - 0.5); out.normalize();
    if (n.dot(out) + n.y * 0.3 < 0) n.negate();                    // face away from the plant
    // in-plane "up": outward and upward, projected on the card plane (leaves radiate from the stem)
    up.copy(out).multiplyScalar(style === "leaf" ? 1 : 0.4).add(new THREE.Vector3(0, style === "leaf" ? 0.35 : 1, 0));
    up.addScaledVector(n, -up.dot(n)); if (up.lengthSq() < 1e-6) up.set(0, 1, 0); up.normalize();
    up.applyAxisAngle(n, (r() - 0.5) * (style === "leaf" ? 0.7 : 1.4));
    side.crossVectors(up, n).normalize();
    const reg = regions[Math.floor(r() * regions.length)];
    const h = size * (0.75 + r() * 0.5) * (style === "leaf" ? 1.25 : 1), w = h * reg.aspect;
    const y0 = reg.base ? 0 : -0.5, flip = r() < 0.5;
    const [u0, v0, u1, v1] = reg.uv;
    const corner = (sx: number, sy: number) => [p.x + side.x * sx * w + up.x * (y0 + sy) * h, p.y + side.y * sx * w + up.y * (y0 + sy) * h, p.z + side.z * sx * w + up.z * (y0 + sy) * h];
    const q = [corner(-0.5, 0), corner(0.5, 0), corner(0.5, 1), corner(-0.5, 1)];
    const quv = [[flip ? u1 : u0, v0], [flip ? u0 : u1, v0], [flip ? u0 : u1, v1], [flip ? u1 : u0, v1]];
    // colour of the model at that point (keeps the crop's own green), a little darker low and inside
    if (C) {
      colA.fromBufferAttribute(C, i * 3); colB.fromBufferAttribute(C, i * 3 + 1); colC.fromBufferAttribute(C, i * 3 + 2);
      colA.multiplyScalar(1 - u - v).add(colB.multiplyScalar(u)).add(colC.multiplyScalar(v));
    } else colA.setRGB(0.35, 0.55, 0.25);
    const shade = 0.78 + 0.32 * Math.min(1, Math.max(0, (p.y - bb.min.y) / H)) * (0.85 + r() * 0.3);
    // normals: half surface, half outward from the plant centre (soft, volumetric light)
    const sn = new THREE.Vector3(p.x, (p.y - cy) * 0.8, p.z).normalize().multiplyScalar(0.5).add(n.clone().multiplyScalar(0.5)).normalize();
    for (const idx of [0, 1, 2, 0, 2, 3]) {
      pos.push(...q[idx]); uv.push(...quv[idx]); nor.push(sn.x, sn.y, sn.z);
      col.push(colA.r * shade, colA.g * shade, colA.b * shade);
    }
  }
  const outG = new THREE.BufferGeometry();
  outG.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  outG.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3));
  outG.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  outG.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  outG.computeBoundingSphere();
  return outG;
}

/** Cards per level of detail: many near, fewer in the middle; far levels keep the plain model. */
export const CARDS: Record<string, number> = { LOD0: 150, LOD1: 40 };
