/**
 * Crops drawn as impostors: plants modelled in Blender (tools/blender/make_crops.py: leaves with midrib and veins,
 * translucency, glossy fruits, tomato stakes) and baked like the trees (engine/impostor.ts). One quad per plant, so
 * a field can show tens of thousands of plants with a much smaller size exaggeration than the 3D models.
 * Fruiting crops have a variant without fruit, used before maturity (fruit is shown only at the mature stage).
 */
import { IMPOSTORS } from "./engine/impostor";
import { Stage } from "./cropLibrary";

type Tint = [number, number, number];
/** Baked plant: impostor names, width / height of the modelled plant (for spacing) and a display tint (the baked colour
 *  is albedo x ambient occlusion, darker than the sunlit look of the scene). */
const CROP_IMP: Record<string, { name: string; green?: string; wh: number; tint: Tint }> = {
  lettuce: { name: "crop_lettuce", wh: 1.65, tint: [1.05, 1.12, 0.95] },
  cabbage: { name: "crop_cabbage", wh: 1.52, tint: [0.8, 0.95, 0.84] },
  tomato: { name: "crop_tomato", green: "crop_tomato_green", wh: 0.64, tint: [1.4, 1.42, 1.1] },
  eggplant: { name: "crop_eggplant", green: "crop_eggplant_green", wh: 0.72, tint: [1.2, 1.25, 1.15] },
};

export function cropImpostor(crop: string, stage: Stage): { name: string; wh: number; tint: Tint } | null {
  const e = CROP_IMP[crop];
  if (!e || stage === "none" || stage === "harvested") return null;
  const name = stage === "mature" || !e.green ? e.name : e.green;
  return IMPOSTORS[name] ? { name, wh: e.wh, tint: e.tint } : null;
}

export const hasCropImpostor = (crop: string) => !!CROP_IMP[crop] && !!IMPOSTORS[CROP_IMP[crop].name];
export const impostorWidth = (crop: string) => CROP_IMP[crop]?.wh ?? 1;
