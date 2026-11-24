/** Terrain mesh, wind-blown grass and forests (with level of detail) of the AgroAI Farm Engine. */
import { useLayoutEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { fbm, rng } from "./noise";
import { QualityProfile } from "./quality";
import { distFromFarm, FarmZone, TerrainSource } from "./terrain";
import { countryside, landcoverTexture, terrainExtent, TreeKind, TreeSpot } from "./countryside";
import { ImpostorSet } from "./ImpostorSet";

export type XZ = [number, number];
const inPoly = (x: number, z: number, poly: XZ[]) => {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, zi] = poly[i], [xj, zj] = poly[j];
    if ((zi > z) !== (zj > z) && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi) c = !c;
  }
  return c;
};

export { terrainExtent };

// ---------------------------------------------------------------- terrain
/** Terrain mesh painted with the demo countryside (fields, woods, hedgerows, roads); close to the camera a tiled
 *  grass photo adds detail so the ground stays sharp. */
export function Terrain({ zone, terrain, quality, grassTex }: { zone: FarmZone; terrain: TerrainSource; quality: QualityProfile; grassTex: THREE.Texture }) {
  const S = terrainExtent(zone);
  const cs = useMemo(() => countryside(zone, terrain, quality.trees), [zone, terrain, quality.trees]);
  const land = useMemo(() => landcoverTexture(cs, zone, quality.landcover), [cs, zone, quality.landcover]);
  const geo = useMemo(() => {
    const g = new THREE.PlaneGeometry(S, S, quality.terrainSegments, quality.terrainSegments);
    g.rotateX(-Math.PI / 2);
    const pos = g.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) pos.setY(i, terrain.heightAt(pos.getX(i) + zone.cx, pos.getZ(i) + zone.cz));
    g.computeVertexNormals();
    return g;
  }, [S, zone, terrain, quality.terrainSegments]);
  const mat = useMemo(() => {
    const detail = grassTex.clone(); detail.needsUpdate = true; detail.wrapS = detail.wrapT = THREE.RepeatWrapping;
    const m = new THREE.MeshStandardMaterial({ map: land, roughness: 1 });
    m.onBeforeCompile = (sh) => {
      sh.uniforms.uDetail = { value: detail };
      sh.vertexShader = "varying vec3 vWorldP;\n" + sh.vertexShader.replace("#include <worldpos_vertex>",
        "#include <worldpos_vertex>\n vWorldP = (modelMatrix * vec4(transformed, 1.0)).xyz;");
      sh.fragmentShader = "uniform sampler2D uDetail;\nvarying vec3 vWorldP;\n" + sh.fragmentShader.replace("#include <map_fragment>", `#include <map_fragment>
        float camD = length(vWorldP - cameraPosition);
        vec3 d1 = texture2D(uDetail, vWorldP.xz / 7.0).rgb;
        vec3 d2 = texture2D(uDetail, vWorldP.xz / 31.0 + 0.37).rgb;
        float l = dot(d1, vec3(0.3, 0.59, 0.11)) * 0.6 + dot(d2, vec3(0.3, 0.59, 0.11)) * 0.4;
        float fade = 1.0 - smoothstep(60.0, 700.0, camD);
        diffuseColor.rgb *= mix(1.0, clamp(l / 0.3, 0.55, 1.5), fade * 0.7);`);
    };
    m.customProgramCacheKey = () => "terrain-landcover";
    return m;
  }, [land, grassTex]);
  return <mesh name="agro-terrain" geometry={geo} material={mat} position={[zone.cx, -0.05, zone.cz]} receiveShadow />;
}

// ---------------------------------------------------------------- grass
/** One clump of 7 curved blades, 1 m high at scale 1, with a dark base and a light tip. */
function grassClump(): THREE.BufferGeometry {
  const r = rng(99);
  const pos: number[] = [], col: number[] = [];
  const base = new THREE.Color("#2b4d1e"), tip = new THREE.Color("#6e9640");
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
      out.push([x, terrain.heightAt(x, z), z, 0.16 + r() * 0.22]);
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
  // the photoreal render grows its own grass blades (userData.noExport)
  return <instancedMesh ref={ref} args={[geo, mat, spots.length]} receiveShadow raycast={() => null} userData={{ noExport: true }} />;
}

// ---------------------------------------------------------------- trees (impostors)
const KINDS: TreeKind[] = ["broadleaf_a", "broadleaf_b", "broadleaf_c", "olive_a"];

/** Woods, hedgerows, olive groves and field trees of the demo countryside: one instanced quad per tree. */
export function Forest({ zone, terrain, quality }: { zone: FarmZone; terrain: TerrainSource; quality: QualityProfile }) {
  const cs = useMemo(() => countryside(zone, terrain, quality.trees), [zone, terrain, quality.trees]);
  const by = useMemo(() => Object.fromEntries(KINDS.map((k) => [k, cs.trees.filter((t) => t.kind === k)])) as Record<TreeKind, TreeSpot[]>, [cs]);
  const shadows = quality.shadowMap > 0;
  return <>{KINDS.map((k) => <ImpostorSet key={k} name={k} items={by[k]} shadows={shadows} />)}</>;
}
