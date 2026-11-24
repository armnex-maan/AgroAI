/**
 * Export of the planner scene for the photoreal render (tools/blender/render_scene.py, Blender Cycles).
 *  - scene.glb: the planner's own meshes as they are now (terrain, beds, roads, buildings, greenhouse, fences...);
 *  - meta: camera, sun, fog, and the repeated objects as lists instead of geometry:
 *      impostors (trees, crops drawn as baked quads here) -> real 3D models in Blender,
 *      other instanced meshes (wheat plants, shrubs) -> one prototype mesh in the glb + their world matrices.
 * UI-only objects (selection lines and handles, labels, water spray, invisible hit areas) are left out.
 * Nothing is computed here: the render shows exactly the data and the drawing on screen.
 */
import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";

export interface RenderMeta {
  version: 1;
  camera: { matrix: number[]; fov: number; aspect: number };
  sun: [number, number, number];
  fog: { near: number; far: number };
  grass: { center: [number, number]; radius: number; density: number } | null;
  impostors: { name: string; items: number[] }[];
  instances: { proto: string; matrices: number[] }[];
  width: number; samples: number;
}

const r3 = (v: number) => Math.round(v * 1000) / 1000;

function skip(o: THREE.Object3D): boolean {
  const a = o as unknown as Record<string, boolean>;
  if (o.userData.noExport || a.isLight || a.isCamera || a.isPoints || a.isLine || a.isLineSegments || a.isLineSegments2 || a.isLine2) return true;
  const m = (o as THREE.Mesh).material as THREE.Material | THREE.Material[] | undefined;
  if (!m) return false;
  const list = Array.isArray(m) ? m : [m];
  return list.some((x) => (x as THREE.ShaderMaterial).isShaderMaterial || (x as THREE.MeshBasicMaterial).isMeshBasicMaterial
    || (x.transparent && x.opacity === 0) || !x.visible);
}

export async function exportRenderScene(scene: THREE.Scene, camera: THREE.PerspectiveCamera, opts: {
  sun: THREE.Vector3; fog: { near: number; far: number }; grass: RenderMeta["grass"]; aspect: number; width?: number; samples?: number;
}): Promise<{ glb: Blob; meta: RenderMeta }> {
  scene.updateMatrixWorld(true);
  const hide: THREE.Object3D[] = [];
  const impostors = new Map<string, number[]>();
  const instances: RenderMeta["instances"] = [];
  const protos = new THREE.Group(); protos.name = "agro-protos";
  const mi = new THREE.Matrix4(), mw = new THREE.Matrix4(), p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3();

  const visible: THREE.Object3D[] = [];
  scene.traverseVisible((o) => { if (o !== scene) visible.push(o); });
  for (const o of visible) {
    if (skip(o)) { hide.push(o); continue; }
    const im = o as THREE.InstancedMesh;
    if (!im.isInstancedMesh) continue;
    hide.push(o);
    const mat = (Array.isArray(im.material) ? im.material[0] : im.material) as THREE.Material;
    const imp = mat?.userData?.impostor as string | undefined;
    if (imp) {                                     // tree / crop impostor: position, height, turn
      const items = impostors.get(imp) ?? impostors.set(imp, []).get(imp)!;
      for (let i = 0; i < im.count; i++) {
        im.getMatrixAt(i, mi); mw.multiplyMatrices(im.matrixWorld, mi).decompose(p, q, s);
        items.push(r3(p.x), r3(p.y), r3(p.z), r3(s.x), r3(2 * Math.atan2(q.y, q.w)));
      }
      continue;
    }
    if (!im.count) continue;
    const proto = new THREE.Mesh(im.geometry, im.material);
    proto.name = `agro-proto-${instances.length}`;
    proto.castShadow = im.castShadow; proto.receiveShadow = im.receiveShadow;
    protos.add(proto);
    const matrices: number[] = [];
    for (let i = 0; i < im.count; i++) {
      im.getMatrixAt(i, mi); mw.multiplyMatrices(im.matrixWorld, mi);
      for (const e of mw.elements) matrices.push(Math.round(e * 10000) / 10000);
    }
    instances.push({ proto: proto.name, matrices });
  }

  for (const o of hide) o.visible = false;
  scene.add(protos);
  try {
    const exporter = new GLTFExporter();
    const glb = await exporter.parseAsync(scene, { binary: true, onlyVisible: true, maxTextureSize: 4096 }) as ArrayBuffer;
    const meta: RenderMeta = {
      version: 1,
      camera: { matrix: camera.matrixWorld.elements.map((e) => Math.round(e * 1e5) / 1e5), fov: camera.fov, aspect: opts.aspect },
      sun: [opts.sun.x, opts.sun.y, opts.sun.z], fog: opts.fog, grass: opts.grass,
      impostors: [...impostors].map(([name, items]) => ({ name, items })),
      instances, width: opts.width ?? 1920, samples: opts.samples ?? 128,
    };
    return { glb: new Blob([glb], { type: "model/gltf-binary" }), meta };
  } finally {
    scene.remove(protos);
    for (const o of hide) o.visible = true;
  }
}
