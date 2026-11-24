/** Terrain mesh, wind-blown grass and forests (with level of detail) of the AgroAI Farm Engine. */
import { useLayoutEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { fbm, rng } from "./noise";
import { QualityProfile } from "./quality";
import { distFromFarm, FarmZone, farmMargin, slopeAt, TerrainSource } from "./terrain";
import { leafCloud, useLeafMaterial } from "./foliage";

export type XZ = [number, number];
const inPoly = (x: number, z: number, poly: XZ[]) => {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, zi] = poly[i], [xj, zj] = poly[j];
    if ((zi > z) !== (zj > z) && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi) c = !c;
  }
  return c;
};

export const terrainExtent = (zone: FarmZone) => zone.size * 8 + 600;
/** Woods are kept within this distance of the farm, so the tree budget is spent where it is visible. */
export const forestRadius = (zone: FarmZone) => Math.min(terrainExtent(zone) * 0.45, zone.size * 1.3 + 320);
export const forestMask = (x: number, z: number) => fbm(x / 300 + 40, z / 300 - 12, 3);

// ---------------------------------------------------------------- terrain
export function Terrain({ zone, terrain, quality, grassTex }: { zone: FarmZone; terrain: TerrainSource; quality: QualityProfile; grassTex: THREE.Texture }) {
  const S = terrainExtent(zone);
  const geo = useMemo(() => {
    const g = new THREE.PlaneGeometry(S, S, quality.terrainSegments, quality.terrainSegments);
    g.rotateX(-Math.PI / 2);
    const pos = g.attributes.position as THREE.BufferAttribute;
    const col = new Float32Array(pos.count * 3);
    const lush = new THREE.Color("#8cc85a"), dry = new THREE.Color("#b3c874"), earth = new THREE.Color("#b9a47c"), deep = new THREE.Color("#7aa652");
    const c = new THREE.Color();
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i) + zone.cx, z = pos.getZ(i) + zone.cz;
      const h = terrain.heightAt(x, z);
      pos.setY(i, h);
      const n = fbm(x / 140, z / 140, 3) * 0.5 + 0.5;               // patches of greener and drier grass
      c.copy(lush).lerp(dry, Math.min(1, Math.max(0, n * 1.1 - 0.15)));
      const forest = forestMask(x, z);
      const inWoods = Math.hypot(x - zone.cx, z - zone.cz) < forestRadius(zone) && distFromFarm(zone, x, z, farmMargin(zone)) > farmMargin(zone) * 0.5;
      if (forest > 0.2 && inWoods) c.lerp(deep, Math.min(0.8, (forest - 0.2) * 3));       // woodland floor under the trees
      c.lerp(earth, Math.min(0.6, slopeAt(terrain, x, z) * 1.6));
      col.set([c.r, c.g, c.b], i * 3);
    }
    g.setAttribute("color", new THREE.BufferAttribute(col, 3));
    g.computeVertexNormals();
    return g;
  }, [S, zone, terrain, quality.terrainSegments]);
  const tex = useMemo(() => { const t = grassTex.clone(); t.needsUpdate = true; t.repeat.set(S / 28, S / 28); return t; }, [grassTex, S]);
  return (
    <mesh geometry={geo} position={[zone.cx, -0.05, zone.cz]} receiveShadow>
      <meshStandardMaterial map={tex} vertexColors roughness={1} />
    </mesh>
  );
}

// ---------------------------------------------------------------- grass
/** One clump of 7 curved blades, 1 m high at scale 1, with a dark base and a light tip. */
function grassClump(): THREE.BufferGeometry {
  const r = rng(99);
  const pos: number[] = [], col: number[] = [];
  const base = new THREE.Color("#3f6a2a"), tip = new THREE.Color("#a9c46a");
  for (let b = 0; b < 7; b++) {
    const a = r() * Math.PI * 2, ox = (r() - 0.5) * 0.18, oz = (r() - 0.5) * 0.18, h = 0.6 + r() * 0.4, lean = 0.15 + r() * 0.25, w = 0.025 + r() * 0.015;
    const dx = Math.cos(a), dz = Math.sin(a), px = -dz * w, pz = dx * w;
    const p = (t: number) => [ox + dx * lean * t * t, h * t, oz + dz * lean * t * t];
    const [b0, m0, tp] = [p(0), p(0.55), p(1)];
    const quad = [
      [b0[0] - px, b0[1], b0[2] - pz], [b0[0] + px, b0[1], b0[2] + pz], [m0[0] + px * 0.6, m0[1], m0[2] + pz * 0.6],
      [b0[0] - px, b0[1], b0[2] - pz], [m0[0] + px * 0.6, m0[1], m0[2] + pz * 0.6], [m0[0] - px * 0.6, m0[1], m0[2] - pz * 0.6],
      [m0[0] - px * 0.6, m0[1], m0[2] - pz * 0.6], [m0[0] + px * 0.6, m0[1], m0[2] + pz * 0.6], tp,
    ];
    quad.forEach((v) => { pos.push(v[0], v[1], v[2]); const k = v[1] / h; const c = base.clone().lerp(tip, k); col.push(c.r, c.g, c.b); });
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  g.computeVertexNormals();
  return g;
}

/** Vertex sway: blade tips move with a slow travelling wave (height-weighted). */
export function windMaterial(base: THREE.MeshStandardMaterial, uniforms: { uTime: { value: number } }, amount = 0.12) {
  base.onBeforeCompile = (shader) => {
    shader.uniforms.uTime = uniforms.uTime;
    shader.vertexShader = "uniform float uTime;\n" + shader.vertexShader.replace("#include <begin_vertex>", `#include <begin_vertex>
      #ifdef USE_INSTANCING
        vec3 ip = vec3(instanceMatrix[3][0], instanceMatrix[3][1], instanceMatrix[3][2]);
      #else
        vec3 ip = vec3(0.0);
      #endif
      float hh = max(transformed.y, 0.0);
      float w = sin(uTime * 1.6 + ip.x * 0.09 + ip.z * 0.07) + 0.5 * sin(uTime * 2.7 + ip.x * 0.21);
      transformed.x += w * ${amount.toFixed(3)} * hh * hh;
      transformed.z += w * ${(amount * 0.6).toFixed(3)} * hh * hh;`);
  };
  base.customProgramCacheKey = () => `wind-${amount}`;
  return base;
}

export function Grass({ zone, terrain, quality, exclude }: { zone: FarmZone; terrain: TerrainSource; quality: QualityProfile; exclude: XZ[][] }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const geo = useMemo(grassClump, []);
  const uniforms = useMemo(() => ({ uTime: { value: 0 } }), []);
  const mat = useMemo(() => windMaterial(new THREE.MeshStandardMaterial({ vertexColors: true, side: THREE.DoubleSide, roughness: 0.95 }), uniforms), [uniforms]);
  const spots = useMemo(() => {
    const out: [number, number, number, number][] = [];
    if (!quality.grass) return out;
    const r = rng(7), R = zone.size * 0.6 + 140;
    let guard = 0;
    while (out.length < quality.grass && guard++ < quality.grass * 8) {
      const x = zone.cx + (r() * 2 - 1) * R, z = zone.cz + (r() * 2 - 1) * R;
      const d = distFromFarm(zone, x, z, 0);
      if (r() > Math.exp(-d / (R * 0.35))) continue;                 // denser close to the farm
      if (exclude.some((p) => inPoly(x, z, p))) continue;            // never on the plots
      if (fbm(x / 60, z / 60, 2) < -0.35) continue;                  // bare patches
      out.push([x, terrain.heightAt(x, z), z, 0.35 + r() * 0.45]);
    }
    return out;
  }, [zone, terrain, quality.grass, exclude]);
  useLayoutEffect(() => {
    const m = ref.current; if (!m) return;
    const o = new THREE.Object3D();
    spots.forEach(([x, y, z, s], i) => { o.position.set(x, y, z); o.rotation.set(0, i * 2.39, 0); o.scale.set(s * 1.6, s, s * 1.6); o.updateMatrix(); m.setMatrixAt(i, o.matrix); });
    m.instanceMatrix.needsUpdate = true; m.computeBoundingSphere();
  }, [spots]);
  useFrame((_, dt) => { if (quality.wind) uniforms.uTime.value += dt; });
  if (!spots.length) return null;
  return <instancedMesh ref={ref} args={[geo, mat, spots.length]} receiveShadow raycast={() => null} />;
}

// ---------------------------------------------------------------- trees (LOD)
type Species = "oak" | "poplar" | "pine";
function colored(g: THREE.BufferGeometry, color: string, jitter = 0, seed = 1) {
  const n = g.index ? g.toNonIndexed() : g;
  n.deleteAttribute("uv");
  const r = rng(seed), c = new THREE.Color(color), out = new Float32Array(n.attributes.position.count * 3);
  for (let i = 0; i < n.attributes.position.count; i += 3) {
    const k = 1 + (r() - 0.5) * jitter;
    for (let v = 0; v < 3; v++) out.set([c.r * k, c.g * k, c.b * k], (i + v) * 3);
  }
  n.setAttribute("color", new THREE.BufferAttribute(out, 3));
  return n;
}
const tr = (g: THREE.BufferGeometry, x: number, y: number, z: number, sx: number, sy: number, sz: number) => {
  const m = new THREE.Matrix4().compose(new THREE.Vector3(x, y, z), new THREE.Quaternion(), new THREE.Vector3(sx, sy, sz));
  return g.clone().applyMatrix4(m);
};
/** Wood of a tree at 1 m scale (trunk and main limbs; pines keep their needle cones). detail: 1 near, 0 far. */
function woodGeo(sp: Species, detail: 0 | 1): THREE.BufferGeometry {
  const r = rng(sp.length * 31 + detail);
  const sides = detail ? 7 : 4;
  const parts = [colored(tr(new THREE.CylinderGeometry(sp === "poplar" ? 0.018 : 0.028, 0.045, 0.5, sides), 0, 0.25, 0, 1, 1, 1), "#4f3d2c", 0.2, 3)];
  if (sp === "pine") {
    for (let i = 0; i < (detail ? 4 : 2); i++) {
      const y = 0.35 + i * (detail ? 0.16 : 0.3), s = 0.32 - i * (detail ? 0.06 : 0.1);
      parts.push(colored(tr(new THREE.ConeGeometry(1, 1, detail ? 9 : 5), 0, y + 0.15, 0, s, detail ? 0.32 : 0.5, s), "#2f5530", 0.25, i + 5));
    }
  } else if (detail) {
    // main limbs reaching into the crown
    const limbs = sp === "poplar" ? 3 : 5;
    for (let i = 0; i < limbs; i++) {
      const a = (i / limbs) * Math.PI * 2 + r(), len = sp === "poplar" ? 0.3 : 0.32, tilt = sp === "poplar" ? 0.25 : 0.75;
      const g = new THREE.CylinderGeometry(0.008, 0.02, len, 5).translate(0, len / 2, 0);
      g.applyMatrix4(new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(tilt * Math.cos(a), 0, tilt * Math.sin(a))));
      parts.push(colored(g.translate(0, 0.42 + r() * 0.08, 0), "#56432f", 0.2, i + 20));
    }
  }
  const g = mergeGeometries(parts, false)!;
  g.computeVertexNormals();
  return g;
}

/** Crown of photographic leaf cards (oak-like and poplar-like shapes); pines have none. */
function crownGeo(sp: Species, detail: 0 | 1): THREE.BufferGeometry | null {
  if (sp === "pine") return null;
  return sp === "poplar"
    ? leafCloud({ center: [0, 0.66, 0], radii: [0.11, 0.32, 0.11], count: detail ? 56 : 11, size: detail ? 0.15 : 0.24, seed: 7 + detail })
    : leafCloud({ center: [0, 0.63, 0], radii: [0.31, 0.24, 0.31], count: detail ? 80 : 15, size: detail ? 0.21 : 0.36, seed: 3 + detail });
}

interface TreeSpot { sp: Species; m: THREE.Matrix4; p: THREE.Vector3; c: THREE.Color }
const TINT: Record<Species, string> = { oak: "#f2f7e6", poplar: "#fbffd6", pine: "#ffffff" };

export function Forest({ zone, terrain, quality }: { zone: FarmZone; terrain: TerrainSource; quality: QualityProfile }) {
  const species: Species[] = ["oak", "poplar", "pine"];
  const geos = useMemo(() => Object.fromEntries(species.map((s) => [s, { wood: [woodGeo(s, 0), woodGeo(s, 1)], crown: [crownGeo(s, 0), crownGeo(s, 1)] }])) as
    Record<Species, { wood: THREE.BufferGeometry[]; crown: (THREE.BufferGeometry | null)[] }>, []); // eslint-disable-line
  const woodMat = useMemo(() => new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.9 }), []);
  const leafMat = useLeafMaterial(0.012);
  const spots = useMemo(() => {
    const out: TreeSpot[] = [];
    const r = rng(2024), margin = farmMargin(zone);
    const add = (sp: Species, x: number, z: number, h: number) => {
      const p = new THREE.Vector3(x, terrain.heightAt(x, z) - 0.2, z);
      const k = 0.82 + r() * 0.3;
      out.push({ sp, p, c: new THREE.Color(TINT[sp]).multiplyScalar(k), m: new THREE.Matrix4().compose(p, new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), r() * 6.28), new THREE.Vector3(h, h, h)) });
    };
    // a row of poplars along the north side and a hedge of oaks along the west side (typical of the Po valley plain)
    for (let x = zone.x0 - margin * 0.6; x < zone.x1 + margin * 0.6; x += 9) add("poplar", x + (r() - 0.5) * 2, zone.z0 - margin * 0.7, 22 + r() * 6);
    for (let z = zone.z0; z < zone.z1; z += 14) if (r() > 0.25) add("oak", zone.x0 - margin * 0.75 + (r() - 0.5) * 4, z, 11 + r() * 6);
    // woods on the hills (noise mask) and scattered field trees
    const S = forestRadius(zone);
    let guard = 0;
    while (out.length < quality.trees && guard++ < quality.trees * 60) {
      const x = zone.cx + (r() * 2 - 1) * S, z = zone.cz + (r() * 2 - 1) * S;
      if (Math.hypot(x - zone.cx, z - zone.cz) > S) continue;
      const d = distFromFarm(zone, x, z, margin);
      if (d < margin * 0.5) continue;
      const forest = forestMask(x, z);
      if (forest > 0.22 || r() < 0.004) add(forest > 0.35 && terrain.heightAt(x, z) > 18 ? "pine" : "oak", x, z, 14 + r() * 9);
    }
    return out;
  }, [zone, terrain, quality.trees]);

  const refs = useRef<Record<string, THREE.InstancedMesh | null>>({});
  const counts = useMemo(() => Object.fromEntries(species.map((s) => [s, spots.filter((t) => t.sp === s).length])) as Record<Species, number>, [spots]); // eslint-disable-line
  const last = useRef({ t: -1, x: NaN, z: NaN });
  const near = Math.min(260, zone.size * 0.7 + 90);
  const assign = (cam: THREE.Vector3) => {
    const n: Record<string, number> = {};
    for (const t of spots) {
      const lod = t.p.distanceToSquared(cam) < near * near ? 1 : 0;
      const k = `${t.sp}${lod}`;
      const i = (n[k] = (n[k] ?? 0) + 1) - 1;
      refs.current[`${k}w`]?.setMatrixAt(i, t.m);
      const crown = refs.current[`${k}l`];
      if (crown) { crown.setMatrixAt(i, t.m); crown.setColorAt(i, t.c); }
    }
    for (const [key, mesh] of Object.entries(refs.current)) if (mesh) {
      mesh.count = n[key.slice(0, -1)] ?? 0; mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
      mesh.computeBoundingSphere();
    }
  };
  useFrame(({ camera, clock }) => {
    const L = last.current;
    if (clock.elapsedTime - L.t < 0.4 && L.t >= 0) return;               // re-check LOD a few times per second
    if (Math.hypot(camera.position.x - L.x, camera.position.z - L.z) < 8 && L.t >= 0) return;
    L.t = clock.elapsedTime; L.x = camera.position.x; L.z = camera.position.z;
    assign(camera.position);
  });
  const shadows = quality.shadowMap > 0;
  return <>{species.flatMap((s) => ([0, 1] as const).flatMap((lod) => {
    const crown = geos[s].crown[lod];
    return [
      <instancedMesh key={`${s}${lod}w`} ref={(m) => { refs.current[`${s}${lod}w`] = m; }} args={[geos[s].wood[lod], woodMat, Math.max(1, counts[s])]}
        castShadow={shadows && lod === 1} receiveShadow={lod === 1} raycast={() => null} frustumCulled={false} />,
      crown && <instancedMesh key={`${s}${lod}l`} ref={(m) => { refs.current[`${s}${lod}l`] = m; if (m && !m.instanceColor) m.setColorAt(0, new THREE.Color(1, 1, 1)); }}
        args={[crown, leafMat, Math.max(1, counts[s])]} castShadow={shadows && lod === 1} receiveShadow raycast={() => null} frustumCulled={false} />,
    ];
  }))}</>;
}
