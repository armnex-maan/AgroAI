import { PlanResult, Plot } from "./types";

export type LL = [number, number]; // [lon, lat]

export interface YearCrop { section_id: string | null; crop: string; name: string; family: string; area: number; proposed?: boolean }

/** What grows on a plot in a year: recorded history up to this season, saved plans after it. */
export function cropsFor(p: Plot, year: number, season: number, proposal?: PlanResult): YearCrop[] {
  const secArea = (id: string | null) => p.sections.find((s) => s.id === id)?.area_m2 ?? null;
  if (year <= season) {
    const rows = p.history.filter((h) => h.year === year && h.status === "crop");
    return rows.map((h) => ({ section_id: h.section_id, crop: h.crop, name: h.name, family: h.family ?? "",
      area: h.area_m2 ?? secArea(h.section_id) ?? (p.area_m2 ?? 0) / rows.length }));
  }
  const plan = p.plans.find((x) => x.year === year);
  const proposed = !plan ? proposal?.years.find((y) => y.year === year) : undefined;  // not saved yet: AgroAI's proposal
  return (plan?.assignments ?? proposed?.assignments ?? []).filter((a) => a.crop !== "cover").map((a) => ({ section_id: a.section_id,
    crop: a.crop, name: a.name, family: a.family, area: a.area_m2 ?? secArea(a.section_id) ?? 0, proposed: !!proposed }));
}

export const ringOf = (p: Plot): LL[] | null => (p.polygon?.coordinates?.[0]?.slice(0, -1) as LL[] | undefined) ?? null;
export type XY = [number, number];
/** Sutherland-Hodgman with the (convex) bed rectangle as window: the outline may be any simple shape. */
export function clipToRect(poly: XY[], x0: number, y0: number, x1: number, y1: number): XY[] {
  let out = poly;
  const edges: [0 | 1, number, boolean][] = [[0, x0, true], [0, x1, false], [1, y0, true], [1, y1, false]];
  for (const [ax, lim, ge] of edges) {
    const inp = out;
    out = [];
    const ins = (p: XY) => (ge ? p[ax] >= lim : p[ax] <= lim);
    inp.forEach((cur, j) => {
      const prev = inp[(j + inp.length - 1) % inp.length];
      if (ins(cur) !== ins(prev)) {
        const t = (lim - prev[ax]) / (cur[ax] - prev[ax]);
        out.push([prev[0] + (cur[0] - prev[0]) * t, prev[1] + (cur[1] - prev[1]) * t]);
      }
      if (ins(cur)) out.push(cur);
    });
    if (!out.length) break;
  }
  return out;
}
