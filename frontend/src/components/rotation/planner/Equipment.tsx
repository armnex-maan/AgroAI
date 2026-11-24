/**
 * Farm elements added in the "attrezzature" update: greenhouses (tunnel, glass, shade house), cover nets, fences,
 * machines and equipment, beehives, compost bins, solar panels. Each one comes from a farm_features row and is
 * selectable; sizes are the real ones drawn on the ground, the look is procedural (no third-party models).
 */
import { useMemo } from "react";
import { Line } from "@react-three/drei";
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import type { Feature } from "./Structures";
import { TerrainSource } from "./engine/terrain";

interface Sel { selected: string | null; onSelect: (k: string) => void }
type P = [number, number];

/** Rectangle aligned with the longest side of a polygon: centre, angle, length (along) and width. */
export function orientedRect(pts: P[]) {
  let best = 0, ang = 0;
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length], l = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (l > best) { best = l; ang = Math.atan2(b[1] - a[1], b[0] - a[0]); }
  }
  const c = Math.cos(ang), s = Math.sin(ang);
  const u = pts.map(([x, z]) => x * c + z * s), v = pts.map(([x, z]) => -x * s + z * c);
  const u0 = Math.min(...u), u1 = Math.max(...u), v0 = Math.min(...v), v1 = Math.max(...v);
  const uc = (u0 + u1) / 2, vc = (v0 + v1) / 2;
  return { cx: uc * c - vc * s, cz: uc * s + vc * c, ang, L: u1 - u0, W: v1 - v0 };
}

const outlineLine = (pts: P[], y: number) => [...pts, pts[0]].map(([x, z]) => [x, y, z] as [number, number, number]);
const click = (sel: Sel, key: string) => (e: { stopPropagation: () => void }) => { e.stopPropagation(); sel.onSelect(key); };

// ---------------------------------------------------------------- greenhouse
function GreenhouseF({ f, pts, y, sel }: { f: Feature; pts: P[]; y: number; sel: Sel }) {
  const key = `feature:${f.id}`, type = f.props.type ?? "tunnel";
  const r = useMemo(() => orientedRect(pts), [pts]);
  const H = f.props.height_m ?? (type === "vetro" ? 4.5 : type === "ombraio" ? 3.5 : 3.2);
  const frame = useMemo(() => {
    const parts: THREE.BufferGeometry[] = [];
    const n = Math.max(2, Math.round(r.L / 2.5));
    for (let i = 0; i <= n; i++) {
      const u = -r.L / 2 + (i * r.L) / n;
      if (type === "tunnel") {
        const arc = new THREE.TorusGeometry(r.W / 2, 0.035, 4, 18, Math.PI);
        arc.scale(1, (H) / (r.W / 2), 1); arc.rotateY(Math.PI / 2); arc.translate(u, 0, 0);
        parts.push(arc);
      } else {
        for (const v of [-r.W / 2, r.W / 2]) parts.push(new THREE.BoxGeometry(0.08, H * 0.75, 0.08).translate(u, H * 0.375, v));
        parts.push(new THREE.BoxGeometry(0.06, 0.06, r.W).translate(u, H * 0.75, 0));
      }
    }
    return mergeGeometries(parts.map((g) => (g.index ? g.toNonIndexed() : g)), false)!;
  }, [r.L, r.W, H, type]);
  const skin = useMemo(() => {
    if (type === "tunnel") {
      const g = new THREE.CylinderGeometry(r.W / 2, r.W / 2, r.L, 24, 1, false, 0, Math.PI);
      g.rotateZ(Math.PI / 2); g.rotateX(-Math.PI / 2); g.scale(1, H / (r.W / 2), 1);
      return g;
    }
    const wall = new THREE.BoxGeometry(r.L, H * 0.75, r.W).translate(0, H * 0.375, 0);
    if (type === "ombraio") return wall;
    const roof = new THREE.CylinderGeometry(0.01, r.W / 2 / Math.SQRT1_2, H * 0.25, 4, 1).rotateY(Math.PI / 4).scale(r.L / r.W, 1, 1).translate(0, H * 0.875, 0);
    return mergeGeometries([wall.toNonIndexed(), roof.toNonIndexed()], false)!;
  }, [r.L, r.W, H, type]);
  const film = type === "ombraio" ? { color: "#2f3a35", opacity: 0.55 } : type === "vetro" ? { color: "#dfeef4", opacity: 0.28 } : { color: "#f1f6f8", opacity: 0.4 };
  if (type === "vetro") return <GlassHouse r={r} H={H} y={y} pts={pts} sel={sel} k={key} />;
  return (
    <group onClick={click(sel, key)}>
      <group position={[r.cx, y, r.cz]} rotation={[0, -r.ang, 0]}>
        <mesh geometry={frame} castShadow><meshStandardMaterial color="#b9c2c6" metalness={0.6} roughness={0.35} /></mesh>
        <mesh geometry={skin}><meshStandardMaterial color={film.color} transparent opacity={film.opacity} roughness={0.15} metalness={0.05} side={THREE.DoubleSide} depthWrite={false} /></mesh>
      </group>
      {sel.selected === key && <Line points={outlineLine(pts, y + 0.2)} color="#2f7cf6" lineWidth={3} />}
    </group>
  );
}

/** Multi-span glass greenhouse: arched roof spans along the long side, aluminium frame, reflective glass, a
 *  concrete floor with walkways and growing benches (structure only: crops inside are drawn only when planned). */
function GlassHouse({ r, H, y, pts, sel, k }: { r: ReturnType<typeof orientedRect>; H: number; y: number; pts: P[]; sel: Sel; k: string }) {
  const spans = Math.max(1, Math.round(r.W / 8));
  const sw = r.W / spans, wallH = H * 0.72, rise = Math.min(sw * 0.32, H - wallH + 0.6);
  const geo = useMemo(() => {
    const frame: THREE.BufferGeometry[] = [], glass: THREE.BufferGeometry[] = [], floor: THREE.BufferGeometry[] = [];
    const bays = Math.max(2, Math.round(r.L / 3));
    // walls: glass panels and posts
    for (const v of [-r.W / 2, r.W / 2]) {
      glass.push(new THREE.PlaneGeometry(r.L, wallH).translate(0, wallH / 2, v));
      for (let i = 0; i <= bays; i++) frame.push(new THREE.BoxGeometry(0.09, wallH, 0.09).translate(-r.L / 2 + (i * r.L) / bays, wallH / 2, v));
    }
    for (const u of [-r.L / 2, r.L / 2]) {
      glass.push(new THREE.PlaneGeometry(r.W, wallH).rotateY(Math.PI / 2).translate(u, wallH / 2, 0));
      for (let j = 0; j <= spans * 2; j++) frame.push(new THREE.BoxGeometry(0.09, wallH, 0.09).translate(u, wallH / 2, -r.W / 2 + (j * r.W) / (spans * 2)));
    }
    for (const h of [0.05, wallH * 0.5, wallH]) for (const v of [-r.W / 2, r.W / 2]) frame.push(new THREE.BoxGeometry(r.L, 0.07, 0.08).translate(0, h, v));
    for (let s = 0; s < spans; s++) {
      const c = -r.W / 2 + sw * (s + 0.5);
      // arched roof: half cylinder flattened to the rise, along the length
      const roof = new THREE.CylinderGeometry(sw / 2, sw / 2, r.L, 28, 1, true, -Math.PI / 2, Math.PI);
      roof.rotateZ(Math.PI / 2); roof.scale(1, rise / (sw / 2), 1); roof.translate(0, wallH, c);
      glass.push(roof);
      for (const u of [-r.L / 2, r.L / 2]) {        // gable ends of each span
        const end = new THREE.CircleGeometry(sw / 2, 24, 0, Math.PI); end.scale(1, rise / (sw / 2), 1); end.rotateY(Math.PI / 2); end.translate(u, wallH, c);
        glass.push(end);
      }
      for (let i = 0; i <= bays; i++) {             // arches
        const a = new THREE.TorusGeometry(sw / 2, 0.035, 4, 20, Math.PI); a.scale(1, rise / (sw / 2), 1); a.rotateY(Math.PI / 2); a.translate(-r.L / 2 + (i * r.L) / bays, wallH, c);
        frame.push(a);
      }
      frame.push(new THREE.BoxGeometry(r.L, 0.06, 0.06).translate(0, wallH + rise, c));                         // ridge
      if (s > 0) frame.push(new THREE.BoxGeometry(r.L, 0.12, 0.22).translate(0, wallH, -r.W / 2 + sw * s));   // gutter
      for (const off of [-0.32, 0.32]) frame.push(new THREE.BoxGeometry(r.L, 0.04, 0.04).translate(0, wallH + rise * 0.82, c + off * sw)); // purlins
    }
    // floor: concrete walkway along the middle, benches across
    floor.push(new THREE.BoxGeometry(r.L * 0.98, 0.04, r.W * 0.98).translate(0, 0.02, 0));
    const benches: THREE.BufferGeometry[] = [];
    const nb = Math.max(2, Math.floor((r.L - 2) / 2.2));
    for (let i = 0; i < nb; i++) for (const side of [-1, 1])
      benches.push(new THREE.BoxGeometry(1.4, 0.75, r.W / 2 - 1.4).translate(-r.L / 2 + 1.2 + i * 2.2, 0.375, side * (r.W / 4 + 0.35)));
    const ni = (g: THREE.BufferGeometry) => (g.index ? g.toNonIndexed() : g);
    const strip = (g: THREE.BufferGeometry) => { const n = ni(g); n.deleteAttribute("uv"); return n; };
    return { frame: mergeGeometries(frame.map(strip), false)!, glass: mergeGeometries(glass.map(strip), false)!,
      floor: mergeGeometries(floor.map(strip), false)!, benches: mergeGeometries(benches.map(strip), false)! };
  }, [r.L, r.W, spans, sw, wallH, rise]);
  return (
    <group onClick={click(sel, k)}>
      <group position={[r.cx, y, r.cz]} rotation={[0, -r.ang, 0]}>
        <mesh geometry={geo.floor} receiveShadow><meshStandardMaterial color="#9c9a92" roughness={0.9} /></mesh>
        <mesh geometry={geo.benches} castShadow receiveShadow><meshStandardMaterial color="#7d8a86" roughness={0.6} metalness={0.3} /></mesh>
        <mesh geometry={geo.frame} castShadow receiveShadow><meshStandardMaterial color="#eef2f3" metalness={0.55} roughness={0.32} /></mesh>
        <mesh geometry={geo.glass} renderOrder={2}>
          <meshPhysicalMaterial color="#e8f4f8" transparent opacity={0.22} roughness={0.04} metalness={0.15} envMapIntensity={1.6}
            clearcoat={1} clearcoatRoughness={0.05} side={THREE.DoubleSide} depthWrite={false} />
        </mesh>
      </group>
      {sel.selected === k && <Line points={outlineLine(pts, y + 0.2)} color="#2f7cf6" lineWidth={3} />}
    </group>
  );
}

// ---------------------------------------------------------------- cover net (hail, shade, insect)
function Net({ f, pts, y, sel }: { f: Feature; pts: P[]; y: number; sel: Sel }) {
  const key = `feature:${f.id}`, H = f.props.height_m ?? 4;
  const shape = useMemo(() => { const g = new THREE.ShapeGeometry(new THREE.Shape(pts.map(([x, z]) => new THREE.Vector2(x, -z)))); g.rotateX(-Math.PI / 2); return g; }, [pts]);
  const posts = useMemo(() => {
    const out: P[] = [];
    pts.forEach((a, i) => { const b = pts[(i + 1) % pts.length], n = Math.max(1, Math.round(Math.hypot(b[0] - a[0], b[1] - a[1]) / 6));
      for (let k = 0; k < n; k++) out.push([a[0] + ((b[0] - a[0]) * k) / n, a[1] + ((b[1] - a[1]) * k) / n]); });
    return mergeGeometries(out.map(([x, z]) => new THREE.CylinderGeometry(0.05, 0.06, H, 6).translate(x, H / 2, z).toNonIndexed()), false)!;
  }, [pts, H]);
  const color = f.props.type === "ombreggiante" ? "#1f2a24" : f.props.type === "antinsetto" ? "#e9eef0" : "#2b3134";
  return (
    <group onClick={click(sel, key)}>
      <mesh geometry={posts} position={[0, y, 0]} castShadow><meshStandardMaterial color="#9aa3a6" roughness={0.6} /></mesh>
      <mesh geometry={shape} position={[0, y + H, 0]}><meshStandardMaterial color={color} transparent opacity={f.props.type === "ombreggiante" ? 0.55 : 0.28} side={THREE.DoubleSide} depthWrite={false} /></mesh>
      <Line points={outlineLine(pts, y + H)} color={sel.selected === key ? "#2f7cf6" : "#59626a"} lineWidth={sel.selected === key ? 3 : 1.5} />
    </group>
  );
}

// ---------------------------------------------------------------- fence
function Fence({ f, pts, terrain, sel }: { f: Feature; pts: P[]; terrain: TerrainSource; sel: Sel }) {
  const key = `feature:${f.id}`, type = f.props.type ?? "rete_metallica", H = f.props.height_m ?? (type === "staccionata" ? 1.2 : 1.8);
  const geo = useMemo(() => {
    const parts: THREE.BufferGeometry[] = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1], len = Math.hypot(b[0] - a[0], b[1] - a[1]), n = Math.max(1, Math.round(len / (type === "staccionata" ? 2 : 3)));
      const ang = Math.atan2(b[1] - a[1], b[0] - a[0]);
      for (let k = 0; k <= n; k++) {
        const x = a[0] + ((b[0] - a[0]) * k) / n, z = a[1] + ((b[1] - a[1]) * k) / n, y0 = terrain.heightAt(x, z);
        parts.push((type === "staccionata" ? new THREE.BoxGeometry(0.12, H, 0.12) : new THREE.CylinderGeometry(0.03, 0.03, H, 5)).translate(x, y0 + H / 2, z).toNonIndexed());
      }
      const rails = type === "staccionata" ? [0.45, 0.85] : type === "elettrica" ? [0.3, 0.6, 0.9] : [0.98];
      const mx = (a[0] + b[0]) / 2, mz = (a[1] + b[1]) / 2, my = terrain.heightAt(mx, mz);
      for (const t of rails) parts.push(new THREE.BoxGeometry(len, type === "staccionata" ? 0.1 : 0.015, type === "staccionata" ? 0.05 : 0.015).rotateY(-ang).translate(mx, my + H * t, mz).toNonIndexed());
    }
    return mergeGeometries(parts, false)!;
  }, [pts, terrain, H, type]);
  const mesh = useMemo(() => {   // the wire mesh panel of a metal fence: a see-through ribbon
    if (type !== "rete_metallica") return null;
    const pos: number[] = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const [ax, az] = pts[i], [bx, bz] = pts[i + 1], ya = terrain.heightAt(ax, az), yb = terrain.heightAt(bx, bz);
      pos.push(ax, ya, az, bx, yb, bz, bx, yb + H, bz, ax, ya, az, bx, yb + H, bz, ax, ya + H, az);
    }
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.computeVertexNormals(); return g;
  }, [pts, terrain, H, type]);
  const color = type === "staccionata" ? "#8a6a48" : "#8f989c";
  return (
    <group onClick={click(sel, key)}>
      <mesh geometry={geo} castShadow><meshStandardMaterial color={color} roughness={0.7} metalness={type === "staccionata" ? 0 : 0.5} /></mesh>
      {mesh && <mesh geometry={mesh}><meshStandardMaterial color="#9aa4a8" transparent opacity={0.22} side={THREE.DoubleSide} depthWrite={false} /></mesh>}
      {sel.selected === key && <Line points={pts.map(([x, z]) => [x, terrain.heightAt(x, z) + H + 0.3, z] as [number, number, number])} color="#2f7cf6" lineWidth={3} />}
    </group>
  );
}

// ---------------------------------------------------------------- machines and equipment
const box = (w: number, h: number, d: number, x: number, y: number, z: number) => new THREE.BoxGeometry(w, h, d).translate(x, y + h / 2, z).toNonIndexed();
const wheel = (r: number, w: number, x: number, z: number) => new THREE.CylinderGeometry(r, r, w, 16).rotateX(Math.PI / 2).translate(x, r, z).toNonIndexed();

function machineParts(type: string): { body: THREE.BufferGeometry[]; dark: THREE.BufferGeometry[]; glass: THREE.BufferGeometry[]; color: string } {
  if (type === "trattore") return { color: "#2f7d3a",   // body, cabin, wheels (front small, rear large)
    body: [box(2.2, 0.9, 1.0, 0.2, 0.75, 0), box(1.2, 0.25, 1.6, -0.6, 1.55, 0), box(0.12, 0.6, 0.12, 1.1, 1.65, 0.3)],
    dark: [wheel(0.75, 0.45, -0.7, 0.85), wheel(0.75, 0.45, -0.7, -0.85), wheel(0.45, 0.3, 1.0, 0.7), wheel(0.45, 0.3, 1.0, -0.7)],
    glass: [box(1.1, 1.0, 1.4, -0.6, 1.65, 0)] };
  if (type === "motocoltivatore") return { color: "#c9402f",
    body: [box(0.6, 0.45, 0.5, 0, 0.35, 0), box(1.2, 0.05, 0.05, -0.8, 0.85, 0.22), box(1.2, 0.05, 0.05, -0.8, 0.85, -0.22)],
    dark: [wheel(0.3, 0.15, 0.1, 0.35), wheel(0.3, 0.15, 0.1, -0.35)], glass: [] };
  if (type === "atomizzatore") return { color: "#e2a11d",
    body: [new THREE.CylinderGeometry(0.6, 0.6, 1.6, 16).rotateZ(Math.PI / 2).translate(0, 1.0, 0).toNonIndexed(), box(0.4, 0.9, 1.3, -1.0, 0.6, 0)],
    dark: [wheel(0.4, 0.25, 0.1, 0.7), wheel(0.4, 0.25, 0.1, -0.7)], glass: [] };
  if (type === "rimorchio") return { color: "#3b5f8f",
    body: [box(3.5, 0.15, 1.9, 0, 0.75, 0), box(3.5, 0.6, 0.06, 0, 0.9, 0.92), box(3.5, 0.6, 0.06, 0, 0.9, -0.92), box(0.06, 0.6, 1.9, 1.72, 0.9, 0), box(0.06, 0.6, 1.9, -1.72, 0.9, 0), box(1.2, 0.08, 0.08, 2.3, 0.7, 0)],
    dark: [wheel(0.45, 0.25, 0, 1.0), wheel(0.45, 0.25, 0, -1.0)], glass: [] };
  if (type === "pompa") return { color: "#2f6fb0",
    body: [box(0.8, 0.5, 0.5, 0, 0, 0), new THREE.CylinderGeometry(0.08, 0.08, 1.2, 8).rotateZ(Math.PI / 2).translate(-0.9, 0.3, 0).toNonIndexed()],
    dark: [box(0.9, 0.08, 0.6, 0, 0, 0)], glass: [] };
  return { color: "#d8dcd6",   // centralina irrigazione: cabinet on a post
    body: [box(0.6, 0.8, 0.3, 0, 0.6, 0)], dark: [box(0.08, 0.6, 0.08, 0, 0, 0)], glass: [] };
}

function Machine({ f, p, y, sel }: { f: Feature; p: P; y: number; sel: Sel }) {
  const key = `feature:${f.id}`, type = f.props.type ?? "trattore";
  const g = useMemo(() => {
    const m = machineParts(type);
    const merge = (l: THREE.BufferGeometry[]) => (l.length ? mergeGeometries(l, false)! : null);
    return { body: merge(m.body), dark: merge(m.dark), glass: merge(m.glass), color: m.color };
  }, [type]);
  return (
    <group position={[p[0], y, p[1]]} rotation={[0, THREE.MathUtils.degToRad(f.props.rotation_deg ?? 0), 0]} onClick={click(sel, key)}>
      {g.body && <mesh geometry={g.body} castShadow><meshStandardMaterial color={g.color} roughness={0.45} metalness={0.3} /></mesh>}
      {g.dark && <mesh geometry={g.dark} castShadow><meshStandardMaterial color="#25282a" roughness={0.85} /></mesh>}
      {g.glass && <mesh geometry={g.glass}><meshStandardMaterial color="#cfe3ec" transparent opacity={0.35} roughness={0.1} metalness={0.2} /></mesh>}
      <mesh visible={false}><boxGeometry args={[3, 2.5, 2.5]} /></mesh>
      {sel.selected === key && <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.08, 0]}><ringGeometry args={[2.2, 2.45, 40]} /><meshBasicMaterial color="#2f7cf6" /></mesh>}
    </group>
  );
}

// ---------------------------------------------------------------- beehives, compost bin, solar panels
function Beehives({ f, p, y, sel }: { f: Feature; p: P; y: number; sel: Sel }) {
  const key = `feature:${f.id}`, n = Math.min(12, Math.max(1, Math.round(f.props.count ?? 3)));
  const geo = useMemo(() => mergeGeometries(Array.from({ length: n }, (_, i) => [box(0.5, 0.25, 0.42, i * 0.9, 0.3, 0), box(0.5, 0.28, 0.42, i * 0.9, 0.56, 0),
    box(0.56, 0.06, 0.48, i * 0.9, 0.84, 0), box(0.5, 0.3, 0.06, i * 0.9, 0, 0.15), box(0.5, 0.3, 0.06, i * 0.9, 0, -0.15)]).flat(), false)!, [n]);
  return (
    <group position={[p[0] - (n - 1) * 0.45, y, p[1]]} onClick={click(sel, key)}>
      <mesh geometry={geo} castShadow><meshStandardMaterial color="#e8c25a" roughness={0.8} /></mesh>
      {sel.selected === key && <mesh rotation={[-Math.PI / 2, 0, 0]} position={[(n - 1) * 0.45, 0.05, 0]}><ringGeometry args={[n * 0.5 + 0.4, n * 0.5 + 0.6, 32]} /><meshBasicMaterial color="#2f7cf6" /></mesh>}
    </group>
  );
}

function Compost({ f, p, y, sel }: { f: Feature; p: P; y: number; sel: Sel }) {
  const key = `feature:${f.id}`, side = Math.cbrt(Math.max(0.2, f.props.volume_m3 ?? 1)) * 1.1;
  const geo = useMemo(() => mergeGeometries(Array.from({ length: 5 }, (_, i) => [box(side, 0.12, 0.04, 0, i * 0.17, side / 2), box(side, 0.12, 0.04, 0, i * 0.17, -side / 2),
    box(0.04, 0.12, side, side / 2, i * 0.17, 0), box(0.04, 0.12, side, -side / 2, i * 0.17, 0)]).flat(), false)!, [side]);
  return (
    <group position={[p[0], y, p[1]]} onClick={click(sel, key)}>
      <mesh geometry={geo} castShadow><meshStandardMaterial color="#8a6a48" roughness={0.9} /></mesh>
      <mesh position={[0, 0.3, 0]}><boxGeometry args={[side * 0.95, 0.6, side * 0.95]} /><meshStandardMaterial color="#5b4630" roughness={1} /></mesh>
      {sel.selected === key && <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.05, 0]}><ringGeometry args={[side, side + 0.2, 32]} /><meshBasicMaterial color="#2f7cf6" /></mesh>}
    </group>
  );
}

function Solar({ f, pts, y, sel }: { f: Feature; pts: P[]; y: number; sel: Sel }) {
  const key = `feature:${f.id}`;
  const r = useMemo(() => orientedRect(pts), [pts]);
  const geo = useMemo(() => {
    const rows = Math.max(1, Math.floor(r.W / 4)), cols = Math.max(1, Math.floor(r.L / 2.1)), out: THREE.BufferGeometry[] = [];
    for (let i = 0; i < rows; i++) for (let j = 0; j < cols; j++) {
      const u = -r.L / 2 + (j + 0.5) * (r.L / cols), v = -r.W / 2 + (i + 0.5) * (r.W / rows);
      out.push(new THREE.BoxGeometry(2, 0.05, 2.2).rotateX(-0.5).translate(u, 1.1, v).toNonIndexed(), box(0.08, 1.0, 0.08, u, 0, v + 0.5), box(0.08, 0.6, 0.08, u, 0, v - 0.5));
    }
    return mergeGeometries(out, false)!;
  }, [r]);
  return (
    <group onClick={click(sel, key)}>
      <mesh geometry={geo} position={[r.cx, y, r.cz]} rotation={[0, -r.ang, 0]} castShadow><meshStandardMaterial color="#1d2b4a" metalness={0.6} roughness={0.25} /></mesh>
      {sel.selected === key && <Line points={outlineLine(pts, y + 0.2)} color="#2f7cf6" lineWidth={3} />}
    </group>
  );
}

/** Renders one of the new element kinds, or null when the kind is handled elsewhere. */
export function equipmentNode(f: Feature, pts: P[], y: number, terrain: TerrainSource, sel: Sel): React.ReactNode | null {
  const poly = f.geometry.type === "Polygon" ? pts.slice(0, -1) : pts;
  switch (f.kind) {
    case "greenhouse": return <GreenhouseF f={f} pts={poly} y={y} sel={sel} />;
    case "net": return <Net f={f} pts={poly} y={y} sel={sel} />;
    case "fence": return <Fence f={f} pts={pts} terrain={terrain} sel={sel} />;
    case "equipment": return <Machine f={f} p={pts[0]} y={y} sel={sel} />;
    case "beehive": return <Beehives f={f} p={pts[0]} y={y} sel={sel} />;
    case "compost": return <Compost f={f} p={pts[0]} y={y} sel={sel} />;
    case "solar": return <Solar f={f} pts={poly} y={y} sel={sel} />;
    default: return null;
  }
}
