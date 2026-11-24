/**
 * Plants of one bed, instanced and split in blocks: every block picks its own level of detail
 * (LOD0 near, LOD1 middle, LOD2 far), so a big field near the camera is detailed only where you look.
 */
import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { XY } from "../plotGeo";
import { CropModel, CropPart, partsFor, Stage } from "./cropLibrary";

interface Chunk { pts: XY[]; centre: THREE.Vector3; radius: number }

function chunkify(pts: XY[], offset: [number, number], side: number): Chunk[] {
  const cells = new Map<string, XY[]>();
  for (const p of pts) {
    const k = `${Math.floor(p[0] / side)}:${Math.floor(p[1] / side)}`;
    (cells.get(k) ?? cells.set(k, []).get(k)!).push(p);
  }
  return [...cells.values()].map((c) => {
    const x = c.reduce((a, p) => a + p[0], 0) / c.length, y = c.reduce((a, p) => a + p[1], 0) / c.length;
    const radius = Math.max(...c.map((p) => Math.hypot(p[0] - x, p[1] - y))) + 1;
    return { pts: c, centre: new THREE.Vector3(offset[0] + x, 0, offset[1] + y), radius };
  });
}

function PartMesh({ part, pts, offset, scale, seed, shadows, handlers, fixedRotation }: {
  part: CropPart; pts: XY[]; offset: [number, number]; scale: number; seed: number; shadows: boolean; fixedRotation?: number;
  handlers: { onPick: () => void; onOver: () => void; onOut: () => void };
}) {
  const ref = useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(() => {
    const mesh = ref.current; if (!mesh) return;
    const m = new THREE.Object3D();
    pts.forEach(([x, y], i) => {
      const j = 0.88 + (((i + 1) * 9301 + seed * 49297) % 233) / 1000;     // stable size variation
      m.position.set(offset[0] + x, 0.12, offset[1] + y);
      m.rotation.set(0, fixedRotation ?? (i * 2.399 + seed) % 6.283, 0);   // vines follow the row, crops vary
      m.scale.setScalar(scale * j);
      m.updateMatrix();
      mesh.setMatrixAt(i, m.matrix);
    });
    mesh.instanceMatrix.needsUpdate = true;
    mesh.computeBoundingSphere();
  }, [pts, offset, scale, seed, part, fixedRotation]);
  return (
    <instancedMesh ref={ref} args={[part.geo, part.mat, pts.length]} castShadow={shadows} receiveShadow
      onClick={(e) => { e.stopPropagation(); handlers.onPick(); }} onPointerOver={(e) => { e.stopPropagation(); handlers.onOver(); }} onPointerOut={handlers.onOut} />
  );
}

function ChunkMesh({ chunk, model, offset, scale, seed, stage, shadows, lodDist, handlers, fixedRotation, farHidden }: {
  chunk: Chunk; model: CropModel; offset: [number, number]; scale: number; seed: number; stage: Stage; shadows: boolean; fixedRotation?: number;
  lodDist: [number, number]; handlers: { onPick: () => void; onOver: () => void; onOut: () => void }; farHidden?: boolean;
}) {
  const [lod, setLod] = useState<0 | 1 | 2>(2);
  const clock = useRef(-1 - (seed % 7) * 0.05);   // stagger the checks of different blocks
  useFrame(({ camera, clock: c }) => {
    if (c.elapsedTime - clock.current < 0.3) return;
    clock.current = c.elapsedTime;
    const d = camera.position.distanceTo(chunk.centre) - chunk.radius * 0.5;
    const next = d < lodDist[0] ? 0 : d < lodDist[1] ? 1 : 2;
    if (next !== lod) setLod(next);
  });
  if (farHidden && lod === 2) return null;          // far away the bed's foliage carpet stands for the plants
  const parts = partsFor(model, lod, stage);
  return <>{parts.map((p) => (
    <PartMesh key={`${lod}:${p.kind}`} part={p} pts={chunk.pts} offset={offset} scale={scale} seed={seed} shadows={shadows && lod < 2} handlers={handlers} fixedRotation={fixedRotation} />
  ))}</>;
}

export function CropField({ model, pts, offset, scale, spacing, seed, stage, shadows, lodDist, onPick, onOver, onOut, fixedRotation, farHidden }: {
  model: CropModel; pts: XY[]; offset: [number, number]; scale: number; spacing: number; seed: number; stage: Stage; shadows: boolean; fixedRotation?: number;
  lodDist: [number, number]; onPick: () => void; onOver: () => void; onOut: () => void; farHidden?: boolean;
}) {
  const chunks = useMemo(() => chunkify(pts, offset, Math.min(40, Math.max(8, spacing * 14))), [pts, offset, spacing]);  // blocks of at most 40 m
  const handlers = useMemo(() => ({ onPick, onOver, onOut }), [onPick, onOver, onOut]);
  if (stage === "none" || stage === "harvested") return null;
  return <>{chunks.map((c, i) => (
    <ChunkMesh key={i} chunk={c} model={model} offset={offset} scale={scale} seed={seed + i} stage={stage} shadows={shadows} lodDist={lodDist} handlers={handlers} fixedRotation={fixedRotation} farHidden={farHidden} />
  ))}</>;
}
