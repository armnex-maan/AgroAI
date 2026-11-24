/**
 * Water of sprinkler heads: droplets on ballistic arcs, a fan that sweeps back and forth like an impulse sprinkler,
 * plus fine mist. GPU-animated points (one draw call for all heads). Animation only: never a hydraulic calculation.
 */
import { useEffect, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { rng } from "./noise";

const VERT = /* glsl */ `
uniform float uTime;
uniform float uScale;
attribute vec4 aHead;     // x, y (nozzle height), z, reach
attribute vec4 aSeed;     // phase, lateral offset, speed, head seed
varying float vFade;
void main() {
  float reach = aHead.w;
  float t = fract(uTime * 0.55 * aSeed.z + aSeed.x);
  float sweep = sin(uTime * 0.35 + aSeed.w * 6.283) * 1.3 + aSeed.w * 6.283;   // the fan sweeps back and forth
  float az = sweep + aSeed.y * 0.55;
  float d = t * reach * (0.55 + 0.45 * aSeed.z);
  float hTop = 0.18 * reach;
  vec3 p = vec3(aHead.x + cos(az) * d, aHead.y + 4.0 * hTop * t * (1.0 - t) * (0.7 + 0.3 * aSeed.z) - t * aHead.y, aHead.z + sin(az) * d);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = uScale * (0.22 + 0.34 * t) / -mv.z;
  vFade = (1.0 - t) * smoothstep(0.0, 0.08, t);
}`;

const FRAG = /* glsl */ `
varying float vFade;
void main() {
  vec2 q = gl_PointCoord * 2.0 - 1.0;
  float r = dot(q, q);
  if (r > 1.0) discard;
  float a = (1.0 - r) * vFade * 0.55;
  gl_FragColor = vec4(mix(vec3(0.82, 0.9, 1.0), vec3(1.0), 1.0 - r), a);
}`;

export function WaterSpray({ heads, reach, nozzle = 0.9, perHead = 420 }: { heads: [number, number, number][]; reach: number; nozzle?: number; perHead?: number }) {
  const geo = useMemo(() => {
    const n = heads.length * perHead, r = rng(91);
    const pos = new Float32Array(n * 3), head = new Float32Array(n * 4), seed = new Float32Array(n * 4);
    heads.forEach(([x, y, z], h) => {
      const hs = r();
      for (let k = 0; k < perHead; k++) {
        const i = h * perHead + k;
        pos.set([x, y, z], i * 3);
        head.set([x, y + nozzle, z, reach], i * 4);
        seed.set([r(), (r() - 0.5) * (r() < 0.75 ? 0.5 : 2), 0.75 + r() * 0.5, hs], i * 4);
      }
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("aHead", new THREE.BufferAttribute(head, 4));
    g.setAttribute("aSeed", new THREE.BufferAttribute(seed, 4));
    g.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1e6);
    return g;
  }, [heads, reach, nozzle, perHead]);
  const mat = useMemo(() => new THREE.ShaderMaterial({
    vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false,
    uniforms: { uTime: { value: 0 }, uScale: { value: 900 } },
  }), []);
  useEffect(() => () => { geo.dispose(); }, [geo]);
  useEffect(() => () => mat.dispose(), [mat]);
  useFrame(({ clock, size }) => { mat.uniforms.uTime.value = clock.elapsedTime; mat.uniforms.uScale.value = size.height * 1.2; });
  if (!heads.length) return null;
  return <points geometry={geo} material={mat} raycast={() => null} frustumCulled={false} />;
}
