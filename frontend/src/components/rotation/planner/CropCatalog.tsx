/** 3D catalogue of the crop library: every dedicated model, by growth stage and level of detail. */
import { Suspense, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { ContactShadows, Environment, Html, OrbitControls } from "@react-three/drei";
import { Icon } from "../../Icon";
import { RCrop, shortName } from "../types";
import { dedicatedCrops, partsFor, Stage, STAGE_LABEL, useCropModels } from "./cropLibrary";

const NEUTRAL = 0.3;

function Models({ crops, stage, lod, real }: { crops: RCrop[]; stage: Stage; lod: 0 | 1 | 2; real: boolean }) {
  const list = useMemo(() => crops.map((c) => ({ key: c.key, group: c.group })), [crops]);
  const models = useCropModels(list);
  const cols = 5, gap = 1.9;
  return <>{crops.map((c, i) => {
    const m = models[c.key];
    const h = real ? (c.height_m ? (c.height_m[0] + c.height_m[1]) / 2 : NEUTRAL) : 1;
    const x = (i % cols - (cols - 1) / 2) * gap, z = (Math.floor(i / cols) - 1) * gap;
    const fit = real ? h : 1.15 / Math.max(1, (m?.width ?? 1));   // same size: every plant fits its cell
    const s = fit * (stage === "young" ? 0.35 : stage === "growing" ? 0.75 : 1);
    return (
      <group key={c.key} position={[x, 0, z]}>
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.002, 0]} receiveShadow><circleGeometry args={[0.7, 24]} /><meshStandardMaterial color="#8a6a4a" roughness={1} /></mesh>
        <group scale={s}>{m && partsFor(m, lod, stage).map((p) => <mesh key={p.kind} geometry={p.geo} material={p.mat} castShadow />)}</group>
        <Html position={[0, 0, 0.85]} center style={{ pointerEvents: "none" }}>
          <div className="cc-label"><b>{shortName(c.name)}</b><span>{c.height_m ? `${c.height_m[0] === c.height_m[1] ? c.height_m[0] : c.height_m.join("–")} m` : "altezza n.d."} · {Math.round(m?.tris[lod] ?? 0)} triangoli</span></div>
        </Html>
      </group>
    );
  })}</>;
}

export default function CropCatalog({ crops, onClose }: { crops: RCrop[]; onClose: () => void }) {
  const [stage, setStage] = useState<Stage>("mature");
  const [lod, setLod] = useState<0 | 1 | 2>(0);
  const [real, setReal] = useState(true);
  const lib = useMemo(() => { const keys = new Set(dedicatedCrops()); return crops.filter((c) => keys.has(c.key)); }, [crops]);
  return (
    <div className="cc">
      <div className="cc-top">
        <b>Libreria colture 3D</b><span className="tiny muted">{lib.length} modelli dedicati · GLB con 3 livelli di dettaglio</span>
        <span className="spacer" />
        <button className="icon-btn" onClick={onClose} aria-label="Chiudi"><Icon name="minus" size={15} /></button>
      </div>
      <div className="cc-controls">
        <div className="vp-modes">{(["young", "growing", "mature"] as Stage[]).map((s) => <button key={s} className={stage === s ? "on" : ""} onClick={() => setStage(s)}>{STAGE_LABEL[s]}</button>)}</div>
        <div className="vp-modes">{([0, 1, 2] as const).map((l) => <button key={l} className={lod === l ? "on" : ""} onClick={() => setLod(l)}>{["Vicino", "Medio", "Lontano"][l]}</button>)}</div>
        <div className="vp-modes"><button className={real ? "on" : ""} onClick={() => setReal(true)}>Altezze reali</button><button className={!real ? "on" : ""} onClick={() => setReal(false)}>Stessa altezza</button></div>
      </div>
      <div className="cc-stage">
        <Canvas shadows camera={{ position: [0, 4.2, 7.4], fov: 40 }} dpr={[1, 2]}>
          <Suspense fallback={null}>
            <color attach="background" args={["#e8efe9"]} />
            <Environment files="/planner/alps_field_1k.hdr" environmentIntensity={0.7} />
            <directionalLight position={[-4, 6, 5]} intensity={2.2} castShadow shadow-mapSize={[1024, 1024]} />
            <Models crops={lib} stage={stage} lod={lod} real={real} />
            <ContactShadows position={[0, 0.001, 0]} opacity={0.35} scale={14} blur={2.2} far={3} />
          </Suspense>
          <OrbitControls target={[0, 0.4, 0]} maxPolarAngle={1.45} minDistance={1.2} maxDistance={14} />
        </Canvas>
      </div>
      <div className="tiny muted">Modelli botanici costruiti da AgroAI (script <code>build-crop-models.mjs</code>); altezze da FAO-56, tabella 12.
        Un modello GLB fatto in Blender con gli stessi nomi dei livelli (LOD0, LOD1, LOD2) può sostituirli.</div>
    </div>
  );
}
