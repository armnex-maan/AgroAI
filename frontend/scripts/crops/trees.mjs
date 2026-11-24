// Fruit trees and grapevine for orchards and vineyards (same GLB contract as crops: LOD0 / LOD1 / LOD2,
// parts trunk, leaves, fruit). Real proportions; the build normalises height to 1 (scaled by FAO-56 height).
import * as THREE from "three";
import { blade, C, ico, merge, paint, rng, solid, tube, xf } from "./geometry.mjs";

/** Leafy clump: a lumpy ball (displaced icosahedron) with leaf blades on its surface. */
function clump(r, seed, leaf, leafDark, blades, bladeL) {
  const rnd = rng(seed);
  const ball = new THREE.IcosahedronGeometry(r, 1);
  const p = ball.attributes.position, v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) { v.fromBufferAttribute(p, i); v.multiplyScalar(0.82 + rnd() * 0.3); p.setXYZ(i, v.x, v.y, v.z); }
  ball.computeVertexNormals();
  const parts = [paint(ball, () => C(leafDark).lerp(C(leaf), rnd() * 0.6))];
  for (let i = 0; i < blades; i++) {
    const u = rnd() * 2 - 1, t = rnd() * Math.PI * 2, s = Math.sqrt(1 - u * u);
    const n = [s * Math.cos(t), u, s * Math.sin(t)];
    const b = blade({ L: bladeL, W: bladeL * 0.5, segL: 2, segW: 1, profile: "ovate", rise: 0.1, droop: 0.3, fold: 0.2, base: leafDark, tip: leaf, seed: seed * 7 + i });
    parts.push(xf(b, { p: n.map((k) => k * r * 0.95), r: [-Math.asin(n[1]) + 0.3, Math.atan2(n[0], n[2]), rnd()] }));
  }
  return merge(parts);
}

/**
 * Generic fruit tree. habit: "round" (apple, cherry, walnut, citrus), "vase" (peach, apricot, almond, plum),
 * "pyramid" (pear), "olive" (gnarled, silvery).
 */
function fruitTree({ seed, h, habit, leaf, leafDark, fruit, fruitR, fruits, bark = "#5c4430" }) {
  const r = rng(seed);
  const trunkH = habit === "olive" ? h * 0.35 : h * 0.3;
  const trunk = [tube([[0, 0, 0], [habit === "olive" ? 0.12 : 0.02, trunkH * 0.5, 0.05], [0, trunkH, 0]], h * 0.035, bark, { seg: 5, radial: 7, taper: 0.3 })];
  const crowns = [];
  const scaff = habit === "vase" ? 4 : 3;
  for (let i = 0; i < scaff; i++) {
    const a = (i / scaff) * Math.PI * 2 + r() * 0.4;
    const spread = habit === "pyramid" ? 0.18 : habit === "vase" ? 0.42 : 0.3;
    const end = [Math.cos(a) * h * spread, h * (habit === "pyramid" ? 0.55 : 0.68), Math.sin(a) * h * spread];
    trunk.push(tube([[0, trunkH * 0.95, 0], [end[0] * 0.5, (trunkH + end[1]) * 0.5, end[2] * 0.5], end], h * 0.018, bark, { seg: 4, radial: 5, taper: 0.5 }));
    crowns.push(end);
  }
  // canopy clumps
  const clumps = [], centres = [];
  const n = habit === "pyramid" ? 7 : 9;
  for (let i = 0; i < n; i++) {
    let c;
    if (habit === "pyramid") { const t = i / n; const rad = h * 0.24 * (1 - t); const a = i * 2.4; c = [Math.cos(a) * rad, h * (0.38 + 0.55 * t), Math.sin(a) * rad]; }
    else if (habit === "vase") { const b = crowns[i % crowns.length]; c = [b[0] * (1 + r() * 0.2), b[1] + h * (r() * 0.18), b[2] * (1 + r() * 0.2)]; }
    else { const u = r() * 2 - 1, t = r() * 6.28, s = Math.sqrt(1 - u * u); c = [s * Math.cos(t) * h * 0.28, h * 0.66 + u * h * 0.2, s * Math.sin(t) * h * 0.28]; }
    centres.push(c);
    clumps.push(xf(clump(h * (habit === "olive" ? 0.17 : 0.19), seed + i, leaf, leafDark, habit === "olive" ? 22 : 16, h * (habit === "olive" ? 0.035 : 0.05)), { p: c }));
  }
  const fr = [], fr1 = [];
  for (let i = 0; i < fruits; i++) {
    const c = centres[i % centres.length], u = r() * 2 - 1, t = r() * 6.28, s = Math.sqrt(1 - u * u), rr = h * 0.17;
    const at = [c[0] + s * Math.cos(t) * rr, c[1] + u * rr * 0.8 - rr * 0.2, c[2] + s * Math.sin(t) * rr];
    fr.push(solid(xf(ico(fruitR, 0), { p: at }), fruit, 0.12, i));
    if (i % 3 === 0) fr1.push(solid(xf(ico(fruitR * 1.3, 0), { p: at }), fruit, 0.1, i));
  }
  // LOD1: trunk + a few smooth canopy balls + fewer fruits
  const l1 = centres.filter((_, i) => i % 2 === 0).map((c, i) => paint(xf(ico(h * 0.2, 0), { p: c }), () => C(i % 2 ? leaf : leafDark)));
  return {
    LOD0: { trunk: merge(trunk), leaves: merge(clumps), fruit: fr.length ? merge(fr) : null },
    LOD1: { trunk: merge([tube([[0, 0, 0], [0, trunkH, 0]], h * 0.035, bark, { seg: 1, radial: 5 })]), leaves: merge(l1),
      fruit: fr1.length ? merge(fr1) : null },
    LOD2: { leaves: merge([paint(xf(ico(0.5, 0), { p: [0, h * 0.62, 0], s: [h * (habit === "pyramid" ? 0.4 : 0.55), h * 0.55, h * (habit === "pyramid" ? 0.4 : 0.55)] }), () => C(leaf)),
      paint(xf(new THREE.CylinderGeometry(h * 0.03, h * 0.04, trunkH, 4).translate(0, trunkH / 2, 0)), () => C(bark))]) },
  };
}

/** Grapevine trained on a vertical trellis (Guyot-like): trunk, cordon along the row, upright canes, bunches. */
function vine({ seed, h, bunch }) {
  const r = rng(seed), trunk = [], leaves = [], fruit = [];
  const cordon = h * 0.45;
  trunk.push(tube([[0, 0, 0], [0.02, cordon * 0.6, 0], [0, cordon, 0]], 0.03, "#5a4532", { seg: 4, radial: 6 }));
  trunk.push(tube([[-0.45, cordon, 0], [0, cordon + 0.02, 0], [0.45, cordon, 0]], 0.018, "#5a4532", { seg: 4, radial: 5 }));
  for (let i = 0; i < 8; i++) {
    const x = -0.4 + (i / 7) * 0.8;
    trunk.push(tube([[x, cordon, 0], [x + (r() - 0.5) * 0.05, cordon + (h - cordon) * 0.6, (r() - 0.5) * 0.08], [x, h, 0]], 0.007, "#6d5a38", { seg: 3, radial: 4 }));
    for (let k = 0; k < 4; k++) {
      const y = cordon + (h - cordon) * (0.2 + k * 0.22);
      for (const side of [-1, 1]) {
        const lf = blade({ L: 0.13, W: 0.13, segL: 3, segW: 1, profile: "round", rise: 0.2, droop: 0.4, fold: 0.1, wave: 0.4, base: "#3f6e2c", tip: "#5f9540", seed: seed + i * 20 + k * 2 + (side > 0 ? 1 : 0) });
        leaves.push(xf(lf, { p: [x, y, 0], r: [0.2, side > 0 ? 0 : Math.PI, r() * 0.6] }));
      }
    }
    if (i % 2 === 0) {
      const g = [];
      for (let b = 0; b < 8; b++) { const t = b / 7; g.push(xf(ico(0.016, 0), { p: [(r() - 0.5) * 0.06 * (1 - t), -t * 0.16, (r() - 0.5) * 0.06 * (1 - t)] })); }
      fruit.push(solid(xf(merge(g), { p: [x + 0.03, cordon + 0.05, 0.06] }), bunch, 0.15, i));
    }
  }
  const l1 = [paint(xf(new THREE.BoxGeometry(0.95, h - cordon, 0.18), { p: [0, (h + cordon) / 2, 0] }), () => C("#4f8336").multiplyScalar(0.9 + r() * 0.2))];
  return {
    LOD0: { trunk: merge(trunk), leaves: merge(leaves), fruit: merge(fruit) },
    LOD1: { trunk: merge(trunk.slice(0, 2)), leaves: merge(l1) },
    LOD2: { leaves: paint(xf(new THREE.BoxGeometry(0.95, h * 0.9, 0.2), { p: [0, h * 0.55, 0] }), () => C("#4f8336")) },
  };
}

export const TREE_GENERATORS = {
  apple: () => fruitTree({ seed: 201, h: 4, habit: "round", leaf: "#5c9443", leafDark: "#3c6e2e", fruit: "#c8302a", fruitR: 0.045, fruits: 40 }),
  pear: () => fruitTree({ seed: 211, h: 4, habit: "pyramid", leaf: "#5f9545", leafDark: "#3b6b2d", fruit: "#c9c24a", fruitR: 0.045, fruits: 30 }),
  cherry: () => fruitTree({ seed: 221, h: 4, habit: "round", leaf: "#4f8a3c", leafDark: "#2f5f26", fruit: "#9e1420", fruitR: 0.02, fruits: 70 }),
  peach: () => fruitTree({ seed: 231, h: 3, habit: "vase", leaf: "#5e9a40", leafDark: "#3d7030", fruit: "#ec9a3e", fruitR: 0.04, fruits: 30 }),
  apricot: () => fruitTree({ seed: 241, h: 3, habit: "vase", leaf: "#5a9440", leafDark: "#3a6a2c", fruit: "#f0a530", fruitR: 0.033, fruits: 36 }),
  plum: () => fruitTree({ seed: 251, h: 3, habit: "vase", leaf: "#4f8a3a", leafDark: "#2f6026", fruit: "#5a2a5e", fruitR: 0.028, fruits: 40 }),
  olive: () => fruitTree({ seed: 261, h: 4, habit: "olive", leaf: "#8fa58a", leafDark: "#5f7660", fruit: "#3b3d2a", fruitR: 0.012, fruits: 50, bark: "#6a6052" }),
  walnut: () => fruitTree({ seed: 271, h: 4.5, habit: "round", leaf: "#5c8f3e", leafDark: "#3a6328", fruit: null, fruitR: 0, fruits: 0, bark: "#6e6458" }),
  almond: () => fruitTree({ seed: 281, h: 5, habit: "vase", leaf: "#6a9a4c", leafDark: "#45703a", fruit: null, fruitR: 0, fruits: 0 }),
  citrus: () => fruitTree({ seed: 291, h: 3, habit: "round", leaf: "#2f6a2a", leafDark: "#1f4d1d", fruit: "#f08a1c", fruitR: 0.04, fruits: 34 }),
  kiwi: () => fruitTree({ seed: 301, h: 3, habit: "vase", leaf: "#4f8a32", leafDark: "#356324", fruit: "#7a6440", fruitR: 0.03, fruits: 30 }),
  grape_wine: () => vine({ seed: 311, h: 1.75, bunch: "#3b2346" }),
  grape_table: () => vine({ seed: 321, h: 2, bunch: "#b9c46a" }),
};
