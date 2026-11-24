/**
 * Visual demonstration of how a bed is irrigated (drip, sprinkler, furrow): falling drops and spreading wet spots,
 * turning jets, water advancing along the furrows. It is an animation to explain the system, not a hydraulic
 * simulation: no flow rate, pressure or timing is computed here (the panel shows the water need with its sources).
 */
import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { XY } from "../plotGeo";
import { BedView, rows, rowsAlongY } from "./layout";

const CYCLE = 8;   // seconds of one wetting cycle
const o = new THREE.Object3D();

function useSpots(bed: BedView, between: number, step: number, max: number) {
  return useMemo(() => rows(bed, step, between, max), [bed, between, step, max]);
}

/** Drip: a drop falls from every emitter, the wet bulb spreads on the soil, then the cycle restarts. */
function Drip({ bed, offset, between, top }: { bed: BedView; offset: [number, number]; between: number; top: number }) {
  const R = Math.min(0.45, Math.max(0.04, between * 0.07));   // drop size follows the (possibly enlarged) row spacing
  const pts = useSpots(bed, Math.max(0.3, between * 0.6), between, 350);
  const drops = useRef<THREE.InstancedMesh>(null), wet = useRef<THREE.InstancedMesh>(null);
  const phase = useMemo(() => pts.map((_, i) => ((i * 0.618) % 1) * 1.2), [pts]);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime, d = drops.current, w = wet.current;
    if (!d || !w) return;
    const k = (t % CYCLE) / CYCLE, spread = Math.min(1, k * 1.6) * between * 0.42 + 0.05;
    pts.forEach(([x, y], i) => {
      const f = ((t + phase[i]) % 1.2) / 1.2;                       // a drop every 1.2 s per emitter
      o.position.set(offset[0] + x, 0.15 + (1 - f) * Math.min(top, 3), offset[1] + y); o.scale.setScalar(f < 0.95 ? R : 0.001); o.updateMatrix(); d.setMatrixAt(i, o.matrix);
      o.position.set(offset[0] + x, 0.135, offset[1] + y); o.rotation.set(-Math.PI / 2, 0, 0); o.scale.set(spread, spread * (rowsAlongY(bed) ? 1.25 : 0.8), 1);
      o.updateMatrix(); w.setMatrixAt(i, o.matrix); o.rotation.set(0, 0, 0);
    });
    d.instanceMatrix.needsUpdate = true; w.instanceMatrix.needsUpdate = true;
    (w.material as THREE.MeshBasicMaterial).opacity = 0.42 * (k < 0.85 ? 1 : (1 - k) / 0.15);
  });
  if (!pts.length) return null;
  return <>
    <instancedMesh ref={drops} args={[undefined, undefined, pts.length]} frustumCulled={false} raycast={() => null}>
      <sphereGeometry args={[1, 6, 5]} /><meshStandardMaterial color="#7cc4f2" roughness={0.05} metalness={0.1} transparent opacity={0.9} />
    </instancedMesh>
    <instancedMesh ref={wet} args={[undefined, undefined, pts.length]} frustumCulled={false} raycast={() => null}>
      <circleGeometry args={[1, 18]} /><meshBasicMaterial color="#3b2a1b" transparent opacity={0.4} depthWrite={false} />
    </instancedMesh>
  </>;
}

/** Sprinkler: turning jets with drops along them and a wetted circle that grows. */
function Sprinkler({ bed, offset }: { bed: BedView; offset: [number, number] }) {
  const reach = Math.max(3, Math.min(10, Math.sqrt(bed.area) / 3));
  const heads = useMemo(() => {
    const { x, y, w, h } = bed.rect, step = reach * 1.6, out: XY[] = [];
    for (let a = Math.min(step / 2, w / 2); a < w; a += step) for (let b = Math.min(step / 2, h / 2); b < h; b += step) out.push([x + a, y + b]);
    return out.slice(0, 40);
  }, [bed, reach]);
  const N = 14, drops = useRef<THREE.InstancedMesh>(null), wet = useRef<THREE.InstancedMesh>(null);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime, d = drops.current, w = wet.current;
    if (!d || !w) return;
    const k = (t % CYCLE) / CYCLE;
    heads.forEach(([x, y], hI) => {
      const ang = t * 0.9 + hI * 1.7;
      for (let j = 0; j < N; j++) {
        const s = ((t * 0.7 + j / N) % 1), r = s * reach;   // drops travel along the parabolic jet
        o.position.set(offset[0] + x + Math.cos(ang) * r, 1.0 + s * reach * 0.42 - s * s * reach * 0.6, offset[1] + y + Math.sin(ang) * r);
        o.scale.setScalar((0.6 + s) * Math.max(1, reach / 4)); o.updateMatrix(); d.setMatrixAt(hI * N + j, o.matrix);
      }
      const R = Math.min(1, k * 1.4) * reach;
      o.position.set(offset[0] + x, 0.135, offset[1] + y); o.rotation.set(-Math.PI / 2, 0, 0); o.scale.set(R, R, 1); o.updateMatrix(); w.setMatrixAt(hI, o.matrix); o.rotation.set(0, 0, 0);
    });
    d.instanceMatrix.needsUpdate = true; w.instanceMatrix.needsUpdate = true;
  });
  if (!heads.length) return null;
  return <>
    <instancedMesh ref={drops} args={[undefined, undefined, heads.length * N]} frustumCulled={false} raycast={() => null}>
      <sphereGeometry args={[0.06, 6, 5]} /><meshStandardMaterial color="#cfeaff" transparent opacity={0.75} roughness={0.05} />
    </instancedMesh>
    <instancedMesh ref={wet} args={[undefined, undefined, heads.length]} frustumCulled={false} raycast={() => null}>
      <circleGeometry args={[1, 32]} /><meshBasicMaterial color="#3b2a1b" transparent opacity={0.28} depthWrite={false} />
    </instancedMesh>
  </>;
}

/** Furrow: water runs along each furrow from the head of the bed to the end, then soaks in. */
function Furrow({ bed, offset, between }: { bed: BedView; offset: [number, number]; between: number }) {
  const alongY = rowsAlongY(bed), { x, y, w, h } = bed.rect;
  const across = alongY ? w : h, len = alongY ? h : w, n = Math.max(1, Math.floor(across / between));
  const pad = (across - (n - 1) * between) / 2;
  const ref = useRef<THREE.InstancedMesh>(null);
  useFrame(({ clock }) => {
    const m = ref.current; if (!m) return;
    const k = (clock.elapsedTime % CYCLE) / CYCLE, fill = Math.min(1, k * 1.5);
    for (let i = 0; i < n; i++) {
      const c = pad + i * between + between / 2, L = Math.max(0.01, len * fill);
      if (alongY) o.position.set(offset[0] + x + c, 0.14, offset[1] + y + L / 2); else o.position.set(offset[0] + x + L / 2, 0.14, offset[1] + y + c);
      o.rotation.set(-Math.PI / 2, 0, alongY ? 0 : Math.PI / 2); o.scale.set(Math.min(0.35, between * 0.3), L, 1); o.updateMatrix(); m.setMatrixAt(i, o.matrix);
    }
    m.instanceMatrix.needsUpdate = true;
    (m.material as THREE.MeshStandardMaterial).opacity = 0.75 * (k < 0.85 ? 1 : (1 - k) / 0.15);
  });
  return <instancedMesh ref={ref} args={[undefined, undefined, n]} frustumCulled={false} raycast={() => null}>
    <planeGeometry args={[1, 1]} /><meshStandardMaterial color="#4f8fbf" roughness={0.05} metalness={0.2} transparent opacity={0.75} depthWrite={false} />
  </instancedMesh>;
}

export function IrrigationDemo({ system, bed, offset, between, top }: { system: string; bed: BedView; offset: [number, number]; between: number; top: number }) {
  if (system === "drip") return <Drip bed={bed} offset={offset} between={between} top={top} />;
  if (system === "sprinkler") return <Sprinkler bed={bed} offset={offset} />;
  if (system === "furrow") return <Furrow bed={bed} offset={offset} between={between} />;
  return null;
}
