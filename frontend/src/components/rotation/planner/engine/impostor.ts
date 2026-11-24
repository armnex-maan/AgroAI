/**
 * Tree impostors: photoscanned CC0 trees (Poly Haven) rendered offline in Blender/Cycles from 64 directions of the
 * upper hemisphere (hemi-octahedral grid) into a colour atlas (lit by a white sky: albedo x ambient occlusion) and a
 * normal atlas. At runtime every tree is ONE quad: the vertex shader picks the frame nearest to the view direction
 * and turns the quad like that frame's camera; the fragment shader reads colour, coverage and normal, so the tree
 * takes the scene's sun, shadows, fog and post-processing like any other mesh. The shadow pass uses the same quad
 * seen from the sun, so trees also cast real tree-shaped shadows.
 * Bake script: tools/blender/bake_impostor.py (see public/planner/impostors/CREDITS.md).
 */
import { useMemo } from "react";
import { useTexture } from "@react-three/drei";
import * as THREE from "three";
import baked from "./impostors.json";

export interface ImpostorSpec { name: string; frames: number; px: number; height: number; radius: number; centre: [number, number, number] }

/** Baked trees (manifest written by the publish script from the bake output). */
export const IMPOSTORS: Record<string, ImpostorSpec> = Object.fromEntries((baked as ImpostorSpec[]).map((s) => [s.name, s]));

const VERT_PARS = /* glsl */ `
uniform float uFrames;
uniform float uRadius;
uniform vec3 uCentre;
varying vec2 vCell;
varying vec2 vSt;
varying vec3 vN0; varying vec3 vN1; varying vec3 vN2;
`;

/** Billboard of the nearest baked frame; sets mvPosition / worldPosition / gl_Position. */
const VERT_MAIN = /* glsl */ `
  vec3 iPos = vec3(instanceMatrix[3][0], instanceMatrix[3][1], instanceMatrix[3][2]);
  float iScale = length(vec3(instanceMatrix[0][0], instanceMatrix[0][1], instanceMatrix[0][2]));
  mat3 iRot = mat3(instanceMatrix) * (1.0 / iScale);
  vec3 centreW = (modelMatrix * vec4(iPos + iRot * (uCentre * iScale), 1.0)).xyz;
  vec3 toCam = isOrthographic ? normalize(vec3(viewMatrix[0][2], viewMatrix[1][2], viewMatrix[2][2]))
                              : normalize(cameraPosition - centreW);
  vec3 dObj = transpose(iRot) * toCam;
  dObj.y = max(dObj.y, 0.0);
  dObj = normalize(dObj + vec3(0.0, 1e-4, 0.0));
  float sAbs = abs(dObj.x) + abs(dObj.y) + abs(dObj.z);
  vec2 oct = vec2(dObj.x + dObj.z, dObj.x - dObj.z) / sAbs * 0.5 + 0.5;
  vec2 cell = clamp(floor(oct * (uFrames - 1.0) + 0.5), 0.0, uFrames - 1.0);
  vec2 g = cell / (uFrames - 1.0) * 2.0 - 1.0;
  vec3 fd = vec3((g.x + g.y) * 0.5, 0.0, (g.x - g.y) * 0.5);
  fd.y = 1.0 - abs(fd.x) - abs(fd.z);
  fd = normalize(fd);
  vec3 upRef = abs(fd.y) < 0.999 ? vec3(0.0, 1.0, 0.0) : vec3(0.0, 0.0, -1.0);
  vec3 bf = -fd;
  vec3 br = normalize(cross(bf, upRef));
  vec3 bu = cross(br, bf);
  vec2 st = position.xy;
  float R = uRadius * iScale;
  vec3 wFacing = iRot * fd;
  vec3 wPos = centreW + iRot * ((br * st.x + bu * st.y) * R) + wFacing * R * 0.35;
  vCell = cell; vSt = st;
  mat3 toView = mat3(viewMatrix) * iRot;
  vN0 = toView[0]; vN1 = toView[1]; vN2 = toView[2];
`;

const FRAG_PARS = /* glsl */ `
uniform sampler2D uColorAtlas;
uniform sampler2D uNormalAtlas;
uniform float uFrames;
uniform float uPx;
varying vec2 vCell;
varying vec2 vSt;
varying vec3 vN0; varying vec3 vN1; varying vec3 vN2;
vec2 impUv() {
  vec2 f = clamp(vSt * 0.5 + 0.5, 0.5 / uPx, 1.0 - 0.5 / uPx);
  return (vCell + f) / uFrames;
}
float impAlpha(float a) {
  // keep alpha-tested foliage full at a distance (mipmaps average coverage away)
  return clamp((a - 0.45) / max(fwidth(a), 0.0001) + 0.5, 0.0, 1.0);
}
`;

function patchStandard(m: THREE.MeshStandardMaterial, uniforms: Record<string, THREE.IUniform>) {
  m.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, uniforms);
    sh.vertexShader = VERT_PARS + sh.vertexShader
      .replace("#include <begin_vertex>", `#include <begin_vertex>\n${VERT_MAIN}\n  transformedNormal = normalize(mat3(viewMatrix) * wFacing);`)
      .replace("#include <project_vertex>", "vec4 mvPosition = viewMatrix * vec4(wPos, 1.0);\ngl_Position = projectionMatrix * mvPosition;")
      .replace("#include <worldpos_vertex>", "vec4 worldPosition = vec4(wPos, 1.0);");
    sh.fragmentShader = FRAG_PARS + sh.fragmentShader
      .replace("#include <map_fragment>", `vec2 iuv = impUv();
  vec4 impC = texture2D(uColorAtlas, iuv);
  diffuseColor.rgb *= impC.rgb;
  diffuseColor.a *= impAlpha(impC.a);`)
      .replace("#include <normal_fragment_begin>", `vec3 objN = texture2D(uNormalAtlas, iuv).xyz * 2.0 - 1.0;
  vec3 normal = normalize(mat3(vN0, vN1, vN2) * objN);
  vec3 nonPerturbedNormal = normal;
  float faceDirection = 1.0;`)
      .replace("#include <normal_fragment_maps>", "");
  };
  m.customProgramCacheKey = () => "impostor-std";
}

function depthMaterial(uniforms: Record<string, THREE.IUniform>) {
  const d = new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking });
  d.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, uniforms);
    sh.vertexShader = VERT_PARS + sh.vertexShader
      .replace("#include <begin_vertex>", `#include <begin_vertex>\n${VERT_MAIN}`)
      .replace("#include <project_vertex>", "vec4 mvPosition = viewMatrix * vec4(wPos, 1.0);\ngl_Position = projectionMatrix * mvPosition;");
    sh.fragmentShader = FRAG_PARS + sh.fragmentShader
      .replace("#include <alphatest_fragment>", "if (texture2D(uColorAtlas, impUv()).a < 0.5) discard;");
  };
  d.customProgramCacheKey = () => "impostor-depth";
  return d;
}

export interface ImpostorKit { spec: ImpostorSpec; material: THREE.MeshStandardMaterial; depth: THREE.MeshDepthMaterial; geometry: THREE.BufferGeometry }

const QUAD = new THREE.PlaneGeometry(2, 2);

/** Material pair (lit + shadow) for one baked tree. */
export function useImpostor(name: string): ImpostorKit {
  const spec = IMPOSTORS[name];
  const [color, normal] = useTexture([`/planner/impostors/${name}_color.webp`, `/planner/impostors/${name}_normal.webp`]);
  return useMemo(() => {
    color.colorSpace = THREE.SRGBColorSpace;
    normal.colorSpace = THREE.NoColorSpace;
    for (const t of [color, normal]) { t.anisotropy = 4; t.generateMipmaps = true; t.minFilter = THREE.LinearMipmapLinearFilter; t.needsUpdate = true; }
    const uniforms = {
      uFrames: { value: spec.frames }, uPx: { value: spec.px }, uRadius: { value: spec.radius },
      uCentre: { value: new THREE.Vector3(...spec.centre) }, uColorAtlas: { value: color }, uNormalAtlas: { value: normal },
    };
    // alpha to coverage: with the multisampled render targets the leaf edges are antialiased and do not shimmer
    const material = new THREE.MeshStandardMaterial({ roughness: 0.85, metalness: 0, alphaTest: 0.5, side: THREE.DoubleSide, alphaToCoverage: true });
    material.userData.impostor = name;              // the photoreal render replaces it with the real 3D model
    patchStandard(material, uniforms);
    return { spec, material, depth: depthMaterial(uniforms), geometry: QUAD };
  }, [spec, color, normal]);
}

/** Instance matrix of a tree whose trunk base is at (x, y, z), `height` metres tall, turned by `rot`. */
export function treeMatrix(m: THREE.Matrix4, x: number, y: number, z: number, height: number, rot: number) {
  const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), rot);
  return m.compose(new THREE.Vector3(x, y, z), q, new THREE.Vector3(height, height, height));
}
