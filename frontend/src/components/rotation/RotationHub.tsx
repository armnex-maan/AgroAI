import { lazy, Suspense, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { Icon } from "../Icon";
import QuickRotation, { CropPicker } from "../Rotation";
import Ecosystems from "./Ecosystems";
import FieldCanvas from "./FieldCanvas";
import PlanView from "./PlanView";
import PlotEditor from "./PlotEditor";
import Setup from "./Setup";
import { Assignment, cropColor, FarmData, fmtArea, isGrowing, Plot, shortName, useFarmData } from "./types";

// three.js is heavy: the planner is loaded only when its tab is opened
const VisualPlanner = lazy(() => import("./planner/VisualPlanner"));

type Tab = "plots" | "map" | "setup" | "quick";
type PlotTab = "plan" | "editor" | "history" | "eco";

export default function RotationHub() {
  const farm = useFarmData();
  const [tab, setTab] = useState<Tab>("plots");
  const [plotId, setPlotId] = useState<string | null>(null);
  const [ptab, setPtab] = useState<PlotTab>("plan");
  const [draw, setDraw] = useState<{ plotId: string | null } | null>(null);
  const f = farm.data;
  if (!f) {
    return farm.isError
      ? <div className="callout danger"><Icon name="alert" /><div style={{ flex: 1 }}>Non riesco a caricare i dati.</div><button className="btn sm" onClick={() => farm.refetch()}>Riprova</button></div>
      : <div className="card muted">Caricamento…</div>;
  }
  const plot = f.plots.find((p) => p.id === plotId) ?? null;
  const firstTime = !f.region && !f.plots.some((p) => p.history.length);

  return (
    <div className="stack">
      <div className="tabs">
        <button className={tab === "plots" ? "on" : ""} onClick={() => { setTab("plots"); setPlotId(null); }}><Icon name="grid" size={14} /> Appezzamenti</button>
        <button className={tab === "map" ? "on" : ""} onClick={() => setTab("map")}><Icon name="layers" size={14} /> Planner 3D</button>
        <button className={tab === "setup" ? "on" : ""} onClick={() => setTab("setup")}><Icon name="edit" size={14} /> Questionario</button>
        <button className={tab === "quick" ? "on" : ""} onClick={() => setTab("quick")}><Icon name="spark" size={14} /> Consiglio veloce</button>
      </div>

      {tab === "setup" && <Setup farm={f} onDone={() => { setTab("plots"); setPlotId(null); }} />}
      {tab === "quick" && <QuickRotation />}
      {tab === "map" && (
        <Suspense fallback={<div className="card muted">Carico il planner 3D…</div>}>
          <VisualPlanner farm={f} draw={draw} onDraw={setDraw} onDrawn={() => setDraw(null)}
                         onOpen={(id, t) => { setTab("plots"); setPlotId(id); setPtab(t); }} />
        </Suspense>
      )}
      {tab === "plots" && !plot && (
        firstTime ? (
          <div className="card empty-start">
            <Icon name="sprout" size={34} />
            <h2>Iniziamo dal tuo terreno</h2>
            <p className="small muted">Poche domande, una alla volta: dove si trova, com'è fatto, cosa hai coltivato negli ultimi anni e cosa vuoi coltivare. Poi AgroAI prepara il piano per ogni appezzamento.</p>
            <div className="row" style={{ gap: 8, flexWrap: "wrap", justifyContent: "center" }}>
              <button className="btn" onClick={() => setTab("setup")}>Rispondi alle domande<Icon name="arrow-right" size={15} /></button>
              <button className="btn ghost" onClick={() => { setDraw({ plotId: null }); setTab("map"); }}><Icon name="map" size={15} />Traccia il terreno sulla mappa</button>
            </div>
          </div>
        ) : <Dashboard farm={f} onOpen={(id, t) => { setPlotId(id); setPtab(t); }} onSetup={() => setTab("setup")}
                       onTrace={(id) => { setDraw({ plotId: id }); setTab("map"); }} />
      )}
      {tab === "plots" && plot && (
        <>
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <button className="btn ghost sm" onClick={() => setPlotId(null)}><Icon name="arrow-left" size={14} />Tutti</button>
            <h2 style={{ margin: 0, fontSize: 20 }}>{plot.name}</h2>
            <span className="muted small">{fmtArea(plot.area_m2)}</span>
            <span className="spacer" />
            <div className="tabs" style={{ marginBottom: 0 }}>
              <button className={ptab === "plan" ? "on" : ""} onClick={() => setPtab("plan")}><Icon name="layers" size={14} /> Piano</button>
              <button className={ptab === "editor" ? "on" : ""} onClick={() => setPtab("editor")}><Icon name="edit" size={14} /> Disegno</button>
              <button className={ptab === "history" ? "on" : ""} onClick={() => setPtab("history")}><Icon name="book" size={14} /> Storico</button>
              <button className={ptab === "eco" ? "on" : ""} onClick={() => setPtab("eco")}><Icon name="leaf" size={14} /> Ecosistemi</button>
            </div>
          </div>
          {ptab === "plan" && <PlanView plot={plot} farm={f} goals={plot.profile?.goals ?? {}} />}
          {ptab === "editor" && <PlotEditor key={plot.id} plot={plot} onDone={() => setPtab("plan")} />}
          {ptab === "history" && <History plot={plot} farm={f} />}
          {ptab === "eco" && <Ecosystems plot={plot} />}
        </>
      )}
    </div>
  );
}

function Dashboard({ farm, onOpen, onSetup, onTrace }: { farm: FarmData; onOpen: (id: string, t: PlotTab) => void; onSetup: () => void;
  onTrace: (plotId: string | null) => void }) {
  const qc = useQueryClient();
  const add = useMutation({
    mutationFn: () => api.post<Plot>("/api/v1/rotation/plots", { name: `Appezzamento ${farm.plots.length + 1}`, width_m: 10, length_m: 20,
      profile: farm.plots[0]?.profile ?? {} }),
    onSuccess: (p) => { qc.invalidateQueries({ queryKey: ["rotation-farm"] }); onOpen(p.id, "editor"); },
  });
  const next = farm.season_year + 1;
  return (
    <div className="stack">
      <div className="card farm-head">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="tiny muted">Azienda</div>
          <b>{farm.name}</b>
          <div className="small muted">{[farm.municipality, farm.province, farm.coverage?.name].filter(Boolean).join(" · ") || "Luogo non indicato"}</div>
        </div>
        <button className="btn ghost sm" onClick={onSetup}><Icon name="edit" size={14} />Modifica risposte</button>
      </div>
      {farm.plots.some((p) => !p.polygon) && (
        <div className="callout info"><Icon name="map" size={18} /><div className="small" style={{ flex: 1 }}>
          Traccia i tuoi appezzamenti sulla mappa satellitare: AgroAI calcola da solo superficie e forma.</div>
          <button className="btn sm" onClick={() => onTrace(farm.plots.find((p) => !p.polygon)!.id)}><Icon name="pen" size={13} />Traccia</button></div>
      )}
      <div className={`coverage cov-${farm.coverage.level}`}><Icon name={farm.coverage.level === "none" ? "alert" : "book"} size={18} /><div className="small">{farm.coverage.text}</div></div>
      <div className="plot-grid">
        {farm.plots.map((p) => {
          const now = p.history.filter((h) => h.year === farm.season_year);
          const plan = p.plans.find((x) => x.year === next);
          const nowMap: Record<string, Assignment> = Object.fromEntries(now.filter((h) => h.section_id).map((h) => [h.section_id!, {
            section_id: h.section_id, section: "", crop: h.crop, name: h.name, family: h.family ?? "", area_m2: h.area_m2 ?? 0, verdict: "ok" } as Assignment]));
          const years = new Set(p.history.map((h) => h.year)).size;
          return (
            <div key={p.id} className="card plot-card">
              <div onClick={() => onOpen(p.id, "plan")} style={{ cursor: "pointer" }}>
                <FieldCanvas width={p.width_m ?? 10} length={p.length_m ?? 10} shape={p.shape} outline={p.outline}
                             orientation={p.orientation_deg} sections={p.sections} mode="view" crops={plan ? Object.fromEntries(plan.assignments.filter((a) => a.section_id).map((a) => [a.section_id!, a])) : nowMap}
                             catalog={farm.crops} compact height={150} />
              </div>
              <div className="row" style={{ marginTop: 8 }}><b>{p.name}</b><span className="spacer" /><span className="small muted">{fmtArea(p.area_m2)}</span></div>
              <div className="tiny muted">{p.sections.filter((s) => isGrowing(s.kind)).length} aiuole · storico: {years} {years === 1 ? "anno" : "anni"}</div>
              <div className="chips-line">
                <span className="tiny muted">{farm.season_year}:</span>
                {now.length ? now.map((h) => <span key={h.id} className="mini-chip" style={{ ["--c" as any]: h.family ? cropColor(h.crop, h.family) : "#b9c4bd" }}>{h.name}</span>)
                  : <span className="tiny muted">non indicato</span>}
              </div>
              {plan && <div className="chips-line"><span className="tiny muted">{next}:</span>
                {[...new Map(plan.assignments.map((a) => [a.crop, a])).values()].map((a) => <span key={a.crop} className="mini-chip" style={{ ["--c" as any]: cropColor(a.crop, a.family) }}>{shortName(a.name)}</span>)}</div>}
              <div className="row" style={{ gap: 6, marginTop: 10 }}>
                <button className="btn sm" onClick={() => onOpen(p.id, "plan")}><Icon name="layers" size={13} />Piano</button>
                <button className="btn ghost sm" onClick={() => onOpen(p.id, "editor")}><Icon name="edit" size={13} />Disegno</button>
                <button className="btn ghost sm" onClick={() => onOpen(p.id, "history")}><Icon name="book" size={13} />Storico</button>
                <button className="btn ghost sm" onClick={() => onOpen(p.id, "eco")}><Icon name="leaf" size={13} />Ecosistemi</button>
                {!p.polygon && <button className="btn ghost sm" onClick={() => onTrace(p.id)}><Icon name="map" size={13} />Mappa</button>}
              </div>
            </div>
          );
        })}
        <button className="card add-plot" onClick={() => onTrace(null)}><Icon name="map" size={26} /><span>Traccia un nuovo appezzamento sulla mappa</span></button>
        <button className="card add-plot" onClick={() => add.mutate()}><Icon name="plus" size={26} /><span>Aggiungi a misura (senza mappa)</span></button>
      </div>
    </div>
  );
}

const STATUS_LABEL: Record<string, string> = { crop: "Coltivato", rest: "Riposo", cover: "Sovescio", unknown: "Non ricordo" };

function History({ plot, farm }: { plot: Plot; farm: FarmData }) {
  const qc = useQueryClient();
  const years = Array.from({ length: 6 }, (_, i) => farm.season_year - i);
  const [edit, setEdit] = useState<number | null>(null);
  const [draft, setDraft] = useState<{ status: string; crops: { crop: string; section_id: string | null; area_m2: string; diseases: string; treatments: string; notes: string }[] }>({ status: "crop", crops: [] });
  const save = useMutation({
    mutationFn: (year: number) => api.put(`/api/v1/rotation/plots/${plot.id}/history`, { year, status: draft.status,
      crops: draft.status === "crop" ? draft.crops.map((c) => ({ ...c, area_m2: c.area_m2 ? parseFloat(c.area_m2.replace(",", ".")) : null })) : [] }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["rotation-farm"] }); setEdit(null); },
  });
  const beds = plot.sections.filter((s) => isGrowing(s.kind));
  const open = (y: number) => {
    const rows = plot.history.filter((h) => h.year === y);
    setDraft({ status: rows[0]?.status ?? "crop", crops: rows.filter((h) => h.status === "crop").map((h) => ({ crop: h.crop, section_id: h.section_id,
      area_m2: h.area_m2 ? String(h.area_m2) : "", diseases: h.diseases ?? "", treatments: h.treatments ?? "", notes: h.notes ?? "" })) });
    setEdit(y);
  };
  return (
    <div className="card">
      <h3><Icon name="book" />Storico degli ultimi 6 anni</h3>
      <div className="small muted mb">Gli anni senza risposta restano vuoti: AgroAI non inventa colture che non conosce.</div>
      <div className="hist-table">
        {years.map((y) => {
          const rows = plot.history.filter((h) => h.year === y);
          return (
            <div key={y} className="hist-year">
              <div className="row" style={{ alignItems: "flex-start" }}>
                <b className="hy">{y}</b>
                <div style={{ flex: 1, minWidth: 0 }}>
                  {rows.length === 0 ? <span className="tiny muted">non indicato</span> : rows[0].status !== "crop" ? <span className="mini-chip">{STATUS_LABEL[rows[0].status]}</span> :
                    rows.map((h) => (
                      <div key={h.id} className="hist-crop">
                        <span className="mini-chip" style={{ ["--c" as any]: h.family ? cropColor(h.crop, h.family) : "#b9c4bd" }}>{h.name}</span>
                        <span className="tiny muted">{[beds.find((b) => b.id === h.section_id)?.name, h.area_m2 ? fmtArea(h.area_m2) : null,
                          h.diseases ? `malattie: ${h.diseases}` : null, h.treatments ? `trattamenti: ${h.treatments}` : null, h.notes].filter(Boolean).join(" · ")}</span>
                      </div>
                    ))}
                </div>
                <button className="icon-btn" title="Modifica" onClick={() => (edit === y ? setEdit(null) : open(y))}><Icon name="edit" size={14} /></button>
              </div>
              {edit === y && (
                <div className="hist-edit">
                  <div className="row" style={{ gap: 6 }}>
                    {Object.entries(STATUS_LABEL).map(([k, l]) => <button key={k} className={`answer ${draft.status === k ? "on" : ""}`} onClick={() => setDraft({ ...draft, status: k })}>{l}</button>)}
                  </div>
                  {draft.status === "crop" && (<>
                    <CropPicker crops={farm.crops} multi values={draft.crops.map((c) => c.crop)}
                                onToggle={(k) => setDraft({ ...draft, crops: draft.crops.some((c) => c.crop === k) ? draft.crops.filter((c) => c.crop !== k)
                                  : [...draft.crops, { crop: k, section_id: null, area_m2: "", diseases: "", treatments: "", notes: "" }] })} />
                    {draft.crops.map((c, i) => (
                      <div key={c.crop} className="form-grid crop-detail">
                        <b style={{ gridColumn: "1 / -1" }}>{shortName(farm.crops.find((x) => x.key === c.crop)?.name ?? c.crop)}</b>
                        {beds.length > 0 && <label className="field">Aiuola<select value={c.section_id ?? ""} onChange={(e) => setDraft({ ...draft, crops: draft.crops.map((x, j) => j === i ? { ...x, section_id: e.target.value || null } : x) })}>
                          <option value="">Tutto l'appezzamento</option>{beds.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>}
                        {(["area_m2", "diseases", "treatments", "notes"] as const).map((k) => (
                          <label key={k} className="field">{{ area_m2: "Superficie (m²)", diseases: "Malattie", treatments: "Trattamenti", notes: "Note" }[k]}
                            <input value={c[k]} onChange={(e) => setDraft({ ...draft, crops: draft.crops.map((x, j) => j === i ? { ...x, [k]: e.target.value } : x) })} /></label>
                        ))}
                      </div>
                    ))}
                  </>)}
                  <div className="row" style={{ gap: 6, marginTop: 8 }}>
                    <button className="btn sm" disabled={save.isPending || (draft.status === "crop" && !draft.crops.length)} onClick={() => save.mutate(y)}><Icon name="check" size={13} />Salva {y}</button>
                    <button className="btn ghost sm" onClick={() => setEdit(null)}>Annulla</button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
