/**
 * Terrain height sources. The farm area (all plots + margin) is always flat at y = 0, so the real plot
 * geometry is never deformed. Around it:
 *  - "demo": procedural hills (clearly labelled as demonstrative, not real data);
 *  - "dem":  a real elevation grid (e.g. Copernicus GLO-30 or TINITALY), to be plugged in phase 3.
 */
import { fbm } from "./noise";

export interface FarmZone { x0: number; x1: number; z0: number; z1: number; cx: number; cz: number; size: number }

export interface TerrainSource {
  kind: "demo" | "dem";
  label: string;
  heightAt(x: number, z: number): number;
}

export interface DemGrid { x0: number; z0: number; cell: number; cols: number; rows: number; heights: Float32Array }

const smooth = (t: number) => { const c = Math.min(1, Math.max(0, t)); return c * c * (3 - 2 * c); };

/** Distance (m) from the flat farm rectangle; 0 inside. */
export function distFromFarm(z: FarmZone, x: number, y: number, margin: number) {
  const dx = Math.max(z.x0 - margin - x, 0, x - (z.x1 + margin));
  const dz = Math.max(z.z0 - margin - y, 0, y - (z.z1 + margin));
  return Math.hypot(dx, dz);
}

export function farmMargin(z: FarmZone) { return Math.max(25, z.size * 0.12); }

/** Demonstrative rolling hills: amplitude grows with distance from the farm (plain near, hills far away). */
export function demoTerrain(zone: FarmZone): TerrainSource {
  const margin = farmMargin(zone);
  const ramp = Math.max(120, zone.size * 0.9);
  return {
    kind: "demo",
    label: "Paesaggio dimostrativo: colline e boschi generati, non sono dati reali",
    heightAt(x, z) {
      const d = distFromFarm(zone, x, z, margin);
      if (d <= 0) return 0;
      const k = smooth(d / ramp);
      const hills = fbm(x / 520, z / 520, 5) * 0.5 + 0.5;          // 0..1 large forms
      const detail = fbm(x / 90 + 17, z / 90 - 9, 3) * 0.12;
      const plain = fbm(x / 160, z / 160, 2) * 0.6;                 // gentle undulation near the farm
      return k * (plain + (hills * hills) * 42 + detail * 10) + (1 - k) * 0;
    },
  };
}

/** Real elevation grid (bilinear), flattened to 0 on the farm and blended over the margin. */
export function demTerrain(zone: FarmZone, grid: DemGrid, label: string): TerrainSource {
  const margin = farmMargin(zone);
  const base = sample(grid, zone.cx, zone.cz);
  return {
    kind: "dem", label,
    heightAt(x, z) {
      const d = distFromFarm(zone, x, z, margin);
      return d <= 0 ? 0 : smooth(d / margin) * (sample(grid, x, z) - base);
    },
  };
}

function sample(g: DemGrid, x: number, z: number) {
  const fx = Math.min(g.cols - 1.001, Math.max(0, (x - g.x0) / g.cell)), fz = Math.min(g.rows - 1.001, Math.max(0, (z - g.z0) / g.cell));
  const i = Math.floor(fx), j = Math.floor(fz), tx = fx - i, tz = fz - j;
  const h = (a: number, b: number) => g.heights[b * g.cols + a];
  return (h(i, j) * (1 - tx) + h(i + 1, j) * tx) * (1 - tz) + (h(i, j + 1) * (1 - tx) + h(i + 1, j + 1) * tx) * tz;
}

/** Normal-ish slope (0 flat .. 1 steep) from finite differences. */
export function slopeAt(t: TerrainSource, x: number, z: number, e = 4) {
  const dx = t.heightAt(x + e, z) - t.heightAt(x - e, z), dz = t.heightAt(x, z + e) - t.heightAt(x, z - e);
  return Math.min(1, Math.hypot(dx, dz) / (2 * e));
}
