/**
 * Final colour grade of the planner (after tone mapping): warm white balance, vibrance (lifts the less saturated colours
 * more, so greens and soil get richer without clipping the red fruit), and a gentle lift/gain/gamma curve.
 */
import { BlendFunction, Effect } from "postprocessing";
import { Uniform } from "three";

const FRAG = /* glsl */ `
uniform float warmth;
uniform float vibrance;
uniform float lift;
uniform float gain;
uniform float gamma;
void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  vec3 c = inputColor.rgb;
  c *= vec3(1.0 + warmth, 1.0 + warmth * 0.3, 1.0 - warmth);
  float mx = max(c.r, max(c.g, c.b)), mn = min(c.r, min(c.g, c.b));
  float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
  c = mix(vec3(l), c, 1.0 + vibrance * (1.0 - clamp(mx - mn, 0.0, 1.0)));
  c = c * gain + lift * (1.0 - c);
  c = pow(max(c, 0.0), vec3(1.0 / gamma));
  outputColor = vec4(clamp(c, 0.0, 1.0), inputColor.a);
}`;

export class GradeEffect extends Effect {
  constructor({ warmth = 0.035, vibrance = 0.45, lift = 0.015, gain = 1.02, gamma = 1.04 } = {}) {
    super("GradeEffect", FRAG, {
      blendFunction: BlendFunction.NORMAL,
      uniforms: new Map<string, Uniform>([["warmth", new Uniform(warmth)], ["vibrance", new Uniform(vibrance)],
        ["lift", new Uniform(lift)], ["gain", new Uniform(gain)], ["gamma", new Uniform(gamma)]]),
    });
  }
}
