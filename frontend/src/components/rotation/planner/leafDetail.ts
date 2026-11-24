/**
 * Photographic surface detail for crop and orchard leaves. The crop models have no texture coordinates, so the
 * detail (veins, light and shade of a real leaf) is projected from three sides in model space ("triplanar").
 * Source: interior of a leaf in the CC0 Poly Haven "Shrub 03" atlas, normalised so its average brightness is 1
 * (it changes the look, never the colour of the crop).
 */
import * as THREE from "three";

const SRC = "/planner/shrubs/shrub_03/textures/shrub_03_diff_1k.jpg";
const detail = { value: new THREE.DataTexture(new Uint8Array([128, 128, 128, 255]), 1, 1) as THREE.Texture };
detail.value.needsUpdate = true;
let started = false;

function load() {
  if (started || typeof document === "undefined") return;
  started = true;
  new THREE.ImageLoader().load(SRC, (img) => {
    // inside of the large leaf on the left of the atlas (only leaf tissue, no background)
    const S = 256, c = document.createElement("canvas"); c.width = c.height = S;
    const g = c.getContext("2d")!;
    g.drawImage(img, 95, 420, 170, 150, 0, 0, S, S);
    const d = g.getImageData(0, 0, S, S);
    let sum = 0;
    for (let i = 0; i < d.data.length; i += 4) sum += d.data[i] * 0.3 + d.data[i + 1] * 0.59 + d.data[i + 2] * 0.11;
    const mean = sum / (S * S);
    for (let i = 0; i < d.data.length; i += 4) {
      const l = d.data[i] * 0.3 + d.data[i + 1] * 0.59 + d.data[i + 2] * 0.11;
      const v = Math.max(0, Math.min(255, (l / mean) * 128));
      d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255;
    }
    // make the tile seamless: blend it with itself shifted by half (cheap and invisible at plant scale)
    g.putImageData(d, 0, 0);
    const c2 = document.createElement("canvas"); c2.width = c2.height = S;
    const g2 = c2.getContext("2d")!;
    g2.drawImage(c, 0, 0);
    g2.globalAlpha = 0.5;
    for (const [x, y] of [[S / 2, S / 2], [-S / 2, S / 2], [S / 2, -S / 2], [-S / 2, -S / 2]]) g2.drawImage(c, x, y);
    const t = new THREE.CanvasTexture(c2);
    t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.NoColorSpace; t.anisotropy = 4;
    detail.value = t;
  });
}

/** Adds the triplanar leaf detail to a material (keeps any shader patch it already has, e.g. wind). */
export function withLeafDetail<T extends THREE.Material>(m: T, scale = 5, strength = 0.85): T {
  load();
  const prev = m.onBeforeCompile;
  m.onBeforeCompile = (shader, renderer) => {
    prev?.call(m, shader, renderer);
    shader.uniforms.uLeafDetail = detail;
    shader.vertexShader = "varying vec3 vLdPos;\nvarying vec3 vLdNor;\n" + shader.vertexShader.replace("#include <begin_vertex>",
      "#include <begin_vertex>\n  vLdPos = position; vLdNor = normal;");
    shader.fragmentShader = "uniform sampler2D uLeafDetail;\nvarying vec3 vLdPos;\nvarying vec3 vLdNor;\n" + shader.fragmentShader.replace("#include <color_fragment>", `#include <color_fragment>
      {
        vec3 w = pow(abs(normalize(vLdNor)), vec3(4.0)); w /= (w.x + w.y + w.z + 1e-4);
        vec3 p = vLdPos * ${scale.toFixed(2)};
        float d = texture2D(uLeafDetail, p.yz).r * w.x + texture2D(uLeafDetail, p.xz).r * w.y + texture2D(uLeafDetail, p.xy).r * w.z;
        diffuseColor.rgb *= mix(1.0, d * 2.0, ${strength.toFixed(2)});
      }`);
  };
  const key = m.customProgramCacheKey.bind(m);
  m.customProgramCacheKey = () => `${key()}-leafdetail-${scale}-${strength}`;
  return m;
}
