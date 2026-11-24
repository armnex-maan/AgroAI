/**
 * Interactive editing in the 3D/2D scene (phase 4): handles to move and resize a plot section, and to move a farm
 * element or its vertices. Dragging works on the ground plane (y = 0); the camera controls pause while dragging.
 * Nothing is written here: the new shape is handed to the planner, which keeps it as an unsaved change.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { ThreeEvent, useFrame } from "@react-three/fiber";
import { Html, Line } from "@react-three/drei";
import * as THREE from "three";
import { fmtArea } from "../types";

export interface Rect { x: number; y: number; w: number; h: number }
type Mode = "move" | "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

const snap = (v: number) => Math.round(v * 10) / 10;            // 10 cm
const MIN = 0.3;
const PLANE = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const fmt = (v: number) => v.toLocaleString("it-IT", { maximumFractionDigits: 1 });

function useDrag(controls: React.MutableRefObject<any>) {
  const hit = useMemo(() => new THREE.Vector3(), []);
  const ground = (e: ThreeEvent<PointerEvent>): [number, number] | null => (e.ray.intersectPlane(PLANE, hit) ? [hit.x, hit.z] : null);
  const grab = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    (e.target as unknown as Element).setPointerCapture?.(e.pointerId);
    if (controls.current) controls.current.enabled = false;
  };
  const release = (e: ThreeEvent<PointerEvent>) => {
    (e.target as unknown as Element).releasePointerCapture?.(e.pointerId);
    if (controls.current) controls.current.enabled = true;
  };
  return { ground, grab, release };
}

function Handle({ pos, size, color = "#ffffff", ring, onDown, onMove, onUp, cursor }: {
  pos: [number, number, number]; size: number; color?: string; ring?: boolean; cursor: string;
  onDown: (e: ThreeEvent<PointerEvent>) => void; onMove: (e: ThreeEvent<PointerEvent>) => void; onUp: (e: ThreeEvent<PointerEvent>) => void;
}) {
  const [hover, setHover] = useState(false);
  const ref = useRef<THREE.Mesh>(null);
  useEffect(() => () => { document.body.style.cursor = ""; }, []);
  // constant size on screen: `size` is in pixels (about), whatever the zoom
  useFrame(({ camera, size: vp }) => {
    const m = ref.current; if (!m) return;
    const px = (camera as THREE.OrthographicCamera).isOrthographicCamera ? 1 / (camera as THREE.OrthographicCamera).zoom
      : (camera.position.distanceTo(m.position) * 2 * Math.tan(((camera as THREE.PerspectiveCamera).fov * Math.PI) / 360)) / vp.height;
    m.scale.setScalar(px * size * (hover ? 1.25 : 1));
  });
  return (
    <mesh ref={ref} position={pos} renderOrder={20} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onClick={(e) => e.stopPropagation()}
      onPointerOver={(e) => { e.stopPropagation(); setHover(true); document.body.style.cursor = cursor; }}
      onPointerOut={() => { setHover(false); document.body.style.cursor = ""; }}>
      {ring ? <cylinderGeometry args={[0.5, 0.5, 0.2, 24]} /> : <boxGeometry args={[1, 0.5, 1]} />}
      <meshBasicMaterial color={hover ? "#2f7cf6" : color} depthTest={false} transparent opacity={0.95} />
    </mesh>
  );
}

/** Move (centre handle) and resize (corners and edges) of an axis-aligned section inside its plot. */
export function SectionGizmo({ rect, offset, limit, controls, onCommit }: {
  rect: Rect; offset: [number, number]; limit: { W: number; L: number }; controls: React.MutableRefObject<any>; onCommit: (r: Rect) => void;
}) {
  const [draft, setDraft] = useState(rect);
  const live = useRef(rect);
  const start = useRef<{ mode: Mode; r: Rect; p: [number, number] } | null>(null);
  useEffect(() => { setDraft(rect); live.current = rect; }, [rect.x, rect.y, rect.w, rect.h]); // eslint-disable-line react-hooks/exhaustive-deps
  const { ground, grab, release } = useDrag(controls);
  const set = (r: Rect) => { live.current = r; setDraft(r); };

  const down = (mode: Mode) => (e: ThreeEvent<PointerEvent>) => {
    const g = ground(e); if (!g) return;
    grab(e);
    start.current = { mode, r: live.current, p: [g[0] - offset[0], g[1] - offset[1]] };
  };
  const move = (e: ThreeEvent<PointerEvent>) => {
    const s = start.current; if (!s) return;
    e.stopPropagation();
    const g = ground(e); if (!g) return;
    const dx = g[0] - offset[0] - s.p[0], dy = g[1] - offset[1] - s.p[1];
    let { x, y, w, h } = s.r;
    if (s.mode === "move") {
      x = Math.min(Math.max(0, s.r.x + dx), limit.W - w); y = Math.min(Math.max(0, s.r.y + dy), limit.L - h);
    } else {
      if (s.mode.includes("w")) { const r = s.r.x + s.r.w; x = Math.min(Math.max(0, s.r.x + dx), r - MIN); w = r - x; }
      if (s.mode.includes("e")) w = Math.min(Math.max(MIN, s.r.w + dx), limit.W - s.r.x);
      if (s.mode.includes("n")) { const b = s.r.y + s.r.h; y = Math.min(Math.max(0, s.r.y + dy), b - MIN); h = b - y; }
      if (s.mode.includes("s")) h = Math.min(Math.max(MIN, s.r.h + dy), limit.L - s.r.y);
    }
    set({ x: snap(x), y: snap(y), w: snap(w), h: snap(h) });
  };
  const up = (e: ThreeEvent<PointerEvent>) => {
    if (!start.current) return;
    e.stopPropagation(); release(e); start.current = null;
    const r = live.current;
    if (r.x !== rect.x || r.y !== rect.y || r.w !== rect.w || r.h !== rect.h) onCommit(r);
  };

  const { x, y, w, h } = draft;
  const X = (v: number) => offset[0] + v, Z = (v: number) => offset[1] + v;
  const size = 13;                 // pixels
  const Y = 0.6;
  const corners: [Mode, number, number][] = [["nw", x, y], ["ne", x + w, y], ["se", x + w, y + h], ["sw", x, y + h]];
  const edges: [Mode, number, number][] = [["n", x + w / 2, y], ["s", x + w / 2, y + h], ["w", x, y + h / 2], ["e", x + w, y + h / 2]];
  const cur: Record<Mode, string> = { move: "move", n: "ns-resize", s: "ns-resize", e: "ew-resize", w: "ew-resize", ne: "nesw-resize", sw: "nesw-resize", nw: "nwse-resize", se: "nwse-resize" };
  return (
    <group>
      <Line points={[[X(x), Y, Z(y)], [X(x + w), Y, Z(y)], [X(x + w), Y, Z(y + h)], [X(x), Y, Z(y + h)], [X(x), Y, Z(y)]]} color="#2f7cf6" lineWidth={3}
        depthTest={false} renderOrder={19} />
      <mesh position={[X(x + w / 2), Y - 0.05, Z(y + h / 2)]} rotation={[-Math.PI / 2, 0, 0]} renderOrder={18} raycast={() => null}>
        <planeGeometry args={[w, h]} /><meshBasicMaterial color="#2f7cf6" transparent opacity={0.12} depthTest={false} depthWrite={false} />
      </mesh>
      <Handle pos={[X(x + w / 2), Y, Z(y + h / 2)]} size={size * 1.5} ring color="#ffd24a" cursor={cur.move} onDown={down("move")} onMove={move} onUp={up} />
      {[...corners, ...edges].map(([m, hx, hy]) => (
        <Handle key={m} pos={[X(hx), Y, Z(hy)]} size={m.length === 2 ? size : size * 0.8} cursor={cur[m]} onDown={down(m)} onMove={move} onUp={up} />
      ))}
      <Html position={[X(x + w / 2), Y + 1.5, Z(y)]} center zIndexRange={[30, 0]} style={{ pointerEvents: "none" }}>
        <div className="vp-dim">{fmt(w)} × {fmt(h)} m · {fmtArea(w * h)}</div>
      </Html>
    </group>
  );
}

/** Move a farm element (centre handle) or reshape it (one handle per vertex of a line or an area). */
export function FeatureGizmo({ pts, closed, controls, onCommit }: {
  pts: [number, number][]; closed: boolean; controls: React.MutableRefObject<any>; onCommit: (pts: [number, number][]) => void;
}) {
  const [draft, setDraft] = useState(pts);
  const live = useRef(pts);
  const start = useRef<{ idx: number; p: [number, number]; pts: [number, number][] } | null>(null);
  const key = pts.map((p) => p.join(",")).join(";");
  useEffect(() => { setDraft(pts); live.current = pts; }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  const { ground, grab, release } = useDrag(controls);
  const cx = draft.reduce((a, p) => a + p[0], 0) / draft.length, cz = draft.reduce((a, p) => a + p[1], 0) / draft.length;
  const span = Math.max(4, ...draft.map((p) => Math.hypot(p[0] - cx, p[1] - cz)));
  const size = 12 + 0 * span;      // pixels

  const down = (idx: number) => (e: ThreeEvent<PointerEvent>) => {
    const g = ground(e); if (!g) return;
    grab(e); start.current = { idx, p: g, pts: live.current };
  };
  const move = (e: ThreeEvent<PointerEvent>) => {
    const s = start.current; if (!s) return;
    e.stopPropagation();
    const g = ground(e); if (!g) return;
    const dx = g[0] - s.p[0], dz = g[1] - s.p[1];
    const next = s.pts.map((p, i) => (s.idx < 0 || i === s.idx ? [snap(p[0] + dx), snap(p[1] + dz)] as [number, number] : p));
    live.current = next; setDraft(next);
  };
  const up = (e: ThreeEvent<PointerEvent>) => {
    if (!start.current) return;
    e.stopPropagation(); release(e); start.current = null;
    if (live.current.map((p) => p.join(",")).join(";") !== key) onCommit(live.current);
  };
  const Y = 0.8;
  return (
    <group>
      {draft.length > 1 && <Line points={[...draft, ...(closed ? [draft[0]] : [])].map(([x, z]) => [x, Y, z] as [number, number, number])}
        color="#2f7cf6" lineWidth={3} dashed dashSize={1.2} gapSize={0.6} depthTest={false} renderOrder={19} />}
      <Handle pos={[cx, Y + 0.3, cz]} size={size * 1.4} ring color="#ffd24a" cursor="move" onDown={down(-1)} onMove={move} onUp={up} />
      {draft.length > 1 && draft.map(([x, z], i) => <Handle key={i} pos={[x, Y, z]} size={size} cursor="crosshair" onDown={down(i)} onMove={move} onUp={up} />)}
    </group>
  );
}
