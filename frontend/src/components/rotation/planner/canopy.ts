/**
 * Dense crop canopy ("carpet") for the beds: the 3D plants are few and exaggerated, so on their own a field looks
 * sparse. Under them each bed gets 1-3 stacked layers textured with rows of photographed leaves (same CC0 leaf
 * atlas as the trees), tinted per crop, with the fruit colour at maturity. Rows follow the same direction and
 * spacing as the 3D plants, so the two match. It is a picture of the declared crop, never extra data.
 */
import * as THREE from "three";
import { Stage } from "./cropLibrary";
import { rng } from "./engine/noise";

interface Look { leaf: string; dark: string; fruit?: string; fruitShare?: number; blades?: boolean; ripe?: string; full?: boolean }

/** Visual look per crop (leaf tint, fruit colour). Generic by group when a crop has no entry. */
const LOOK: Record<string, Look> = {
  tomato: { leaf: "#5f9142", dark: "#2f5426", fruit: "#d8342a", fruitShare: 0.16 },
  pepper: { leaf: "#4f8a3c", dark: "#2a4f22", fruit: "#cf2f25", fruitShare: 0.1 },
  eggplant: { leaf: "#5d7f4f", dark: "#2f4a2a", fruit: "#3d2048", fruitShare: 0.1 },
  zucchini: { leaf: "#5f9446", dark: "#2f5528", fruit: "#e8c23a", fruitShare: 0.04 },
  cucumber: { leaf: "#5f9446", dark: "#2f5528", fruit: "#e8c23a", fruitShare: 0.04 },
  pumpkin: { leaf: "#6a9a48", dark: "#36592a", fruit: "#e07b22", fruitShare: 0.07 },
  melon: { leaf: "#6a9a48", dark: "#36592a", fruit: "#d9c27a", fruitShare: 0.06 },
  watermelon: { leaf: "#5f9446", dark: "#2f5528", fruit: "#3f6e2e", fruitShare: 0.06 },
  lettuce: { leaf: "#a6d36a", dark: "#5f9a3c" },
  cabbage: { leaf: "#8fb79a", dark: "#4f7a5e" },
  spinach: { leaf: "#4f8f3a", dark: "#2a5622" },
  potato: { leaf: "#5a8c40", dark: "#2f5426", fruit: "#f2efe6", fruitShare: 0.03 },
  carrot: { leaf: "#78b04a", dark: "#3f6e2a", blades: true },
  onion: { leaf: "#7fa86a", dark: "#4a6e3e", blades: true },
  garlic: { leaf: "#86ad6e", dark: "#4f7042", blades: true },
  leek: { leaf: "#6f9e66", dark: "#3f6a3a", blades: true },
  bean: { leaf: "#5a9446", dark: "#2f5a28" },
  green_bean: { leaf: "#5a9446", dark: "#2f5a28" },
  pea: { leaf: "#7cae5e", dark: "#43703a" },
  wheat: { leaf: "#8db654", dark: "#5e8638", blades: true, ripe: "#d8b45a", full: true },
  barley: { leaf: "#94b85a", dark: "#64883c", blades: true, ripe: "#dcc070", full: true },
  maize: { leaf: "#6a9c3e", dark: "#3a6426", blades: true },
  sunflower: { leaf: "#5f9442", dark: "#33582a", fruit: "#f2c232", fruitShare: 0.12 },
};
const BY_GROUP: Record<string, Look> = {
  frutto: { leaf: "#5c8f42", dark: "#2f5426" }, foglia: { leaf: "#8cc462", dark: "#4f8a3a" }, radice: { leaf: "#6fa44c", dark: "#3c6a2c" },
  legume: { leaf: "#5f9646", dark: "#33602a" }, cereale: { leaf: "#8db654", dark: "#5e8638", blades: true, full: true },
};
export const lookOf = (crop: string, group: string): Look => LOOK[crop] ?? BY_GROUP[group] ?? BY_GROUP.frutto;

// ------------------------------------------------------------------ leaf sprite (photo + alpha mask)
let sprite: HTMLCanvasElement | null = null;
/** Builds once an RGBA image of a leafy twig from the atlas (diffuse + separate alpha), as a grey-scale stamp. */
function leafSprite(diff: HTMLImageElement, alpha: HTMLImageElement) {
  if (sprite) return sprite;
  const W = 256, H = 280;                      // left spray, upper half of the atlas: x 0-470, y 0-512 of 1024
  const c = document.createElement("canvas"); c.width = W; c.height = H;
  const g = c.getContext("2d")!;
  g.drawImage(diff, 0, 0, 470, 512, 0, 0, W, H);
  const col = g.getImageData(0, 0, W, H);
  g.clearRect(0, 0, W, H); g.drawImage(alpha, 0, 0, 470, 512, 0, 0, W, H);
  const a = g.getImageData(0, 0, W, H);
  for (let i = 0; i < col.data.length; i += 4) {
    const l = (col.data[i] * 0.3 + col.data[i + 1] * 0.59 + col.data[i + 2] * 0.11) / 255;   // keep the leaf detail as light/shade
    const v = Math.min(255, l * 1.7 * 255);
    col.data[i] = col.data[i + 1] = col.data[i + 2] = v;
    col.data[i + 3] = a.data[i] > 120 ? 255 : 0;
  }
  g.putImageData(col, 0, 0);
  sprite = c;
  return c;
}

const cache = new Map<string, THREE.CanvasTexture>();

/**
 * Texture of one tile: rows run along V. The tile is one row spacing wide (U) and two spacings long (V).
 * band = share of the row spacing covered by foliage at this layer (0..1).
 */
export function canopyTexture(crop: string, group: string, stage: Stage, band: number, layer: number, diff: HTMLImageElement, alpha: HTMLImageElement) {
  const key = `${crop}|${stage}|${band.toFixed(2)}|${layer}`;
  const hit = cache.get(key); if (hit) return hit;
  const look = lookOf(crop, group);
  const W = 128, H = 256;
  const c = document.createElement("canvas"); c.width = W; c.height = H;
  const g = c.getContext("2d")!;
  const r = rng(crop.length * 97 + layer * 13 + Math.round(band * 100));
  const ripe = stage === "mature" && look.ripe;
  const leaf = ripe ? look.ripe! : look.leaf, dark = ripe ? shade(look.ripe!, 0.72) : look.dark;
  const bw = (look.full ? Math.max(band, 0.96) : band) * W;
  const x0 = (W - bw) / 2;
  const tinted = tintCanvas(leafSprite(diff, alpha), leaf), tintedDark = tintCanvas(leafSprite(diff, alpha), dark);
  // dense under-layer, then lit leaves on top; stamps wrap vertically so the tile repeats along the row
  const stamp = (img: HTMLCanvasElement, n: number, size: number) => {
    for (let i = 0; i < n; i++) {
      const x = x0 + r() * bw, y = r() * H, s = size * (0.7 + r() * 0.6), rot = r() * Math.PI * 2;
      for (const dy of [0, -H, H]) {
        if (y + dy < -s || y + dy > H + s) continue;
        g.save(); g.translate(x, y + dy); g.rotate(rot); g.drawImage(img, -s / 2, -s * 0.55, s, s * 1.1); g.restore();
      }
    }
  };
  // bottom layer: an opaque under-storey across the band, so the bed never shows bare soil from a distance
  // (alpha-tested mipmaps would otherwise thin the foliage away)
  if (layer === 0) { g.fillStyle = dark; g.fillRect(x0, 0, bw, H); }
  if (look.blades) {
    // grasses and alliums: upright blades seen from above = fine strokes
    g.lineCap = "round";
    for (let i = 0; i < 900; i++) {
      const x = x0 + r() * bw, y = r() * H, a = (r() - 0.5) * 1.2, len = 8 + r() * 14;
      g.strokeStyle = r() < 0.45 ? dark : r() < 0.5 ? leaf : shade(leaf, 1.15);
      g.lineWidth = 1 + r() * 1.6;
      g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.sin(a) * len, y + Math.cos(a) * len * 0.5); g.stroke();
    }
  } else {
    const size = Math.max(16, Math.min(46, bw * 0.55));
    stamp(tintedDark, Math.round((bw * H) / (size * size) * 2.2), size);
    stamp(tinted, Math.round((bw * H) / (size * size) * 2.6), size * 0.85);
  }
  if (look.fruit && stage === "mature" && layer > 0) {
    const n = Math.round((bw * H) / 90 * (look.fruitShare ?? 0.1));
    for (let i = 0; i < n; i++) {
      const x = x0 + bw * (0.1 + r() * 0.8), y = r() * H, s = 2.5 + r() * 3.2;
      const grad = g.createRadialGradient(x - s * 0.3, y - s * 0.3, s * 0.2, x, y, s);
      grad.addColorStop(0, shade(look.fruit, 1.35)); grad.addColorStop(1, shade(look.fruit, 0.8));
      g.fillStyle = grad; g.beginPath(); g.arc(x, y, s, 0, Math.PI * 2); g.fill();
    }
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace; t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8;
  t.generateMipmaps = true; t.minFilter = THREE.LinearMipmapLinearFilter;
  cache.set(key, t);
  return t;
}

function shade(hex: string, k: number) { const c = new THREE.Color(hex).multiplyScalar(k); return `#${c.getHexString()}`; }

function tintCanvas(src: HTMLCanvasElement, color: string) {
  const c = document.createElement("canvas"); c.width = src.width; c.height = src.height;
  const g = c.getContext("2d")!;
  g.drawImage(src, 0, 0);
  g.globalCompositeOperation = "multiply"; g.fillStyle = color; g.fillRect(0, 0, c.width, c.height);
  g.globalCompositeOperation = "destination-in"; g.drawImage(src, 0, 0);
  return c;
}

/** Texture coordinates for a bed carpet: U across the rows (one unit per row spacing, row centres at 0.5), V along. */
export function carpetUV(g: THREE.BufferGeometry, alongY: boolean, firstRow: number, between: number) {
  const p = g.attributes.position, uv = new Float32Array(p.count * 2);
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getZ(i);            // shape lies in XZ, z = plot-local y
    const across = alongY ? x : y, along = alongY ? y : x;
    uv[i * 2] = (across - firstRow) / between + 0.5;
    uv[i * 2 + 1] = along / (between * 2);
  }
  g.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
  return g;
}

/** Alpha-tested foliage keeps its coverage at a distance (mipmaps average the alpha below the threshold). */
export function sharpAlpha<T extends THREE.Material>(m: T): T {
  m.onBeforeCompile = (sh) => {
    sh.fragmentShader = sh.fragmentShader.replace("#include <alphatest_fragment>",
      "diffuseColor.a = clamp((diffuseColor.a - 0.5) / max(fwidth(diffuseColor.a), 0.0001) + 0.5, 0.0, 1.0);\n#include <alphatest_fragment>");
  };
  m.customProgramCacheKey = () => "sharp-alpha";
  return m;
}
