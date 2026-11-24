/**
 * Small pictures of a crop for the planner panels (year cards, properties): the same photographic canopy tile the 3D
 * beds use (canopy.ts), seen from above, so the picture always matches what the scene shows for that crop.
 */
import { useEffect, useState } from "react";
import { canopyTexture } from "./canopy";
import { Stage } from "./cropLibrary";

const LEAF = ["/planner/foliage/tree_small_02_leaves_diff_1k.jpg", "/planner/foliage/tree_small_02_leaves_alpha_1k.jpg"];
let imgs: Promise<[HTMLImageElement, HTMLImageElement]> | null = null;
const load = (src: string) => new Promise<HTMLImageElement>((ok, ko) => { const i = new Image(); i.onload = () => ok(i); i.onerror = ko; i.src = src; });
const urls = new Map<string, string>();

function compose(crop: string, group: string, stage: Stage, diff: HTMLImageElement, alpha: HTMLImageElement) {
  const key = `${crop}|${group}|${stage}`;
  const hit = urls.get(key); if (hit) return hit;
  const layers = [0, 1, 2].map((l) => canopyTexture(crop, group, stage, l === 0 ? 0.9 : l === 1 ? 0.72 : 0.46, l, diff, alpha).image as HTMLCanvasElement);
  const c = document.createElement("canvas"); c.width = layers[0].width; c.height = layers[0].height;
  const g = c.getContext("2d")!;
  g.fillStyle = "#6b5236"; g.fillRect(0, 0, c.width, c.height);
  layers.forEach((l) => g.drawImage(l, 0, 0));
  const url = c.toDataURL("image/jpeg", 0.86);
  urls.set(key, url);
  return url;
}

/** Data URLs of crop pictures keyed by `crop|group|stage`; empty until the leaf photos are loaded. */
export function useCropThumbs(list: { crop: string; group: string; stage?: Stage }[]): Record<string, string> {
  const sig = list.map((x) => `${x.crop}|${x.group}|${x.stage ?? "mature"}`).sort().join(",");
  const [out, setOut] = useState<Record<string, string>>({});
  useEffect(() => {
    let live = true;
    imgs ??= Promise.all([load(LEAF[0]), load(LEAF[1])]);
    imgs.then(([d, a]) => {
      if (!live) return;
      const res: Record<string, string> = {};
      for (const k of sig.split(",").filter(Boolean)) { const [c, g, s] = k.split("|"); res[`${c}|${g}`] = compose(c, g, s as Stage, d, a); }
      setOut(res);
    }).catch(() => { /* pictures are optional */ });
    return () => { live = false; };
  }, [sig]);
  return out;
}
