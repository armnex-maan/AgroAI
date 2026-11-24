/**
 * Distant landscape beyond the 3D terrain: a panoramic band rendered offline in Blender/Cycles
 * (tools/blender/make_horizon.py: rolling Tuscan hills, field patchwork, woods, cypresses, farmhouses, aerial haze),
 * drawn on a sphere band that follows the camera like a sky. Transparent sky, no depth writes: the 3D terrain and
 * everything nearer always covers it. Demonstrative scenery, never data (the planner says so on screen).
 */
import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { useTexture } from "@react-three/drei";
import * as THREE from "three";

export const HORIZON_IMG = "/planner/horizon/horizon.webp";
/** Latitude range of the band (degrees), as rendered by make_horizon.py. */
const LAT_MIN = -24, LAT_MAX = 8;

export function Horizon({ radius }: { radius: number }) {
  const tex = useTexture(HORIZON_IMG);
  const ref = useRef<THREE.Mesh>(null);
  const geo = useMemo(() => {
    const t0 = THREE.MathUtils.degToRad(90 - LAT_MAX), t1 = THREE.MathUtils.degToRad(LAT_MAX - LAT_MIN);
    return new THREE.SphereGeometry(1, 128, 24, 0, Math.PI * 2, t0, t1);
  }, []);
  const mat = useMemo(() => {
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.wrapS = THREE.RepeatWrapping;
    // panorama u: 0.25 west, 0.5 north, 0.75 east; sphere u runs west -> south -> east: mirror and shift
    tex.repeat.set(-1, 1); tex.offset.set(0.25, 0);
    tex.anisotropy = 8; tex.needsUpdate = true;
    return new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, fog: false, side: THREE.BackSide });
  }, [tex]);
  useFrame(({ camera }) => { ref.current?.position.copy(camera.position); });
  return <mesh ref={ref} geometry={geo} material={mat} scale={radius} renderOrder={-10} raycast={() => null} frustumCulled={false} userData={{ noExport: true }} />;
}
