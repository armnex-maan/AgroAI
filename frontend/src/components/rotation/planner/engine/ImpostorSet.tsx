/** A set of baked trees/plants drawn as impostors: one instanced quad each (see impostor.ts). Never raycast:
 *  owners that must be selectable add their own simple hit area. */
import { useLayoutEffect, useRef } from "react";
import * as THREE from "three";
import { treeMatrix, useImpostor } from "./impostor";

export interface ImpostorItem { x: number; y: number; z: number; h: number; rot: number; tint?: THREE.Color }

const WHITE = new THREE.Color(1, 1, 1);

export function ImpostorSet({ name, items, shadows }: { name: string; items: ImpostorItem[]; shadows: boolean }) {
  const kit = useImpostor(name);
  const ref = useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(() => {
    const m = ref.current; if (!m) return;
    const mat = new THREE.Matrix4();
    items.forEach((t, i) => { treeMatrix(mat, t.x, t.y, t.z, t.h, t.rot); m.setMatrixAt(i, mat); m.setColorAt(i, t.tint ?? WHITE); });
    m.instanceMatrix.needsUpdate = true; if (m.instanceColor) m.instanceColor.needsUpdate = true;
  }, [items]);
  if (!items.length) return null;
  return <instancedMesh ref={ref} args={[kit.geometry, kit.material, items.length]} customDepthMaterial={kit.depth}
    castShadow={shadows} receiveShadow={false} raycast={() => null} frustumCulled={false} />;
}
