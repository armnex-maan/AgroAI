import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Loader, PerformanceMonitor } from "@react-three/drei";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../../api/client";
import { Icon } from "../../Icon";
import FarmMap from "../FarmMap";
import { Assignment, cropColor, FarmData, fmtArea, isGrowing, Kind, KIND_LABEL, LEVEL, PlanResult, Reason, Section, shortName } from "../types";
import { Rect } from "./Editor";
import { BedView, buildFarm, Edits, PlotView, yearAssignments } from "./layout";
import { FarmScene, plantFactor, SceneApi } from "./Scene";
import { Calendar, STAGE_LABEL, stageFor } from "./cropLibrary";
import { FeatureProps, FeaturesData, Palette } from "./FeaturePanel";
import { FarmRef, Feature, featurePoints, toLonLat } from "./Structures";
import { KIND_ICON } from "./FeaturePanel";
const CropCatalog = lazy(() => import("./CropCatalog"));
const AiGenerator = lazy(() => import("./AiGenerator"));
import type { AiVariant } from "./AiGenerator";
import { IrrigationPanel } from "./IrrigationPanel";
import { detectQuality, loadQuality, lower, PROFILES, QualityChoice, QualityLevel, storeQuality } from "./engine/quality";

type Mode = "3d" | "2d" | "sat";
const VERDICT = { ok: ["Ottimale", "ok"], care: ["Con attenzione", "warn"], no: ["Sconsigliata", "bad"] } as const;
const MONTHS = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"];
const IRRIGATION: Record<string, string> = { drip: "A goccia", sprinkler: "A pioggia", furrow: "A scorrimento / solchi", manual: "A mano", none: "Nessuna" };

interface Judged { verdict: Assignment["verdict"]; reasons: Reason[]; name: string; family: string }
/** One step of the undo history: crop changes and section drawings not saved yet. */
interface Snap { edits: Edits; layouts: Record<string, Section[]> }
const EMPTY: Snap = { edits: {}, layouts: {} };
const isTmp = (id?: string | null) => !!id && id.startsWith("tmp-");
const SECTION_KINDS: Kind[] = ["bed", "greenhouse", "path", "access", "water", "no_crop", "shade"];
export const SECTION_ICON: Record<string, string> = { bed: "grid", greenhouse: "home", path: "move", access: "pin", water: "drop", no_crop: "ban", shade: "leaf" };
const snap10 = (v: number) => Math.round(v * 10) / 10;

export default function VisualPlanner({ farm, onOpen, draw, onDraw, onDrawn }: {
  farm: FarmData; onOpen: (plotId: string, tab: "plan" | "editor" | "history") => void;
  draw: { plotId: string | null } | null; onDraw: (d: { plotId: string | null }) => void; onDrawn: () => void;
}) {
  const qc = useQueryClient();
  const season = farm.season_year;
  const years = useMemo(() => Array.from({ length: 5 }, (_, i) => season + i), [season]);
  const [year, setYear] = useState(season + 1);
  const [mode, setMode] = useState<Mode>(draw ? "sat" : "3d");
  const [selected, setSelected] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [hist, setHist] = useState<{ stack: Snap[]; i: number }>({ stack: [EMPTY], i: 0 });
  const [editOn, setEditOn] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [demo, setDemo] = useState<{ plotId: string; system: string } | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [qChoice, setQChoice] = useState<QualityChoice>(loadQuality);
  const [autoLevel, setAutoLevel] = useState<QualityLevel>(detectQuality);
  const [lowered, setLowered] = useState(false);
  const [terrainLabel, setTerrainLabel] = useState<string | null>(null);
  const [catalog, setCatalog] = useState(false);
  const [month, setMonth] = useState(0);   // 0 = full season: every crop at its mature stage
  const calQ = useQuery({ queryKey: ["rotation-calendar"], refetchInterval: false, staleTime: Infinity,
    queryFn: () => api.get<{ note: string; crops: Record<string, Calendar & { name: string }> }>("/api/v1/rotation/calendar") });
  const calendar = calQ.data?.crops ?? {};
  // farm elements (buildings, tanks, roads, orchards...): stored in lon/lat, drawn in the farm frame
  const featQ = useQuery({ queryKey: ["rotation-features"], refetchInterval: false, staleTime: 60_000,
    queryFn: () => api.get<FeaturesData>("/api/v1/rotation/features") });
  const features = featQ.data?.features ?? [];
  const farmRef = useMemo<FarmRef | null>(() => {
    const p = farm.plots.find((x) => x.polygon?.origin && x.polygon?.k);
    return p ? { origin: p.polygon!.origin as [number, number], k: p.polygon!.k as [number, number] } : null;
  }, [farm.plots]);
  const [palette, setPalette] = useState(false);
  type Placing = { kind: string; geom: "Point" | "LineString" | "Polygon" | "Rect"; pts: [number, number][] } | null;
  const [placing, setPlacingState] = useState<Placing>(null);
  // taps can arrive faster than the scene re-renders: keep the latest value in a ref too
  const placingRef = useRef<Placing>(null);
  const setPlacing = (v: Placing) => { placingRef.current = v; setPlacingState(v); };
  const create = useMutation({
    mutationFn: (v: { kind: string; geom: string; pts: [number, number][] }) => {
      const spec = featQ.data!.kinds[v.kind];
      const n = features.filter((f) => f.kind === v.kind).length + 1;
      const ll = v.pts.map((p) => toLonLat(farmRef!, p));
      const geometry = v.geom === "Point" ? { type: "Point", coordinates: ll[0] } : v.geom === "LineString" ? { type: "LineString", coordinates: ll }
        : { type: "Polygon", coordinates: [[...ll, ll[0]]] };
      const DEFAULT: Record<string, Record<string, unknown>> = { building: { type: "casale" }, orchard: { species: "apple" }, vineyard: { species: "grape_wine" },
        greenhouse: { type: "tunnel" }, net: { type: "antigrandine" }, fence: { type: "rete_metallica" }, equipment: { type: "trattore" } };
      const props = DEFAULT[v.kind] ?? {};
      return api.post<{ id: string }>("/api/v1/rotation/features", { kind: v.kind, name: `${spec.label} ${n}`, geometry, props });
    },
    onSuccess: (f) => { setPlacing(null); qc.invalidateQueries({ queryKey: ["rotation-features"] }); setSelected(`feature:${f.id}`);
      setMsg("Elemento aggiunto: completa i dati nel pannello a destra."); },
  });
  const onGround = (x: number, z: number) => {
    const placing = placingRef.current;
    if (!placing) return;
    const pts = [...placing.pts, [x, z] as [number, number]];
    if (placing.geom === "Rect") {
      if (pts.length === 1) {
        if (!plotAt(x, z)) { setMsg("Tocca dentro un appezzamento: le parti stanno sempre in un appezzamento."); return; }
        setPlacing({ ...placing, pts });
      } else finishRect(placing.kind.slice(8) as Kind, pts[0], pts[1]);
      return;
    }
    if (placing.geom === "Point") create.mutate({ ...placing as any, pts });
    else setPlacing({ ...placing, pts });
  };
  const startPlacing = (kind: string) => {
    setPalette(false);
    if (!farmRef) { setMsg("Per inserire elementi serve almeno un appezzamento tracciato sulla mappa: è il riferimento geografico."); return; }
    setSelected(null);
    setPlacing({ kind, geom: featQ.data!.kinds[kind].geom, pts: [] });
  };
  const focusFeature = (f: Feature) => {
    if (!farmRef) return;
    const pts = featurePoints(f, farmRef);
    const xs = pts.map((p) => p[0]), zs = pts.map((p) => p[1]);
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cz = (Math.min(...zs) + Math.max(...zs)) / 2;
    scene.current?.focus(cx, cz, Math.max(25, Math.max(...xs) - Math.min(...xs), Math.max(...zs) - Math.min(...zs)) * 1.1);
  };
  const selFeature = selected?.startsWith("feature:") ? features.find((f) => `feature:${f.id}` === selected) ?? null : null;
  const quality = PROFILES[qChoice === "auto" ? autoLevel : qChoice];
  const { edits, layouts } = hist.stack[hist.i];
  const scene = useRef<SceneApi>(null);
  const compass = useRef<HTMLDivElement>(null);
  const zoomLabel = useRef<HTMLSpanElement>(null);
  const wrap = useRef<HTMLDivElement>(null);

  const proposalQs = useQueries({ queries: farm.plots.map((p) => ({
    queryKey: ["plan-proposal", p.id, p.sections.map((x) => x.id).join(), p.history.length, JSON.stringify(p.profile?.goals ?? {})],
    queryFn: () => api.post<PlanResult>(`/api/v1/rotation/plots/${p.id}/plan`, p.profile?.goals ?? {}),
    staleTime: 5 * 60_000, refetchInterval: false,
  })) });
  const propStamp = proposalQs.map((q) => q.dataUpdatedAt).join();
  const proposals = useMemo(() => Object.fromEntries(farm.plots.map((p, i) => [p.id, proposalQs[i]?.data])) as Record<string, PlanResult | undefined>,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [farm, propStamp]);
  const byKey = useMemo(() => Object.fromEntries(farm.crops.map((c) => [c.key, c])), [farm.crops]);
  // drawings changed in the editor and not saved yet replace the saved sections of their plot
  const farmV = useMemo<FarmData>(() => (Object.keys(layouts).length
    ? { ...farm, plots: farm.plots.map((p) => (layouts[p.id] ? { ...p, sections: layouts[p.id] } : p)) } : farm), [farm, layouts]);
  const views = useMemo(() => buildFarm(farmV, year, proposals, edits), [farmV, year, proposals, edits]);
  const exag = useMemo(() => plantFactor(views, byKey, quality.plants), [views, byKey, quality.plants]);
  const perYear = useMemo(() => years.map((y) => ({ y, views: y === year ? views : buildFarm(farmV, y, proposals, edits) })), [years, year, views, farmV, proposals, edits]);

  const sel = useMemo(() => {
    for (const v of views) for (const b of [...v.beds, ...v.others]) if (b.key === selected) return { bed: b, view: v };
    return null;
  }, [views, selected]);

  const pushSnap = (x: Partial<Snap>) => setHist((h) => ({ stack: [...h.stack.slice(0, h.i + 1), { ...h.stack[h.i], ...x }], i: h.i + 1 }));
  const pushEdits = (e: Edits) => pushSnap({ edits: e });

  // ---- sections (parts of a plot): drawn and changed in the scene, saved with «Salva progetto» ----
  const sectionsOf = (pid: string): Section[] => layouts[pid] ?? farm.plots.find((p) => p.id === pid)?.sections ?? [];
  const setSections = (pid: string, secs: Section[]) => pushSnap({ layouts: { ...layouts, [pid]: secs } });
  const updateSection = (pid: string, sid: string, patch: Partial<Section>) => {
    setSections(pid, sectionsOf(pid).map((x) => (x.id === sid ? { ...x, ...patch, area_m2: undefined } : x)));
    setMsg("Parte modificata. Le modifiche restano in prova finché non premi «Salva progetto».");
  };
  const removeSection = (pid: string, sid: string) => {
    setSections(pid, sectionsOf(pid).filter((x) => x.id !== sid)); setSelected(null);
    setMsg("Parte eliminata (puoi annullare). Storico e piani di quella parte passeranno all'intero appezzamento quando salvi.");
  };
  const plotAt = (x: number, z: number) => views.find((v) => {
    const lx = x - v.offset[0], ly = z - v.offset[1];
    return v.plot.width_m && v.plot.length_m && lx >= 0 && ly >= 0 && lx <= v.plot.width_m && ly <= v.plot.length_m;
  });
  const finishRect = (kind: Kind, a: [number, number], b: [number, number]) => {
    const v = plotAt(a[0], a[1]);
    setPlacing(null);
    if (!v) return;
    const W = v.plot.width_m!, L = v.plot.length_m!;
    const cl = (t: number, m: number) => Math.min(Math.max(0, t), m);
    const x0 = snap10(cl(Math.min(a[0], b[0]) - v.offset[0], W)), x1 = snap10(cl(Math.max(a[0], b[0]) - v.offset[0], W));
    const y0 = snap10(cl(Math.min(a[1], b[1]) - v.offset[1], L)), y1 = snap10(cl(Math.max(a[1], b[1]) - v.offset[1], L));
    if (x1 - x0 < 0.3 || y1 - y0 < 0.3) { setMsg("Parte troppo piccola: tocca due angoli opposti più distanti."); return; }
    const secs = sectionsOf(v.plot.id);
    const n = secs.filter((x) => x.kind === kind).length + 1;
    const id = `tmp-${Math.random().toString(36).slice(2, 10)}`;
    setSections(v.plot.id, [...secs, { id, name: kind === "bed" ? `Aiuola ${n}` : `${KIND_LABEL[kind]} ${n}`, kind, x: x0, y: y0, w: snap10(x1 - x0), h: snap10(y1 - y0) }]);
    setSelected(`${v.plot.id}:${id}`); setEditOn(true);
    setMsg(`${KIND_LABEL[kind]} aggiunta in «${v.plot.name}». Trascina le maniglie per sistemarla, poi «Salva progetto».`);
  };
  const startSection = (kind: Kind) => {
    setPalette(false); setSelected(null);
    if (!views.some((v) => v.plot.width_m && v.plot.length_m)) { setMsg("Prima crea un appezzamento con le sue misure o tracciato sulla mappa."); return; }
    if (mode === "sat") setMode("3d");
    setPlacing({ kind: `section:${kind}`, geom: "Rect", pts: [] });
  };
  // ---- farm elements: moving them saves at once (they are single records) ----
  const moveFeature = useMutation({
    mutationFn: ({ id, pts }: { id: string; pts: [number, number][] }) => {
      const f = features.find((x) => x.id === id)!;
      const ll = pts.map((q) => toLonLat(farmRef!, q));
      const geometry = f.geometry.type === "Point" ? { type: "Point", coordinates: ll[0] } : f.geometry.type === "LineString"
        ? { type: "LineString", coordinates: ll } : { type: "Polygon", coordinates: [[...ll, ll[0]]] };
      return api.put(`/api/v1/rotation/features/${id}`, { geometry });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["rotation-features"] }); setMsg("Elemento spostato e salvato."); },
    onError: (e) => setMsg((e as Error).message),
  });

  // ---- manual change: check the chosen year, then re-check the later years of the same bed ----
  const assignCrop = async (base: Edits, view: PlotView, bed: BedView, crop: string | null): Promise<Edits> => {
      const p = view.plot;
      const next: Edits = { ...base, [p.id]: { ...(base[p.id] ?? {}) } };
      const planned: Record<string, string> = {};
      for (const y of years.filter((y) => y > season)) {
        let ass = yearAssignments(p, y, season, proposals[p.id], next).map((a) => ({ ...a }));
        let mine = ass.find((a) => (a.section_id ?? null) === bed.sectionId);
        if (y === year && crop === null && mine) { ass = ass.filter((a) => a !== mine); mine = undefined; }   // crop moved away
        if (y >= year) {
          const c = y === year ? crop : mine?.crop;
          if (c && c !== "cover") {
            const j = await api.post<Judged>(`/api/v1/rotation/plots/${p.id}/check`, { section_id: isTmp(bed.sectionId) ? null : bed.sectionId, crop: c, year: y, planned,
              integrated: p.profile?.goals?.integrated ?? null });
            const upd = { section_id: bed.sectionId, section: bed.name, crop: c, name: j.name, family: j.family, area_m2: Math.round(bed.area),
              verdict: j.verdict, reasons: j.reasons, manual: y === year ? true : (mine as any)?.manual } as Assignment;
            if (mine) Object.assign(mine, upd, { proposed: false }); else { mine = upd; ass.push(upd); }
          }
          next[p.id][y] = ass.map(({ proposed, ...a }: any) => a);
        }
        if (mine?.crop) planned[String(y)] = mine.crop;
      }
      return next;
  };
  const change = useMutation({
    mutationFn: async ({ view, bed, crop, other }: { view: PlotView; bed: BedView; crop: string; other?: { bed: BedView; crop: string | null } }) => {
      let next = await assignCrop(edits, view, bed, crop);
      if (other) next = await assignCrop(next, view, other.bed, other.crop);
      return next;
    },
    onSuccess: (e, v) => { pushEdits(e); setMsg(v.other ? "Colture spostate e controllate con le regole. Ricorda di salvare." : "Coltura cambiata e controllata con le regole. Ricorda di salvare."); },
  });

  // ---- save the 2027-2030 plan of every plot (edits, saved plans or proposals) ----
  const save = useMutation({
    mutationFn: async () => {
      // one request, one transaction: drawings and plans are written together or not at all
      const body: { layouts: Record<string, unknown>; plans: Record<string, Record<number, Assignment[]>>; goals: Record<string, unknown> } = { layouts: {}, plans: {}, goals: {} };
      let drawn = 0, n = 0;
      for (const [pid, secs] of Object.entries(layouts)) {
        const p = farm.plots.find((x) => x.id === pid);
        if (!p || !p.width_m || !p.length_m) continue;
        body.layouts[pid] = { width_m: p.width_m, length_m: p.length_m, shape: p.shape, outline: p.shape === "irregular" ? p.outline : null,
          orientation_deg: p.orientation_deg ?? 0, exposure: p.exposure, sections: secs.map(({ area_m2, rows, ...x }) => x) };
        drawn++;
      }
      for (const p of farmV.plots) {
        const per: Record<number, Assignment[]> = {};
        for (const y of years.filter((y) => y > season)) {
          const a = yearAssignments(p, y, season, proposals[p.id], edits).map(({ proposed, ...x }: any) => x as Assignment);
          if (a.length) per[y] = a;
        }
        if (!Object.keys(per).length) continue;
        body.plans[p.id] = per; body.goals[p.id] = p.profile?.goals ?? null; n++;
      }
      if (!drawn && !n) return { n, drawn };
      await api.put("/api/v1/rotation/project", body);
      return { n, drawn };
    },
    onSuccess: ({ n, drawn }) => {
      setHist({ stack: [EMPTY], i: 0 });
      clearDraft();
      qc.invalidateQueries({ queryKey: ["planner-revisions"] });
      setSelected(null);
      qc.invalidateQueries({ queryKey: ["rotation-farm"] });
      const parts = [drawn ? `disegno di ${drawn} ${drawn === 1 ? "appezzamento" : "appezzamenti"}` : "",
        n ? `piano ${season + 1}–${season + 4} di ${n} ${n === 1 ? "appezzamento" : "appezzamenti"}` : ""].filter(Boolean);
      setMsg(parts.length ? `Salvato: ${parts.join(" e ")}.` : "Niente da salvare: nessun appezzamento ha colture pianificate.");
    },
  });

  // ---- AI layout: split undivided plots, then the proposals refresh ----
  const generate = useMutation({
    mutationFn: async () => {
      const todo = farm.plots.filter((p) => !p.sections.some((s) => isGrowing(s.kind)) && p.width_m && p.length_m);
      for (const p of todo) await api.post(`/api/v1/rotation/plots/${p.id}/auto-layout`, {});
      return todo.length;
    },
    onSuccess: (n) => {
      qc.invalidateQueries({ queryKey: ["rotation-farm"] });
      setYear(season + 1);
      setMsg(n ? `Ho diviso ${n} ${n === 1 ? "appezzamento" : "appezzamenti"} in parti uguali: la proposta ${season + 1}–${season + 4} è sulla mappa. Controllala e salvala.`
        : "Proposta aggiornata: tutti gli appezzamenti erano già divisi. Controlla e salva.");
    },
  });

  // ---- saved versions (server) ----
  const revQ = useQuery({ queryKey: ["planner-revisions"], refetchInterval: false, staleTime: 30_000,
    queryFn: () => api.get<{ revisions: Revision[]; max: number }>("/api/v1/rotation/project/revisions") });
  const restore = useMutation({
    mutationFn: (id: string) => api.post<{ skipped_plots: number }>(`/api/v1/rotation/project/revisions/${id}/restore`, {}),
    onSuccess: (r) => {
      setHist({ stack: [EMPTY], i: 0 }); clearDraft(); setSelected(null);
      qc.invalidateQueries({ queryKey: ["rotation-farm"] }); qc.invalidateQueries({ queryKey: ["planner-revisions"] });
      setMsg(`Versione ripristinata${r.skipped_plots ? ` (${r.skipped_plots} appezzamenti eliminati nel frattempo non possono tornare)` : ""}. Lo storico delle colture non cambia.`);
    },
    onError: (e) => setMsg((e as Error).message),
  });
  // ---- unsaved changes survive a refresh: kept in this browser only, until saved or discarded ----
  const DRAFT_KEY = `agroai.planner.draft.${farm.id}`;
  const clearDraft = () => { try { localStorage.removeItem(DRAFT_KEY); } catch { /* storage not available */ } };
  const [draft, setDraft] = useState<{ at: string; snap: Snap } | null>(() => {
    try { const d = JSON.parse(localStorage.getItem(DRAFT_KEY) ?? "null"); return d?.snap ? d : null; } catch { return null; }
  });
  const dirty = hist.i > 0 && (Object.keys(edits).length > 0 || Object.keys(layouts).length > 0);
  useEffect(() => {
    if (!dirty) return;
    try { localStorage.setItem(DRAFT_KEY, JSON.stringify({ at: new Date().toISOString(), snap: { edits, layouts } })); } catch { /* storage not available */ }
  }, [dirty, edits, layouts, DRAFT_KEY]);
  useEffect(() => { if (!dirty && hist.stack.length > 1) clearDraft(); }, [dirty, hist.stack.length]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  // ---- AI layout: a proposal goes in as an unsaved change (drawing + its plan), undoable, saved with the project ----
  const applyAi = (pid: string, v: AiVariant) => {
    const plan: Record<number, Assignment[]> = {};
    for (const y of v.plan) plan[y.year] = y.assignments.map((a) => ({ ...a, proposed: true } as Assignment));
    pushSnap({ layouts: { ...layouts, [pid]: v.sections.map(({ area_m2, ...x }) => x as Section) }, edits: { ...edits, [pid]: plan } });
    setSelected(null); setEditOn(false); setAiOpen(false); setYear(season + 1);
    if (mode === "sat") setMode("3d");
    const vw = views.find((x) => x.plot.id === pid);
    if (vw?.plot.width_m && vw.plot.length_m) scene.current?.focus(vw.offset[0] + vw.plot.width_m / 2, vw.offset[1] + vw.plot.length_m / 2, Math.max(vw.plot.width_m, vw.plot.length_m) * 0.9);
    setMsg(`Proposta «${v.title}» in prova nel 3D: premi «Salva progetto» per tenerla o «Annulla» per tornare com'era.`);
  };

  const proposedCount = views.reduce((a, v) => a + v.beds.filter((b) => b.crop?.proposed).length, 0);
  const editedCount = Object.values(edits).reduce((a, y) => a + Object.keys(y).length, 0) + Object.keys(layouts).length;
  const fullscreen = () => { const el = wrap.current; if (!el) return; document.fullscreenElement ? document.exitFullscreen() : el.requestFullscreen?.(); };

  return (
    <div className="vp" ref={wrap}>
      <div className="vp-top">
        <label className="vp-year"><Icon name="calendar" size={16} />
          <select value={year} onChange={(e) => { setYear(+e.target.value); setSelected(null); }}>
            {years.map((y) => <option key={y} value={y}>Anno: {y}{y === season ? " (oggi)" : ""}</option>)}
          </select>
        </label>
        <div className="vp-modes">
          {(["3d", "2d", "sat"] as Mode[]).map((m) => (
            <button key={m} className={mode === m ? "on" : ""} onClick={() => setMode(m)}>
              <Icon name={m === "3d" ? "layers" : m === "2d" ? "grid" : "map"} size={15} />{m === "3d" ? "3D" : m === "2d" ? "2D" : "Satellite"}
            </button>
          ))}
        </div>
        <label className="vp-year" title="Fase di crescita dal calendario indicativo">
          <Icon name="sprout" size={15} />
          <select value={month} onChange={(e) => setMonth(+e.target.value)}>
            <option value={0}>Piena stagione</option>
            {MONTHS.map((m, i) => <option key={m} value={i + 1}>Mese: {m}</option>)}
          </select>
        </label>
        <label className="vp-year vp-quality" title="Qualità grafica">
          <Icon name="settings" size={15} />
          <select value={qChoice} onChange={(e) => { const v = e.target.value as QualityChoice; setQChoice(v); storeQuality(v); setLowered(false); }}>
            <option value="auto">Qualità: automatica ({PROFILES[autoLevel].label})</option>
            <option value="high">Qualità: alta</option>
            <option value="medium">Qualità: media</option>
            <option value="battery">Risparmio batteria</option>
          </select>
        </label>
        <span className="spacer" />
        <button className="btn vp-save" disabled={save.isPending} onClick={() => save.mutate()}>
          <Icon name="check" size={15} />{save.isPending ? "Salvo…" : "Salva progetto"}{editedCount + proposedCount > 0 && <span className="vp-dot" />}
        </button>
      </div>

      <div className="vp-body">
        <div className="vp-stage">
          {mode === "sat" ? (
            <FarmMap farm={farm} draw={draw} onDrawn={onDrawn} onOpen={(id) => onOpen(id, "plan")} />
          ) : (
            <>
              <Canvas key={quality.level} dpr={quality.dpr} shadows={quality.shadowMap > 0 ? "soft" : false} frameloop={quality.frameloop}
                      gl={{ antialias: true, powerPreference: quality.level === "battery" ? "low-power" : "high-performance" }}
                      onPointerMissed={() => setSelected(null)} className="vp-canvas">
                {qChoice === "auto" && autoLevel !== "battery" && (
                  <PerformanceMonitor flipflops={1} onDecline={() => { setAutoLevel((l) => lower(l)); setLowered(true); }} />
                )}
                <Suspense fallback={null}>
                  <FarmScene ref={scene} views={views} byKey={byKey} mode={mode} exag={exag} selected={selected} hovered={hovered}
                    quality={quality} onTerrainLabel={setTerrainLabel} month={month} calendar={calendar}
                    features={features} farmRef={farmRef} placing={placing ? { kind: placing.geom, pts: placing.pts } : null} onGround={onGround}
                    onSelect={setSelected} onHover={setHovered} compass={compass} zoomLabel={zoomLabel}
                    demo={mode === "3d" ? demo : null}
                    edit={{ on: editOn, onSection: (pid, sid, r: Rect) => updateSection(pid, sid, r), onFeature: (id, pts) => moveFeature.mutate({ id, pts }) }} />
                </Suspense>
              </Canvas>
              <Loader containerStyles={{ background: "rgba(233,239,230,.85)" }} barStyles={{ background: "#1f9d4f" }} dataInterpolation={(p) => `Carico il terreno ${p.toFixed(0)}%`} />
              <div className="vp-compass" title="Bussola: la lettera N indica il nord reale" aria-hidden>
                <div ref={compass} className="vp-dial">
                  <span className="vp-cardinal n">N</span><span className="vp-cardinal e">E</span>
                  <span className="vp-cardinal s">S</span><span className="vp-cardinal o">O</span>
                  <i className="vp-needle" />
                </div>
              </div>
              <div className="vp-tools">
                <button title="Seleziona e guarda" className={editOn ? "" : "on"} onClick={() => setEditOn(false)}><Icon name="hand" size={17} /></button>
                <button title="Modifica forme: sposta e ridimensiona parti ed elementi" className={editOn ? "on" : ""}
                  onClick={() => { setEditOn((v) => !v); if (!editOn) setMsg("Modifica: tocca una parte o un elemento, poi trascina la maniglia gialla per spostarlo e quelle bianche per cambiarne le misure."); }}>
                  <Icon name="move" size={17} /></button>
                <button title="Traccia un terreno sulla mappa" onClick={() => { setMode("sat"); onDraw({ plotId: null }); }}><Icon name="pen" size={17} /></button>
                <button title="Dividi e disegna le parti" disabled={!sel} onClick={() => sel && onOpen(sel.view.plot.id, "editor")}><Icon name="split" size={17} /></button>
                <button title="Storico dell'appezzamento" disabled={!sel} onClick={() => sel && onOpen(sel.view.plot.id, "history")}><Icon name="book" size={17} /></button>
                <button title="Aggiungi edificio, cisterna, strada, frutteto…" className={palette || placing ? "on" : ""} onClick={() => setPalette((v) => !v)}><Icon name="plus" size={17} /></button>
                <button title="Libreria colture 3D" onClick={() => setCatalog(true)}><Icon name="sprout" size={17} /></button>
                <button title="Schermo intero" onClick={fullscreen}><Icon name="compass" size={17} /></button>
              </div>
              {palette && featQ.data && <Palette kinds={featQ.data.kinds} onPick={startPlacing} onClose={() => setPalette(false)}
                sections={SECTION_KINDS.map((k) => ({ kind: k, label: KIND_LABEL[k], icon: SECTION_ICON[k] }))} onPickSection={(k) => startSection(k as Kind)} />}
              {placing && (
                <div className="vp-placing">
                  <b>{placing.geom === "Rect" ? `Nuova parte: ${KIND_LABEL[placing.kind.slice(8) as Kind]}` : featQ.data?.kinds[placing.kind].label}</b>
                  <span className="tiny">{placing.geom === "Rect" ? (placing.pts.length ? "Ora tocca l'angolo opposto." : "Tocca un angolo della parte, dentro un appezzamento.")
                    : placing.geom === "Point" ? "Tocca il terreno dove si trova." : placing.geom === "LineString"
                    ? "Tocca il terreno lungo il percorso, poi «Fine»." : "Tocca gli angoli dell'area, poi «Fine»."} {placing.pts.length ? `${placing.pts.length} punti` : ""}</span>
                  <div className="row" style={{ gap: 6 }}>
                    {placing.geom !== "Point" && placing.geom !== "Rect" && <button className="btn sm" disabled={placing.pts.length < (placing.geom === "Polygon" ? 3 : 2) || create.isPending}
                      onClick={() => create.mutate(placing)}><Icon name="check" size={13} />Fine</button>}
                    {placing.pts.length > 0 && <button className="btn ghost sm" onClick={() => setPlacing({ ...placing, pts: placing.pts.slice(0, -1) })}><Icon name="undo" size={13} />Togli</button>}
                    <button className="btn ghost sm" onClick={() => setPlacing(null)}>Annulla</button>
                  </div>
                  {create.isError && <span className="tiny" style={{ color: "var(--danger)" }}>{(create.error as Error).message}</span>}
                </div>
              )}
              <div className="vp-zoom">
                <button title="Annulla" disabled={hist.i === 0} onClick={() => { setHist((h) => ({ ...h, i: h.i - 1 })); setMsg(null); }}><Icon name="undo" size={15} /></button>
                <button title="Ripeti" disabled={hist.i >= hist.stack.length - 1} onClick={() => setHist((h) => ({ ...h, i: h.i + 1 }))}><Icon name="undo" size={15} className="flip" /></button>
                <span className="vp-sep" />
                <button title="Allontana" onClick={() => scene.current?.zoomBy(0.8)}><Icon name="minus" size={15} /></button>
                <span ref={zoomLabel} className="vp-pct">100%</span>
                <button title="Avvicina" onClick={() => scene.current?.zoomBy(1.25)}><Icon name="plus" size={15} /></button>
                <button title="Vista iniziale" onClick={() => scene.current?.reset()}><Icon name="locate" size={15} /></button>
              </div>
              <div className="vp-notes">
                {exag > 1 && mode === "3d" && <span>Piante ingrandite ×{exag} per vederle a questa distanza</span>}
                {proposedCount > 0 && <span className="prop">Proposta di AgroAI non salvata</span>}
                {editedCount > 0 && <span className="prop">Modifiche non salvate: premi «Salva progetto»</span>}
                {year === season && <span>Oggi: colture registrate nello storico</span>}
                {lowered && <span>Qualità ridotta automaticamente per fluidità</span>}
                {terrainLabel && mode === "3d" && <span>{terrainLabel}</span>}
                {month > 0 && <span>{MONTHS[month - 1]}: fasi dal calendario indicativo (Centro-Nord)</span>}
                {editOn && <span className="prop">Modifica forme attiva</span>}
                {demo && mode === "3d" && <span>Dimostrazione irrigazione {demo.system === "drip" ? "a goccia" : demo.system === "sprinkler" ? "a pioggia" : "a solchi"}: animazione per capire il sistema, non un calcolo idraulico</span>}
              </div>
            </>
          )}
        </div>

        <aside className="vp-panel">
          {aiOpen ? <Suspense fallback={<div className="tiny muted">Carico il generatore…</div>}>
              <AiGenerator farm={farm} onClose={() => setAiOpen(false)} onApply={applyAi} /></Suspense>
            : selFeature && featQ.data ? <FeatureProps feature={selFeature} data={featQ.data} onClose={() => setSelected(null)} onFocus={() => focusFeature(selFeature)} />
            : sel ? <Props sel={sel} year={year} season={season} byKey={byKey} farm={farm} views={perYear} month={month} calendar={calendar}
                         busy={change.isPending} onChange={(crop) => change.mutate({ view: sel.view, bed: sel.bed, crop })}
                         onMove={(target) => sel.bed.crop && change.mutate({ view: sel.view, bed: target, crop: sel.bed.crop.crop, other: { bed: sel.bed, crop: target.crop?.crop ?? null } })}
                         section={sel.bed.sectionId ? sectionsOf(sel.view.plot.id).find((x) => x.id === sel.bed.sectionId) ?? null : null}
                         onSection={(patch) => updateSection(sel.view.plot.id, sel.bed.sectionId!, patch)}
                         onRemove={() => removeSection(sel.view.plot.id, sel.bed.sectionId!)} editOn={editOn} onEdit={() => setEditOn(true)}
                         demoOn={demo?.plotId === sel.view.plot.id} onDemo={(system) => { setDemo(system ? { plotId: sel.view.plot.id, system } : null); if (system && mode !== "3d") setMode("3d"); }}
                         onClose={() => setSelected(null)} onOpen={onOpen} />
            : <Overview farm={farm} onGenerate={() => setAiOpen(true)} busy={generate.isPending} features={features}
                        onFeature={(f) => { setSelected(`feature:${f.id}`); focusFeature(f); }} onAdd={() => setPalette(true)}
                        revisions={revQ.data?.revisions ?? []} dirty={dirty} restoring={restore.isPending} onRestore={(id) => restore.mutate(id)} />}
          {draft && !dirty && (
            <div className="vp-msg">
              <span>Hai modifiche non salvate del {new Date(draft.at).toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" })}.</span>
              <div className="row" style={{ gap: 6, marginTop: 6 }}>
                <button className="btn sm" onClick={() => { setHist({ stack: [EMPTY, draft.snap], i: 1 }); setDraft(null); setMsg("Modifiche riprese: controllale e premi «Salva progetto»."); }}>
                  <Icon name="undo" size={13} />Riprendi</button>
                <button className="btn ghost sm" onClick={() => { clearDraft(); setDraft(null); }}>Scarta</button>
              </div>
            </div>
          )}
          {(msg || change.isError || save.isError) && (
            <div className={`vp-msg ${change.isError || save.isError ? "err" : ""}`}>
              {change.isError ? (change.error as Error).message : save.isError ? (save.error as Error).message : msg}
              <button className="icon-btn" onClick={() => { setMsg(null); change.reset(); save.reset(); }} aria-label="Chiudi"><Icon name="minus" size={13} /></button>
            </div>
          )}
        </aside>
      </div>

      {catalog && (
        <Suspense fallback={<div className="card muted">Carico la libreria…</div>}>
          <CropCatalog crops={farm.crops} onClose={() => setCatalog(false)} />
        </Suspense>
      )}
      <div className="vp-bottom">
        <div className="card vp-timeline">
          <div className="row"><b>Piano di rotazione ({season}–{season + 4})</b><span className="spacer" />
            <button className="btn ghost sm" onClick={() => onOpen((sel?.view.plot ?? farm.plots[0])?.id, "plan")} disabled={!farm.plots.length}>
              <Icon name="shuffle" size={13} />Confronta anni</button></div>
          <div className="vp-years">
            {perYear.map(({ y, views: vs }, i) => {
              const agg = new Map<string, { c: string; a: number }>();
              let proposed = false, total = 0;
              vs.forEach((v) => v.beds.forEach((b) => { if (!b.crop) return; total += b.area; proposed ||= !!b.crop.proposed;
                const e = agg.get(b.crop.crop) ?? { c: cropColor(b.crop.crop, b.crop.family), a: 0 }; e.a += b.area; agg.set(b.crop.crop, e); }));
              const saved = farm.plots.some((p) => p.plans.some((x) => x.year === y));
              return (
                <button key={y} className={`vp-yr ${y === year ? "on" : ""}`} onClick={() => { setYear(y); setSelected(null); }}>
                  <b>{y}</b><small>{i === 0 ? "Situazione attuale" : `Rotazione ${i}`}</small>
                  <span className="vp-bar">{total ? [...agg.values()].map((e, k) => <i key={k} style={{ background: e.c, flex: e.a }} />) : <i style={{ flex: 1, background: "#d9dfda" }} />}</span>
                  <span className="vp-tag">{i === 0 ? "storico" : proposed ? "proposta" : saved ? "salvato" : "vuoto"}</span>
                </button>
              );
            })}
          </div>
        </div>
        <Stats farm={farm} views={views} year={year} />
      </div>
    </div>
  );
}

function Props({ sel, year, season, byKey, farm, views, busy, onChange, onClose, onOpen, month, calendar, onMove, section, onSection, onRemove, editOn, onEdit, demoOn, onDemo }: {
  sel: { bed: BedView; view: PlotView }; year: number; season: number; byKey: Record<string, any>; farm: FarmData;
  month: number; calendar: Record<string, Calendar>;
  views: { y: number; views: PlotView[] }[]; busy: boolean; onChange: (crop: string) => void; onClose: () => void;
  onOpen: (plotId: string, tab: "plan" | "editor" | "history") => void;
  onMove: (target: BedView) => void; section: Section | null; onSection: (p: Partial<Section>) => void; onRemove: () => void;
  editOn: boolean; onEdit: () => void; demoOn: boolean; onDemo: (system: string | null) => void;
}) {
  const { bed, view } = sel;
  const c = bed.crop;
  const h = c ? byKey[c.crop]?.height_m : null;
  const nextView = views.find((x) => x.y === year + 1)?.views.find((v) => v.plot.id === view.plot.id);
  const next = nextView?.beds.find((b) => b.sectionId === bed.sectionId)?.crop;
  const growing = isGrowing(bed.kind);
  const badge = !c ? null : year === season ? "Coltura attiva" : c.proposed ? "Proposta AgroAI" : c.manual ? "Scelta da te" : "Piano salvato";
  return (
    <div className="vp-props">
      <div className="row"><b>Proprietà</b><span className="spacer" /><button className="icon-btn" onClick={onClose} aria-label="Chiudi"><Icon name="minus" size={14} /></button></div>
      <div className="vp-crop">
        <span className="vp-sw" style={{ background: c ? cropColor(c.crop, c.family) : "#cdb68c" }}><Icon name={c ? "sprout" : growing ? "grid" : "map"} size={22} /></span>
        <div style={{ minWidth: 0 }}>
          <b>{c ? shortName(c.name) : growing ? "Nessuna coltura" : bed.name}</b>
          {badge && <span className={`vp-badge ${c?.proposed ? "prop" : ""}`}>{badge}</span>}
        </div>
      </div>
      <dl className="vp-kv">
        <dt>Appezzamento</dt><dd>{view.plot.name}</dd>
        <dt>Parte</dt><dd>{bed.name}</dd>
        <dt>Superficie</dt><dd>{fmtArea(bed.area)}</dd>
        {c && <><dt>Altezza pianta</dt><dd>{h ? `${h[0] === h[1] ? h[0] : h.join("–")} m` : "n.d."}</dd></>}
        {growing && <><dt>Filari</dt><dd>{section?.row_spacing_m ? rowCount(section) : "non indicati"}</dd></>}
        {growing && section?.row_spacing_m && <><dt>Distanza filari</dt><dd>{Math.round(section.row_spacing_m * 100)} cm</dd></>}
        {c?.verdict && year > season && <><dt>Stato</dt><dd><span className={`vp-st ${VERDICT[c.verdict][1]}`} />{VERDICT[c.verdict][0]}</dd></>}
        {c && month > 0 && <><dt>Fase ({MONTHS[month - 1].slice(0, 3).toLowerCase()})</dt><dd>{calendar[c.crop] ? STAGE_LABEL[stageFor(calendar[c.crop], month)] : "n.d."}</dd></>}
      </dl>
      {c?.wholePlot && <div className="tiny muted">Coltura registrata per l'intero appezzamento: la parte esatta non è indicata.</div>}
      {h && <div className="tiny muted">Altezza: FAO-56, tabella 12.</div>}
      {c && !h && <div className="tiny muted">Altezza non presente in FAO-56: disegnata con un valore neutro.</div>}

      {growing && (
        <div className="vp-sec">
          <div className="vp-h">Rotazione colturale</div>
          {year > season ? (
            <label className="field">Coltura nel {year}
              <select value={c?.crop ?? ""} disabled={busy} onChange={(e) => e.target.value && onChange(e.target.value)}>
                <option value="">— scegli —</option>
                {farm.crops.filter((x) => x.season !== "pluriennale").map((x) => <option key={x.key} value={x.key}>{shortName(x.name)}</option>)}
              </select>
            </label>
          ) : <div className="small muted">Per cambiare le colture di oggi usa lo Storico.</div>}
          {year > season && c && (
            <label className="field">Sposta questa coltura in
              <select value="" disabled={busy} onChange={(e) => { const t = view.beds.find((b) => b.key === e.target.value); if (t) onMove(t); }}>
                <option value="">— scegli una parte —</option>
                {view.beds.filter((b) => b.key !== bed.key).map((b) => <option key={b.key} value={b.key}>{b.name}{b.crop ? ` (scambia con ${shortName(b.crop.name)})` : " (libera)"}</option>)}
              </select>
            </label>
          )}
          {busy && <div className="tiny muted">Controllo con le regole…</div>}
          {year + 1 <= season + 4 && <div className="small" style={{ marginTop: 6 }}>Anno successivo ({year + 1}): <b>{next ? shortName(next.name) : "—"}</b>{next?.proposed ? " (proposta)" : ""}</div>}
          {c?.reasons && c.reasons.length > 0 && (
            <ul className="vp-reasons">
              {c.reasons.slice(0, 4).map((r, i) => (
                <li key={i} className={`e-${r.effect}`}>
                  <span className={`lv ${LEVEL[r.level]?.cls}`}>{LEVEL[r.level]?.label}</span> {r.text}
                  {r.source && <> <a href={r.source.url} target="_blank" rel="noreferrer">fonte</a></>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {section ? <SectionForm key={`${bed.key}:${section.x}:${section.y}:${section.w}:${section.h}:${section.kind}:${section.row_spacing_m}:${section.row_dir}`}
        section={section} plot={view.plot} others={view.plot.sections.filter((x) => x.id !== section.id)} onApply={onSection} onRemove={onRemove}
        editOn={editOn} onEdit={onEdit} />
        : <div className="vp-sec"><div className="tiny muted">Questo appezzamento non è diviso: aggiungi una parte con «+» o dividilo per modificarne forma e filari.</div></div>}
      <div className="vp-sec">
        <div className="vp-h">Impianti</div>
        {growing && c && c.crop !== "cover" ? (
          <IrrigationPanel plotId={view.plot.id} year={year} sectionId={bed.sectionId && !isTmp(bed.sectionId) ? bed.sectionId : null} section={bed.name}
            crop={c.crop} area={bed.area} demoOn={demoOn} onDemo={onDemo} />
        ) : <div className="vp-imp"><Icon name="drop" size={15} />Irrigazione<span className="spacer" />{view.irrigation ? IRRIGATION[view.irrigation] ?? view.irrigation : "non indicata"}</div>}
        <div className="vp-imp"><Icon name="home" size={15} />Serra<span className="spacer" />{bed.kind === "greenhouse" ? "Sì" : view.plot.sections.some((s) => s.kind === "greenhouse") ? "Nell'appezzamento" : "No"}</div>
      </div>
      <div className="row" style={{ gap: 6, flexWrap: "wrap", marginTop: 10 }}>
        <button className="btn sm" onClick={() => onOpen(view.plot.id, "plan")}><Icon name="layers" size={13} />Piano e motivi</button>
        <button className="btn ghost sm" onClick={() => onOpen(view.plot.id, "editor")}><Icon name="split" size={13} />Modifica parti</button>
      </div>
    </div>
  );
}

interface Revision { id: string; label: string; created_at: string; summary: { plots: number; parts: number; plans: number; years: number[] } | null }
const when = (iso: string) => new Date(iso.endsWith("Z") ? iso : `${iso}Z`).toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" });

function Overview({ farm, onGenerate, busy, features, onFeature, onAdd, revisions, dirty, restoring, onRestore }: { farm: FarmData; onGenerate: () => void; busy: boolean;
  features: Feature[]; onFeature: (f: Feature) => void; onAdd: () => void;
  revisions: Revision[]; dirty: boolean; restoring: boolean; onRestore: (id: string) => void }) {
  const [ask, setAsk] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  return (
    <div className="vp-props">
      <b>{farm.name}</b>
      <div className="small muted">{[farm.municipality, farm.province, farm.coverage?.name].filter(Boolean).join(" · ") || "Luogo non indicato"}</div>
      <div className="vp-hint"><Icon name="hand" size={16} />Tocca un'aiuola o un campo per vedere coltura, stato, rotazione e impianti.</div>
      <div className="vp-sec">
        <div className="row"><div className="vp-h" style={{ margin: 0 }}>Elementi aziendali</div><span className="spacer" />
          <button className="btn ghost sm" onClick={onAdd}><Icon name="plus" size={13} />Aggiungi</button></div>
        {features.length ? (
          <div className="vp-flist">{features.map((f) => (
            <button key={f.id} onClick={() => onFeature(f)}><Icon name={KIND_ICON[f.kind] ?? "map"} size={15} /><span>{f.name}</span>
              <small>{f.label}{f.area_m2 ? ` · ${fmtArea(f.area_m2)}` : f.length_m ? ` · ${Math.round(f.length_m)} m` : ""}</small></button>
          ))}</div>
        ) : <div className="tiny muted">Casali, cisterne, strade, frutteti e vigneti che aggiungi compaiono qui.</div>}
      </div>
      <div className="vp-sec">
        <div className="vp-h">Versioni salvate</div>
        {revisions.length ? <>
          <div className="tiny muted">Ultimo salvataggio: {when(revisions[0].created_at)}. Ogni «Salva progetto» crea una versione (disegno e piani, non lo storico).</div>
          <div className="vp-revs">{(all ? revisions : revisions.slice(0, 4)).map((r, i) => (
            <div key={r.id} className="vp-rev">
              <div style={{ minWidth: 0 }}><b>{r.label}</b>
                <small>{when(r.created_at)}{r.summary ? ` · ${r.summary.parts} parti · ${r.summary.plans} piani${r.summary.years.length ? ` (${r.summary.years[0]}–${r.summary.years[r.summary.years.length - 1]})` : ""}` : ""}</small></div>
              {i === 0 ? <span className="vp-badge">Attuale</span> : ask === r.id
                ? <span className="row" style={{ gap: 4 }}><button className="btn sm" disabled={restoring} onClick={() => { onRestore(r.id); setAsk(null); }}>Sì, ripristina</button>
                    <button className="btn ghost sm" onClick={() => setAsk(null)}>No</button></span>
                : <button className="btn ghost sm" disabled={restoring || dirty} title={dirty ? "Prima salva o annulla le modifiche in corso" : "Torna a questa versione"}
                    onClick={() => setAsk(r.id)}><Icon name="undo" size={13} />Ripristina</button>}
            </div>
          ))}</div>
          {revisions.length > 4 && <button className="btn ghost sm" onClick={() => setAll((v) => !v)}>{all ? "Mostra meno" : `Tutte le versioni (${revisions.length})`}</button>}
          {ask && <div className="tiny muted">Il ripristino riporta disegno e piani a quella versione; la versione di adesso resta nell'elenco.</div>}
        </> : <div className="tiny muted">Nessuna versione ancora: la prima nasce quando premi «Salva progetto».</div>}
      </div>
      <div className="vp-gen">
        <Icon name="spark" size={20} />
        <b>Genera organizzazione con AgroAI</b>
        <div className="tiny muted">Più proposte di layout (parti, passaggi, serra, punto d'acqua), ognuna con le colture {farm.season_year + 1}–{farm.season_year + 4} scelte con le regole della tua regione. Le confronti e le provi nel 3D.</div>
        <button className="btn sm" disabled={busy} onClick={onGenerate}><Icon name="spark" size={13} />Apri il generatore</button>
      </div>
    </div>
  );
}

function Stats({ farm, views, year }: { farm: FarmData; views: PlotView[]; year: number }) {
  const total = farm.plots.reduce((a, p) => a + (p.area_m2 ?? 0), 0);
  const agg = new Map<string, { n: string; c: string; a: number }>();
  views.forEach((v) => v.beds.forEach((b) => { if (!b.crop) return; const e = agg.get(b.crop.crop) ?? { n: shortName(b.crop.name), c: cropColor(b.crop.crop, b.crop.family), a: 0 }; e.a += b.area; agg.set(b.crop.crop, e); }));
  const rows = [...agg.values()].sort((a, b) => b.a - a.a);
  const used = rows.reduce((a, r) => a + r.a, 0);
  let acc = 0;
  const R = 34, C = 2 * Math.PI * R;
  return (
    <div className="card vp-stats">
      <b>Statistiche terreno {year}</b>
      <div className="row" style={{ gap: 14, alignItems: "center", marginTop: 8 }}>
        <div style={{ flex: 1 }}>
          <div className="tiny muted">Superficie totale</div><div className="vp-big">{fmtArea(total)}</div>
          <div className="tiny muted" style={{ marginTop: 4 }}>Appezzamenti</div><div className="vp-big">{farm.plots.length}</div>
        </div>
        <svg width="92" height="92" viewBox="0 0 92 92" aria-label="Superficie per coltura">
          <circle cx="46" cy="46" r={R} fill="none" stroke="#e3e8e4" strokeWidth="14" />
          {rows.map((r, i) => { const len = (r.a / Math.max(total, used)) * C; const el = <circle key={i} cx="46" cy="46" r={R} fill="none" stroke={r.c} strokeWidth="14"
            strokeDasharray={`${len} ${C - len}`} strokeDashoffset={-acc} transform="rotate(-90 46 46)" />; acc += len; return el; })}
        </svg>
      </div>
      <div className="vp-legend">{rows.slice(0, 5).map((r) => <span key={r.n}><i style={{ background: r.c }} />{r.n} {total ? Math.round((r.a / total) * 100) : 0}%</span>)}</div>
    </div>
  );
}

function rowCount(x: Section) {
  const across = x.row_dir === "x" ? x.h : x.row_dir === "y" ? x.w : Math.min(x.w, x.h);
  return Math.max(1, Math.floor(across / (x.row_spacing_m || 1)));
}

/** Real dimensions, kind and declared rows of a part; applied as an unsaved change (undo/redo, «Salva progetto»). */
function SectionForm({ section, plot, others, onApply, onRemove, editOn, onEdit }: {
  section: Section; plot: FarmData["plots"][number]; others: Section[]; onApply: (p: Partial<Section>) => void; onRemove: () => void;
  editOn: boolean; onEdit: () => void;
}) {
  const [f, setF] = useState({ name: section.name, kind: section.kind, x: section.x, y: section.y, w: section.w, h: section.h,
    row_spacing_m: section.row_spacing_m ?? null, plant_spacing_m: section.plant_spacing_m ?? null, row_dir: section.row_dir ?? null });
  const [confirm, setConfirm] = useState(false);
  const W = plot.width_m ?? 0, L = plot.length_m ?? 0;
  const num = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value === "" ? null : +e.target.value });
  const growing = isGrowing(f.kind);
  const fits = f.x >= 0 && f.y >= 0 && f.w >= 0.3 && f.h >= 0.3 && f.x + f.w <= W + 1e-6 && f.y + f.h <= L + 1e-6;
  const rowsOk = !f.row_spacing_m || (f.row_spacing_m >= 0.1 && f.row_spacing_m <= 20);
  const plantOk = !f.plant_spacing_m || (f.plant_spacing_m >= 0.05 && f.plant_spacing_m <= 20);
  const overlaps = others.filter((o) => Math.min(f.x + f.w, o.x + o.w) - Math.max(f.x, o.x) > 0.05 && Math.min(f.y + f.h, o.y + o.h) - Math.max(f.y, o.y) > 0.05);
  const changed = JSON.stringify(f) !== JSON.stringify({ name: section.name, kind: section.kind, x: section.x, y: section.y, w: section.w, h: section.h,
    row_spacing_m: section.row_spacing_m ?? null, plant_spacing_m: section.plant_spacing_m ?? null, row_dir: section.row_dir ?? null });
  return (
    <div className="vp-sec">
      <div className="row"><div className="vp-h" style={{ margin: 0 }}>Forma e filari</div><span className="spacer" />
        {!editOn && <button className="btn ghost sm" onClick={onEdit}><Icon name="edit" size={13} />Modifica nel 3D</button>}</div>
      <div className="vp-form">
        <label className="field">Nome<input value={f.name} maxLength={64} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
        <label className="field">Tipo<select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value as Kind })}>
          {SECTION_KINDS.map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}</select></label>
        <label className="field">Da ovest (m)<input type="number" step="0.1" min={0} value={f.x} onChange={num("x")} /></label>
        <label className="field">Da nord (m)<input type="number" step="0.1" min={0} value={f.y} onChange={num("y")} /></label>
        <label className="field">Larghezza (m)<input type="number" step="0.1" min={0.3} value={f.w} onChange={num("w")} /></label>
        <label className="field">Lunghezza (m)<input type="number" step="0.1" min={0.3} value={f.h} onChange={num("h")} /></label>
        {growing && <>
          <label className="field">Distanza tra i filari (m)<input type="number" step="0.05" min={0.1} max={20} placeholder="non indicata" value={f.row_spacing_m ?? ""} onChange={num("row_spacing_m")} /></label>
          <label className="field">Distanza sulla fila (m)<input type="number" step="0.05" min={0.05} max={20} placeholder="non indicata" value={f.plant_spacing_m ?? ""} onChange={num("plant_spacing_m")} /></label>
          <label className="field">Direzione dei filari<select value={f.row_dir ?? ""} onChange={(e) => setF({ ...f, row_dir: (e.target.value || null) as "x" | "y" | null })}>
            <option value="">Lungo il lato lungo</option><option value="y">Nord – Sud</option><option value="x">Est – Ovest</option></select></label>
        </>}
      </div>
      <div className="tiny muted">Misure in metri dall'angolo nord-ovest dell'appezzamento ({W.toLocaleString("it-IT")} × {L.toLocaleString("it-IT")} m). Superficie: {fmtArea(f.w * f.h)}.</div>
      {growing && f.row_spacing_m && rowsOk && <div className="tiny">Ci stanno {rowCount(f as Section)} filari con la distanza che hai indicato.</div>}
      {growing && !f.row_spacing_m && <div className="tiny muted">Distanze non indicate: il 3D mostra file indicative, non dati agronomici.</div>}
      {!fits && <div className="tiny" style={{ color: "var(--danger)" }}>La parte esce dall'appezzamento: riduci misure o posizione.</div>}
      {(!rowsOk || !plantOk) && <div className="tiny" style={{ color: "var(--danger)" }}>Distanze fuori scala (filari 0,1–20 m, sulla fila 0,05–20 m).</div>}
      {overlaps.length > 0 && <div className="tiny" style={{ color: "var(--warn, #b7791f)" }}>Si sovrappone a: {overlaps.map((o) => o.name).join(", ")}.</div>}
      <div className="row" style={{ gap: 6, marginTop: 8, flexWrap: "wrap" }}>
        <button className="btn sm" disabled={!changed || !fits || !rowsOk || !plantOk || !f.name.trim()}
          onClick={() => onApply({ ...f, name: f.name.trim(), x: snap10(f.x), y: snap10(f.y), w: snap10(f.w), h: snap10(f.h) })}><Icon name="check" size={13} />Applica</button>
        {confirm ? <><button className="btn danger sm" onClick={onRemove}><Icon name="trash" size={13} />Conferma eliminazione</button>
          <button className="btn ghost sm" onClick={() => setConfirm(false)}>No</button></>
          : <button className="btn ghost sm" onClick={() => setConfirm(true)}><Icon name="trash" size={13} />Elimina parte</button>}
      </div>
    </div>
  );
}
