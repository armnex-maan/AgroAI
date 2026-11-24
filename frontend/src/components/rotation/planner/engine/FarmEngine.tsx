/**
 * AgroAI Farm Engine – the environment around the farm data: terrain, grass, woods, sun, sky, haze,
 * shadows and post-processing, with quality profiles. It draws scenery only: nothing here is selectable
 * and nothing here is agronomic data (see the agroai-farm-planner skill).
 */
import { createContext, useContext, useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Environment } from "@react-three/drei";
import { Bloom, BrightnessContrast, EffectComposer, HueSaturation, N8AO, ToneMapping, Vignette } from "@react-three/postprocessing";
import { ToneMappingMode } from "postprocessing";
import * as THREE from "three";
import { Forest, Grass, Terrain, terrainExtent, XZ } from "./Landscape";
import { QualityProfile } from "./quality";
import { Shrubs } from "./Shrubs";
import { FOLIAGE_WIND } from "./foliage";
import { CROP_WIND } from "../cropLibrary";
import { FarmZone, TerrainSource } from "./terrain";
import { GradeEffect } from "./grade";
import { Horizon } from "./Horizon";

export interface EngineCtx { terrain: TerrainSource; quality: QualityProfile; zone: FarmZone }
const Ctx = createContext<EngineCtx | null>(null);
export const useEngine = () => useContext(Ctx);

/** Sky: CC0 HDRI "Kloofendal 48d Partly Cloudy (Pure Sky)" from Poly Haven (real photographed clouds, no ground).
 *  Its sun was measured in the file (pixel 1218,239 of 2048x1024: 47.9° above the horizon). The sky is turned
 *  so that the sun comes from the south-west, and the shadow-casting light uses exactly the same direction. */
export const SKY_HDRI = "/planner/kloofendal_48d_partly_cloudy_puresky_2k.hdr";
const SKY_SUN = new THREE.Vector3(0.555, 0.742, 0.377).normalize();
export const SKY_ROTATION = -1.75;
/** Shadow-casting sun: same azimuth as the sky's sun but lower (32 degrees, late-morning light) for long, readable
 *  shadows. The sun disc of the HDRI is never in view from the planner's aerial cameras. */
const SUN_ELEVATION = THREE.MathUtils.degToRad(32);
const SUN_AZ = SKY_SUN.clone().applyAxisAngle(new THREE.Vector3(0, 1, 0), SKY_ROTATION).setY(0).normalize();
export const SUN_DIR = new THREE.Vector3(SUN_AZ.x * Math.cos(SUN_ELEVATION), Math.sin(SUN_ELEVATION), SUN_AZ.z * Math.cos(SUN_ELEVATION));
export const HAZE = "#d3e0ea";
export const FOG = { near: 150, far: 10500 };

function Sun({ zone, quality }: { zone: FarmZone; quality: QualityProfile }) {
  const light = useRef<THREE.DirectionalLight>(null);
  const { scene } = useThree();
  const target = useMemo(() => new THREE.Object3D(), []);
  const half = zone.size * 0.62 + 30;               // the shadow box covers the whole farm and its edges
  useEffect(() => {
    target.position.set(zone.cx, 0, zone.cz);
    scene.add(target);
    if (light.current) light.current.target = target;
    return () => { scene.remove(target); };
  }, [scene, target, zone.cx, zone.cz]);
  const d = zone.size * 1.5 + 200;
  return (
    <directionalLight ref={light} position={[zone.cx + SUN_DIR.x * d, SUN_DIR.y * d, zone.cz + SUN_DIR.z * d]} intensity={4.4} color="#ffe7c4"
      castShadow={quality.shadowMap > 0} shadow-mapSize={[quality.shadowMap || 512, quality.shadowMap || 512]} shadow-bias={-0.0004} shadow-normalBias={0.6}
      shadow-camera-left={-half} shadow-camera-right={half} shadow-camera-top={half} shadow-camera-bottom={-half}
      shadow-camera-near={1} shadow-camera-far={d * 2.2} />
  );
}

/** Post-processing applies its own tone mapping: avoid doing it twice. */
function ToneMap({ composer }: { composer: boolean }) {
  const { gl } = useThree();
  useEffect(() => { gl.toneMapping = composer ? THREE.NoToneMapping : THREE.ACESFilmicToneMapping; gl.toneMappingExposure = 1.0; }, [gl, composer]);
  return null;
}

/** Advances the wind of crop leaves (stops in battery-saving mode). */
function WindClock({ on }: { on: boolean }) {
  useFrame((_, dt) => { if (on) { CROP_WIND.uTime.value += dt; FOLIAGE_WIND.uTime.value += dt; } });
  return null;
}

/** Keeps the camera above the hills. */
function CameraGuard({ terrain }: { terrain: TerrainSource }) {
  const { camera } = useThree();
  useFrame(() => {
    const min = terrain.heightAt(camera.position.x, camera.position.z) + 3;
    if (camera.position.y < min) camera.position.y = min;
  });
  return null;
}

/** Development-only counters (frame rate, draw calls, triangles), read by the performance checks. */
function DevStats({ quality }: { quality: QualityProfile }) {
  const { gl, scene } = useThree();
  const acc = useRef({ n: 0, t: 0 });
  // with post-processing a frame has several passes: count them all (info is reset by hand each frame)
  useEffect(() => { if (import.meta.env.DEV) gl.info.autoReset = false; return () => { gl.info.autoReset = true; }; }, [gl]);
  useFrame((_, dt) => {
    if (!import.meta.env.DEV) return;
    acc.current.n++; acc.current.t += dt;
    if (acc.current.t >= 1) {
      (window as unknown as { __farmEngine: unknown }).__farmEngine = { fps: Math.round(acc.current.n / acc.current.t), quality: quality.level,
        calls: gl.info.render.calls, triangles: gl.info.render.triangles, geometries: gl.info.memory.geometries, textures: gl.info.memory.textures,
        shadows: (() => { let casters = 0, sun = null as null | object; scene.traverse((o) => {
          if ((o as THREE.DirectionalLight).isDirectionalLight) { const l = o as THREE.DirectionalLight; sun = { cast: l.castShadow, map: !!l.shadow.map, size: l.shadow.mapSize.x }; }
          else if (o.castShadow) casters++; }); return { enabled: gl.shadowMap.enabled, casters, sun }; })() };
      acc.current = { n: 0, t: 0 };
    }
    gl.info.reset();
  });
  return null;
}

export function FarmEngine({ zone, terrain, quality, exclude, grassTex, topView, children }: {
  zone: FarmZone; terrain: TerrainSource; quality: QualityProfile; exclude: XZ[][]; grassTex: THREE.Texture; topView: boolean;
  children?: React.ReactNode;
}) {
  const S = terrainExtent(zone);
  const ctx = useMemo(() => ({ terrain, quality, zone }), [terrain, quality, zone]);
  const grade = useMemo(() => new GradeEffect(), []);
  useEffect(() => () => grade.dispose(), [grade]);
  return (
    <Ctx.Provider value={ctx}>
      {/* linear fog close to the aerial haze baked into the horizon panorama, so the 3D terrain edge blends into it */}
      {!topView && <fog attach="fog" args={[HAZE, FOG.near, FOG.far]} />}
      {topView && <color attach="background" args={["#e9efe6"]} />}
      <Environment files={SKY_HDRI} background={!topView} environmentIntensity={0.8} backgroundIntensity={1}
        backgroundRotation={[0, SKY_ROTATION, 0]} environmentRotation={[0, SKY_ROTATION, 0]} />
      <hemisphereLight args={["#e4f0ff", "#5d6b3c", 0.35]} />
      <Sun zone={zone} quality={quality} />
      <Terrain zone={zone} terrain={terrain} quality={quality} grassTex={grassTex} />
      {!topView && <Horizon radius={zone.size * 30 + 2000} />}
      {!topView && <Grass zone={zone} terrain={terrain} quality={quality} exclude={exclude} />}
      {!topView && <Forest zone={zone} terrain={terrain} quality={quality} />}
      {!topView && quality.shrubs > 0 && <Shrubs zone={zone} terrain={terrain} quality={quality} />}
      {!topView && <CameraGuard terrain={terrain} />}
      {children}
      {!quality.ao && quality.level === "medium" && !topView && (
        /* medium: colour grading only (cheap full-screen passes, no ambient occlusion or bloom) */
        <EffectComposer multisampling={4} enableNormalPass={false}>
          <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
          <HueSaturation saturation={0.06} />
          <BrightnessContrast brightness={0.02} contrast={0.12} />
          <primitive object={grade} />
          <Vignette offset={0.38} darkness={0.32} />
        </EffectComposer>
      )}
      {quality.ao && !topView && (
        <EffectComposer multisampling={4} enableNormalPass={false}>
          <N8AO aoRadius={quality.level === "ultra" ? 4 : 3} distanceFalloff={1.2} intensity={2.4} halfRes={quality.level !== "ultra"} quality={quality.level === "ultra" ? "medium" : "performance"} />
          <Bloom luminanceThreshold={0.9} luminanceSmoothing={0.25} intensity={0.3} mipmapBlur />
          <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
          <HueSaturation saturation={0.04} />
          <BrightnessContrast brightness={0.02} contrast={0.14} />
          <primitive object={grade} />
          <Vignette offset={0.38} darkness={0.32} />
        </EffectComposer>
      )}
      <ToneMap composer={(quality.ao || quality.level === "medium") && !topView} />
      <WindClock on={quality.wind && !topView} />
      <DevStats quality={quality} />
    </Ctx.Provider>
  );
}
