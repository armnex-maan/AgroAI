// Builds the AgroAI crop library: one GLB per crop in public/planner/crops/, with nodes LOD0, LOD1, LOD2
// (and LOD0_green / LOD1_green / LOD2_green for cereals before ripening). Each node holds one mesh per part
// (leaves, stem, fruit, flower, ear, cob, silk, tassel, head, root) with vertex colours.
// A model made in Blender with the same node and mesh names can replace any file without code changes.
//
//   node scripts/build-crop-models.mjs
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { ALIASES, GENERATORS } from "./crops/crops.mjs";
import { TREE_GENERATORS } from "./crops/trees.mjs";
import { tris } from "./crops/geometry.mjs";

// GLTFExporter (binary) needs FileReader, which Node does not have
globalThis.FileReader ??= class {
  readAsArrayBuffer(blob) { blob.arrayBuffer().then((b) => { this.result = b; this.onloadend?.(); }); }
  readAsDataURL(blob) { blob.arrayBuffer().then((b) => { this.result = "data:application/octet-stream;base64," + Buffer.from(b).toString("base64"); this.onloadend?.(); }); }
};

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const OUT = join(root, "public", "planner", "crops");
const MANIFEST = join(root, "src", "components", "rotation", "planner", "crops", "manifest.json");
mkdirSync(OUT, { recursive: true });
mkdirSync(dirname(MANIFEST), { recursive: true });

const ROUGH = { fruit: 0.35, flower: 0.6, cob: 0.6, head: 0.7, root: 0.6 };
const DOUBLE = new Set(["leaves", "head", "flower"]);

const manifest = { generated: "2026-11-22", note: "Procedural botanical models (AgroAI). Height normalised to 1 m; scale by FAO-56 height.", crops: {}, trees: {}, aliases: ALIASES };
mkdirSync(join(OUT, "..", "trees"), { recursive: true });

for (const [set, key, gen] of [...Object.entries(GENERATORS).map(([k, g]) => ["crops", k, g]), ...Object.entries(TREE_GENERATORS).map(([k, g]) => ["trees", k, g])]) {
  const lods = gen();
  // normalise: base at y = 0, height 1, centred on x/z (from LOD0)
  const box = new THREE.Box3();
  for (const g of Object.values(lods.LOD0)) if (g) { g.computeBoundingBox(); box.union(g.boundingBox); }
  const size = box.getSize(new THREE.Vector3()), centre = box.getCenter(new THREE.Vector3());
  const k = 1 / size.y;
  const norm = new THREE.Matrix4().makeScale(k, k, k).multiply(new THREE.Matrix4().makeTranslation(-centre.x, -box.min.y, -centre.z));
  const scene = new THREE.Scene();
  const info = { file: `${key}.glb`, width: +(Math.max(size.x, size.z) * k).toFixed(3), tris: {}, parts: {} };
  for (const [lodName, parts] of Object.entries(lods)) {
    const group = new THREE.Group();
    group.name = lodName;
    let t = 0;
    for (const [part, geo] of Object.entries(parts)) {
      if (!geo) continue;
      geo.applyMatrix4(norm);
      geo.computeVertexNormals();
      const mat = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: ROUGH[part] ?? 0.85, side: DOUBLE.has(part) ? THREE.DoubleSide : THREE.FrontSide });
      mat.name = part;
      const mesh = new THREE.Mesh(geo, mat);
      mesh.name = part;
      group.add(mesh);
      t += tris(geo);
    }
    info.tris[lodName] = Math.round(t);
    info.parts[lodName] = group.children.map((m) => m.name);
    scene.add(group);
  }
  const glb = await new GLTFExporter().parseAsync(scene, { binary: true });
  writeFileSync(join(OUT, "..", set, info.file), Buffer.from(glb));
  info.bytes = glb.byteLength;
  manifest[set][key] = info;
  console.log(key.padEnd(9), `LOD0 ${String(info.tris.LOD0).padStart(5)} tris`, `LOD1 ${String(info.tris.LOD1).padStart(4)}`, `LOD2 ${String(info.tris.LOD2).padStart(3)}`,
    `${(glb.byteLength / 1024).toFixed(0)} KB`);
}
writeFileSync(MANIFEST, JSON.stringify(manifest, null, 2));
console.log("manifest:", MANIFEST);
