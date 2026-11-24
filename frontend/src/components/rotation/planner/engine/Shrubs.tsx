/**
 * Wild bushes and herbs around the farm: scenery only (never selectable, never agronomic data).
 * Models: CC0 photoscans from Poly Haven ("Shrub 03" and "Shrub Sorrel 01", see public/planner/CREDITS.md).
 * The photoscans are small plants (0.25-0.4 m and ~5 cm): here they are scaled up to field-margin bushes
 * (about 1-2 m) and herb clumps (about 0.3 m). Every variant is one InstancedMesh.
 */
import { useLayoutEffect, useMemo, useRef } from "react";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { rng } from "./noise";
import { QualityProfile } from "./quality";
import { distFromFarm, FarmZone, farmMargin, TerrainSource } from "./terrain";

const SHRUB = "/planner/shrubs/shrub_03/shrub_03_1k.gltf";
const HERB = "/planner/shrubs/shrub_sorrel_01/shrub_sorrel_01_1k.gltf";

interface Variant { geo: THREE.BufferGeometry; mat: THREE.Material; height: number }

/** Every mesh of a glTF as a variant standing on y = 0, centred on its own base. */
function variantsOf(scene: THREE.Object3D): Variant[] {
  const out: Variant[] = [];
  scene.updateMatrixWorld(true);
  scene.traverse((o) => {
    const m = o as THREE.Mesh;
    if (!m.isMesh) return;
    const g = m.geometry.clone().applyMatrix4(m.matrixWorld);
    g.computeBoundingBox();
    const b = g.boundingBox!;
    g.translate(-(b.min.x + b.max.x) / 2, -b.min.y, -(b.min.z + b.max.z) / 2);
    const mat = (m.material as THREE.MeshStandardMaterial).clone();
    mat.alphaTest = 0.5; mat.side = THREE.DoubleSide; mat.transparent = false;
    out.push({ geo: g, mat, height: b.max.y - b.min.y });
  });
  return out;
}

function Instances({ v, mats, shadows }: { v: Variant; mats: THREE.Matrix4[]; shadows: boolean }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(() => {
    const m = ref.current; if (!m) return;
    mats.forEach((x, i) => m.setMatrixAt(i, x));
    m.instanceMatrix.needsUpdate = true; m.computeBoundingSphere();
  }, [mats]);
  if (!mats.length) return null;
  return <instancedMesh ref={ref} args={[v.geo, v.mat, mats.length]} castShadow={shadows} receiveShadow raycast={() => null} />;
}

export function Shrubs({ zone, terrain, quality }: { zone: FarmZone; terrain: TerrainSource; quality: QualityProfile }) {
  const shrub = useGLTF(SHRUB), herb = useGLTF(HERB);
  const bushes = useMemo(() => variantsOf(shrub.scene), [shrub.scene]);
  const herbs = useMemo(() => variantsOf(herb.scene).filter((v) => v.height > 0.03), [herb.scene]);

  const place = (variants: Variant[], count: number, seed: number, band: [number, number], size: [number, number], cluster: number) => {
    const per: THREE.Matrix4[][] = variants.map(() => []);
    if (!variants.length || !count) return per;
    const r = rng(seed), margin = farmMargin(zone), q = new THREE.Quaternion(), up = new THREE.Vector3(0, 1, 0);
    let n = 0, guard = 0;
    while (n < count && guard++ < count * 40) {
      // cluster centre in a band just outside the farm (field margins, ditches, edges of the woods)
      const a = r() * Math.PI * 2, R = zone.size * 0.75 + margin * 2;
      const cx = zone.cx + Math.cos(a) * R * r(), cz = zone.cz + Math.sin(a) * R * r();
      const d = distFromFarm(zone, cx, cz, 0);
      if (d < band[0] || d > band[1]) continue;
      const k = 2 + Math.floor(r() * cluster);
      for (let j = 0; j < k && n < count; j++, n++) {
        const x = cx + (r() - 0.5) * 6, z = cz + (r() - 0.5) * 6;
        if (distFromFarm(zone, x, z, 0) < band[0]) continue;
        const vi = Math.floor(r() * variants.length), v = variants[vi];
        const target = size[0] + r() * (size[1] - size[0]);
        const s = target / v.height;
        per[vi].push(new THREE.Matrix4().compose(new THREE.Vector3(x, terrain.heightAt(x, z) - 0.05, z), q.setFromAxisAngle(up, r() * 6.28).clone(),
          new THREE.Vector3(s * (0.9 + r() * 0.3), s, s * (0.9 + r() * 0.3))));
      }
    }
    return per;
  };

  const margin = farmMargin(zone);
  const bushMats = useMemo(() => place(bushes, quality.shrubs, 77, [2, margin * 0.9], [0.9, 2.2], 5), [bushes, quality.shrubs, zone, terrain]); // eslint-disable-line react-hooks/exhaustive-deps
  const herbMats = useMemo(() => place(herbs, quality.herbs, 91, [0.6, margin * 0.5], [0.2, 0.45], 8), [herbs, quality.herbs, zone, terrain]); // eslint-disable-line react-hooks/exhaustive-deps
  const shadows = quality.shadowMap > 0 && quality.plantShadows;
  return <>
    {bushes.map((v, i) => <Instances key={`b${i}`} v={v} mats={bushMats[i]} shadows={shadows} />)}
    {herbs.map((v, i) => <Instances key={`h${i}`} v={v} mats={herbMats[i]} shadows={false} />)}
  </>;
}

useGLTF.preload(SHRUB);
useGLTF.preload(HERB);
