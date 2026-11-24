/**
 * Photographic foliage for trees and hedges: canopies built from "leaf cards" (small quads carrying a photo of a
 * leafy twig with a transparency mask), the technique used by real-time vegetation in games.
 * Leaves: CC0 Poly Haven "Tree Small 02" leaf atlas (diffuse + alpha + normal), see public/planner/CREDITS.md.
 * Cards get "spherical" normals (pointing out of the canopy) so the crown is lit as one soft volume.
 */
import { useMemo } from "react";
import { useTexture } from "@react-three/drei";
import * as THREE from "three";
import { windMaterial } from "./Landscape";
import { rng } from "./noise";

export const FOLIAGE_WIND = { uTime: { value: 0 } };

const FILES = ["/planner/foliage/tree_small_02_leaves_diff_1k.jpg", "/planner/foliage/tree_small_02_leaves_alpha_1k.jpg",
  "/planner/foliage/tree_small_02_leaves_nor_gl_1k.jpg"];

/** Regions of the atlas holding a leafy twig: [u0, v0, u1, v1] (v measured from the bottom) and width/height. */
const REGIONS: { uv: [number, number, number, number]; aspect: number }[] = [
  { uv: [0.0, 0.5, 0.46, 1.0], aspect: 0.92 },      // left spray, upper half
  { uv: [0.0, 0.0, 0.46, 0.5], aspect: 0.92 },      // left spray, lower half
  { uv: [0.527, 0.326, 0.86, 0.961], aspect: 0.52 }, // single upright twig
];

export function useLeafMaterial(wind = 0.012) {
  const [map, alpha, nor] = useTexture(FILES);
  return useMemo(() => {
    map.colorSpace = THREE.SRGBColorSpace;
    for (const t of [map, alpha, nor]) t.anisotropy = 4;
    const m = new THREE.MeshStandardMaterial({ map, alphaMap: alpha, normalMap: nor, alphaTest: 0.45, side: THREE.DoubleSide,
      roughness: 0.78, vertexColors: true, normalScale: new THREE.Vector2(0.6, 0.6) });
    return windMaterial(m, FOLIAGE_WIND, wind);
  }, [map, alpha, nor, wind]);
}

export interface CloudOpts {
  center: [number, number, number]; radii: [number, number, number]; count: number; size: number; seed: number;
  /** 0..1: how much darker the inside and the underside of the crown are (self-shadowing). */
  shade?: number;
}

/** A crown of leaf cards on an ellipsoid (1 m tree scale). */
export function leafCloud(o: CloudOpts): THREE.BufferGeometry {
  const r = rng(o.seed);
  const pos: number[] = [], nor: number[] = [], uv: number[] = [], col: number[] = [];
  const [cx, cy, cz] = o.center, [rx, ry, rz] = o.radii, shade = o.shade ?? 0.45;
  const n = new THREE.Vector3(), t = new THREE.Vector3(), b = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0);
  for (let i = 0; i < o.count; i++) {
    // point inside the ellipsoid, biased toward the surface
    const th = r() * Math.PI * 2, ph = Math.acos(2 * r() - 1), k = 0.55 + 0.45 * Math.sqrt(r());
    const dx = Math.sin(ph) * Math.cos(th), dy = Math.cos(ph), dz = Math.sin(ph) * Math.sin(th);
    const px = cx + dx * rx * k, py = cy + dy * ry * k, pz = cz + dz * rz * k;
    // card faces outward with some randomness; up vector keeps twigs mostly hanging/upright
    n.set(dx + (r() - 0.5) * 0.9, dy * 0.6 + (r() - 0.5) * 0.6, dz + (r() - 0.5) * 0.9).normalize();
    t.crossVectors(up, n); if (t.lengthSq() < 1e-4) t.set(1, 0, 0); t.normalize().applyAxisAngle(n, (r() - 0.5) * 1.6);
    b.crossVectors(n, t).normalize();
    const reg = REGIONS[Math.floor(r() * REGIONS.length)];
    const h = o.size * (0.75 + r() * 0.5), w = h * reg.aspect;
    const [u0, v0, u1, v1] = reg.uv;
    const flip = r() < 0.5;
    const corners: [number, number, number, number][] = [[-0.5, -0.5, flip ? u1 : u0, v0], [0.5, -0.5, flip ? u0 : u1, v0], [0.5, 0.5, flip ? u0 : u1, v1], [-0.5, 0.5, flip ? u1 : u0, v1]];
    const v = corners.map(([a, c, uu, vv]) => ({ p: [px + t.x * a * w + b.x * c * h, py + t.y * a * w + b.y * c * h, pz + t.z * a * w + b.z * c * h], uv: [uu, vv] }));
    // normal = outward from the crown centre (soft volume lighting); colour = self-shadowing
    const sn = new THREE.Vector3(px - cx, (py - cy) * 1.4, pz - cz).normalize();
    const depth = Math.min(1, k), low = Math.min(1, Math.max(0, (py - (cy - ry)) / (2 * ry)));
    const light = 1 - shade + shade * (0.55 * depth + 0.45 * low);
    const jitter = 0.92 + r() * 0.16;
    for (const idx of [0, 1, 2, 0, 2, 3]) {
      pos.push(...v[idx].p); uv.push(...v[idx].uv); nor.push(sn.x, sn.y, sn.z);
      col.push(light * jitter, light * jitter * (0.98 + r() * 0.04), light * jitter * 0.95);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  g.computeBoundingSphere();
  return g;
}
