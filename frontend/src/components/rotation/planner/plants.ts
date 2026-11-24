/**
 * Procedural low-poly crop models for the Visual Farm Planner (no third-party models).
 * Every model is built at unit height (top ~ y = 1) with natural proportions; the scene scales it
 * uniformly by the FAO-56 height of the crop (times the visual factor shown on screen).
 * A model is a list of parts; each part becomes one InstancedMesh shared by all plants of a bed.
 */
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

export interface Part { geo: THREE.BufferGeometry; color: string; rough?: number }
export interface PlantModel { parts: Part[]; width: number; tris?: number } // width = footprint at unit height

const farCache = new Map<string, PlantModel>();
/** Far level of detail: the plant becomes one low-poly blob with its canopy colour and a hint of fruit colour. */
export function farModel(key: string, group: string): PlantModel {
  const hit = farCache.get(key);
  if (hit) return hit;
  const near = plantModel(key, group);
  const leaf = new THREE.Color(near.parts[0].color);
  if (near.parts[1] && group === "frutto") leaf.lerp(new THREE.Color(near.parts[1].color), 0.25);
  const tall = group === "cereale" || ["maize", "sorghum", "sunflower", "leek", "onion", "garlic"].includes(key);
  const geo = tall ? new THREE.ConeGeometry(near.width * 0.5, 1, 4).translate(0, 0.5, 0)
    : new THREE.IcosahedronGeometry(0.5, 0).scale(near.width, 0.8, near.width).translate(0, 0.42, 0);
  const m: PlantModel = { parts: [{ geo, color: "#" + leaf.getHexString(), rough: 0.9 }], width: near.width, tris: geo.attributes.position.count / 3 };
  farCache.set(key, m);
  return m;
}

const LEAF = "#4f8a3a", LEAF_DARK = "#3c6f2c", LEAF_LIGHT = "#86b84f", BLUE_LEAF = "#6f9a86", STEM = "#5e7d36";

// deterministic pseudo-random, so the same farm always looks the same
function rng(seed: number) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }

const T = new THREE.Object3D();
function place(g: THREE.BufferGeometry, x: number, y: number, z: number, sx = 1, sy = 1, sz = 1, rx = 0, ry = 0, rz = 0) {
  T.position.set(x, y, z); T.rotation.set(rx, ry, rz); T.scale.set(sx, sy, sz); T.updateMatrix();
  const c = g.clone(); c.applyMatrix4(T.matrix); return c;
}
const merge = (gs: THREE.BufferGeometry[]) => {
  const clean = gs.map((g) => { const n = g.index ? g : g; n.deleteAttribute("uv"); return n.index ? n.toNonIndexed() : n; });
  return mergeGeometries(clean, false)!;
};

const ICO = new THREE.IcosahedronGeometry(0.5, 0);
const ICO1 = new THREE.IcosahedronGeometry(0.5, 1);
const SPH = new THREE.IcosahedronGeometry(0.5, 0); // 20 triangles: fruits and leaves are small, low poly is enough
const CYL = new THREE.CylinderGeometry(0.5, 0.5, 1, 5, 1, false);
const CONE = new THREE.ConeGeometry(0.5, 1, 5);
const BOX = new THREE.BoxGeometry(1, 1, 1);

/** Bushy fruiting crop (tomato, pepper, eggplant, potato): leafy clumps, fruits inside, optional stake. */
function bush(seed: number, fruitColor: string | null, fruitShape: "round" | "long", fruitSize: number, stake: boolean, leaf = LEAF): PlantModel {
  const r = rng(seed);
  const leaves: THREE.BufferGeometry[] = [place(CYL, 0, 0.35, 0, 0.04, 0.7, 0.04)];
  for (let i = 0; i < 7; i++) {
    const a = r() * Math.PI * 2, d = 0.08 + r() * 0.18, y = 0.25 + r() * 0.65;
    leaves.push(place(ICO, Math.cos(a) * d, y, Math.sin(a) * d, 0.32 + r() * 0.12, 0.26 + r() * 0.1, 0.32 + r() * 0.12, r(), r(), r()));
  }
  const parts: Part[] = [{ geo: merge(leaves), color: leaf, rough: 0.9 }];
  if (fruitColor) {
    const fr: THREE.BufferGeometry[] = [];
    for (let i = 0; i < 7; i++) {
      const a = r() * Math.PI * 2, d = 0.18 + r() * 0.12, y = 0.2 + r() * 0.6;
      fr.push(fruitShape === "round"
        ? place(SPH, Math.cos(a) * d, y, Math.sin(a) * d, fruitSize, fruitSize, fruitSize)
        : place(SPH, Math.cos(a) * d, y, Math.sin(a) * d, fruitSize * 0.7, fruitSize * 1.8, fruitSize * 0.7, 0.3, 0, 0.2));
    }
    parts.push({ geo: merge(fr), color: fruitColor, rough: 0.45 });
  }
  if (stake) parts.push({ geo: place(BOX, 0.02, 0.55, 0.02, 0.025, 1.1, 0.025), color: "#8b6a43", rough: 1 });
  return { parts, width: 0.55 };
}

/** Running cucurbit: large flat leaves close to the ground, fruits lying on the soil. */
function cucurbit(seed: number, fruit: string, shape: "long" | "round", size: number, stripe = false): PlantModel {
  const r = rng(seed);
  const leaves: THREE.BufferGeometry[] = [];
  for (let i = 0; i < 9; i++) {
    const a = (i / 9) * Math.PI * 2 + r() * 0.4, d = 0.15 + r() * 0.45;
    leaves.push(place(CYL, Math.cos(a) * d, 0.35 + r() * 0.5, Math.sin(a) * d, 0.42, 0.04, 0.42, (r() - 0.5) * 0.9, 0, (r() - 0.5) * 0.9));
    leaves.push(place(CYL, Math.cos(a) * d * 0.6, 0.2 + r() * 0.3, Math.sin(a) * d * 0.6, 0.02, 0.5, 0.02));
  }
  const fr: THREE.BufferGeometry[] = [];
  for (let i = 0; i < (shape === "long" ? 3 : 2); i++) {
    const a = r() * Math.PI * 2, d = 0.3 + r() * 0.3;
    fr.push(shape === "long" ? place(CYL, Math.cos(a) * d, size * 0.4, Math.sin(a) * d, size * 0.45, size * 2.6, size * 0.45, Math.PI / 2, a, 0)
      : place(SPH, Math.cos(a) * d, size * 0.45, Math.sin(a) * d, size, size * 0.9, size * (stripe ? 1.25 : 1)));
  }
  return { parts: [{ geo: merge(leaves), color: LEAF, rough: 0.85 }, { geo: merge(fr), color: fruit, rough: 0.5 }], width: 1.3 };
}

/** Leafy head (lettuce, cabbage) or rosette (chard, spinach, rocket...). */
function head(seed: number, color: string, inner: string, closed: boolean): PlantModel {
  const r = rng(seed);
  const outer: THREE.BufferGeometry[] = [];
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2 + r() * 0.3;
    outer.push(place(SPH, Math.cos(a) * 0.25, 0.32, Math.sin(a) * 0.25, 0.42, 0.55, 0.22, 0, -a, closed ? 0.5 : 0.9));
  }
  const parts: Part[] = [{ geo: merge(outer), color, rough: 0.8 }];
  parts.push({ geo: closed ? place(ICO1, 0, 0.42, 0, 0.55, 0.55, 0.55) : merge([0, 1, 2].map((k) => place(SPH, (k - 1) * 0.08, 0.55, 0, 0.18, 0.7, 0.12, 0, k, 0))), color: inner, rough: 0.7 });
  return { parts, width: 1.0 };
}

/** Upright blades (onion, garlic, leek, shallot, asparagus spears). */
function blades(seed: number, color: string, bulb: string | null): PlantModel {
  const r = rng(seed);
  const b: THREE.BufferGeometry[] = [];
  for (let i = 0; i < 6; i++) b.push(place(CONE, (r() - 0.5) * 0.1, 0.5, (r() - 0.5) * 0.1, 0.06, 1, 0.06, (r() - 0.5) * 0.35, 0, (r() - 0.5) * 0.35));
  const parts: Part[] = [{ geo: merge(b), color, rough: 0.7 }];
  if (bulb) parts.push({ geo: place(SPH, 0, 0.06, 0, 0.22, 0.18, 0.22), color: bulb, rough: 0.6 });
  return { parts, width: 0.3 };
}

/** Feathery root-crop tuft (carrot, radish, turnip, beet, fennel, celery, parsley). */
function tuft(seed: number, color: string, root: string | null, broad = false): PlantModel {
  const r = rng(seed);
  const t: THREE.BufferGeometry[] = [];
  for (let i = 0; i < 9; i++) {
    const a = (i / 9) * Math.PI * 2;
    t.push(broad ? place(SPH, Math.cos(a) * 0.15, 0.5, Math.sin(a) * 0.15, 0.25, 0.9, 0.08, 0, -a, 0.35)
      : place(CONE, Math.cos(a) * 0.08, 0.5, Math.sin(a) * 0.08, 0.18, 1, 0.18, Math.sin(a) * 0.35, 0, -Math.cos(a) * 0.35 + r() * 0.1));
  }
  const parts: Part[] = [{ geo: merge(t), color, rough: 0.8 }];
  if (root) parts.push({ geo: place(SPH, 0, 0.04, 0, 0.2, 0.12, 0.2), color: root, rough: 0.6 });
  return { parts, width: 0.5 };
}

/** Cereal clump (wheat, barley): thin stems with ears on top. */
function cereal(seed: number, stem: string, ear: string): PlantModel {
  const r = rng(seed);
  const s: THREE.BufferGeometry[] = [], e: THREE.BufferGeometry[] = [];
  for (let i = 0; i < 9; i++) {
    const x = (r() - 0.5) * 0.25, z = (r() - 0.5) * 0.25, h = 0.78 + r() * 0.12, tilt = (r() - 0.5) * 0.15;
    s.push(place(CYL, x, h / 2, z, 0.015, h, 0.015, tilt, 0, tilt));
    e.push(place(CYL, x + tilt * h, h + 0.08, z - tilt * h, 0.035, 0.18, 0.035, tilt, 0, tilt));
  }
  return { parts: [{ geo: merge(s), color: stem, rough: 0.9 }, { geo: merge(e), color: ear, rough: 0.9 }], width: 0.3 };
}

/** Tall stalk crops: maize (cobs + tassel), sorghum (panicle), sunflower (head). */
function tall(seed: number, kind: "maize" | "sorghum" | "sunflower"): PlantModel {
  const r = rng(seed);
  const leaves: THREE.BufferGeometry[] = [place(CYL, 0, 0.5, 0, 0.03, 1, 0.03)];
  for (let i = 0; i < 7; i++) {
    const y = 0.15 + i * 0.1, a = i * 2.4;
    leaves.push(kind === "sunflower" ? place(SPH, Math.cos(a) * 0.12, y, Math.sin(a) * 0.12, 0.22, 0.03, 0.18, 0, -a, 0)
      : place(BOX, Math.cos(a) * 0.14, y + 0.04, Math.sin(a) * 0.14, 0.32, 0.01, 0.05, 0, -a, -0.5));
  }
  const parts: Part[] = [{ geo: merge(leaves), color: kind === "sunflower" ? LEAF_DARK : "#5f8f3a", rough: 0.85 }];
  if (kind === "maize") {
    parts.push({ geo: merge([place(CYL, 0.05, 0.55, 0, 0.05, 0.16, 0.05, 0, 0, 0.35), place(CYL, -0.05, 0.45, 0.02, 0.045, 0.14, 0.045, 0, 0, -0.35)]), color: "#e9c75a", rough: 0.6 });
    parts.push({ geo: merge([0, 1, 2, 3].map((k) => place(CYL, 0, 1.03, 0, 0.008, 0.1, 0.008, 0.6, k * 1.57, 0))), color: "#c9a45a" });
  } else if (kind === "sorghum") {
    parts.push({ geo: place(ICO, 0, 1.0, 0, 0.12, 0.18, 0.12), color: "#9c4a2a", rough: 0.8 });
  } else {
    parts.push({ geo: place(CYL, 0, 0.97, 0.04, 0.2, 0.03, 0.2, Math.PI / 2.6, 0, 0), color: "#f2c230", rough: 0.6 });
    parts.push({ geo: place(CYL, 0, 0.975, 0.055, 0.11, 0.035, 0.11, Math.PI / 2.6, 0, 0), color: "#5a3b1c", rough: 0.9 });
  }
  void r;
  return { parts, width: 0.35 };
}

/** Legume bush with small pods; rapeseed / alfalfa as dense low canopy with flowers. */
function legume(seed: number, pod: string, flowers: string | null): PlantModel {
  const m = bush(seed, null, "round", 0, false, "#5c9440");
  const r = rng(seed + 7);
  const extra: THREE.BufferGeometry[] = [];
  for (let i = 0; i < 6; i++) { const a = r() * 6.28; extra.push(place(CYL, Math.cos(a) * 0.22, 0.3 + r() * 0.4, Math.sin(a) * 0.22, 0.03, 0.16, 0.03, 0.3, 0, 0.2)); }
  m.parts.push({ geo: merge(extra), color: pod });
  if (flowers) {
    const f: THREE.BufferGeometry[] = [];
    for (let i = 0; i < 8; i++) { const a = r() * 6.28, d = r() * 0.25; f.push(place(ICO, Math.cos(a) * d, 0.85 + r() * 0.15, Math.sin(a) * d, 0.08, 0.06, 0.08)); }
    m.parts.push({ geo: merge(f), color: flowers });
  }
  return m;
}

const cache = new Map<string, PlantModel>();

/** Model for a crop key (falls back on its rotation group). */
export function plantModel(key: string, group: string): PlantModel {
  const hit = cache.get(key);
  if (hit) return hit;
  const seed = [...key].reduce((a, c) => a * 31 + c.charCodeAt(0), 7);
  let m: PlantModel;
  switch (key) {
    case "tomato": m = bush(seed, "#d63b2a", "round", 0.1, true); break;
    case "pepper": m = bush(seed, "#c9302c", "long", 0.09, false, LEAF_DARK); break;
    case "eggplant": m = bush(seed, "#4b2a5e", "long", 0.11, false, "#4d7a3c"); break;
    case "potato": m = legume(seed, LEAF, "#f3f0e6"); break;
    case "zucchini": m = cucurbit(seed, "#2f5d2a", "long", 0.11); break;
    case "cucumber": m = cucurbit(seed, "#3f7a32", "long", 0.08); break;
    case "pumpkin": m = cucurbit(seed, "#e07b22", "round", 0.3); break;
    case "melon": m = cucurbit(seed, "#d9c98a", "round", 0.24); break;
    case "watermelon": m = cucurbit(seed, "#2f6b2f", "round", 0.3, true); break;
    case "strawberry": m = bush(seed, "#d92b3a", "round", 0.12, false, LEAF_DARK); break;
    case "lettuce": m = head(seed, LEAF_LIGHT, "#b5d86b", true); break;
    case "cabbage": m = head(seed, BLUE_LEAF, "#a9c7a0", true); break;
    case "chicory": m = head(seed, "#7a2f45", "#d8d0c0", true); break;
    case "spinach": case "chard": case "rocket": case "basil": m = head(seed, key === "chard" ? "#3f7a32" : LEAF, key === "chard" ? "#c23b4a" : LEAF_LIGHT, false); break;
    case "onion": m = blades(seed, BLUE_LEAF, "#c79a4a"); break;
    case "garlic": case "shallot": m = blades(seed, BLUE_LEAF, "#e8e2d4"); break;
    case "leek": m = blades(seed, "#5f8f6a", null); break;
    case "asparagus": m = blades(seed, "#6e9a3c", null); break;
    case "carrot": m = tuft(seed, "#4f8f32", "#e07a1f"); break;
    case "radish": m = tuft(seed, LEAF, "#c8324a", true); break;
    case "turnip": m = tuft(seed, LEAF, "#e9dfe6", true); break;
    case "sugar_beet": m = tuft(seed, LEAF_DARK, "#e8dccb", true); break;
    case "celery": case "parsley": case "fennel": m = tuft(seed, key === "fennel" ? "#7aa84a" : LEAF, null); break;
    case "wheat": m = cereal(seed, "#b99a4a", "#d8b35c"); break;
    case "barley": m = cereal(seed, "#bfa25a", "#e0c27a"); break;
    case "maize": m = tall(seed, "maize"); break;
    case "sorghum": m = tall(seed, "sorghum"); break;
    case "sunflower": m = tall(seed, "sunflower"); break;
    case "rapeseed": m = legume(seed, "#5c9440", "#f1d12c"); break;
    case "alfalfa": m = legume(seed, "#5c9440", "#8a6bc4"); break;
    case "bean": case "green_bean": case "pea": case "faba": case "chickpea": case "soybean": m = legume(seed, "#7fae4a", key === "faba" ? "#eeeeee" : null); break;
    default:
      m = group === "cereale" ? cereal(seed, "#b99a4a", "#d8b35c") : group === "foglia" ? head(seed, LEAF, LEAF_LIGHT, false)
        : group === "radice" ? tuft(seed, LEAF, null) : group === "legume" ? legume(seed, "#7fae4a", null) : bush(seed, null, "round", 0, false);
  }
  m.tris = m.parts.reduce((a, p) => a + p.geo.attributes.position.count / 3, 0);
  cache.set(key, m);
  return m;
}

/** Simple tree for shade sections and scenery: trunk + three canopy blobs (about 7 m high at scale 1). */
export function treeModel(seed: number): PlantModel {
  const r = rng(seed);
  const canopy = [0, 1, 2].map(() => place(ICO1, (r() - 0.5) * 1.6, 4.6 + r() * 1.2, (r() - 0.5) * 1.6, 2.8 + r(), 2.4 + r(), 2.8 + r()));
  return { parts: [{ geo: place(CYL, 0, 1.8, 0, 0.35, 3.6, 0.35), color: "#6b4a2f", rough: 1 }, { geo: merge(canopy), color: "#3f6e33", rough: 0.9 }], width: 4 };
}
