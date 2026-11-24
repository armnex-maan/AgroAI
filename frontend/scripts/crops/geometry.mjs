// Geometry helpers for the AgroAI crop library (Node, three.js). All parts carry vertex colours.
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

export const C = (hex) => new THREE.Color(hex);

export function rng(seed) { let s = seed >>> 0 || 1; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }

/** Paint a geometry: fn(position, i) -> THREE.Color. */
export function paint(geo, fn) {
  const g = geo.index ? geo.toNonIndexed() : geo;
  g.deleteAttribute("uv");
  const p = g.attributes.position, col = new Float32Array(p.count * 3), v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) { v.fromBufferAttribute(p, i); const c = fn(v, i); col.set([c.r, c.g, c.b], i * 3); }
  g.setAttribute("color", new THREE.BufferAttribute(col, 3));
  if (!g.attributes.normal) g.computeVertexNormals();
  return g;
}
export const solid = (geo, hex, jitter = 0, seed = 1) => {
  const r = rng(seed), c = C(hex);
  return paint(geo, () => c.clone().multiplyScalar(1 + (r() - 0.5) * jitter));
};

/** Apply position / rotation (XYZ euler, radians) / scale. */
export function xf(geo, { p = [0, 0, 0], r = [0, 0, 0], s = [1, 1, 1] } = {}) {
  const m = new THREE.Matrix4().compose(new THREE.Vector3(...p), new THREE.Quaternion().setFromEuler(new THREE.Euler(...r, "YXZ")),
    new THREE.Vector3(...(Array.isArray(s) ? s : [s, s, s])));
  return geo.clone().applyMatrix4(m);
}
/** Orient a geometry built along +Z so that +Z points along `dir` (from `origin`). */
export function along(geo, origin, dir) {
  const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), new THREE.Vector3(...dir).normalize());
  return geo.clone().applyMatrix4(new THREE.Matrix4().compose(new THREE.Vector3(...origin), q, new THREE.Vector3(1, 1, 1)));
}

export function merge(list) {
  const clean = list.filter(Boolean).map((g) => {
    const n = g.index ? g.toNonIndexed() : g;
    if (n.attributes.uv) n.deleteAttribute("uv");
    if (!n.attributes.normal) n.computeVertexNormals();
    return n;
  });
  return clean.length ? mergeGeometries(clean, false) : null;
}

const PROFILES = {
  ovate: (t) => Math.pow(Math.sin(Math.PI * Math.min(1, t * 1.05)), 0.75) * (1 - 0.25 * t),
  lanceolate: (t) => Math.sin(Math.PI * t) * (1 - 0.45 * t),
  strap: (t) => (1 - Math.pow(t, 6)) * (0.85 + 0.15 * (1 - t)),
  round: (t) => Math.sqrt(Math.max(0, Math.sin(Math.PI * t))),
  obovate: (t) => Math.pow(Math.sin(Math.PI * t), 0.6) * (0.55 + 0.6 * t) * (1 - Math.pow(t, 8)),
  needle: (t) => 1 - t,
};

/**
 * A leaf blade along +Z, lying roughly in the XZ plane, rising then drooping.
 * length, width in metres; fold = V shape along the midrib; wave = frilly edge; twist = rotation along the blade.
 */
export function blade({ L, W, segL = 6, segW = 2, rise = 0.45, droop = 0.55, fold = 0.25, wave = 0, waveF = 5, twist = 0,
  profile = "ovate", base = "#3d6b2a", tip = "#6fa043", rib = null, spots = 0, seed = 1 }) {
  const w = PROFILES[profile], r = rng(seed);
  const cols = segW * 2 + 1, pos = [], idx = [];
  for (let i = 0; i <= segL; i++) {
    const t = i / segL, wt = w(t) * W / 2;
    for (let j = -segW; j <= segW; j++) {
      const s = j / segW;
      let x = s * wt;
      let y = L * (rise * t - droop * t * t) - fold * Math.abs(s) * wt + wave * Math.sin(t * waveF * Math.PI + s * 2.7) * Math.abs(s) * wt * 0.5;
      const z = t * L;
      const a = twist * t, cx = x * Math.cos(a) - y * Math.sin(a), cy = x * Math.sin(a) + y * Math.cos(a);
      x = cx; y = cy;
      pos.push(x, y, z);
    }
  }
  for (let i = 0; i < segL; i++) for (let j = 0; j < cols - 1; j++) {
    const a = i * cols + j, b = a + 1, c = a + cols, d = c + 1;
    idx.push(a, c, b, b, c, d);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  const cb = C(base), ct = C(tip), cr = rib ? C(rib) : null;
  return paint(g, (v) => {
    const t = Math.min(1, Math.max(0, v.z / L));
    const c = cb.clone().lerp(ct, t);
    if (cr && Math.abs(v.x) < W * 0.06) c.lerp(cr, 0.55);
    if (spots && r() < spots) c.lerp(C("#d9e6cf"), 0.45);
    return c;
  });
}

/** A tube through points (stems, petioles, vines). */
export function tube(points, radius, color, { seg = 6, radial = 5, taper = 0.6 } = {}) {
  const curve = new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p)));
  const g = new THREE.TubeGeometry(curve, seg, radius, radial, false);
  // taper towards the end
  const p = g.attributes.position, v = new THREE.Vector3(), n = seg + 1;
  for (let i = 0; i < p.count; i++) {
    const ring = Math.floor(i / (radial + 1)), t = ring / (n - 1);
    const c = curve.getPointAt(Math.min(1, t)); v.fromBufferAttribute(p, i);
    v.sub(c).multiplyScalar(1 - taper * t).add(c); p.setXYZ(i, v.x, v.y, v.z);
  }
  g.computeVertexNormals();
  return solid(g, color, 0.08, points.length);
}

/** Lathe solid of revolution from [radius, height] pairs, optional lobes (bell pepper, pumpkin ribs). */
export function lathe(profile, { seg = 12, lobes = 0, lobeDepth = 0.1, color = "#c0261c", tipColor = null, seed = 3 } = {}) {
  const g = new THREE.LatheGeometry(profile.map(([r, y]) => new THREE.Vector2(r, y)), seg);
  if (lobes) {
    const p = g.attributes.position, v = new THREE.Vector3();
    for (let i = 0; i < p.count; i++) {
      v.fromBufferAttribute(p, i);
      const a = Math.atan2(v.z, v.x), k = 1 - lobeDepth * (0.5 - 0.5 * Math.cos(lobes * a));
      p.setXYZ(i, v.x * k, v.y, v.z * k);
    }
    g.computeVertexNormals();
  }
  const top = Math.max(...profile.map((q) => q[1])), c0 = C(color), c1 = tipColor ? C(tipColor) : c0, r = rng(seed);
  return paint(g, (v) => c0.clone().lerp(c1, v.y / top).multiplyScalar(0.94 + r() * 0.12));
}

export const ico = (r, detail = 1) => new THREE.IcosahedronGeometry(r, detail);
export const cone = (r, h, seg = 6) => new THREE.ConeGeometry(r, h, seg).translate(0, h / 2, 0);
export const cyl = (r1, r2, h, seg = 6) => new THREE.CylinderGeometry(r1, r2, h, seg).translate(0, h / 2, 0);

/** Palmate lobed leaf (cucurbits) as a cupped disc; radius in metres. */
export function palmate({ R, lobes = 5, depth = 0.28, cup = 0.35, rings = 4, seg = 20, base = "#3f7a32", tip = "#5d9a43", spots = 0.12, seed = 5 }) {
  const pos = [], idx = [], r = rng(seed);
  pos.push(0, 0, 0);
  for (let k = 1; k <= rings; k++) {
    const t = k / rings;
    for (let s = 0; s < seg; s++) {
      const a = (s / seg) * Math.PI * 2;
      if (Math.abs(Math.atan2(Math.sin(a), Math.cos(a)) - Math.PI) < 0.0001) { /* keep */ }
      const lobe = 1 - depth * Math.pow(Math.abs(Math.sin((lobes / 2) * a)), 1.6);
      const notch = Math.abs(Math.cos(a / 2)) < 0.12 ? 0.6 : 1;                // heart-shaped base towards -X
      const rr = R * t * lobe * notch;
      const x = Math.cos(a) * rr, z = Math.sin(a) * rr;
      const y = cup * R * t * t - 0.12 * R * Math.pow(t, 3) + (r() - 0.5) * 0.01 * R;
      pos.push(x, y, z);
    }
  }
  for (let s = 0; s < seg; s++) idx.push(0, 1 + s, 1 + ((s + 1) % seg));
  for (let k = 1; k < rings; k++) for (let s = 0; s < seg; s++) {
    const a = 1 + (k - 1) * seg + s, b = 1 + (k - 1) * seg + ((s + 1) % seg), c = a + seg, d = b + seg;
    idx.push(a, c, b, b, c, d);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx); g.computeVertexNormals();
  const cb = C(base), ct = C(tip);
  return paint(g, (v) => { const t = Math.hypot(v.x, v.z) / R; const c = cb.clone().lerp(ct, t); if (r() < spots) c.lerp(C("#cfe0c4"), 0.5); return c; });
}

/** Triangle count of a geometry. */
export const tris = (g) => (g ? (g.index ? g.index.count : g.attributes.position.count) / 3 : 0);
