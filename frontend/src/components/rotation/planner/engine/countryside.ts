/**
 * Demonstrative countryside around the farm (Italian hills: a patchwork of wheat, ploughed land, meadows, olive groves,
 * vineyards and woods, with hedgerows and dirt roads). Deterministic: same farm -> same landscape on every device.
 * It is SCENERY ONLY: never selectable, never data; the planner labels the landscape as not real.
 * One model feeds both the painted ground texture and the 3D trees standing on it, so they always agree.
 */
import * as THREE from "three";
import { fbm, rng } from "./noise";
import { distFromFarm, FarmZone, farmMargin, slopeAt, TerrainSource } from "./terrain";

export type XZ = [number, number];
export type FieldKind = "wheat" | "stubble" | "ploughed" | "meadow" | "green" | "olive" | "vineyard" | "forest" | "hay";
export interface Field { kind: FieldKind; poly: XZ[]; angle: number; tone: number; centre: XZ }
export type TreeKind = "broadleaf_a" | "broadleaf_b" | "broadleaf_c" | "olive_a";
export interface TreeSpot { kind: TreeKind; x: number; y: number; z: number; h: number; rot: number; tint: THREE.Color }
export interface Countryside { S: number; x0: number; z0: number; fields: Field[]; hedges: [XZ, XZ][]; roads: XZ[][]; trees: TreeSpot[] }

export const terrainExtent = (zone: FarmZone) => zone.size * 8 + 600;

const inPoly = (x: number, z: number, poly: XZ[]) => {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, zi] = poly[i], [xj, zj] = poly[j];
    if ((zi > z) !== (zj > z) && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi) c = !c;
  }
  return c;
};

const KIND_WEIGHTS: [FieldKind, number][] = [["wheat", 0.24], ["stubble", 0.06], ["ploughed", 0.15], ["meadow", 0.2], ["green", 0.1],
  ["olive", 0.13], ["vineyard", 0.08], ["hay", 0.04]];

function pickKind(r: number): FieldKind {
  let a = 0;
  for (const [k, w] of KIND_WEIGHTS) { a += w; if (r < a) return k; }
  return "meadow";
}

const cache = new Map<string, Countryside>();

/** Fields, hedgerows, roads and trees of the demo landscape (tree budget from the quality profile). */
export function countryside(zone: FarmZone, terrain: TerrainSource, treeBudget: number): Countryside {
  const key = `${zone.x0.toFixed(1)}:${zone.z0.toFixed(1)}:${zone.x1.toFixed(1)}:${zone.z1.toFixed(1)}:${treeBudget}`;
  const hit = cache.get(key); if (hit) return hit;
  const S = terrainExtent(zone), x0 = zone.cx - S / 2, z0 = zone.cz - S / 2;
  const r = rng(4242);
  const margin = farmMargin(zone);
  const cell = 120;
  const n = Math.ceil(S / cell) + 1;
  // jittered grid nodes shared by neighbouring fields -> irregular quads that tile the hills
  const nodes: XZ[][] = [];
  for (let j = 0; j <= n; j++) {
    nodes.push([]);
    for (let i = 0; i <= n; i++) {
      const jx = fbm(i * 0.71 + 3, j * 0.71 - 5, 2) * cell * 0.38, jz = fbm(i * 0.71 - 11, j * 0.71 + 7, 2) * cell * 0.38;
      nodes[j].push([x0 + i * cell + jx, z0 + j * cell + jz]);
    }
  }
  const fields: Field[] = [];
  const hedges: [XZ, XZ][] = [];
  const nearFarm = (x: number, z: number) => distFromFarm(zone, x, z, margin * 0.6) <= 0;
  for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
    const quad: XZ[] = [nodes[j][i], nodes[j][i + 1], nodes[j + 1][i + 1], nodes[j + 1][i]];
    const cx = quad.reduce((a, p) => a + p[0], 0) / 4, cz = quad.reduce((a, p) => a + p[1], 0) / 4;
    if (quad.some(([x, z]) => nearFarm(x, z)) || nearFarm(cx, cz)) continue;   // the farm and its margin stay lawn
    const forest = fbm(cx / 420 + 40, cz / 420 - 12, 3);
    const steep = slopeAt(terrain, cx, cz, 20) > 0.32;
    // long side of the quad: direction of the rows
    const e1 = Math.atan2(quad[1][1] - quad[0][1], quad[1][0] - quad[0][0]), e2 = Math.atan2(quad[3][1] - quad[0][1], quad[3][0] - quad[0][0]);
    const split = r() < 0.45;   // many fields are long strips: split the quad in two along its long side
    const parts: XZ[][] = split
      ? (r() < 0.5
        ? [[quad[0], mid(quad[0], quad[1]), mid(quad[3], quad[2]), quad[3]], [mid(quad[0], quad[1]), quad[1], quad[2], mid(quad[3], quad[2])]]
        : [[quad[0], quad[1], mid(quad[1], quad[2]), mid(quad[0], quad[3])], [mid(quad[0], quad[3]), mid(quad[1], quad[2]), quad[2], quad[3]]])
      : [quad];
    for (const p of parts) {
      const pcx = p.reduce((a, q) => a + q[0], 0) / 4, pcz = p.reduce((a, q) => a + q[1], 0) / 4;
      const kind: FieldKind = forest > 0.16 || (steep && r() < 0.7) ? "forest" : pickKind(r());
      fields.push({ kind, poly: p, angle: r() < 0.5 ? e1 : e2, tone: r(), centre: [pcx, pcz] });
    }
    // hedgerows along some field edges (more often near the farm)
    const d = distFromFarm(zone, cx, cz, 0);
    for (const [a, b] of [[quad[0], quad[1]], [quad[0], quad[3]]] as [XZ, XZ][]) {
      if (r() < (d < 600 ? 0.42 : 0.25) && forest < 0.12) hedges.push([a, b]);
    }
  }
  // roads: a few grid lines followed across the hills (dirt / white roads)
  const roads: XZ[][] = [];
  for (const [axis, idx] of [["i", Math.floor(n * 0.3)], ["i", Math.floor(n * 0.72)], ["j", Math.floor(n * 0.24)], ["j", Math.floor(n * 0.66)]] as ["i" | "j", number][]) {
    const line: XZ[] = [];
    for (let k = 0; k <= n; k++) {
      const p = axis === "i" ? nodes[k][idx] : nodes[idx][k];
      if (nearFarm(p[0], p[1])) { if (line.length > 1) roads.push(line.splice(0)); else line.length = 0; continue; }
      line.push(p);
    }
    if (line.length > 1) roads.push(line);
  }
  const trees = placeTrees(zone, terrain, fields, hedges, treeBudget, S);
  const out = { S, x0, z0, fields, hedges, roads, trees };
  cache.set(key, out);
  return out;
}

const mid = (a: XZ, b: XZ): XZ => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];

function placeTrees(zone: FarmZone, terrain: TerrainSource, fields: Field[], hedges: [XZ, XZ][], budget: number, S: number): TreeSpot[] {
  const r = rng(9001);
  const cand: (TreeSpot & { d: number })[] = [];
  const R = S * 0.48;
  const green = new THREE.Color();
  const add = (kind: TreeKind, x: number, z: number, h: number, tintK = 1) => {
    const d = Math.hypot(x - zone.cx, z - zone.cz);
    if (d > R) return;
    const y = terrain.heightAt(x, z) - 0.15;
    const k = (1.0 + r() * 0.34) * tintK;
    green.setRGB(k * (0.95 + r() * 0.1), k * (1.0 + r() * 0.08), k * (0.86 + r() * 0.12));
    cand.push({ kind, x, y, z, h, rot: r() * Math.PI * 2, tint: green.clone(), d });
  };
  const broad: TreeKind[] = ["broadleaf_a", "broadleaf_b", "broadleaf_c"];
  for (const f of fields) {
    const xs = f.poly.map((p) => p[0]), zs = f.poly.map((p) => p[1]);
    const bx0 = Math.min(...xs), bx1 = Math.max(...xs), bz0 = Math.min(...zs), bz1 = Math.max(...zs);
    const d = Math.hypot(f.centre[0] - zone.cx, f.centre[1] - zone.cz);
    if (f.kind === "forest") {
      const step = d < 500 ? 6.5 : d < 900 ? 8.5 : 11;          // denser near the farm, the painted canopy fills the rest
      for (let z = bz0; z < bz1; z += step) for (let x = bx0; x < bx1; x += step) {
        const px = x + (r() - 0.5) * step * 0.9, pz = z + (r() - 0.5) * step * 0.9;
        if (!inPoly(px, pz, f.poly)) continue;
        add(broad[Math.floor(r() * 3)], px, pz, 10 + r() * 9);
      }
    } else if (f.kind === "olive") {
      const step = 7, c = Math.cos(f.angle), s = Math.sin(f.angle);
      const L = Math.hypot(bx1 - bx0, bz1 - bz0);
      for (let v = -L / 2; v < L / 2; v += step) for (let u = -L / 2; u < L / 2; u += step) {
        const px = f.centre[0] + u * c - v * s + (r() - 0.5) * 0.8, pz = f.centre[1] + u * s + v * c + (r() - 0.5) * 0.8;
        if (inPoly(px, pz, f.poly)) add("olive_a", px, pz, 4.2 + r() * 1.8, 0.95);
      }
    } else if ((f.kind === "meadow" || f.kind === "hay") && r() < 0.45) {
      const k = 1 + Math.floor(r() * 3);
      for (let i = 0; i < k; i++) {
        const px = bx0 + r() * (bx1 - bx0), pz = bz0 + r() * (bz1 - bz0);
        if (inPoly(px, pz, f.poly)) add(broad[Math.floor(r() * 3)], px, pz, 9 + r() * 8);
      }
    }
  }
  for (const [a, b] of hedges) {
    const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const step = 6 + r() * 3;
    for (let t = step / 2; t < L; t += step) {
      if (r() < 0.12) continue;                                       // gaps in the hedge
      const px = a[0] + ((b[0] - a[0]) * t) / L + (r() - 0.5) * 2, pz = a[1] + ((b[1] - a[1]) * t) / L + (r() - 0.5) * 2;
      add(r() < 0.5 ? "broadleaf_b" : "broadleaf_c", px, pz, 6 + r() * 7);
    }
  }
  // keep the nearest trees when the candidates exceed the budget (far woods are carried by the painted canopy)
  cand.sort((p, q) => p.d - q.d);
  return cand.slice(0, budget);
}

// ------------------------------------------------------------------------------------------------ painting
const PALETTE: Record<FieldKind, { base: string[]; line?: string; lineEvery?: number; lineW?: number }> = {
  wheat: { base: ["#d8b65a", "#cfa94c", "#e0c06a"], line: "#b8913c", lineEvery: 9, lineW: 0.7 },
  stubble: { base: ["#d9c58e", "#cdb77c"], line: "#bfa56a", lineEvery: 4, lineW: 0.6 },
  hay: { base: ["#c7c27a", "#b9b86c"], line: "#a7a35a", lineEvery: 6, lineW: 1.2 },
  ploughed: { base: ["#9a7a55", "#8b6c49", "#a4835c"], line: "#72583a", lineEvery: 2.2, lineW: 0.8 },
  meadow: { base: ["#6c9a3c", "#628f36", "#77a544"] },
  green: { base: ["#86744f"], line: "#4f8a2e", lineEvery: 2.4, lineW: 1.4 },
  olive: { base: ["#b3ab73", "#a99f68"] },
  vineyard: { base: ["#a58d61", "#9b845a"], line: "#4b7a2c", lineEvery: 2.8, lineW: 1.2 },
  forest: { base: ["#3f6229", "#365a25", "#46692e"] },
};

function noiseCanvas(size: number, seed: number, scale: number) {
  const c = document.createElement("canvas"); c.width = c.height = size;
  const g = c.getContext("2d")!, img = g.createImageData(size, size);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    // tileable: noise on a torus
    const a = (x / size) * Math.PI * 2, b = (y / size) * Math.PI * 2;
    const v = fbm(Math.cos(a) * scale + seed, Math.sin(a) * scale + Math.cos(b) * scale, 4) * 0.5 + fbm(Math.sin(b) * scale - seed, Math.cos(b) * scale + 3, 3) * 0.5;
    const k = Math.max(0, Math.min(255, 128 + v * 150));
    const i = (y * size + x) * 4; img.data[i] = img.data[i + 1] = img.data[i + 2] = k; img.data[i + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  return c;
}

const texCache = new Map<string, THREE.CanvasTexture>();

/** Painted ground of the whole terrain (the farm zone is lawn; the real plots are drawn on top in 3D). */
export function landcoverTexture(cs: Countryside, zone: FarmZone, size: number): THREE.CanvasTexture {
  const key = `${cs.x0}:${cs.z0}:${cs.S}:${size}:${cs.trees.length}`;
  const hit = texCache.get(key); if (hit) return hit;
  const c = document.createElement("canvas"); c.width = c.height = size;
  const g = c.getContext("2d")!;
  const k = size / cs.S;
  const P = ([x, z]: XZ): [number, number] => [(x - cs.x0) * k, (z - cs.z0) * k];
  const r = rng(77);
  g.fillStyle = "#567f31"; g.fillRect(0, 0, size, size);
  for (const f of cs.fields) {
    const pal = PALETTE[f.kind];
    g.save();
    g.beginPath(); f.poly.forEach((p, i) => { const [x, y] = P(p); if (i) g.lineTo(x, y); else g.moveTo(x, y); }); g.closePath();
    g.fillStyle = pal.base[Math.floor(f.tone * pal.base.length)]; g.fill();
    g.clip();
    if (pal.line) {
      const [cx, cy] = P(f.centre), L = 260 * k, step = Math.max(1.2, pal.lineEvery! * k);
      g.translate(cx, cy); g.rotate(f.angle);
      g.strokeStyle = pal.line; g.lineWidth = Math.max(0.6, pal.lineW! * k); g.globalAlpha = 0.75;
      g.beginPath();
      for (let v = -L; v < L; v += step) { g.moveTo(-L, v); g.lineTo(L, v); }
      g.stroke();
      g.globalAlpha = 1;
    } else if (f.kind === "olive") {
      // the olive trees themselves are 3D; underneath, the dry grass is darker in their shade
      g.fillStyle = "rgba(96,104,58,0.35)";
      const [cx, cy] = P(f.centre);
      g.translate(cx, cy); g.rotate(f.angle);
      for (let v = -260 * k; v < 260 * k; v += 7 * k) for (let u = -260 * k; u < 260 * k; u += 7 * k) { g.beginPath(); g.arc(u, v, 2.4 * k, 0, 6.283); g.fill(); }
    } else if (f.kind === "forest") {
      // canopy seen from above: overlapping crowns, lit tops and dark gaps
      const xs = f.poly.map((p) => P(p)[0]), ys = f.poly.map((p) => P(p)[1]);
      const bx0 = Math.min(...xs), bx1 = Math.max(...xs), by0 = Math.min(...ys), by1 = Math.max(...ys);
      const nCrowns = Math.min(4000, Math.round(((bx1 - bx0) * (by1 - by0)) / Math.max(4, 22 * k * k)));
      for (let i = 0; i < nCrowns; i++) {
        const x = bx0 + r() * (bx1 - bx0), y = by0 + r() * (by1 - by0), s = (2.5 + r() * 3.5) * k;
        g.fillStyle = r() < 0.5 ? "#2b4a1c" : r() < 0.5 ? "#4d7433" : "#3a5f27";
        g.beginPath(); g.arc(x, y, s, 0, 6.283); g.fill();
      }
    } else if (f.kind === "meadow") {
      g.globalAlpha = 0.25; g.fillStyle = r() < 0.5 ? "#9cc160" : "#5f8f35";
      const [cx, cy] = P(f.centre); g.beginPath(); g.arc(cx, cy, 40 * k, 0, 6.283); g.fill(); g.globalAlpha = 1;
    }
    g.restore();
  }
  // hedgerows (the trees are 3D; this is their shade and the scrub at their feet)
  g.lineCap = "round";
  for (const [a, b] of cs.hedges) {
    const [ax, ay] = P(a), [bx, by] = P(b);
    g.strokeStyle = "rgba(52,78,32,0.85)"; g.lineWidth = Math.max(1.5, 5 * k);
    g.beginPath(); g.moveTo(ax, ay); g.lineTo(bx, by); g.stroke();
  }
  // white roads
  for (const line of cs.roads) {
    g.strokeStyle = "#d9c9a0"; g.lineWidth = Math.max(1.5, 4.5 * k);
    g.beginPath(); line.forEach((p, i) => { const [x, y] = P(p); if (i) g.lineTo(x, y); else g.moveTo(x, y); }); g.stroke();
    g.strokeStyle = "rgba(160,140,100,0.5)"; g.lineWidth = Math.max(0.8, 1.2 * k); g.stroke();
  }
  // farm zone: lawn
  const m = farmMargin(zone);
  const [fx0, fy0] = P([zone.x0 - m * 0.55, zone.z0 - m * 0.55]), [fx1, fy1] = P([zone.x1 + m * 0.55, zone.z1 + m * 0.55]);
  const grad = g.createRadialGradient((fx0 + fx1) / 2, (fy0 + fy1) / 2, 0, (fx0 + fx1) / 2, (fy0 + fy1) / 2, Math.max(fx1 - fx0, fy1 - fy0) * 0.75);
  grad.addColorStop(0, "#557f30"); grad.addColorStop(0.8, "#537d2f"); grad.addColorStop(1, "rgba(83,125,47,0)");
  g.fillStyle = grad; g.fillRect(fx0 - 40 * k, fy0 - 40 * k, fx1 - fx0 + 80 * k, fy1 - fy0 + 80 * k);
  // lawn texture: darker and lighter patches of grass
  for (let i = 0; i < 260; i++) {
    const x = fx0 - 30 * k + r() * (fx1 - fx0 + 60 * k), y = fy0 - 30 * k + r() * (fy1 - fy0 + 60 * k), rad = (4 + r() * 16) * k;
    g.fillStyle = r() < 0.55 ? "rgba(52,92,30,0.16)" : "rgba(150,190,90,0.12)";
    g.beginPath(); g.ellipse(x, y, rad * 1.6, rad, r() * 3.14, 0, 6.283); g.fill();
  }
  // natural variation: two scales of soft noise
  const nz = noiseCanvas(256, 5, 1.6);
  g.globalCompositeOperation = "soft-light"; g.globalAlpha = 0.55;
  const pat1 = g.createPattern(nz, "repeat")!;
  pat1.setTransform(new DOMMatrix().scale((size / 256) * 0.5));
  g.fillStyle = pat1; g.fillRect(0, 0, size, size);
  g.globalAlpha = 0.35;
  const pat2 = g.createPattern(nz, "repeat")!;
  pat2.setTransform(new DOMMatrix().scale((size / 256) * 0.09).rotate(30));
  g.fillStyle = pat2; g.fillRect(0, 0, size, size);
  g.globalCompositeOperation = "source-over"; g.globalAlpha = 1;
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 16; t.generateMipmaps = true; t.minFilter = THREE.LinearMipmapLinearFilter;
  texCache.set(key, t);
  return t;
}
