/**
 * Farm elements (farm_features) in the 3D scene: buildings, tanks, wells, rural roads, irrigation mains, hedges,
 * ponds, orchards and vineyards. Every object comes from a database row and is selectable.
 * Geometry arrives in WGS84 and is converted to the farm frame (metres, X east, Z south).
 */
import { useLayoutEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Html, Line, useGLTF, useTexture } from "@react-three/drei";
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { XY } from "../plotGeo";
import { CropField } from "./CropField";
import { CropModel, useTreeModels } from "./cropLibrary";
import { rng } from "./engine/noise";
import { TerrainSource } from "./engine/terrain";
import { ImpostorItem, ImpostorSet } from "./engine/ImpostorSet";
import { WaterSpray } from "./engine/WaterSpray";
import { IMPOSTORS } from "./engine/impostor";
import { equipmentNode } from "./Equipment";

export interface Feature {
  id: string; kind: string; label: string; name: string; props: Record<string, any>;
  geometry: { type: "Point" | "LineString" | "Polygon"; coordinates: any };
  area_m2?: number; length_m?: number; height_m?: number[]; species_name?: string;
}
export interface FarmRef { origin: [number, number]; k: [number, number] }

export const toWorld = (ref: FarmRef, [lon, lat]: number[]): [number, number] => [(lon - ref.origin[0]) * ref.k[0], (ref.origin[1] - lat) * ref.k[1]];
export const toLonLat = (ref: FarmRef, [x, z]: number[]): [number, number] => [+(ref.origin[0] + x / ref.k[0]).toFixed(8), +(ref.origin[1] - z / ref.k[1]).toFixed(8)];

/** All points of a feature in the farm frame (for bounds and the flat farm zone). */
export function featurePoints(f: Feature, ref: FarmRef): [number, number][] {
  const g = f.geometry;
  if (g.type === "Point") return [toWorld(ref, g.coordinates)];
  if (g.type === "LineString") return g.coordinates.map((c: number[]) => toWorld(ref, c));
  return g.coordinates[0].map((c: number[]) => toWorld(ref, c));
}

// --------------------------------------------------------------------------- geometry helpers
function painted(g: THREE.BufferGeometry, color: string | ((v: THREE.Vector3) => THREE.Color)) {
  const n = g.index ? g.toNonIndexed() : g;
  if (n.attributes.uv) n.deleteAttribute("uv");
  const p = n.attributes.position, col = new Float32Array(p.count * 3), v = new THREE.Vector3(), c = new THREE.Color();
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    const cc = typeof color === "string" ? c.set(color) : color(v);
    col.set([cc.r, cc.g, cc.b], i * 3);
  }
  n.setAttribute("color", new THREE.BufferAttribute(col, 3));
  n.computeVertexNormals();
  return n;
}
const box = (w: number, h: number, d: number, x: number, y: number, z: number, color: string | ((v: THREE.Vector3) => THREE.Color)) =>
  painted(new THREE.BoxGeometry(w, h, d).translate(x, y + h / 2, z), color);

/** Gable roof over a W x L rectangle (ridge along Z), eave at y0, rise r, overhang o. */
function gableRoof(W: number, L: number, y0: number, r: number, o: number, color: string, stripes = true) {
  const w = W / 2 + o, l = L / 2 + o;
  const pos = [
    -w, y0, -l, 0, y0 + r, -l, 0, y0 + r, l, -w, y0, -l, 0, y0 + r, l, -w, y0, l,   // west slope
    w, y0, -l, w, y0, l, 0, y0 + r, l, w, y0, -l, 0, y0 + r, l, 0, y0 + r, -l,        // east slope
  ];
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  const base = new THREE.Color(color), dark = base.clone().multiplyScalar(0.78);
  return painted(g, (v) => (stripes && Math.floor((v.z + 50) / 0.45) % 2 ? dark.clone() : base.clone()));
}
function gableEnds(W: number, L: number, y0: number, r: number, color: string) {
  const w = W / 2, l = L / 2;
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute([-w, y0, -l, w, y0, -l, 0, y0 + r, -l, w, y0, l, -w, y0, l, 0, y0 + r, l], 3));
  return painted(g, color);
}
/** Hip roof (pyramidal ends) typical of Italian farmhouses. */
function hipRoof(W: number, L: number, y0: number, r: number, o: number, color: string, stripes = true) {
  const w = W / 2 + o, l = L / 2 + o, rl = Math.max(0.01, l - w);
  const A = [-w, y0, -l], B = [w, y0, -l], Cc = [w, y0, l], D = [-w, y0, l], P = [0, y0 + r, -rl], Q = [0, y0 + r, rl];
  const tri = (...p: number[][]) => p.flat();
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute([
    ...tri(A, P, B), ...tri(Cc, Q, D), ...tri(B, P, Q), ...tri(B, Q, Cc), ...tri(D, Q, P), ...tri(D, P, A)], 3));
  const base = new THREE.Color(color), dark = base.clone().multiplyScalar(0.8);
  return painted(g, (v) => (stripes && Math.floor((v.y - y0) / (r / 7)) % 2 ? dark.clone() : base.clone()));
}

// --------------------------------------------------------------------------- textured materials
/** Surface groups of a building; each one is a mesh with its own CC0 material (Poly Haven, see CREDITS.md). */
type Surf = "wall" | "plank" | "metal" | "roof" | "metalRoof" | "plain";
const SURFS: Surf[] = ["wall", "plank", "metal", "roof", "metalRoof", "plain"];

/** Texture coordinates in tiles: walls projected on their own plane, roofs along the slope (so the courses
 *  of tiles and the corrugations run the right way). */
function projectUV(g: THREE.BufferGeometry, tile: number, roof: boolean) {
  const p = g.attributes.position, uv = new Float32Array(p.count * 2);
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), n = new THREE.Vector3(), e = new THREE.Vector3();
  for (let i = 0; i < p.count; i += 3) {
    a.fromBufferAttribute(p, i); b.fromBufferAttribute(p, i + 1); c.fromBufferAttribute(p, i + 2);
    n.subVectors(c, b).cross(e.subVectors(a, b)).normalize();
    const ax = Math.abs(n.x), ay = Math.abs(n.y), az = Math.abs(n.z);
    for (let k = 0; k < 3; k++) {
      const v = k === 0 ? a : k === 1 ? b : c;
      let u = 0, w = 0;
      if (roof && ay < 0.985 && ay > 0.05) {
        const hl = Math.hypot(n.x, n.z), hx = n.x / hl, hz = n.z / hl;
        u = -v.x * hz + v.z * hx; w = (v.x * hx + v.z * hz) / ay;
      } else if (ay >= ax && ay >= az) { u = v.x; w = v.z; }
      else if (ax >= az) { u = v.z; w = v.y; }
      else { u = v.x; w = v.y; }
      uv[(i + k) * 2] = u / tile; uv[(i + k) * 2 + 1] = w / tile;
    }
  }
  g.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
  return g;
}

const TILE: Record<Surf, number> = { wall: 3, plank: 2.2, metal: 2, roof: 2, metalRoof: 2, plain: 1 };
const MAT_FILES = ["plastered_wall", "weathered_planks", "corrugated_iron", "clay_roof_tiles"]
  .flatMap((n) => [`/planner/${n}_diff_1k.jpg`, `/planner/${n}_nor_gl_1k.jpg`, `/planner/${n}_rough_1k.jpg`]);

export function useBuildingMaterials() {
  const t = useTexture(MAT_FILES);
  return useMemo(() => {
    t.forEach((x, i) => { x.wrapS = x.wrapT = THREE.RepeatWrapping; x.anisotropy = 8; if (i % 3 === 0) x.colorSpace = THREE.SRGBColorSpace; });
    const mk = (i: number, extra: THREE.MeshStandardMaterialParameters = {}) =>
      new THREE.MeshStandardMaterial({ vertexColors: true, map: t[i * 3], normalMap: t[i * 3 + 1], roughnessMap: t[i * 3 + 2], ...extra });
    return {
      wall: mk(0), plank: mk(1), metal: mk(2, { metalness: 0.5 }), roof: mk(3), metalRoof: mk(2, { metalness: 0.5 }),
      plain: new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.85 }),
    } as Record<Surf, THREE.MeshStandardMaterial>;
  }, [t]);
}

function windowsAlong(W: number, L: number, floors: number, fh: number, shutters: string | null) {
  const parts: THREE.BufferGeometry[] = [];
  const n = Math.max(1, Math.floor(L / 3.2));
  for (let f = 0; f < floors; f++) for (let i = 0; i < n; i++) {
    const z = -L / 2 + (i + 0.5) * (L / n), y = f * fh + fh * 0.38;
    for (const side of [-1, 1]) {
      if (f === 0 && i === Math.floor(n / 2) && side === 1) continue;                         // door here
      parts.push(box(0.06, 1.25, 0.85, side * (W / 2 + 0.01), y, z, "#2b3236"));
      parts.push(box(0.09, 1.45, 0.08, side * (W / 2 + 0.02), y - 0.1, z - 0.47, "#efe9dc"));
      parts.push(box(0.09, 1.45, 0.08, side * (W / 2 + 0.02), y - 0.1, z + 0.47, "#efe9dc"));
      if (shutters) {
        parts.push(box(0.05, 1.3, 0.42, side * (W / 2 + 0.06), y - 0.02, z - 0.7, shutters));
        parts.push(box(0.05, 1.3, 0.42, side * (W / 2 + 0.06), y - 0.02, z + 0.7, shutters));
      }
    }
  }
  return parts;
}

/** Building geometry by type, centred on the origin, long side along Z: one merged geometry per surface group. */
function buildingGeometry(type: string, W: number, L: number, floors: number, seed: number): Record<Surf, THREE.BufferGeometry | null> {
  const r = rng(seed);
  const S: Record<Surf, THREE.BufferGeometry[]> = { wall: [], plank: [], metal: [], roof: [], metalRoof: [], plain: [] };
  const parts = S.plain;
  const stucco = (base: string) => (v: THREE.Vector3) => new THREE.Color(base).multiplyScalar(0.94 + ((Math.sin(v.x * 3.1 + v.y * 1.7 + v.z * 2.3) + 1) / 2) * 0.1);
  if (type === "casale" || type === "stalla") {
    const fh = type === "stalla" ? 3.6 : 3.1, H = fh * floors;
    parts.push(box(W + 0.15, 0.6, L + 0.15, 0, 0, 0, "#a39787"));                          // stone plinth
    S.wall.push(box(W, H, L, 0, 0, 0, stucco(type === "stalla" ? "#f4e6c8" : "#f2d6a6")));
    parts.push(...windowsAlong(W, L, floors, fh, type === "casale" ? "#3f6b4b" : null));
    parts.push(box(0.12, 2.3, 1.3, W / 2 + 0.02, 0, 0, "#5b3b24"));                         // door
    S.roof.push(type === "casale" ? hipRoof(W, L, H, W * 0.28, 0.45, "#ffffff", false) : gableRoof(W, L, H, W * 0.22, 0.4, "#f2e6e0", false));
    if (type === "stalla") S.wall.push(gableEnds(W, L, H, W * 0.22, "#f4e6c8"));
    if (type === "casale") { S.wall.push(box(0.7, 1.6, 0.7, W * 0.2, H + W * 0.12, L * 0.25, "#e9cfa4")); parts.push(box(0.85, 0.15, 0.85, W * 0.2, H + W * 0.12 + 1.6, L * 0.25, "#8f8578")); }
  } else if (type === "fienile") {
    const H = 6.5;
    S.plank.push(box(W, H, L, 0, 0, 0, () => new THREE.Color("#ffab8c").multiplyScalar(0.95 + r() * 0.08)));
    const n = Math.max(2, Math.floor(L / 4.5));
    for (let i = 0; i < n; i++) parts.push(box(0.1, H * 0.62, (L / n) * 0.62, W / 2 + 0.01, 0, -L / 2 + (i + 0.5) * (L / n), "#5a4636"));   // open bays
    S.roof.push(gableRoof(W, L, H, W * 0.3, 0.5, "#ffffff", false)); S.plank.push(gableEnds(W, L, H, W * 0.3, "#f5a084"));
  } else if (type === "magazzino") {
    const H = 5.5;
    S.metal.push(box(W, H, L, 0, 0, 0, "#e4e8e6"));
    parts.push(box(0.1, 4, Math.min(5, L * 0.4), W / 2 + 0.01, 0, 0, "#6f7a80"));
    S.metalRoof.push(gableRoof(W, L, H, W * 0.12, 0.3, "#c4ccd0", false)); S.metal.push(gableEnds(W, L, H, W * 0.12, "#e4e8e6"));
  } else {                                                                                   // ricovero attrezzi: open shed
    const H = 4;
    for (const x of [-W / 2, W / 2]) for (let i = 0; i <= 3; i++) parts.push(box(0.25, H, 0.25, x, 0, -L / 2 + (i * L) / 3, "#6b4a2f"));
    S.plank.push(box(W, H, 0.15, 0, 0, -L / 2, "#e0c7a8"));
    S.metalRoof.push(gableRoof(W, L, H, W * 0.15, 0.4, "#c4ccd0", false));
  }
  const out = {} as Record<Surf, THREE.BufferGeometry | null>;
  for (const k of SURFS) {
    const list = S[k].map((g) => { const n = g.index ? g.toNonIndexed() : g; if (n.attributes.uv) n.deleteAttribute("uv"); return n; });
    out[k] = list.length ? projectUV(mergeGeometries(list, false)!, TILE[k], k === "roof" || k === "metalRoof") : null;
  }
  return out;
}

const BUILDING_DEFAULT: Record<string, [number, number, number]> = {
  casale: [10, 16, 2], fienile: [10, 20, 1], magazzino: [12, 24, 1], stalla: [11, 30, 1], ricovero_attrezzi: [6, 10, 1] };

// --------------------------------------------------------------------------- components
interface Sel { selected: string | null; onSelect: (k: string) => void }

function Building({ f, p, y, sel }: { f: Feature; p: [number, number]; y: number; sel: Sel }) {
  const type = f.props.type ?? "casale";
  const [dw, dl, df] = BUILDING_DEFAULT[type] ?? BUILDING_DEFAULT.casale;
  const W = f.props.width_m ?? dw, L = f.props.length_m ?? dl, floors = f.props.floors ?? df;
  const geo = useMemo(() => buildingGeometry(type, W, L, floors, f.id.length), [type, W, L, floors, f.id]);
  const mats = useBuildingMaterials();
  const key = `feature:${f.id}`;
  return (
    <group position={[p[0], y, p[1]]} rotation={[0, THREE.MathUtils.degToRad(f.props.rotation_deg ?? 0), 0]}>
      {SURFS.map((k) => geo[k] && (
        <mesh key={k} geometry={geo[k]!} material={mats[k]} castShadow receiveShadow onClick={(e) => { e.stopPropagation(); sel.onSelect(key); }} />
      ))}
      {sel.selected === key && <Line points={[[-W / 2 - 1, 0.2, -L / 2 - 1], [W / 2 + 1, 0.2, -L / 2 - 1], [W / 2 + 1, 0.2, L / 2 + 1], [-W / 2 - 1, 0.2, L / 2 + 1], [-W / 2 - 1, 0.2, -L / 2 - 1]]} color="#2f7cf6" lineWidth={3} />}
    </group>
  );
}

/** Tuscan farmhouse modelled in Blender (tools/blender/make_casale.py): plinth and quoins, string course, windows with
 *  green shutters, hip roof in coppi with a dovecote tower and chimneys, portico at the main door. Canonical 14 x 24 m,
 *  2 floors; scaled to the declared width, length and floors. Surfaces get the CC0 PBR textures by material name and the
 *  ambient occlusion baked in Blender (vertex colour). */
const CASALE_GLB = "/planner/buildings/casale.glb";
const CASALE = { W: 14, L: 24, H: 6.6 };
useGLTF.preload(CASALE_GLB);

function useCasaleParts() {
  const gltf = useGLTF(CASALE_GLB);
  const mats = useBuildingMaterials();
  return useMemo(() => {
    const tinted = (m: THREE.MeshStandardMaterial, color: string) => { const c = m.clone(); c.color.set(color); return c; };
    const byName: Record<string, THREE.Material> = {
      wall: tinted(mats.wall, "#f3d6a4"), stone: tinted(mats.wall, "#c9b896"), roof: tinted(mats.roof, "#ffffff"),
      wood: tinted(mats.plank, "#8a6444"),
      shutter: new THREE.MeshStandardMaterial({ color: "#3f6c47", roughness: 0.65, vertexColors: true }),
      glass: new THREE.MeshStandardMaterial({ color: "#1b262b", roughness: 0.12, metalness: 0.4, vertexColors: true, envMapIntensity: 1.4 }),
    };
    const parts: { geo: THREE.BufferGeometry; mat: THREE.Material }[] = [];
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      const name = ((m.material as THREE.Material).name || "").replace(/\.\d+$/, "");
      parts.push({ geo: m.geometry.clone().applyMatrix4(m.matrixWorld), mat: byName[name] ?? mats.plain });
    });
    return parts;
  }, [gltf, mats]);
}

function CasaleBuilding({ f, p, y, sel }: { f: Feature; p: [number, number]; y: number; sel: Sel }) {
  const [dw, dl, df] = BUILDING_DEFAULT.casale;
  const W = f.props.width_m ?? dw, L = f.props.length_m ?? dl, floors = f.props.floors ?? df;
  const parts = useCasaleParts();
  const key = `feature:${f.id}`;
  return (
    <group position={[p[0], y, p[1]]} rotation={[0, THREE.MathUtils.degToRad(f.props.rotation_deg ?? 0), 0]}>
      <group scale={[W / CASALE.W, (floors * 3.3) / CASALE.H, L / CASALE.L]}>
        {parts.map((pt, i) => <mesh key={i} geometry={pt.geo} material={pt.mat} castShadow receiveShadow onClick={(e) => { e.stopPropagation(); sel.onSelect(key); }} />)}
      </group>
      {sel.selected === key && <Line points={[[-W / 2 - 1, 0.2, -L / 2 - 1], [W / 2 + 1, 0.2, -L / 2 - 1], [W / 2 + 1, 0.2, L / 2 + 1], [-W / 2 - 1, 0.2, L / 2 + 1], [-W / 2 - 1, 0.2, -L / 2 - 1]]} color="#2f7cf6" lineWidth={3} />}
    </group>
  );
}

function Tank({ f, p, y, sel }: { f: Feature; p: [number, number]; y: number; sel: Sel }) {
  const d = f.props.diameter_m ?? 4, h = f.props.height_m ?? 3, key = `feature:${f.id}`;
  const geo = useMemo(() => mergeGeometries([
    painted(new THREE.CylinderGeometry(d / 2, d / 2, h, 28, 6, false).translate(0, h / 2, 0), (v) => new THREE.Color(Math.floor(v.y / (h / 6)) % 2 ? "#c4cbcf" : "#b3bbc0")),
    painted(new THREE.ConeGeometry(d / 2 + 0.1, d * 0.12, 28).translate(0, h + d * 0.06, 0), "#9fa8ad"),
    painted(new THREE.BoxGeometry(0.05, h, 0.05).translate(d / 2 + 0.12, h / 2, -0.22), "#6b7378"),
    painted(new THREE.BoxGeometry(0.05, h, 0.05).translate(d / 2 + 0.12, h / 2, 0.22), "#6b7378"),
    ...Array.from({ length: Math.floor(h / 0.4) }, (_, i) => painted(new THREE.BoxGeometry(0.04, 0.04, 0.44).translate(d / 2 + 0.12, 0.3 + i * 0.4, 0), "#6b7378")),
  ].map((g) => (g.index ? g.toNonIndexed() : g)), false)!, [d, h]);
  return (
    <group position={[p[0], y, p[1]]}>
      <mesh geometry={geo} castShadow receiveShadow onClick={(e) => { e.stopPropagation(); sel.onSelect(key); }}><meshStandardMaterial vertexColors metalness={0.55} roughness={0.35} /></mesh>
      {sel.selected === key && <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.15, 0]}><ringGeometry args={[d / 2 + 0.6, d / 2 + 0.9, 32]} /><meshBasicMaterial color="#2f7cf6" /></mesh>}
    </group>
  );
}

function Well({ f, p, y, sel }: { f: Feature; p: [number, number]; y: number; sel: Sel }) {
  const key = `feature:${f.id}`;
  const geo = useMemo(() => mergeGeometries([
    painted(new THREE.CylinderGeometry(0.85, 0.9, 0.9, 16, 3, true).translate(0, 0.45, 0), (v) => new THREE.Color(Math.floor((v.y + 0.01) / 0.3) % 2 ? "#a49a8a" : "#968c7c")),
    painted(new THREE.TorusGeometry(0.85, 0.1, 6, 18).rotateX(Math.PI / 2).translate(0, 0.9, 0), "#b0a796"),
    painted(new THREE.CircleGeometry(0.8, 16).rotateX(-Math.PI / 2).translate(0, 0.5, 0), "#2c3a40"),
    painted(new THREE.BoxGeometry(0.12, 2, 0.12).translate(-0.8, 1, 0), "#6b4a2f"), painted(new THREE.BoxGeometry(0.12, 2, 0.12).translate(0.8, 1, 0), "#6b4a2f"),
    painted(new THREE.BoxGeometry(1.8, 0.1, 0.12).translate(0, 2, 0), "#6b4a2f"),
  ].map((g) => (g.index ? g.toNonIndexed() : g)), false)!, []);
  return (
    <group position={[p[0], y, p[1]]}>
      <mesh geometry={geo} castShadow onClick={(e) => { e.stopPropagation(); sel.onSelect(key); }}><meshStandardMaterial vertexColors roughness={0.95} side={THREE.DoubleSide} /></mesh>
      {sel.selected === key && <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.1, 0]}><ringGeometry args={[1.4, 1.7, 32]} /><meshBasicMaterial color="#2f7cf6" /></mesh>}
    </group>
  );
}

const SPRAY_ORIGIN: [number, number, number][] = [[0, 0, 0]];

/** Irrigation sprinkler placed by the farmer: riser, head, turning jet; wetted circle only when the radius is declared. */
function Sprinkler({ f, p, y, sel, animate }: { f: Feature; p: [number, number]; y: number; sel: Sel; animate: boolean }) {
  const key = `feature:${f.id}`, R: number | undefined = f.props.radius_m;
  const reach = R ?? 3;                                     // indicative jet when the radius is not declared
  const jet = useMemo(() => {
    const pts = Array.from({ length: 14 }, (_, i) => { const t = i / 13; return new THREE.Vector3(t * reach, 0.9 + t * reach * 0.4 - t * t * reach * 0.55, 0); });
    return new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 20, 0.035, 5, false);
  }, [reach]);
  const spin = useRef<THREE.Group>(null);
  useFrame((_, dt) => { if (animate && spin.current) spin.current.rotation.y += dt * 0.8; });
  return (
    <group position={[p[0], y, p[1]]} onClick={(e) => { e.stopPropagation(); sel.onSelect(key); }}>
      <mesh position={[0, 0.4, 0]} castShadow><cylinderGeometry args={[0.03, 0.04, 0.8, 8]} /><meshStandardMaterial color="#59626a" metalness={0.6} roughness={0.4} /></mesh>
      <mesh position={[0, 0.86, 0]} castShadow><cylinderGeometry args={[0.07, 0.06, 0.12, 12]} /><meshStandardMaterial color="#2f6fb0" roughness={0.5} /></mesh>
      <mesh position={[0, 0.6, 0]} visible={false}><boxGeometry args={[1.2, 1.4, 1.2]} /></mesh>{/* easier to tap */}
      {animate ? <WaterSpray heads={SPRAY_ORIGIN} reach={reach} />
        : <group ref={spin}><mesh geometry={jet} raycast={() => null}><meshStandardMaterial color="#d9eefb" transparent opacity={0.5} roughness={0.1} depthWrite={false} /></mesh></group>}
      {R && <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.08, 0]} raycast={() => null}>
        <circleGeometry args={[R, 48]} /><meshBasicMaterial color="#5aa7e0" transparent opacity={sel.selected === key ? 0.22 : 0.1} depthWrite={false} />
      </mesh>}
      {sel.selected === key && <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.1, 0]}><ringGeometry args={[(R ?? 1.2) - 0.08, R ?? 1.2, 48]} /><meshBasicMaterial color="#2f7cf6" /></mesh>}
    </group>
  );
}

/** Flat ribbon along a polyline, following the terrain. */
function ribbon(pts: [number, number][], width: number, heightAt: (x: number, z: number) => number, lift: number, color: (side: number) => THREE.Color) {
  const pos: number[] = [], col: number[] = [];
  const left: number[][] = [], right: number[][] = [];
  for (let i = 0; i < pts.length; i++) {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
    const dx = b[0] - a[0], dz = b[1] - a[1], len = Math.hypot(dx, dz) || 1, nx = -dz / len, nz = dx / len;
    const [x, z] = pts[i];
    left.push([x + nx * width / 2, z + nz * width / 2]); right.push([x - nx * width / 2, z - nz * width / 2]);
  }
  // densify so long segments follow the hills
  const seg = (p: number[], q: number[], i: number, n: number) => [p[0] + (q[0] - p[0]) * (i / n), p[1] + (q[1] - p[1]) * (i / n)];
  for (let i = 0; i < pts.length - 1; i++) {
    const n = Math.max(1, Math.ceil(Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) / 6));
    for (let k = 0; k < n; k++) {
      const l0 = seg(left[i], left[i + 1], k, n), l1 = seg(left[i], left[i + 1], k + 1, n), r0 = seg(right[i], right[i + 1], k, n), r1 = seg(right[i], right[i + 1], k + 1, n);
      const v = (p: number[]) => [p[0], heightAt(p[0], p[1]) + lift, p[1]];
      const quad = [v(l0), v(r0), v(l1), v(l1), v(r0), v(r1)], side = [1, -1, 1, 1, -1, -1];
      quad.forEach((q, j) => { pos.push(...q); const c = color(side[j]); col.push(c.r, c.g, c.b); });
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  g.setAttribute("uv", new THREE.Float32BufferAttribute(pos.flatMap((_, i) => (i % 3 === 1 ? [] : [pos[i] / 3])), 2));   // x, z in 3 m tiles
  g.computeVertexNormals();
  return g;
}

const SURFACE: Record<string, [string, string]> = { sterrato: ["#d8b88e", "#c8a77c"], ghiaia: ["#f2ece0", "#e2dbcd"], asfalto: ["#55585a", "#3f4244"], cemento: ["#c2beb6", "#a7a39b"] };
const ROAD_FILES = ["/planner/gravel_road_diff_1k.jpg", "/planner/gravel_road_nor_gl_1k.jpg"];

/** Ribbon along a polyline with track coordinates: u across the road (0..1), v along it in road widths / 4. */
function trackRibbon(pts: [number, number][], width: number, heightAt: (x: number, z: number) => number, lift: number) {
  const pos: number[] = [], uv: number[] = [];
  const side = (i: number) => {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
    const dx = b[0] - a[0], dz = b[1] - a[1], len = Math.hypot(dx, dz) || 1;
    return [-dz / len, dx / len];
  };
  let along = 0;
  for (let i = 0; i < pts.length - 1; i++) {
    const [ax, az] = pts[i], [bx, bz] = pts[i + 1], L = Math.hypot(bx - ax, bz - az);
    const na = side(i), nb = side(i + 1);
    const n = Math.max(1, Math.ceil(L / 4));                       // densify: follows the hills, keeps the texture even
    for (let k = 0; k < n; k++) {
      const t0 = k / n, t1 = (k + 1) / n;
      const p = (t: number) => [ax + (bx - ax) * t, az + (bz - az) * t];
      const nrm = (t: number) => [na[0] + (nb[0] - na[0]) * t, na[1] + (nb[1] - na[1]) * t];
      const v = (t: number, s: number): [number, number, number] => {
        const [x, z] = p(t), [nx, nz] = nrm(t), px = x + nx * (s * width) / 2, pz = z + nz * (s * width) / 2;
        return [px, heightAt(px, pz) + lift, pz];
      };
      const v0 = (along + L * t0) / (width * 4), v1 = (along + L * t1) / (width * 4);
      const quad: [[number, number, number], number, number][] = [[v(t0, -1), 0, v0], [v(t0, 1), 1, v0], [v(t1, -1), 0, v1], [v(t1, -1), 0, v1], [v(t0, 1), 1, v0], [v(t1, 1), 1, v1]];
      for (const [q, uu, vv] of quad) { pos.push(...q); uv.push(uu, vv); }
    }
    along += L;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  g.computeVertexNormals();
  return g;
}

const trackCache = new Map<string, THREE.CanvasTexture>();
/** Picture of a farm track seen from above (across = U, along = V, repeats along): dirt with two wheel ruts, a grass strip
 *  in the middle and ragged grassy edges (alpha) for dirt roads; ruts on pale gravel; plain surface for asphalt/concrete. */
function trackTexture(surface: string) {
  const hit = trackCache.get(surface); if (hit) return hit;
  const W = 128, H = 512, r = rng(surface.length * 31 + 7);
  const c = document.createElement("canvas"); c.width = W; c.height = H;
  const g = c.getContext("2d")!, img = g.createImageData(W, H);
  const hex = (h: string) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  const loose = surface === "sterrato" || surface === "ghiaia";
  const base = hex(surface === "sterrato" ? "#b8946a" : surface === "ghiaia" ? "#d9cfbd" : surface === "asfalto" ? "#4f5254" : "#bdb9b1");
  const rut = hex(surface === "sterrato" ? "#8e6c48" : "#b4a891"), grass = hex("#5f8c34"), grass2 = hex("#7aa647");
  // edge wobble per row (ragged verge), smooth along the road; wraps so the tile repeats
  const wob = (y: number, ph: number) => 0.06 + 0.035 * Math.sin((y / H) * Math.PI * 2 * 3 + ph) + 0.02 * Math.sin((y / H) * Math.PI * 2 * 11 + ph * 2);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const u = (x + 0.5) / W, i = (y * W + x) * 4, n = r();
    let col = base.map((v) => v * (0.88 + n * 0.22));
    let a = 255;
    if (loose) {
      const dr = Math.min(Math.abs(u - 0.27), Math.abs(u - 0.73));
      if (dr < 0.075) { const k = 1 - dr / 0.075; col = col.map((v, j) => v + (rut[j] * (0.9 + n * 0.2) - v) * k * 0.85); }
      if (surface === "sterrato" && Math.abs(u - 0.5) < 0.085 + 0.02 * Math.sin(y * 0.11)) col = (n < 0.55 ? grass : grass2).map((v) => v * (0.8 + r() * 0.35));
      const el = wob(y, 0.7), er = wob(y, 2.9);
      if (u < el || u > 1 - er) a = 0;
      else if (u < el + 0.06 || u > 1 - er - 0.06) { if (r() < 0.45) col = (r() < 0.5 ? grass : grass2).map((v) => v * (0.8 + r() * 0.3)); }
    }
    img.data[i] = col[0]; img.data[i + 1] = col[1]; img.data[i + 2] = col[2]; img.data[i + 3] = a;
  }
  g.putImageData(img, 0, 0);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace; t.wrapS = THREE.ClampToEdgeWrapping; t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8;
  trackCache.set(surface, t);
  return t;
}

function Road({ f, pts, terrain, sel }: { f: Feature; pts: [number, number][]; terrain: TerrainSource; sel: Sel }) {
  const w = f.props.width_m ?? 4, surface = SURFACE[f.props.surface ?? "sterrato"] ? (f.props.surface ?? "sterrato") : "sterrato", key = `feature:${f.id}`;
  const geo = useMemo(() => trackRibbon(pts, w, terrain.heightAt, 0.07), [pts, w, terrain]);
  const [, gNor] = useTexture(ROAD_FILES);
  const mat = useMemo(() => {
    gNor.wrapS = gNor.wrapT = THREE.RepeatWrapping;
    return new THREE.MeshStandardMaterial({ map: trackTexture(surface), normalMap: gNor, normalScale: new THREE.Vector2(0.6, 0.6),
      roughness: 1, alphaTest: 0.5, alphaToCoverage: true });
  }, [surface, gNor]);
  const line = useMemo(() => pts.map(([x, z]) => [x, terrain.heightAt(x, z) + 0.3, z] as [number, number, number]), [pts, terrain]);
  return <group>
    <mesh geometry={geo} material={mat} receiveShadow onClick={(e) => { e.stopPropagation(); sel.onSelect(key); }} />
    {sel.selected === key && <Line points={line} color="#2f7cf6" lineWidth={3} />}
  </group>;
}

function Pipe({ f, pts, terrain, sel }: { f: Feature; pts: [number, number][]; terrain: TerrainSource; sel: Sel }) {
  const key = `feature:${f.id}`, buried = f.props.buried !== false;
  const line = useMemo(() => pts.map(([x, z]) => [x, terrain.heightAt(x, z) + (buried ? 0.08 : 0.15), z] as [number, number, number]), [pts, terrain, buried]);
  const tube = useMemo(() => buried ? null : new THREE.TubeGeometry(new THREE.CatmullRomCurve3(line.map((p) => new THREE.Vector3(...p)), false, "catmullrom", 0),
    Math.max(8, line.length * 8), Math.max(0.04, (f.props.diameter_mm ?? 90) / 2000), 8), [line, buried, f.props.diameter_mm]);
  return <group onClick={(e) => { e.stopPropagation(); sel.onSelect(key); }}>
    {buried ? <Line points={line} color="#2f80d1" lineWidth={sel.selected === key ? 5 : 3} dashed dashSize={1.5} gapSize={1} />
      : <mesh geometry={tube!} castShadow><meshStandardMaterial color="#5c6670" roughness={0.6} /></mesh>}
    {sel.selected === key && !buried && <Line points={line} color="#2f7cf6" lineWidth={3} />}
  </group>;
}

function Hedge({ f, pts, terrain, sel }: { f: Feature; pts: [number, number][]; terrain: TerrainSource; sel: Sel }) {
  const key = `feature:${f.id}`, h = f.props.height_m ?? 2.5;
  // trees and shrubs of the hedge: photoscanned impostors, spaced by their height
  const sets = useMemo(() => {
    const r = rng(f.id.length * 7 + 3), a: ImpostorItem[] = [], b: ImpostorItem[] = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const L = Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]);
      const n = Math.max(1, Math.round(L / Math.max(1.2, h * 0.75)));
      for (let k = 0; k < n; k++) {
        const t = (k + 0.5) / n, x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t + (r() - 0.5) * h * 0.15, z = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t + (r() - 0.5) * h * 0.15;
        const k2 = 0.85 + r() * 0.3;
        (r() < 0.55 ? a : b).push({ x, y: terrain.heightAt(x, z) - 0.1, z, h: h * k2, rot: r() * 6.28, tint: new THREE.Color(1.2 + r() * 0.15, 1.32 + r() * 0.12, 1.0 + r() * 0.1) });
      }
    }
    return { a, b };
  }, [pts, h, terrain, f.id]);
  const hit = useMemo(() => ribbon(pts, Math.max(1.5, h * 0.6), terrain.heightAt, h * 0.4, () => new THREE.Color(1, 1, 1)), [pts, h, terrain]);
  return <group>
    <ImpostorSet name="broadleaf_c" items={sets.a} shadows />
    <ImpostorSet name="broadleaf_b" items={sets.b} shadows />
    <mesh geometry={hit} onClick={(e) => { e.stopPropagation(); sel.onSelect(key); }}><meshBasicMaterial transparent opacity={0} depthWrite={false} /></mesh>
    {sel.selected === key && <Line points={pts.map(([x, z]) => [x, terrain.heightAt(x, z) + h + 0.4, z] as [number, number, number])} color="#2f7cf6" lineWidth={3} />}
  </group>;
}

function shapeXZ(pts: [number, number][]) {
  const s = new THREE.Shape(pts.map(([x, z]) => new THREE.Vector2(x, -z)));
  const g = new THREE.ShapeGeometry(s); g.rotateX(-Math.PI / 2); return g;
}

function Pond({ f, pts, sel }: { f: Feature; pts: [number, number][]; sel: Sel }) {
  const key = `feature:${f.id}`;
  const water = useMemo(() => shapeXZ(pts), [pts]);
  const cx = pts.reduce((a, p) => a + p[0], 0) / pts.length, cz = pts.reduce((a, p) => a + p[1], 0) / pts.length;
  const bank = useMemo(() => shapeXZ(pts.map(([x, z]) => [cx + (x - cx) * 1.08, cz + (z - cz) * 1.08] as [number, number])), [pts, cx, cz]);
  return <group onClick={(e) => { e.stopPropagation(); sel.onSelect(key); }}>
    <mesh geometry={bank} position={[0, 0.03, 0]} receiveShadow><meshStandardMaterial color="#7d6a4c" roughness={1} /></mesh>
    <mesh geometry={water} position={[0, 0.06, 0]}><meshStandardMaterial color="#3d6f7c" roughness={0.08} metalness={0.25} envMapIntensity={1.2} /></mesh>
    {sel.selected === key && <Line points={[...pts, pts[0]].map(([x, z]) => [x, 0.3, z] as [number, number, number])} color="#2f7cf6" lineWidth={3} />}
  </group>;
}

/** Impostor of an orchard tree. Fruit is drawn only in the full-season view (month 0): there is no sourced fruiting
 *  calendar, so with a month selected the trees are shown without fruit. Colour by species, red or orange. */
const FRUIT_RED = new Set(["apple", "cherry", "plum"]), FRUIT_ORANGE = new Set(["peach", "apricot", "citrus"]);
function orchardImpostor(species: string, month: number) {
  if (species === "olive") return "olive_a";
  const fruit = !month && FRUIT_RED.has(species) ? "fruit_red" : !month && FRUIT_ORANGE.has(species) ? "fruit_orange" : null;
  return fruit && IMPOSTORS[fruit] ? fruit : "broadleaf_b";
}

/** Rows inside a polygon along its longest edge; spacing from the farmer or an indicative layout. */
function rowsInPolygon(poly: [number, number][], rowGap: number, step: number) {
  let best = 0, ang = 0;
  for (let i = 0; i < poly.length; i++) {
    const a = poly[i], b = poly[(i + 1) % poly.length], l = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (l > best) { best = l; ang = Math.atan2(b[1] - a[1], b[0] - a[0]); }
  }
  const c = Math.cos(ang), s = Math.sin(ang);
  const rot = poly.map(([x, z]) => [x * c + z * s, -x * s + z * c]);          // row direction -> +u
  const us = rot.map((p) => p[0]), vs = rot.map((p) => p[1]);
  const inside = (u: number, v: number) => {
    let k = false;
    for (let i = 0, j = rot.length - 1; i < rot.length; j = i++) {
      const [ui, vi] = rot[i], [uj, vj] = rot[j];
      if ((vi > v) !== (vj > v) && u < ((uj - ui) * (v - vi)) / (vj - vi) + ui) k = !k;
    }
    return k;
  };
  const pts: XY[] = [];
  for (let v = Math.min(...vs) + rowGap / 2; v < Math.max(...vs); v += rowGap)
    for (let u = Math.min(...us) + step / 2; u < Math.max(...us); u += step)
      if (inside(u, v)) pts.push([u * c - v * s, u * s + v * c]);
  return { pts, angle: ang };
}

function Planting({ f, pts, model, month, sel, quality }: { f: Feature; pts: [number, number][]; model: CropModel; month: number; sel: Sel; quality: { plantShadows: boolean; plantLod: number } }) {
  const key = `feature:${f.id}`;
  const h = f.height_m ? (f.height_m[0] + f.height_m[1]) / 2 : 3;
  const vine = f.kind === "vineyard";
  const rowGap = f.props.row_spacing_m ?? (vine ? 2.5 : Math.max(3.5, h * 1.2));
  const step = (vine ? f.props.plant_spacing_m : f.props.tree_spacing_m) ?? (vine ? 1 : Math.max(1.5, h * 0.7));
  const { pts: plants, angle } = useMemo(() => rowsInPolygon(pts, rowGap, step), [pts, rowGap, step]);
  const limited = plants.slice(0, 4000);
  const trees = useMemo<ImpostorItem[] | null>(() => {
    if (vine) return null;
    const r = rng(f.id.length * 13 + 1);
    return limited.map(([x, z]) => ({ x, y: 0, z, h: h * (0.88 + r() * 0.24), rot: r() * 6.28,
      tint: new THREE.Color(0.98 + r() * 0.1, 1.24 + r() * 0.1, 0.9 + r() * 0.08) }));   // greener leaves; red fruit keeps its hue
  }, [limited, h, vine, f.id]);
  const area = useMemo(() => shapeXZ(pts), [pts]);
  if (trees) return <group>
    <ImpostorSet name={orchardImpostor(f.props.species, month)} items={trees} shadows={quality.plantShadows} />
    <mesh geometry={area} position={[0, 0.05, 0]} onClick={(e) => { e.stopPropagation(); sel.onSelect(key); }}><meshBasicMaterial transparent opacity={0} depthWrite={false} /></mesh>
    {sel.selected === key && <Line points={[...pts, pts[0]].map(([x, z]) => [x, 0.4, z] as [number, number, number])} color="#2f7cf6" lineWidth={3} />}
  </group>;
  // the vine model is planar along X: turn every plant along the row (CropField rotates by index, so use a wrapper group per row angle)
  return <group onClick={(e) => { e.stopPropagation(); sel.onSelect(key); }}>
    <CropField model={model} pts={limited} offset={[0, 0]} scale={h} spacing={Math.max(rowGap, step)} seed={f.id.length} stage={month ? "growing" : "mature"}
      shadows={quality.plantShadows} lodDist={vine ? [quality.plantLod * 0.22, quality.plantLod * 1.6] : [quality.plantLod * 0.5, quality.plantLod * 3]} onPick={() => sel.onSelect(key)} onOver={() => {}} onOut={() => {}}
      fixedRotation={vine ? -angle : undefined} />
    {vine && <VineTrellis plants={limited} angle={angle} h={h} />}
    {sel.selected === key && <Line points={[...pts, pts[0]].map(([x, z]) => [x, 0.4, z] as [number, number, number])} color="#2f7cf6" lineWidth={3} />}
  </group>;
}

/** Posts every few metres along each vineyard row. */
function VineTrellis({ plants, angle, h }: { plants: XY[]; angle: number; h: number }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const posts = useMemo(() => plants.filter((_, i) => i % 5 === 0), [plants]);
  useLayoutEffect(() => {
    const m = ref.current; if (!m) return;
    const o = new THREE.Object3D();
    posts.forEach(([x, z], i) => { o.position.set(x + Math.cos(angle) * 0.5, h * 0.55, z + Math.sin(angle) * 0.5); o.scale.set(1, h * 1.1, 1); o.updateMatrix(); m.setMatrixAt(i, o.matrix); });
    m.instanceMatrix.needsUpdate = true; m.computeBoundingSphere();
  }, [posts, angle, h]);
  return <instancedMesh ref={ref} args={[undefined, undefined, posts.length]} raycast={() => null}>
    <boxGeometry args={[0.07, 1, 0.07]} /><meshStandardMaterial color="#7a6a55" roughness={1} />
  </instancedMesh>;
}

export function Structures({ features, farmRef: ref, terrain, month, selected, onSelect, quality }: {
  features: Feature[]; farmRef: FarmRef | null; terrain: TerrainSource; month: number; selected: string | null; onSelect: (k: string) => void;
  quality: { plantShadows: boolean; plantLod: number; wind?: boolean };
}) {
  const species = useMemo(() => [...new Set(features.filter((f) => f.kind === "orchard" || f.kind === "vineyard").map((f) => f.props.species).filter(Boolean))].sort() as string[], [features]);
  const trees = useTreeModels(species);
  if (!ref) return null;
  const sel = { selected, onSelect };
  return <>{features.map((f) => {
    const pts = featurePoints(f, ref);
    const label = (
      selected === `feature:${f.id}` && (
        <Html position={[pts[0][0], terrain.heightAt(pts[0][0], pts[0][1]) + 6, pts[0][1]]} center zIndexRange={[20, 0]} style={{ pointerEvents: "none" }}>
          <div className="vp-tip"><b>{f.name}</b><span>{f.label}{f.species_name ? ` · ${f.species_name}` : ""}</span></div>
        </Html>
      ));
    const y = terrain.heightAt(pts[0][0], pts[0][1]);
    let node: React.ReactNode = null;
    if (f.kind === "building") node = (f.props.type ?? "casale") === "casale" ? <CasaleBuilding f={f} p={pts[0]} y={y} sel={sel} /> : <Building f={f} p={pts[0]} y={y} sel={sel} />;
    else if (f.kind === "tank") node = <Tank f={f} p={pts[0]} y={y} sel={sel} />;
    else if (f.kind === "well") node = <Well f={f} p={pts[0]} y={y} sel={sel} />;
    else if (f.kind === "sprinkler") node = <Sprinkler f={f} p={pts[0]} y={y} sel={sel} animate={quality.wind ?? true} />;
    else if (f.kind === "road") node = <Road f={f} pts={pts} terrain={terrain} sel={sel} />;
    else if (f.kind === "pipe") node = <Pipe f={f} pts={pts} terrain={terrain} sel={sel} />;
    else if (f.kind === "hedge") node = <Hedge f={f} pts={pts} terrain={terrain} sel={sel} />;
    else if (f.kind === "pond") node = <Pond f={f} pts={pts.slice(0, -1)} sel={sel} />;
    else if ((node = equipmentNode(f, pts, y, terrain, sel))) { /* greenhouse, net, fence, machines, hives, compost, solar */ }
    else if ((f.kind === "orchard" || f.kind === "vineyard") && trees[f.props.species]) node = <Planting f={f} pts={pts.slice(0, -1)} model={trees[f.props.species]} month={month} sel={sel} quality={quality} />;
    return <group key={f.id}>{node}{label}</group>;
  })}</>;
}
