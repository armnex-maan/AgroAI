/** Farm data -> 3D world layout (metres, X east, Z south). Pure functions, no three.js. */
import { clipToRect, cropsFor, XY } from "../plotGeo";
import { Assignment, FarmData, isGrowing, PlanResult, Plot, Reason, Section } from "../types";

export interface BedCrop {
  crop: string; name: string; family: string; verdict?: "ok" | "care" | "no"; reasons?: Reason[];
  manual?: boolean; proposed?: boolean; wholePlot?: boolean;
}
export interface BedView {
  key: string; plotId: string; sectionId: string | null; name: string; kind: Section["kind"];
  local: XY[];            // polygon in plot-local metres (x east, y south)
  rect: { x: number; y: number; w: number; h: number };
  area: number; crop?: BedCrop;
  rowDir?: "x" | "y" | null; rowSpacing?: number | null; plantSpacing?: number | null;   // declared by the farmer
}
export interface PlotView {
  plot: Plot; offset: [number, number]; traced: boolean; outline: XY[]; beds: BedView[]; others: BedView[];
  irrigation: string | null;
}
export type Edits = Record<string, Record<number, Assignment[]>>; // plotId -> year -> assignments

const area2 = (pts: XY[]) => Math.abs(pts.reduce((a, p, i) => a + p[0] * pts[(i + 1) % pts.length][1] - pts[(i + 1) % pts.length][0] * p[1], 0)) / 2;

export function plotOutline(p: Plot): XY[] {
  const W = p.width_m ?? 10, L = p.length_m ?? 10;
  return p.shape === "irregular" && p.outline?.length ? (p.outline as XY[]) : [[0, 0], [W, 0], [W, L], [0, L]];
}

/** Assignments shown for a plot in a year: history (today), edits, saved plan, or AgroAI's proposal. */
export function yearAssignments(p: Plot, year: number, season: number, proposal: PlanResult | undefined, edits: Edits): (Assignment & { proposed?: boolean })[] {
  if (year <= season) {
    return cropsFor(p, year, season).map((c) => ({ section_id: c.section_id, section: "", crop: c.crop, name: c.name, family: c.family,
      area_m2: c.area, verdict: "ok" as const }));
  }
  const e = edits[p.id]?.[year];
  if (e) return e;
  const saved = p.plans.find((x) => x.year === year);
  if (saved) return saved.assignments;
  return (proposal?.years.find((y) => y.year === year)?.assignments ?? []).map((a) => ({ ...a, proposed: true }));
}

export function buildFarm(farm: FarmData, year: number, proposals: Record<string, PlanResult | undefined>, edits: Edits): PlotView[] {
  const ref = farm.plots.find((p) => p.polygon?.origin && p.polygon?.k)?.polygon;
  let nextX = 0;
  const traced = farm.plots.filter((p) => p.polygon?.origin && ref);
  const views: PlotView[] = [];
  for (const p of farm.plots) {
    const outline = plotOutline(p);
    let offset: [number, number];
    const o = p.polygon?.origin;
    if (o && ref?.origin && ref.k) offset = [(o[0] - ref.origin[0]) * ref.k[0], (ref.origin[1] - o[1]) * ref.k[1]];
    else offset = [0, 0];
    views.push({ plot: p, offset, traced: !!(o && ref), outline, beds: [], others: [], irrigation: p.profile?.irrigation ?? null });
  }
  // plots without a map boundary: in a row to the east of the traced ones
  const maxX = Math.max(0, ...views.filter((v) => v.traced).map((v) => v.offset[0] + (v.plot.width_m ?? 0)));
  nextX = traced.length ? maxX + 15 : 0;
  for (const v of views) if (!v.traced) { v.offset = [nextX, 0]; nextX += (v.plot.width_m ?? 10) + 15; }

  for (const v of views) {
    const p = v.plot;
    const ass = yearAssignments(p, year, farm.season_year, proposals[p.id], edits);
    const growing = p.sections.filter((s) => isGrowing(s.kind));
    const secs: Section[] = growing.length ? p.sections
      : [...p.sections, { id: undefined, name: "Intero appezzamento", kind: "bed", x: 0, y: 0, w: p.width_m ?? 10, h: p.length_m ?? 10 }];
    const loose = ass.filter((a) => !a.section_id || !secs.some((s) => s.id === a.section_id));
    let li = 0;
    for (const s of secs) {
      const local = clipToRect(v.outline, s.x, s.y, s.x + s.w, s.y + s.h);
      if (local.length < 3) continue;
      const bed: BedView = { key: `${p.id}:${s.id ?? "all"}`, plotId: p.id, sectionId: s.id ?? null, name: s.name, kind: s.kind,
        local, rect: { x: s.x, y: s.y, w: s.w, h: s.h }, area: area2(local),
        rowDir: s.row_dir ?? null, rowSpacing: s.row_spacing_m ?? null, plantSpacing: s.plant_spacing_m ?? null };
      if (isGrowing(s.kind)) {
        let a = ass.find((x) => s.id && x.section_id === s.id);
        let whole = false;
        if (!a && loose.length) { a = loose[li % loose.length]; li++; whole = true; } // recorded for the whole plot
        if (a && a.crop !== "cover") {
          bed.crop = { crop: a.crop, name: a.name, family: a.family, verdict: a.verdict, reasons: a.reasons, manual: (a as any).manual,
            proposed: (a as any).proposed, wholePlot: whole && !!growing.length };
        }
        v.beds.push(bed);
      } else v.others.push(bed);
    }
  }
  return views;
}

/** Planting positions in rows along the long side of the bed, inside its real polygon (plot-local metres). */
export function rows(bed: BedView, inRow: number, between: number, max: number): XY[] {
  const { x, y, w, h } = bed.rect;
  const alongY = rowsAlongY(bed);
  const inside = (pt: XY) => {
    let c = false; const poly = bed.local;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const [xi, yi] = poly[i], [xj, yj] = poly[j];
      if ((yi > pt[1]) !== (yj > pt[1]) && pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi) + xi) c = !c;
    }
    return c;
  };
  const out: XY[] = [];
  const across = alongY ? w : h, along = alongY ? h : w;
  const nRows = Math.max(1, Math.floor(across / between));
  const pad = (across - (nRows - 1) * between) / 2;
  for (let r = 0; r < nRows && out.length < max; r++) {
    const c = pad + r * between;
    for (let t = inRow / 2; t < along && out.length < max; t += inRow) {
      const pt: XY = alongY ? [x + c, y + t] : [x + t, y + c];
      if (inside(pt)) out.push(pt);
    }
  }
  return out;
}

/** Rows run along Y (north-south) or X (east-west): as declared, otherwise along the long side. */
export const rowsAlongY = (bed: BedView) => (bed.rowDir ? bed.rowDir === "y" : bed.rect.h >= bed.rect.w);
