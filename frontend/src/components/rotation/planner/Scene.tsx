import { forwardRef, useEffect, useImperativeHandle, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Html, Line, MapControls, OrbitControls, OrthographicCamera, PerspectiveCamera, useTexture } from "@react-three/drei";
import { canopyTexture, carpetUV, sharpAlpha } from "./canopy";
import * as THREE from "three";
import { XY } from "../plotGeo";
import { cropColor, fmtArea, RCrop, shortName } from "../types";
import { BedView, PlotView, rows, rowsAlongY } from "./layout";
import { PlantModel, plantModel, treeModel } from "./plants";
import { Calendar, CropModel, STAGE_LABEL, STAGE_SCALE, Stage, stageFor, useCropModels } from "./cropLibrary";
import { CropField } from "./CropField";
import { FeatureGizmo, Rect, SectionGizmo } from "./Editor";
import { IrrigationDemo } from "./IrrigationDemo";
import { FarmRef, Feature, featurePoints, Structures } from "./Structures";
import { FarmEngine, FOG, SUN_DIR } from "./engine/FarmEngine";
import { exportRenderScene, RenderMeta } from "./renderExport";
import { XZ } from "./engine/Landscape";
import { QualityProfile } from "./engine/quality";
import { demoTerrain, FarmZone } from "./engine/terrain";
import { treeMatrix, useImpostor } from "./engine/impostor";
import { WaterSpray } from "./engine/WaterSpray";
import { cropImpostor, hasCropImpostor, impostorWidth } from "./cropImpostors";

export const NEUTRAL_H = 0.3; // crops missing from FAO-56 Table 12
const VERDICT_TXT = { ok: "Ottimale", care: "Con attenzione", no: "Meglio di no" } as const;

export interface SceneApi { zoomBy: (f: number) => void; reset: () => void; zoomPct: () => number; focus: (x: number, z: number, r: number) => void;
  /** scene as it is now, for the photoreal render (Blender Cycles) */
  exportRender: () => Promise<{ glb: Blob; meta: RenderMeta }> }
export interface SceneProps {
  views: PlotView[]; byKey: Record<string, RCrop>; mode: "3d" | "2d"; exag: number; quality: QualityProfile;
  month: number; calendar: Record<string, Calendar>;
  features: Feature[]; farmRef: FarmRef | null;
  placing: { kind: string; pts: [number, number][] } | null; onGround: (x: number, z: number) => void;
  onTerrainLabel?: (label: string) => void;
  selected: string | null; hovered: string | null; onSelect: (k: string | null) => void; onHover: (k: string | null) => void;
  compass: React.RefObject<HTMLDivElement>; zoomLabel: React.RefObject<HTMLSpanElement>;
  /** phase 4 editor: handles on the selected section or farm element */
  edit?: { on: boolean; onSection: (plotId: string, sectionId: string, r: Rect) => void; onFeature: (id: string, pts: [number, number][]) => void };
  /** irrigation demonstration on the beds of one plot */
  demo?: { plotId: string; system: string } | null;
}

const heightOf = (byKey: Record<string, RCrop>, crop: string) => {
  const h = byKey[crop]?.height_m;
  return h ? (h[0] + h[1]) / 2 : NEUTRAL_H;
};

/** Visual factor so that the plants fit the budget (1 = real size). Crops baked as impostors are one quad per plant
 *  and get their own, much larger budget: when the farm has them, they set the factor and the other beds adapt
 *  their spacing to their own budget instead (see BedMesh). */
export function plantFactor(views: PlotView[], byKey: Record<string, RCrop>, budget: number, impBudget = budget): number {
  let glb = 0, imp = 0;
  for (const v of views) for (const b of v.beds) if (b.crop) {
    const hgt = heightOf(byKey, b.crop.crop);
    if (hasCropImpostor(b.crop.crop)) { const w = impostorWidth(b.crop.crop) * hgt; imp += b.area / (1.15 * w * w); }
    else { const w = plantModel(b.crop.crop, byKey[b.crop.crop]?.group ?? "frutto").width * hgt; glb += b.area / (1.2 * w * w); }
  }
  const need = imp > 0 ? imp / impBudget : glb / budget;
  return need <= 1 ? 1 : Math.max(1, Math.round(Math.sqrt(need) * 2) / 2);
}

/** Spacing grown evenly when a bed would need more plants than its budget (the bed stays fully planted). */
function fitBudget(area: number, inRow: number, between: number, budget: number): [number, number] {
  const n = area / (inRow * between);
  if (n <= budget) return [inRow, between];
  const f = Math.sqrt(n / budget);
  return [inRow * f, between * f];
}

/** Plants of a bed as impostors (Blender-baked crops): one instanced quad per plant, shadows from the same quads. */
function ImpostorCrops({ name, pts, offset, height, seed, shadows, tint }: {
  name: string; pts: XY[]; offset: [number, number]; height: number; seed: number; shadows: boolean; tint: [number, number, number];
}) {
  const kit = useImpostor(name);
  const ref = useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(() => {
    const m = ref.current; if (!m) return;
    const mat = new THREE.Matrix4(), col = new THREE.Color();
    pts.forEach(([x, y], i) => {
      const a = ((i + 1) * 9301 + seed * 49297) % 1000 / 1000, b = ((i + 7) * 7919 + seed * 104729) % 1000 / 1000;
      treeMatrix(mat, offset[0] + x + (a - 0.5) * height * 0.12, 0.1, offset[1] + y + (b - 0.5) * height * 0.12, height * (0.86 + a * 0.28), (a + b) * 6.283);
      m.setMatrixAt(i, mat);
      col.setRGB((0.92 + b * 0.16) * tint[0], (0.92 + a * 0.14) * tint[1], (0.9 + b * 0.1) * tint[2]); m.setColorAt(i, col);
    });
    m.instanceMatrix.needsUpdate = true; if (m.instanceColor) m.instanceColor.needsUpdate = true;
  }, [pts, offset, height, seed, tint]);
  if (!pts.length) return null;
  return <instancedMesh ref={ref} args={[kit.geometry, kit.material, pts.length]} customDepthMaterial={kit.depth}
    castShadow={shadows} receiveShadow={false} raycast={() => null} frustumCulled={false} />;
}

function bounds(views: PlotView[], extra: [number, number][] = []) {
  let x0 = Infinity, z0 = Infinity, x1 = -Infinity, z1 = -Infinity;
  for (const [x, z] of extra) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); z0 = Math.min(z0, z); z1 = Math.max(z1, z); }
  for (const v of views) for (const [x, y] of v.outline) {
    x0 = Math.min(x0, v.offset[0] + x); x1 = Math.max(x1, v.offset[0] + x);
    z0 = Math.min(z0, v.offset[1] + y); z1 = Math.max(z1, v.offset[1] + y);
  }
  if (!isFinite(x0)) { x0 = z0 = -10; x1 = z1 = 10; }
  return { cx: (x0 + x1) / 2, cz: (z0 + z1) / 2, size: Math.max(20, x1 - x0, z1 - z0), x0, x1, z0, z1 };
}

/** Plot-local polygon -> flat shape in the XZ plane (shape y = -local y, then rotated). */
function shapeGeo(pts: XY[], depth = 0) {
  const shape = new THREE.Shape(pts.map(([x, y]) => new THREE.Vector2(x, -y)));
  const g = depth > 0 ? new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: false }) : new THREE.ShapeGeometry(shape);
  g.rotateX(-Math.PI / 2);
  return g;
}
const centroid = (pts: XY[]): XY => [pts.reduce((a, p) => a + p[0], 0) / pts.length, pts.reduce((a, p) => a + p[1], 0) / pts.length];

const SOIL_NORMAL = new THREE.Vector2(1.4, 1.4);
function useTextures() {
  // CC0 Poly Haven: "Farm Soil" (tilled beds), "Gravel Road" (paths), "Dirt Aerial 02" (plot ground), "Aerial Grass Rock"
  const [soil, soilN, soilR, dirt, grass, gravel, gravelN] = useTexture(["/planner/farm_soil_diff_1k.jpg", "/planner/farm_soil_nor_gl_1k.jpg",
    "/planner/farm_soil_rough_1k.jpg", "/planner/dirt_aerial_02_diff_1k.jpg", "/planner/aerial_grass_rock_diff_1k.jpg",
    "/planner/gravel_road_diff_1k.jpg", "/planner/gravel_road_nor_gl_1k.jpg"]);
  return useMemo(() => {
    for (const t of [soil, soilN, soilR, dirt, grass, gravel, gravelN]) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 8; }
    soil.colorSpace = dirt.colorSpace = grass.colorSpace = gravel.colorSpace = THREE.SRGBColorSpace;
    for (const t of [soil, soilN, soilR]) t.repeat.set(1 / 2.5, 1 / 2.5);   // UVs are metres: one tile every 2.5 m
    dirt.repeat.set(1 / 6, 1 / 6);
    for (const t of [gravel, gravelN]) t.repeat.set(1 / 3, 1 / 3);
    grass.repeat.set(1 / 25, 1 / 25);   // for shapes (UVs in metres)
    const ground = grass.clone();       // the big ground plane has UVs 0..1: repeat set by its size
    ground.needsUpdate = true;
    return { soil, soilN, soilR, dirt, grass, ground, gravel, gravelN };
  }, [soil, soilN, soilR, dirt, grass, gravel, gravelN]);
}

/** All parts of one plant model as InstancedMeshes, one transform per plant. */
function Plants({ model, pts, offset, scale, onPick, onOver, onOut, seed, shadows }: {
  model: PlantModel; pts: XY[]; offset: [number, number]; scale: number; seed: number; shadows: boolean;
  onPick: () => void; onOver: () => void; onOut: () => void;
}) {
  const refs = useRef<(THREE.InstancedMesh | null)[]>([]);
  useLayoutEffect(() => {
    const m = new THREE.Object3D();
    refs.current.forEach((mesh) => {
      if (!mesh) return;
      pts.forEach(([x, y], i) => {
        const j = 0.88 + (((i + 1) * 9301 + seed * 49297) % 233) / 1000;
        m.position.set(offset[0] + x, 0.12, offset[1] + y);
        m.rotation.set(0, (i * 2.399 + seed) % 6.283, 0);
        m.scale.setScalar(scale * j);
        m.updateMatrix();
        mesh.setMatrixAt(i, m.matrix);
      });
      mesh.instanceMatrix.needsUpdate = true;
      mesh.computeBoundingSphere();
    });
  }, [pts, offset, scale, seed, model]); // model too: the LOD switch creates new meshes
  return (
    <>
      {model.parts.map((p, i) => (
        <instancedMesh key={i} ref={(r) => { refs.current[i] = r; }} args={[p.geo, undefined, pts.length]} frustumCulled={false} castShadow={shadows} receiveShadow
          onClick={(e) => { e.stopPropagation(); onPick(); }} onPointerOver={(e) => { e.stopPropagation(); onOver(); }} onPointerOut={onOut}>
          <meshStandardMaterial color={p.color} roughness={p.rough ?? 0.8} flatShading />
        </instancedMesh>
      ))}
    </>
  );
}

function Greenhouse({ bed, offset }: { bed: BedView; offset: [number, number] }) {
  const { x, y, w, h } = bed.rect;
  const alongY = h >= w, across = alongY ? w : h, along = alongY ? h : w;
  const r = across / 2, height = Math.min(r, 3.2);
  const arches = Math.max(2, Math.round(along / 2.5));
  return (
    <group position={[offset[0] + x + w / 2, 0.12, offset[1] + y + h / 2]} rotation={[0, alongY ? 0 : Math.PI / 2, 0]}>
      {/* tunnel along local Z: half cylinder (upper half), flattened to the tunnel height */}
      <mesh rotation={[Math.PI / 2, 0, 0]} scale={[1, 1, height / r]} raycast={() => null}>
        <cylinderGeometry args={[r, r, along, 24, 1, true, Math.PI / 2, Math.PI]} />
        <meshStandardMaterial color="#eef6fa" transparent opacity={0.28} roughness={0.1} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
      {Array.from({ length: arches + 1 }, (_, i) => (
        <mesh key={i} position={[0, 0, -along / 2 + (i * along) / arches]} scale={[1, height / r, 1]} raycast={() => null}>
          <torusGeometry args={[r, 0.04, 4, 20, Math.PI]} />
          <meshStandardMaterial color="#cfd6d8" metalness={0.6} roughness={0.4} />
        </mesh>
      ))}
      {/* end walls with a door, base rails and ridge */}
      {[-1, 1].map((sd) => (
        <group key={sd} position={[0, 0, (sd * along) / 2]}>
          <mesh scale={[1, height / r, 1]} raycast={() => null}>
            <circleGeometry args={[r, 20, 0, Math.PI]} />
            <meshStandardMaterial color="#eaf4f8" transparent opacity={0.35} side={THREE.DoubleSide} depthWrite={false} />
          </mesh>
          <mesh position={[0, Math.min(2.1, height * 0.8) / 2, sd * 0.02]} raycast={() => null}>
            <boxGeometry args={[Math.min(1.6, r), Math.min(2.1, height * 0.8), 0.04]} /><meshStandardMaterial color="#5f6b70" transparent opacity={0.55} />
          </mesh>
        </group>
      ))}
      {[-r, r].map((xx) => <mesh key={xx} position={[xx, 0.06, 0]} raycast={() => null}><boxGeometry args={[0.08, 0.12, along]} /><meshStandardMaterial color="#9aa3a6" metalness={0.5} /></mesh>)}
      <mesh position={[0, height, 0]} raycast={() => null}><boxGeometry args={[0.06, 0.06, along]} /><meshStandardMaterial color="#cfd6d8" metalness={0.6} /></mesh>
    </group>
  );
}

function Trees({ spots, scale = 1, pick }: { spots: [number, number][]; scale?: number; pick?: boolean }) {
  const model = useMemo(() => treeModel(11), []);
  const pts = useMemo(() => spots.map(([x, z]) => [x, z] as XY), [spots]);
  const refs = useRef<(THREE.InstancedMesh | null)[]>([]);
  useLayoutEffect(() => {
    const m = new THREE.Object3D();
    refs.current.forEach((mesh) => {
      if (!mesh) return;
      pts.forEach(([x, z], i) => {
        m.position.set(x, 0, z); m.rotation.set(0, i * 1.7, 0); m.scale.setScalar(scale * (0.8 + ((i * 37) % 10) / 25)); m.updateMatrix();
        mesh.setMatrixAt(i, m.matrix);
      });
      mesh.instanceMatrix.needsUpdate = true;
      mesh.computeBoundingSphere();
    });
  }, [pts, scale]);
  return <>{model.parts.map((p, i) => (
    <instancedMesh key={i} ref={(r) => { refs.current[i] = r; }} args={[p.geo, undefined, pts.length]} raycast={pick ? undefined : () => null}>
      <meshStandardMaterial color={p.color} roughness={0.9} flatShading />
    </instancedMesh>
  ))}</>;
}

/** Irrigation the farmer declared: drip lines along the rows, or sprinkler heads. */
function Irrigation({ kind, bed, offset, between, animate }: { kind: string; bed: BedView; offset: [number, number]; between: number; animate: boolean }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const items = useMemo(() => {
    const { x, y, w, h } = bed.rect;
    const alongY = rowsAlongY(bed);
    if (kind === "drip" || kind === "furrow") {
      const across = alongY ? w : h, n = Math.max(1, Math.floor(across / between));
      const pad = (across - (n - 1) * between) / 2;
      return Array.from({ length: n }, (_, i) => {
        const c = pad + i * between + (kind === "furrow" ? between / 2 : 0);
        return alongY ? { p: [x + c, y + h / 2], s: [kind === "drip" ? 0.03 : between * 0.35, 1, h * 0.96] } : { p: [x + w / 2, y + c], s: [w * 0.96, 1, kind === "drip" ? 0.03 : between * 0.35] };
      });
    }
    if (kind === "sprinkler") {
      const step = Math.max(8, Math.sqrt(bed.area / 25));
      const out: { p: number[]; s: number[] }[] = [];
      for (let a = step / 2; a < w; a += step) for (let b = step / 2; b < h; b += step) out.push({ p: [x + a, y + b], s: [1, 1, 1] });
      return out;
    }
    return [];
  }, [kind, bed, between]);
  useLayoutEffect(() => {
    const m = new THREE.Object3D();
    if (!ref.current) return;
    items.forEach((it, i) => {
      m.position.set(offset[0] + it.p[0], kind === "sprinkler" ? 0.6 : 0.14, offset[1] + it.p[1]);
      m.scale.set(it.s[0], kind === "sprinkler" ? 1 : 0.02, it.s[2]); m.updateMatrix();
      ref.current!.setMatrixAt(i, m.matrix);
    });
    ref.current.instanceMatrix.needsUpdate = true;
  }, [items, offset, kind]);
  if (!items.length) return null;
  const heads = kind === "sprinkler" ? items.map((it) => [offset[0] + it.p[0], offset[1] + it.p[1]] as [number, number]) : [];
  return (
    <>
      <instancedMesh ref={ref} args={[undefined, undefined, items.length]} raycast={() => null}>
        {kind === "sprinkler" ? <cylinderGeometry args={[0.05, 0.05, 1.2, 6]} /> : <boxGeometry args={[1, 1, 1]} />}
        <meshStandardMaterial color={kind === "drip" ? "#1d1f1e" : kind === "furrow" ? "#5a4128" : "#2f80d1"} roughness={0.8} />
      </instancedMesh>
      {animate && heads.length > 0 && <WaterSpray heads={heads.map(([x, z]) => [x, 0, z] as [number, number, number])}
        reach={Math.max(4, Math.sqrt(bed.area / Math.max(1, heads.length)) * 0.55)} nozzle={1.2} perHead={260} />}
    </>
  );
}

const LEAF_IMGS = ["/planner/foliage/tree_small_02_leaves_diff_1k.jpg", "/planner/foliage/tree_small_02_leaves_alpha_1k.jpg"];
const LAYERS = [{ y: 0.32, band: 1 }, { y: 0.62, band: 0.78 }, { y: 0.86, band: 0.5 }];

/** Dense rows of photographed foliage under the 3D plants (see canopy.ts): 1-3 layers by quality. */
function CropCarpet({ bed, offset, crop, group, stage, h, w, between, layers }: {
  bed: BedView; offset: [number, number]; crop: string; group: string; stage: Stage; h: number; w: number; between: number; layers: number;
}) {
  const [diff, alpha] = useTexture(LEAF_IMGS);
  const alongY = rowsAlongY(bed);
  const across = alongY ? bed.rect.w : bed.rect.h;
  const nRows = Math.max(1, Math.floor(across / between));
  const firstRow = (alongY ? bed.rect.x : bed.rect.y) + (across - (nRows - 1) * between) / 2;
  const geo = useMemo(() => carpetUV(shapeGeo(bed.local), alongY, firstRow, between), [bed.local, alongY, firstRow, between]);
  const k = STAGE_SCALE[stage];
  const base = Math.min(0.98, (w * k) / between);
  const mats = useMemo(() => LAYERS.slice(0, layers).map((L, i) => sharpAlpha(new THREE.MeshStandardMaterial({
    map: canopyTexture(crop, group, stage, base * L.band, i, diff.image as HTMLImageElement, alpha.image as HTMLImageElement),
    alphaTest: 0.5, side: THREE.DoubleSide, roughness: 0.82,
  }))), [crop, group, stage, base, layers, diff, alpha]);
  useEffect(() => () => mats.forEach((m) => m.dispose()), [mats]);
  if (k <= 0) return null;
  const top = Math.max(0.08, h * k);
  return <>{mats.map((m, i) => (
    <mesh key={i} geometry={geo} material={m} position={[offset[0], 0.13 + top * LAYERS[i].y * (layers === 1 ? 0.5 : 1), offset[1]]}
      receiveShadow castShadow={i === layers - 1} raycast={() => null} />
  ))}</>;
}

function BedMesh({ bed, view, exag, byKey, mode, selected, hovered, onSelect, onHover, budget, impBudget, tex, shadows, lodDist, models, stage, month, animate, layers, demo }: {
  bed: BedView; view: PlotView; exag: number; byKey: Record<string, RCrop>; mode: "3d" | "2d"; selected: boolean; hovered: boolean;
  onSelect: (k: string | null) => void; onHover: (k: string | null) => void; budget: number; impBudget: number; tex: ReturnType<typeof useTextures>; shadows: boolean; lodDist: number;
  models: Record<string, CropModel>; stage: Stage; month: number; animate: boolean; layers: number; demo?: string | null;
}) {
  const geo = useMemo(() => shapeGeo(bed.local, 0.12), [bed.local]);
  const flatGeo = useMemo(() => shapeGeo(bed.local), [bed.local]);
  const c = bed.crop;
  const info = c ? byKey[c.crop] : undefined;
  const model = c ? models[c.crop] : null;
  const h = c ? heightOf(byKey, c.crop) * exag : 0;
  const imp = useMemo(() => (c && mode === "3d" ? cropImpostor(c.crop, stage) : null), [c?.crop, mode, stage]); // eslint-disable-line react-hooks/exhaustive-deps
  const w = imp ? imp.wh * h : model ? model.width * h : 1;
  // declared spacing when it is wider than the (exaggerated) plants; then grown evenly if the bed exceeds its budget
  const [inRow, between] = imp
    ? fitBudget(bed.area, Math.max(w * 0.9 * STAGE_SCALE[stage], bed.plantSpacing ?? 0, 0.1), Math.max(w * 1.08 * STAGE_SCALE[stage], bed.rowSpacing ?? 0, 0.2), impBudget)
    : fitBudget(bed.area, Math.max(0.2, w * 0.9, bed.plantSpacing ?? 0), Math.max(0.45, w * 1.35, bed.rowSpacing ?? 0), budget);
  const pts = useMemo(() => ((model || imp) && mode === "3d" ? rows(bed, inRow, between, imp ? impBudget * 1.3 : budget * 1.3) : []),
    [bed, model, imp, inRow, between, budget, impBudget, mode]);
  const k = Math.max(1, exag / 6);  // bigger (exaggerated) plants stay readable a bit further away
  const lods = useMemo<[number, number]>(() => [lodDist * 0.35 * k, lodDist * 1.4 * k], [lodDist, k]);
  const seed = useMemo(() => [...bed.key].reduce((a, ch) => a + ch.charCodeAt(0), 0), [bed.key]);
  const outline = useMemo(() => [...bed.local, bed.local[0]].map(([x, y]) => [view.offset[0] + x, 0.3 + h * 0.02, view.offset[1] + y] as [number, number, number]), [bed.local, view.offset, h]);
  const [cx, cy] = centroid(bed.local);
  const pick = () => onSelect(bed.key);
  const over = () => onHover(bed.key);
  const out = () => onHover(null);
  return (
    <group>
      <mesh geometry={geo} position={[view.offset[0], 0, view.offset[1]]} receiveShadow onClick={(e) => { e.stopPropagation(); pick(); }}
            onPointerOver={(e) => { e.stopPropagation(); over(); }} onPointerOut={out}>
        <meshStandardMaterial map={tex.soil} normalMap={tex.soilN} roughnessMap={tex.soilR} normalScale={SOIL_NORMAL}
          color={bed.kind === "greenhouse" ? "#b9a088" : "#a3866a"} />
      </mesh>
      {mode === "2d" && c && (
        <mesh geometry={flatGeo} position={[view.offset[0], 0.15, view.offset[1]]} raycast={() => null}>
          <meshBasicMaterial color={cropColor(c.crop, c.family)} transparent opacity={c.proposed ? 0.62 : 0.85} />
        </mesh>
      )}
      {c && mode === "3d" && layers > 0 && !demo && !imp && (   /* during the irrigation demo the foliage carpet is hidden to show the water */
        <CropCarpet bed={bed} offset={view.offset} crop={c.crop} group={info?.group ?? "frutto"} stage={stage} h={h} w={w} between={between} layers={layers} />
      )}
      {imp && pts.length > 0 && (
        <ImpostorCrops name={imp.name} pts={pts} offset={view.offset} height={h * STAGE_SCALE[stage]} seed={seed} shadows={shadows} tint={imp.tint} />
      )}
      {!imp && model && pts.length > 0 && (
        <CropField model={model} pts={pts} offset={view.offset} scale={h * STAGE_SCALE[stage]} spacing={between} seed={seed} stage={stage}
                   shadows={shadows} lodDist={lods} onPick={pick} onOver={over} onOut={out} farHidden={layers > 0} />
      )}
      {mode === "3d" && c && view.irrigation && ["drip", "sprinkler", "furrow"].includes(view.irrigation) && (
        <Irrigation kind={view.irrigation} bed={bed} offset={view.offset} between={between} animate={animate} />
      )}
      {bed.kind === "greenhouse" && mode === "3d" && <Greenhouse bed={bed} offset={view.offset} />}
      {demo && <IrrigationDemo system={demo} bed={bed} offset={view.offset} between={between} top={Math.max(0.3, h * STAGE_SCALE[stage])} />}
      {(selected || hovered) && <Line points={outline} color={selected ? "#3d8bff" : "#ffffff"} lineWidth={selected ? 4 : 2} />}
      {selected && bed.local.map(([x, y], i) => (   /* corner handles of the selected part */
        <group key={i} position={[view.offset[0] + x, 0.35 + h * 0.02, view.offset[1] + y]}>
          <mesh raycast={() => null}><sphereGeometry args={[0.55, 16, 12]} /><meshBasicMaterial color="#ffffff" /></mesh>
          <mesh raycast={() => null} rotation={[-Math.PI / 2, 0, 0]}><ringGeometry args={[0.55, 0.85, 24]} /><meshBasicMaterial color="#3d8bff" /></mesh>
        </group>
      ))}
      {(selected || hovered) && (
        <Html position={[view.offset[0] + cx, h + 0.6, view.offset[1] + cy]} center zIndexRange={[20, 0]} style={{ pointerEvents: "none" }}>
          <div className="vp-tip">
            <div className="vp-tip-h">
              {c && <span className="vp-tip-dot" style={{ background: cropColor(c.crop, c.family) }} />}
              <b>{c ? shortName(c.name) : bed.name}</b>
            </div>
            <span>Superficie: {fmtArea(bed.area)}</span>
            {c?.verdict && <span className={`vp-v v-${c.verdict}`}>{c.proposed ? "Proposta · " : "Stato: "}{VERDICT_TXT[c.verdict]}
              {c.verdict === "ok" && <i className="vp-ok-ic">✓</i>}</span>}
            {c && month > 0 && <span>{STAGE_LABEL[stage]}</span>}
          </div>
        </Html>
      )}
    </group>
  );
}

function Other({ bed, view, tex, onSelect }: { bed: BedView; view: PlotView; tex: ReturnType<typeof useTextures>; onSelect: (k: string) => void }) {
  const geo = useMemo(() => shapeGeo(bed.local), [bed.local]);
  const [cx, cy] = centroid(bed.local);
  const { x, y, w, h } = bed.rect;
  const click = (e: { stopPropagation: () => void }) => { e.stopPropagation(); onSelect(bed.key); };
  const pos: [number, number, number] = [view.offset[0], 0.03, view.offset[1]];
  if (bed.kind === "water") {
    const r = Math.min(3, Math.min(w, h) * 0.35);
    return (
      <group>
        <mesh geometry={geo} position={pos} onClick={click}><meshStandardMaterial color="#9fc2d8" roughness={0.6} /></mesh>
        <mesh position={[view.offset[0] + cx, 1.25, view.offset[1] + cy]} onClick={click}>
          <cylinderGeometry args={[r, r, 2.5, 20]} /><meshStandardMaterial color="#b8c2c8" metalness={0.7} roughness={0.35} />
        </mesh>
      </group>
    );
  }
  if (bed.kind === "shade") {
    const n = Math.max(1, Math.min(6, Math.round(bed.area / 40)));
    const spots = Array.from({ length: n }, (_, i) => [view.offset[0] + x + w * ((i % 3) + 0.5) / Math.min(3, n), view.offset[1] + y + h * (Math.floor(i / 3) + 0.5) / Math.ceil(n / 3)] as [number, number]);
    return <group><mesh geometry={geo} position={pos} onClick={click}><meshStandardMaterial map={tex.grass} color="#9fb88a" /></mesh><Trees spots={spots} /></group>;
  }
  if (bed.kind === "access") {
    return (
      <group>
        <mesh geometry={geo} position={pos} onClick={click} receiveShadow><meshStandardMaterial map={tex.gravel} normalMap={tex.gravelN} color="#f0e4cc" roughness={1} /></mesh>
        {[-1, 1].map((s) => <mesh key={s} position={[view.offset[0] + cx + s * Math.min(w, h) * 0.45, 0.6, view.offset[1] + cy]}><boxGeometry args={[0.15, 1.2, 0.15]} /><meshStandardMaterial color="#6b4a2f" /></mesh>)}
      </group>
    );
  }
  if (bed.kind === "path") return <mesh geometry={geo} position={pos} onClick={click} receiveShadow><meshStandardMaterial map={tex.gravel} normalMap={tex.gravelN} color="#ece4d6" roughness={1} /></mesh>;
  const color = bed.kind === "no_crop" ? "#8fa47a" : "#b5a07a";
  return <mesh geometry={geo} position={pos} onClick={click} receiveShadow><meshStandardMaterial map={bed.kind === "no_crop" ? tex.grass : tex.dirt} color={color} roughness={1} /></mesh>;
}

function Compass({ target, compass, zoomLabel, ortho, base }: {
  target: THREE.Vector3; compass: React.RefObject<HTMLDivElement>; zoomLabel: React.RefObject<HTMLSpanElement>; ortho: boolean; base: number;
}) {
  const { camera } = useThree();
  useFrame(() => {
    if (compass.current) {
      const a = ortho ? 0 : Math.atan2(camera.position.x - target.x, camera.position.z - target.z);
      compass.current.style.setProperty("--a", `${a.toFixed(4)}rad`);   // dial turns, letters stay upright (CSS)
    }
    if (zoomLabel.current) {
      const pct = ortho ? (camera as THREE.OrthographicCamera).zoom / base : base / camera.position.distanceTo(target);
      zoomLabel.current.textContent = `${Math.round(pct * 100)}%`;
    }
  });
  return null;
}

export const FarmScene = forwardRef<SceneApi, SceneProps>(function FarmScene(props, ref) {
  const { views, byKey, mode, exag, selected, hovered, onSelect, onHover, compass, zoomLabel } = props;
  const tex = useTextures();
  const featPts = useMemo(() => (props.farmRef ? props.features.flatMap((f) => featurePoints(f, props.farmRef!)) : []), [props.features, props.farmRef]);
  const b = useMemo(() => bounds(views, featPts), [views, featPts]);
  // screen centre a little south-east of the farm: the side panel and the rotation strip cover the right and the bottom
  // home view: oblique aerial view of the plots (not of every road and hedge) from the south, low enough (~20 degrees)
  // for the wooded hills and the distant horizon to fill the top of the frame; the plots sit in the middle and bottom.
  const bp = useMemo(() => bounds(views), [views]);
  const target = useMemo(() => new THREE.Vector3(bp.cx + bp.size * 0.05, 0, bp.cz - bp.size * 0.09), [bp.cx, bp.cz, bp.size]);
  const home = useMemo<[number, number, number]>(() => [bp.cx + bp.size * 0.223, bp.size * 0.364, bp.cz + bp.size * 0.909], [bp.cx, bp.cz, bp.size]);
  const controls = useRef<any>(null);
  const { camera, size, scene } = useThree();
  const orthoZoom = Math.min(size.width, size.height) / (b.size * 1.25);
  const dist0 = Math.hypot(home[0] - target.x, home[1], home[2] - target.z);

  useImperativeHandle(ref, () => ({
    zoomBy: (f: number) => {
      if (mode === "2d") { const c = camera as THREE.OrthographicCamera; c.zoom = Math.max(0.05, c.zoom * f); c.updateProjectionMatrix(); return; }
      const t = controls.current?.target ?? target;
      const d = camera.position.clone().sub(t).multiplyScalar(1 / f);
      camera.position.copy(t.clone().add(d));
    },
    reset: () => {
      if (mode === "2d") { const c = camera as THREE.OrthographicCamera; c.zoom = orthoZoom; c.position.set(b.cx, 500, b.cz); c.updateProjectionMatrix(); }
      else camera.position.set(...home);
      controls.current?.target.copy(target);
    },
    zoomPct: () => 1,
    exportRender: () => exportRenderScene(scene, camera as THREE.PerspectiveCamera, {
      sun: SUN_DIR, fog: FOG, aspect: size.width / size.height,
      grass: { center: [b.cx, b.cz], radius: b.size * 0.75 + 60, density: 7 },
    }),
    focus: (x: number, z: number, r: number) => {
      const d = Math.max(12, r);
      if (mode === "2d") { const c = camera as THREE.OrthographicCamera; c.position.set(x, 500, z); c.zoom = Math.min(size.width, size.height) / (d * 2.5); c.updateProjectionMatrix(); }
      else camera.position.set(x + d * 0.8, d * 0.9, z + d * 1.4);
      controls.current?.target.set(x, 0, z);
    },
  }), [mode, camera, target, b, orthoZoom, size, home, scene]);

  // development only: place the camera from scripts (visual checks with fixed framing)
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    const w = window as unknown as { __plannerCam?: (c: { p: number[]; t: number[] }) => void };
    w.__plannerCam = ({ p, t }) => { camera.position.set(p[0], p[1], p[2]); controls.current?.target.set(t[0], t[1], t[2]); controls.current?.update?.(); };
    return () => { delete w.__plannerCam; };
  }, [camera]);

  // plant budget shared by area
  const total =views.reduce((a, v) => a + v.beds.reduce((s, x) => s + (x.crop ? x.area : 0), 0), 0) || 1;
  const zone = useMemo<FarmZone>(() => ({ x0: b.x0, x1: b.x1, z0: b.z0, z1: b.z1, cx: b.cx, cz: b.cz, size: b.size }), [b]);
  const terrain = useMemo(() => demoTerrain(zone), [zone]);
  useEffect(() => { props.onTerrainLabel?.(terrain.label); }, [terrain]); // eslint-disable-line react-hooks/exhaustive-deps
  const exclude = useMemo(() => views.map((v) => v.outline.map(([x, y]) => [v.offset[0] + x, v.offset[1] + y] as XZ)), [views]);
  const cropKeys = views.flatMap((v) => v.beds.map((b) => b.crop?.crop)).filter(Boolean).sort().join();
  const cropList = useMemo(() => [...new Set(cropKeys.split(",").filter(Boolean))].map((key) => ({ key, group: byKey[key]?.group ?? "frutto" })), [cropKeys, byKey]);
  const models = useCropModels(cropList);

  return (
    <>
      {mode === "3d" ? (
        <>
          <PerspectiveCamera makeDefault fov={45} near={0.5} far={b.size * 40 + 3000} position={home} />
          <OrbitControls ref={controls} target={target} enableDamping maxPolarAngle={1.47} minDistance={3} maxDistance={b.size * 5 + 300} />
        </>
      ) : (
        <>
          <OrthographicCamera makeDefault position={[b.cx, 500, b.cz]} zoom={orthoZoom} near={1} far={2000} up={[0, 0, -1]} onUpdate={(c) => c.lookAt(b.cx, 0, b.cz)} />
          <MapControls ref={controls} target={target} enableRotate={false} screenSpacePanning />
        </>
      )}
      <Compass target={controls.current?.target ?? target} compass={compass} zoomLabel={zoomLabel} ortho={mode === "2d"} base={mode === "2d" ? orthoZoom : dist0} />
      <FarmEngine zone={zone} terrain={terrain} quality={props.quality} exclude={exclude} grassTex={tex.grass} topView={mode === "2d"} />
      <Structures features={props.features} farmRef={props.farmRef} terrain={terrain} month={props.month} selected={selected}
                  onSelect={onSelect} quality={props.quality} />
      {props.placing && (
        <>
          {/* invisible catcher: a click anywhere returns a ground point for the element being placed */}
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[b.cx, 0.3, b.cz]} onClick={(e) => { e.stopPropagation(); props.onGround(e.point.x, e.point.z); }}>
            <planeGeometry args={[b.size * 6 + 400, b.size * 6 + 400]} />
            <meshBasicMaterial transparent opacity={0} depthWrite={false} />
          </mesh>
          {props.placing.pts.map(([x, z], i) => <mesh key={i} position={[x, terrain.heightAt(x, z) + 0.6, z]} raycast={() => null}><sphereGeometry args={[0.9, 12, 8]} /><meshBasicMaterial color="#ffd24a" /></mesh>)}
          {props.placing.pts.length > 1 && <Line points={[...props.placing.pts, ...(props.placing.kind === "Polygon" && props.placing.pts.length > 2 ? [props.placing.pts[0]] : [])]
            .map(([x, z]) => [x, terrain.heightAt(x, z) + 0.6, z] as [number, number, number])} color="#ffd24a" lineWidth={3} dashed dashSize={2} gapSize={1} />}
        </>
      )}

      {props.edit?.on && (() => {
        for (const v of views) for (const bd of [...v.beds, ...v.others]) {
          if (bd.key !== selected || !bd.sectionId) continue;
          return <SectionGizmo key={bd.key} rect={bd.rect} offset={v.offset} limit={{ W: v.plot.width_m ?? 10, L: v.plot.length_m ?? 10 }} controls={controls}
            onCommit={(r) => props.edit!.onSection(v.plot.id, bd.sectionId!, r)} />;
        }
        const f = props.farmRef && selected?.startsWith("feature:") ? props.features.find((x) => `feature:${x.id}` === selected) : null;
        if (f && props.farmRef) {
          const pts = featurePoints(f, props.farmRef);
          const closed = f.geometry.type === "Polygon";
          return <FeatureGizmo key={f.id} pts={closed ? pts.slice(0, -1) : pts} closed={closed} controls={controls} onCommit={(p) => props.edit!.onFeature(f.id, p)} />;
        }
        return null;
      })()}
      {views.map((v) => (
        <group key={v.plot.id}>
          <mesh geometry={useMemoShape(v.outline)} position={[v.offset[0], 0.02, v.offset[1]]} receiveShadow onClick={(e) => { e.stopPropagation(); onSelect(null); }}>
            <meshStandardMaterial color="#c9b896" map={tex.dirt} roughness={1} />
          </mesh>
          {v.others.map((o) => <Other key={o.key} bed={o} view={v} tex={tex} onSelect={onSelect} />)}
          {v.beds.map((bd) => (
            <BedMesh key={bd.key} bed={bd} view={v} exag={exag} byKey={byKey} mode={mode} tex={tex}
              selected={selected === bd.key} hovered={hovered === bd.key} onSelect={onSelect} onHover={onHover}
              budget={Math.max(30, Math.round((props.quality.plants * (bd.crop ? bd.area : 0)) / total))}
              impBudget={Math.max(60, Math.round((props.quality.cropImpostors * 3 * (bd.crop ? bd.area : 0)) / total))} shadows={props.quality.plantShadows} lodDist={props.quality.plantLod}
              models={models} month={props.month} stage={bd.crop ? stageFor(props.calendar[bd.crop.crop], props.month) : "mature"} animate={props.quality.wind}
              layers={props.quality.level === "high" || props.quality.level === "ultra" ? 3 : props.quality.level === "medium" ? 2 : 1}
              demo={props.demo?.plotId === v.plot.id ? props.demo.system : null} />
          ))}
          {!selected?.startsWith(`${v.plot.id}:`) && <Html position={[v.offset[0] + centroid(v.outline)[0], 0.5, v.offset[1] + Math.min(...v.outline.map((p) => p[1])) - 2]} center
                zIndexRange={[10, 0]} style={{ pointerEvents: "none" }}>
            <div className="vp-plot-label">{v.plot.name}{!v.traced && <small> · non tracciato</small>}</div>
          </Html>}
        </group>
      ))}
    </>
  );
});

const shapeCache = new WeakMap<XY[], THREE.BufferGeometry>();
function useMemoShape(pts: XY[]) {
  let g = shapeCache.get(pts);
  if (!g) { g = shapeGeo(pts); shapeCache.set(pts, g); }
  return g;
}
