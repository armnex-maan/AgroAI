// Botanical generators for the AgroAI crop library. Units: metres, real proportions; the build script then
// normalises every model to 1 m of height (the planner scales it by the FAO-56 height of the crop).
// Each generator returns { LOD0: {part: geometry}, LOD1: {...}, LOD2: {...} } (optionally LOD0_green / LOD1_green
// for cereals before ripening). Part names drive the growth stages: fruit, flower, ear, cob, silk, tassel are
// hidden or shown depending on the stage.
import { along, blade, C, cone, cyl, ico, lathe, merge, paint, palmate, rng, solid, tube, xf } from "./geometry.mjs";

const GOLD = 2.39996; // golden angle: leaves arranged like real phyllotaxis
const deg = (d) => (d * Math.PI) / 180;

/** A leaf geometry placed at `at`, pointing to azimuth `az`, tilted by `pitch` (radians, + up). */
function leafAt(geo, at, az, pitch = 0, roll = 0) { return xf(geo, { p: at, r: [-pitch, az, roll] }); }

/** Compound (pinnate) leaf: petiole + pairs of leaflets + terminal one, along +Z. */
function compoundLeaf({ len, leaflet, pairs, base, tip, seed, lod }) {
  const parts = [tube([[0, 0, 0], [0, len * 0.12, len * 0.5], [0, len * 0.05, len]], len * 0.025, "#4e7a31", { seg: lod ? 4 : 2, radial: lod ? 4 : 3 })];
  const r = rng(seed);
  for (let i = 0; i < pairs; i++) {
    const t = 0.3 + (0.6 * i) / Math.max(1, pairs - 1), y = len * (0.12 * Math.sin(Math.PI * t));
    for (const side of [-1, 1]) {
      const lf = blade({ ...leaflet, seed: seed + i * 7 + side, segL: lod ? 4 : 2, segW: lod ? 1 : 1, base, tip });
      parts.push(leafAt(lf, [0, y, len * t], side * deg(62 + r() * 15), deg(5)));
    }
  }
  parts.push(leafAt(blade({ ...leaflet, L: leaflet.L * 1.15, seed: seed + 99, segL: lod ? 4 : 2, segW: 1, base, tip }), [0, len * 0.05, len], 0, deg(-5)));
  return merge(parts);
}

// ----------------------------------------------------------------------------------------- Solanaceae
function solanaceous({ seed, h, leafCount, leafSpread, makeLeaf, fruits, flowers, stake = false, branches = 1, lod1Leaf }) {
  const r = rng(seed);
  const stem = [], leaves = [], fruit = [], flower = [];
  // stems: a main stem that forks into `branches`
  const tops = [];
  stem.push(tube([[0, 0, 0], [0.01, h * 0.25, 0], [0, h * 0.4, 0.01]], h * 0.012, "#5a7d33", { seg: 4, radial: 5 }));
  for (let b = 0; b < branches; b++) {
    const a = (b / branches) * Math.PI * 2 + r(), spread = branches > 1 ? h * 0.18 : h * 0.02;
    const top = [Math.cos(a) * spread, h, Math.sin(a) * spread];
    tops.push(top);
    stem.push(tube([[0, h * 0.4, 0.01], [top[0] * 0.5, h * 0.7, top[2] * 0.5], top], h * 0.009, "#5a7d33", { seg: 5, radial: 5 }));
  }
  for (let i = 0; i < leafCount; i++) {
    const t = 0.15 + 0.8 * (i / leafCount), az = i * GOLD;
    const b = tops[i % tops.length], ax = b[0] * t * 0.8, az0 = b[2] * t * 0.8;
    leaves.push(leafAt(makeLeaf(seed + i, true), [ax, h * (0.1 + 0.85 * t), az0], az, deg(10 - 35 * t + r() * 10)));
  }
  if (stake) stem.push(solid(xf(cyl(0.011, 0.011, h * 1.12, 4), { p: [0.04, 0, 0.03] }), "#8a6a44", 0.05));
  fruits.forEach((f, i) => fruit.push(xf(f.geo, { p: f.at, r: f.rot ?? [0, i, 0] })));
  flowers?.forEach((f) => flower.push(xf(f.geo, { p: f.at })));

  // LOD1: fewer, simpler leaves, same fruits but low poly
  const l1 = [];
  for (let i = 0; i < Math.ceil(leafCount / 2); i++) {
    const t = 0.15 + 0.8 * (i / Math.ceil(leafCount / 2)), b = tops[i % tops.length];
    l1.push(leafAt(lod1Leaf(seed + i), [b[0] * t * 0.8, h * (0.1 + 0.85 * t), b[2] * t * 0.8], i * GOLD, deg(5 - 30 * t)));
  }
  const f1 = fruits.filter((_, i) => i % 2 === 0).map((f) => xf(solid(ico(f.r1 ?? 0.03, 0), f.color), { p: f.at }));
  return {
    LOD0: { stem: merge(stem), leaves: merge(leaves), fruit: merge(fruit), flower: merge(flower) },
    LOD1: { stem: merge([tube([[0, 0, 0], [0, h, 0]], h * 0.012, "#5a7d33", { seg: 2, radial: 3 })]), leaves: merge(l1), fruit: merge(f1) },
    LOD2: { leaves: blob(h, leafSpread, "#4c7f34", fruits[0]?.color, seed) },
  };
}

/** Far LOD: a low-poly canopy with a hint of fruit colour. */
function blob(h, w, leaf, fruit, seed) {
  const r = rng(seed), cl = C(leaf), cf = fruit ? C(fruit) : null;
  return paint(xf(ico(0.5, 0), { p: [0, h * 0.5, 0], s: [w, h, w] }), () => (cf && r() < 0.22 ? cf : cl.clone().multiplyScalar(0.9 + r() * 0.2)));
}

function tomato() {
  const h = 1, r = rng(11), fruits = [], flowers = [];
  const trusses = [[0.32, 5, "#c9301f"], [0.46, 5, "#d6402a"], [0.6, 4, "#e47a2d"], [0.74, 4, "#82a83c"]];
  trusses.forEach(([y, n, color], k) => {
    const a = k * 2.1;
    for (let i = 0; i < n; i++) {
      const rad = 0.028 + r() * 0.006;
      fruits.push({ geo: lathe([[0, 0], [rad, rad * 0.75], [rad * 0.7, rad * 1.55], [0, rad * 1.7]], { seg: 7, color, tipColor: color, seed: k * 10 + i }),
        at: [Math.cos(a) * 0.13 + (i % 3) * 0.035 - 0.03, y - (i >> 1) * 0.04, Math.sin(a) * 0.13 + (i % 2) * 0.03], color, r1: rad });
    }
  });
  for (let i = 0; i < 6; i++) flowers.push({ geo: solid(cone(0.012, 0.012, 5), "#f2d23a"), at: [Math.cos(i) * 0.1, 0.86 + (i % 2) * 0.04, Math.sin(i) * 0.1] });
  return solanaceous({
    seed: 11, h, leafCount: 16, leafSpread: 0.6, stake: true, fruits, flowers,
    makeLeaf: (s) => compoundLeaf({ len: 0.28, leaflet: { L: 0.095, W: 0.056, profile: "ovate", rise: 0.15, droop: 0.4, fold: 0.2, wave: 0.25 },
      pairs: 3, base: "#3f6e2b", tip: "#5f9640", seed: s, lod: true }),
    lod1Leaf: (s) => blade({ L: 0.26, W: 0.15, segL: 3, segW: 1, profile: "lanceolate", base: "#3f6e2b", tip: "#5f9640", seed: s }),
  });
}

function pepper() {
  const h = 0.7, r = rng(21), fruits = [], flowers = [];
  for (let i = 0; i < 7; i++) {
    const ripe = i < 5, color = ripe ? (i % 3 === 2 ? "#e3a21a" : "#bf2418") : "#3f7a2a", a = i * 1.9, y = 0.22 + r() * 0.3;
    const geo = merge([lathe([[0, 0], [0.018, 0.004], [0.034, 0.022], [0.037, 0.06], [0.03, 0.088], [0.01, 0.097], [0, 0.1]], { seg: 8, lobes: 4, lobeDepth: 0.12, color, seed: i }),
      solid(xf(cyl(0.004, 0.006, 0.03, 5), { p: [0, 0.095, 0] }), "#3d6b25")]);
    fruits.push({ geo: xf(geo, { r: [Math.PI, 0, 0.25] }), at: [Math.cos(a) * 0.12, y + 0.1, Math.sin(a) * 0.12], color, r1: 0.035 });
  }
  for (let i = 0; i < 5; i++) flowers.push({ geo: solid(cone(0.01, 0.008, 5), "#f4f2e6"), at: [Math.cos(i * 1.3) * 0.15, 0.55 + r() * 0.1, Math.sin(i * 1.3) * 0.15] });
  return solanaceous({
    seed: 21, h, leafCount: 46, leafSpread: 0.55, branches: 4, fruits, flowers,
    makeLeaf: (s) => blade({ L: 0.11, W: 0.055, segL: 4, segW: 1, profile: "ovate", rise: 0.2, droop: 0.45, fold: 0.15, base: "#2f5d22", tip: "#467f32", rib: "#5c9640", seed: s }),
    lod1Leaf: (s) => blade({ L: 0.16, W: 0.09, segL: 2, segW: 1, profile: "ovate", base: "#2f5d22", tip: "#467f32", seed: s }),
  });
}

function eggplant() {
  const h = 0.8, r = rng(31), fruits = [], flowers = [];
  for (let i = 0; i < 4; i++) {
    const a = i * 1.6;
    const geo = merge([lathe([[0, 0], [0.025, 0.012], [0.042, 0.05], [0.04, 0.11], [0.028, 0.16], [0.012, 0.18], [0, 0.185]], { seg: 12, color: "#3a1b47", tipColor: "#4d2860", seed: i }),
      solid(xf(cone(0.03, 0.035, 6), { p: [0, 0.165, 0] }), "#557a3a")]);
    fruits.push({ geo: xf(geo, { r: [Math.PI, 0, 0.35] }), at: [Math.cos(a) * 0.14, 0.32 + r() * 0.12, Math.sin(a) * 0.14], color: "#3a1b47", r1: 0.045 });
  }
  for (let i = 0; i < 4; i++) flowers.push({ geo: solid(cone(0.014, 0.01, 5), "#8d6bc2"), at: [Math.cos(i * 1.7) * 0.18, 0.62 + r() * 0.1, Math.sin(i * 1.7) * 0.18] });
  return solanaceous({
    seed: 31, h, leafCount: 16, leafSpread: 0.6, branches: 2, fruits, flowers,
    makeLeaf: (s) => blade({ L: 0.2, W: 0.12, segL: 5, segW: 2, profile: "ovate", rise: 0.15, droop: 0.5, fold: 0.18, wave: 0.35, base: "#4d6b3f", tip: "#6a8a55", rib: "#7a5d8c", seed: s }),
    lod1Leaf: (s) => blade({ L: 0.24, W: 0.15, segL: 2, segW: 1, profile: "ovate", base: "#4d6b3f", tip: "#6a8a55", seed: s }),
  });
}

function potato() {
  const h = 0.6, r = rng(41), flowers = [];
  for (let i = 0; i < 10; i++) {
    const a = r() * 6.28, d = 0.05 + r() * 0.15;
    flowers.push({ geo: merge([solid(cone(0.014, 0.008, 5), i % 3 ? "#f1eef7" : "#c9b6e6"), solid(xf(cone(0.004, 0.01, 4), { p: [0, 0.006, 0] }), "#f2cf2b")]),
      at: [Math.cos(a) * d, 0.55 + r() * 0.08, Math.sin(a) * d] });
  }
  return solanaceous({
    seed: 41, h, leafCount: 22, leafSpread: 0.65, branches: 4, fruits: [], flowers,
    makeLeaf: (s) => compoundLeaf({ len: 0.22, leaflet: { L: 0.075, W: 0.05, profile: "ovate", rise: 0.15, droop: 0.35, fold: 0.15, wave: 0.15 },
      pairs: 2, base: "#3a6a2c", tip: "#58903e", seed: s, lod: true }),
    lod1Leaf: (s) => blade({ L: 0.2, W: 0.12, segL: 2, segW: 1, profile: "lanceolate", base: "#3a6a2c", tip: "#58903e", seed: s }),
  });
}

// ----------------------------------------------------------------------------------------- Cucurbits
function cucurbit({ seed, leafR, leaves, fruitGeo, fruitColor, fruitCount, fruitR, spread }) {
  const r = rng(seed), lv = [], st = [], fr = [], fl = [];
  for (let i = 0; i < leaves; i++) {
    const az = i * GOLD, d = spread * (0.35 + r() * 0.55), hgt = 0.12 + r() * 0.22;
    const tip = [Math.cos(az) * d, hgt, Math.sin(az) * d];
    st.push(tube([[0, 0.02, 0], [tip[0] * 0.5, hgt * 0.85, tip[2] * 0.5], tip], 0.008, "#6c9a48", { seg: 4, radial: 4, taper: 0.3 }));
    const leaf = palmate({ R: leafR * (0.8 + r() * 0.4), seed: seed + i, rings: 4, seg: 18 });
    lv.push(xf(leaf, { p: tip, r: [deg(-18 - r() * 25), az + Math.PI / 2, deg((r() - 0.5) * 20)] }));
  }
  for (let i = 0; i < fruitCount; i++) {
    const a = r() * 6.28, d = spread * (0.15 + r() * 0.35);
    fr.push(xf(fruitGeo(i), { p: [Math.cos(a) * d, fruitR * 0.8, Math.sin(a) * d], r: [0, a, 0] }));
  }
  for (let i = 0; i < 3; i++) {
    const a = r() * 6.28, d = spread * 0.25;
    fl.push(xf(merge([solid(xf(cone(0.032, 0.07, 6), { r: [Math.PI, 0, 0], p: [0, 0.07, 0] }), "#f2b21c"), solid(cyl(0.004, 0.004, 0.06, 4), "#6c9a48")]),
      { p: [Math.cos(a) * d, 0.08, Math.sin(a) * d], r: [deg(25), a, 0] }));
  }
  const l1 = [];
  for (let i = 0; i < Math.ceil(leaves / 2); i++) {
    const az = i * GOLD * 2, d = spread * 0.55;
    l1.push(xf(palmate({ R: leafR * 1.25, seed: seed + i, rings: 2, seg: 8, spots: 0 }), { p: [Math.cos(az) * d, 0.22, Math.sin(az) * d], r: [deg(-20), az + Math.PI / 2, 0] }));
  }
  return {
    LOD0: { stem: merge(st), leaves: merge(lv), fruit: merge(fr), flower: merge(fl) },
    LOD1: { leaves: merge(l1), fruit: merge(fr.slice(0, 2).map((g) => g)) },
    LOD2: { leaves: blob(0.45, spread * 2, "#3f7a32", fruitColor, seed) },
  };
}

function zucchini() {
  return cucurbit({ seed: 51, leafR: 0.16, leaves: 9, spread: 0.45, fruitCount: 3, fruitR: 0.03, fruitColor: "#2c5a28",
    fruitGeo: (i) => paint(xf(lathe([[0, 0], [0.022, 0.01], [0.028, 0.06], [0.027, 0.16], [0.02, 0.21], [0.008, 0.225], [0, 0.23]], { seg: 10, color: "#2c5a28" }), { r: [0, 0, Math.PI / 2] }),
      (() => { const r = rng(60 + i); return () => (r() < 0.2 ? C("#7aa65a") : C("#2c5a28")); })()) });
}
function pumpkin() {
  return cucurbit({ seed: 61, leafR: 0.2, leaves: 12, spread: 0.7, fruitCount: 2, fruitR: 0.14, fruitColor: "#e07b22",
    fruitGeo: (i) => merge([lathe([[0, 0], [0.09, 0.01], [0.16, 0.06], [0.17, 0.13], [0.12, 0.2], [0.03, 0.215], [0, 0.21]], { seg: 16, lobes: 8, lobeDepth: 0.09, color: "#d9701d", tipColor: "#e98a2c", seed: i }),
      solid(xf(cyl(0.012, 0.016, 0.06, 5), { p: [0, 0.2, 0] }), "#6d5a2e")]) });
}

// ----------------------------------------------------------------------------------------- leafy heads
function cabbage() {
  const r = rng(71), leaves = [], head = [];
  // head: dense ball with wrapped leaf bands
  const ball = xf(ico(0.11, 3), { p: [0, 0.16, 0], s: [1, 0.92, 1] });
  head.push(paint(ball, (v) => { const a = Math.atan2(v.z, v.x); const band = Math.abs(Math.sin(a * 3 + v.y * 40)) < 0.12; return C(band ? "#b8d3b0" : "#86ac85").multiplyScalar(0.95 + r() * 0.08); }));
  for (let i = 0; i < 4; i++) head.push(leafAt(blade({ L: 0.2, W: 0.2, segL: 6, segW: 2, profile: "round", rise: 1.1, droop: 0.9, fold: -0.2, base: "#6f9a7a", tip: "#86ad8f", rib: "#b9d2bd", seed: 72 + i }),
    [0, 0.04, 0], i * Math.PI / 2 + 0.4, deg(20)));
  for (let i = 0; i < 9; i++) leaves.push(leafAt(blade({ L: 0.27, W: 0.26, segL: 6, segW: 3, profile: "round", rise: 0.55, droop: 0.75, fold: -0.15, wave: 0.55, waveF: 4,
    base: "#5f8d7c", tip: "#86ad9f", rib: "#c7dccf", seed: 80 + i }), [0, 0.03, 0], i * GOLD, deg(18)));
  const l1 = []; for (let i = 0; i < 5; i++) l1.push(leafAt(blade({ L: 0.27, W: 0.28, segL: 2, segW: 1, profile: "round", rise: 0.5, droop: 0.7, base: "#5f8d7c", tip: "#86ad9f", seed: 90 + i }), [0, 0.03, 0], i * 1.25, deg(15)));
  return {
    LOD0: { leaves: merge(leaves), head: merge(head) },
    LOD1: { leaves: merge(l1), head: solid(xf(ico(0.11, 1), { p: [0, 0.15, 0] }), "#a9c9a2") },
    LOD2: { leaves: blob(0.3, 0.55, "#7ea896", null, 71) },
  };
}

function lettuce() {
  const leaves = [], r = rng(81);
  for (let i = 0; i < 20; i++) {
    const k = i / 20, inner = 1 - k;
    leaves.push(leafAt(blade({ L: 0.09 + 0.1 * k, W: 0.08 + 0.08 * k, segL: 5, segW: 2, profile: "obovate", rise: 0.4 + 0.9 * inner, droop: 0.3 + 0.5 * k,
      fold: -0.1, wave: 0.9, waveF: 7, base: inner > 0.5 ? "#a8cf63" : "#77a843", tip: inner > 0.5 ? "#cfe58c" : "#9cc85c", seed: 82 + i }),
      [Math.cos(i) * 0.01, 0.01, Math.sin(i) * 0.01], i * GOLD, deg(10 + 30 * inner + r() * 8)));
  }
  const l1 = []; for (let i = 0; i < 7; i++) l1.push(leafAt(blade({ L: 0.17, W: 0.15, segL: 2, segW: 1, profile: "obovate", rise: 0.6, droop: 0.5, base: "#86b84f", tip: "#b5d86b", seed: 99 + i }), [0, 0.01, 0], i * 0.9, deg(20)));
  return { LOD0: { leaves: merge(leaves) }, LOD1: { leaves: merge(l1) }, LOD2: { leaves: blob(0.2, 0.32, "#94c257", null, 81) } };
}

function carrot() {
  const fronds = [], r = rng(91);
  for (let i = 0; i < 9; i++) {
    const az = i * GOLD, lean = deg(15 + r() * 25), L = 0.22 + r() * 0.1;
    const dir = [Math.sin(lean) * Math.cos(az), Math.cos(lean), Math.sin(lean) * Math.sin(az)];
    const end = dir.map((d) => d * L);
    fronds.push(tube([[0, 0.01, 0], [end[0] * 0.5, end[1] * 0.55, end[2] * 0.5], end], 0.003, "#5c8f3a", { seg: 3, radial: 3, taper: 0.4 }));
    for (let j = 0; j < 7; j++) {
      const t = 0.35 + 0.6 * (j / 6), at = end.map((e) => e * t);
      for (const side of [-1, 1]) fronds.push(leafAt(blade({ L: 0.045 * (1.2 - t * 0.5), W: 0.02, segL: 2, segW: 1, profile: "lanceolate", rise: 0.1, droop: 0.2,
        base: "#3f7d2c", tip: "#5d9a3f", seed: 92 + i * 20 + j }), at, az + side * deg(70), deg(30 - 40 * t)));
    }
  }
  const crown = solid(xf(cone(0.018, 0.025, 7), { r: [Math.PI, 0, 0], p: [0, 0.02, 0] }), "#e07a1f");
  const l1 = []; for (let i = 0; i < 5; i++) l1.push(leafAt(blade({ L: 0.3, W: 0.07, segL: 2, segW: 1, profile: "lanceolate", rise: 0.9, droop: 0.6, base: "#3f7d2c", tip: "#5d9a3f", seed: 120 + i }), [0, 0.01, 0], i * 1.25, deg(25)));
  return { LOD0: { leaves: merge(fronds), root: crown }, LOD1: { leaves: merge(l1), root: crown }, LOD2: { leaves: blob(0.3, 0.3, "#4f8f32", null, 91) } };
}

// ----------------------------------------------------------------------------------------- cereals
function cereal({ seed, h, tillers, earLen, awns, ripe, green }) {
  const make = (stemC, leafC, earC) => {
    const r = rng(seed), stems = [], leaves = [], ears = [];
    for (let i = 0; i < tillers; i++) {
      const az = r() * 6.28, lean = deg(r() * 12), hh = h * (0.85 + r() * 0.15);
      const top = [Math.sin(lean) * Math.cos(az) * hh, hh, Math.sin(lean) * Math.sin(az) * hh];
      stems.push(tube([[0, 0, 0], [top[0] * 0.4, hh * 0.5, top[2] * 0.4], top], 0.0035, stemC, { seg: 4, radial: 3, taper: 0.2 }));
      for (let k = 0; k < 2; k++) leaves.push(leafAt(blade({ L: 0.25, W: 0.012, segL: 4, segW: 1, profile: "strap", rise: 0.7, droop: 1.1, fold: 0.3, base: leafC, tip: leafC, seed: seed + i * 3 + k }),
        [top[0] * 0.3, hh * (0.25 + 0.25 * k), top[2] * 0.3], az + k * Math.PI, deg(30)));
      const dir = [top[0] / hh * 0.3, 1, top[2] / hh * 0.3];
      for (let s = 0; s < 8; s++) {
        const t = s / 7, at = [top[0] + dir[0] * earLen * t, top[1] + earLen * t, top[2] + dir[2] * earLen * t];
        ears.push(solid(xf(ico(0.006, 0), { p: [at[0] + (s % 2 ? 0.004 : -0.004), at[1], at[2]], s: [1, 1.6, 0.8] }), earC, 0.1, s));
        if (awns) ears.push(solid(along(cone(0.0008, awns, 3).rotateX(Math.PI / 2), at, [(s % 2 ? 0.25 : -0.25), 1, 0.05]), earC, 0, s));
      }
    }
    const l1 = [];
    for (let i = 0; i < Math.ceil(tillers / 2); i++) { const az = i * 2.3; l1.push(solid(along(cone(0.008, h, 3).rotateX(Math.PI / 2), [0, 0, 0], [Math.cos(az) * 0.08, 1, Math.sin(az) * 0.08]), stemC)); }
    const ear1 = []; for (let i = 0; i < Math.ceil(tillers / 2); i++) { const az = i * 2.3; ear1.push(solid(xf(ico(0.012, 0), { p: [Math.cos(az) * 0.08 * h, h * 1.02, Math.sin(az) * 0.08 * h], s: [1, 3.5, 1] }), earC)); }
    return { lod0: { stem: merge(stems), leaves: merge(leaves), ear: merge(ears) }, lod1: { stem: merge(l1), ear: merge(ear1) } };
  };
  const R = make(ripe.stem, ripe.leaf, ripe.ear), G = make(green.stem, green.leaf, green.ear);
  return { LOD0: R.lod0, LOD1: R.lod1, LOD0_green: G.lod0, LOD1_green: G.lod1,
    LOD2: { stem: paint(cone(0.12, h, 4), () => C(ripe.ear)) }, LOD2_green: { stem: paint(cone(0.12, h, 4), () => C(green.leaf)) } };
}
const wheat = () => cereal({ seed: 101, h: 1, tillers: 7, earLen: 0.09, awns: 0.025,
  ripe: { stem: "#c9a55a", leaf: "#b8975a", ear: "#dcb866" }, green: { stem: "#6f9a3e", leaf: "#5f8f35", ear: "#86ad55" } });
const barley = () => cereal({ seed: 111, h: 1, tillers: 7, earLen: 0.07, awns: 0.09,
  ripe: { stem: "#cdb06c", leaf: "#bfa36a", ear: "#e3c780" }, green: { stem: "#76a046", leaf: "#64923a", ear: "#93b866" } });

function maize() {
  const h = 2, r = rng(121), leaves = [], stem = [], cob = [], silk = [], tassel = [];
  stem.push(tube([[0, 0, 0], [0.005, h * 0.5, 0], [0, h * 0.92, 0.004]], 0.016, "#7fa047", { seg: 6, radial: 6, taper: 0.5 }));
  for (let i = 0; i < 14; i++) {
    const t = 0.06 + 0.8 * (i / 13), az = (i % 2) * Math.PI + (r() - 0.5) * 0.6;
    leaves.push(leafAt(blade({ L: 0.6 + 0.3 * Math.sin(Math.PI * t), W: 0.095, segL: 7, segW: 1, profile: "strap", rise: 0.55, droop: 0.95, fold: 0.35, twist: 0.4,
      base: "#4f7f30", tip: "#78a447", rib: "#a9c97a", seed: 122 + i }), [0, h * t, 0], az, deg(35)));
  }
  for (const [y, a] of [[0.95, 0.6], [0.78, 3.6]]) {
    const ear = merge([lathe([[0, 0], [0.025, 0.015], [0.03, 0.08], [0.026, 0.16], [0.01, 0.2], [0, 0.21]], { seg: 10, color: "#d8c88f", tipColor: "#b9a96e" })]);
    cob.push(xf(ear, { p: [Math.cos(a) * 0.03, y, Math.sin(a) * 0.03], r: [deg(25), a, 0] }));
    silk.push(solid(xf(cone(0.012, 0.05, 5), { p: [Math.cos(a) * 0.08, y + 0.19, Math.sin(a) * 0.08] }), "#8a5a2e"));
  }
  for (let i = 0; i < 7; i++) tassel.push(solid(along(cone(0.0025, 0.22, 3).rotateX(Math.PI / 2), [0, h * 0.92, 0], [Math.cos(i * 0.9) * (i ? 0.7 : 0), 1, Math.sin(i * 0.9) * (i ? 0.7 : 0)]), "#c9a95a"));
  const l1 = []; for (let i = 0; i < 6; i++) l1.push(leafAt(blade({ L: 0.7, W: 0.08, segL: 3, segW: 1, profile: "strap", rise: 0.5, droop: 0.9, base: "#4f7f30", tip: "#78a447", seed: 140 + i }), [0, h * (0.1 + 0.13 * i), 0], i * Math.PI + i * 0.3, deg(30)));
  return {
    LOD0: { stem: merge(stem), leaves: merge(leaves), cob: merge(cob), silk: merge(silk), tassel: merge(tassel) },
    LOD1: { stem: merge([tube([[0, 0, 0], [0, h * 0.95, 0]], 0.018, "#7fa047", { seg: 1, radial: 4 })]), leaves: merge(l1), tassel: merge(tassel.slice(0, 3)) },
    LOD2: { leaves: paint(cone(0.25, h, 5), () => C("#5f8f3a")) },
  };
}

// ----------------------------------------------------------------------------------------- legumes
function bean() {
  const h = 0.45, r = rng(131), stem = [], leaves = [], fruit = [], flower = [];
  for (let b = 0; b < 4; b++) {
    const a = b * 1.6 + r(), top = [Math.cos(a) * 0.12, h, Math.sin(a) * 0.12];
    stem.push(tube([[0, 0, 0], [top[0] * 0.5, h * 0.55, top[2] * 0.5], top], 0.004, "#6a9a3e", { seg: 4, radial: 4 }));
    for (let i = 0; i < 4; i++) {
      const t = 0.3 + 0.7 * (i / 3), at = top.map((c, k) => (k === 1 ? c * t : c * t));
      const az = a + i * GOLD;
      const tri = [0, 1, -1].map((k) => leafAt(blade({ L: 0.07, W: 0.055, segL: 3, segW: 1, profile: "ovate", rise: 0.1, droop: 0.35, fold: 0.1, base: "#4c8a33", tip: "#6aa64a", seed: 132 + b * 10 + i * 3 + k }),
        [0, 0, 0], k * deg(75), 0));
      leaves.push(xf(merge([tube([[0, 0, 0], [0, 0.01, 0.05]], 0.002, "#6a9a3e", { seg: 1, radial: 3 }), ...tri.map((g) => xf(g, { p: [0, 0.01, 0.05] }))]), { p: at, r: [deg(-10), az, 0] }));
    }
    for (let p = 0; p < 3; p++) fruit.push(solid(xf(cyl(0.005, 0.004, 0.11, 5), { p: [top[0] * (0.6 + p * 0.1), h * (0.35 + p * 0.08), top[2] * (0.6 + p * 0.1)], r: [deg(160), a + p, deg(10)] }), "#6e9e3a", 0.1, p));
    flower.push(solid(xf(ico(0.008, 0), { p: [top[0], h * 0.9, top[2]] }), "#f3f1e6"));
  }
  const l1 = []; for (let i = 0; i < 6; i++) l1.push(leafAt(blade({ L: 0.16, W: 0.12, segL: 2, segW: 1, profile: "ovate", base: "#4c8a33", tip: "#6aa64a", seed: 150 + i }), [0, h * (0.3 + 0.1 * i), 0], i * GOLD, deg(0)));
  return { LOD0: { stem: merge(stem), leaves: merge(leaves), fruit: merge(fruit), flower: merge(flower) }, LOD1: { leaves: merge(l1) }, LOD2: { leaves: blob(h, 0.4, "#5a9a3c", null, 131) } };
}

/** Pea (Pisum sativum): slender climbing stems, compound leaves with 2 pairs of round leaflets ending in a tendril,
 *  large leafy stipules at each node, white flowers and hanging flat pods. FAO-56 height 0.5 m. */
function pea() {
  const h = 0.5, r = rng(141), stem = [], leaves = [], fruit = [], flower = [];
  const leaflet = (sd, L) => blade({ L, W: L * 0.78, segL: 3, segW: 1, profile: "ovate", rise: 0.12, droop: 0.3, fold: 0.18, base: "#5f9a57", tip: "#86b874", rib: "#9cc68a", seed: sd });
  for (let b = 0; b < 5; b++) {
    const a = b * 1.26 + r() * 0.6, lean = 0.05 + r() * 0.1;
    const pts = Array.from({ length: 7 }, (_, i) => { const t = i / 6; return [Math.cos(a) * lean * t + (r() - 0.5) * 0.02, h * t * (0.85 + r() * 0.15), Math.sin(a) * lean * t + (r() - 0.5) * 0.02]; });
    stem.push(tube(pts, 0.003, "#7aa65a", { seg: 6, radial: 4 }));
    for (let n = 1; n < 5; n++) {
      const at = pts[n + 1], az = a + n * GOLD + r() * 0.5, L = 0.03 + r() * 0.012;
      // leafy stipules hugging the stem
      leaves.push(leafAt(leaflet(150 + b * 20 + n, L * 1.15), at, az + Math.PI, deg(25)), leafAt(leaflet(151 + b * 20 + n, L), at, az + Math.PI * 0.6, deg(20)));
      // compound leaf: petiole, 2 pairs of leaflets, curling tendril
      const parts = [tube([[0, 0, 0], [0, 0.01, 0.04], [0, 0.015, 0.08]], 0.0018, "#7aa65a", { seg: 2, radial: 3 })];
      for (const [k, z] of [[0, 0.035], [1, 0.065]]) for (const side of [-1, 1])
        parts.push(xf(leaflet(160 + b * 20 + n * 3 + k + side, L), { p: [0, 0.012, z], r: [0, side * deg(70), 0] }));
      parts.push(tube([[0, 0.015, 0.08], [0.01, 0.03, 0.1], [0.02, 0.04, 0.095], [0.016, 0.05, 0.085]], 0.0009, "#8fbf6a", { seg: 4, radial: 3 }));
      leaves.push(xf(merge(parts), { p: at, r: [deg(-15 - r() * 20), az, 0] }));
      if (n >= 3 && r() < 0.55) flower.push(xf(merge([solid(cone(0.011, 0.01, 6), "#f7f6ee"), solid(xf(cone(0.007, 0.008, 5), { p: [0, 0.006, 0.004] }), "#efe9f4")]),
        { p: [at[0] + 0.02, at[1] + 0.02, at[2]], r: [deg(80), az, 0] }));
      if (n >= 2 && n <= 4 && r() < 0.7) {
        const pod = lathe([[0, 0], [0.006, 0.01], [0.008, 0.035], [0.006, 0.06], [0, 0.07]], { seg: 6, color: "#7fb04a", tipColor: "#9cc463", seed: b * 9 + n });
        fruit.push(xf(pod, { p: [at[0], at[1] - 0.01, at[2]], r: [deg(170), az, deg(15)], s: [1, 1, 0.55] }));   // flat pod, hanging
      }
    }
  }
  const l1 = [];
  for (let i = 0; i < 10; i++) l1.push(leafAt(blade({ L: 0.1, W: 0.08, segL: 2, segW: 1, profile: "ovate", base: "#5f9a57", tip: "#86b874", seed: 170 + i }), [0, h * (0.2 + 0.07 * i), 0], i * GOLD, deg(10)));
  return { LOD0: { stem: merge(stem), leaves: merge(leaves), fruit: merge(fruit), flower: merge(flower) },
    LOD1: { stem: merge([tube([[0, 0, 0], [0.02, h * 0.5, 0], [0, h, 0.02]], 0.004, "#7aa65a", { seg: 2, radial: 3 })]), leaves: merge(l1) },
    LOD2: { leaves: blob(h, 0.35, "#6aa65a", "#7fb04a", 141) } };
}

/** crop key (rotation catalogue) -> generator. Every listed crop gets its own GLB. */
export const GENERATORS = { tomato, pepper, eggplant, potato, zucchini, pumpkin, cabbage, lettuce, carrot, wheat, barley, maize, bean, pea };
// rotation crops drawn with a dedicated model of a close relative (same botanical form)
export const ALIASES = { green_bean: "bean", cucumber: "zucchini" };
