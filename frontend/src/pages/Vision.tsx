import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from "recharts";
import { api } from "../api/client";
import { useZones } from "../api/hooks";
import { Icon } from "../components/Icon";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { Empty, PageHeader, Steps } from "../components/ui";
import { RemedyCard, useRemedies } from "../components/Remedies";
import { Link } from "react-router-dom";
import { dateTime, LIKELIHOOD, num, pct, URGENCY } from "../lib/it";

const API = import.meta.env.VITE_API_URL || "";

type Tier = "probable" | "possible" | "unlikely";
interface Evidence { text: string; effect: "supports" | "weakens" | "neutral"; strength: string; origin: string }
interface Cause {
  id: string; name: string; category: string; urgency: string; likelihood: "high" | "medium" | "low";
  tier?: Tier; probability?: number; evidence?: Evidence[];
  why: string; signs: string; sensor_checks: { effect: "supports" | "weakens"; text: string }[];
  fix: string[]; prevent: string[]; verify: string[]; sources: { title: string; url: string }[];
}
interface PlantModel {
  version: string; applicable: boolean; crop: string | null; notes: string[]; datasets: string[];
  real_photo_accuracy: number; real_photo_top3: number; cause_accuracy: number;
  top: { label: string; name: string; score: number }[];
}
interface Question { id: string; text: string; options: { value: string; label: string }[] }
interface Soil {
  value: number; status: string; status_label: string; usable: boolean; reliability: string;
  texture_label?: string; texture_assumed?: boolean; notes: string[]; sources: { title: string; url: string }[];
}
interface Findings {
  crop: string | null; notes: string | null; overall: string;
  color: { plant_coverage: number; healthy_green: number; chlorotic_yellow: number; necrotic_brown: number;
           whitish_coating?: number; symptom_fraction: number; pattern: string; warnings: string[]; method: string };
  ai: null | { plant_guess: string | null; plant_part: string; image_quality: string; visible_symptoms: string[];
               overall: string; summary: string; cannot_tell: string };
  ai_error: string | null; ai_model: string | null; causes: Cause[];
  questions?: Question[]; answers?: Record<string, string>; soil?: Soil | null; engine?: string;
  plant_model?: PlantModel | null;
  observations?: Record<string, { value: string; origin: string; label: string }>;
  context: Record<string, number | null> & { sources: Record<string, string> };
  disclaimer: string;
}
interface Analysis {
  id: string; zone_id: string | null; ts: string; model: string; confidence: number; findings: Findings;
  verifications?: { verdict: string; actual_cause: string | null; notes: string | null; created_at: string }[];
}

const OVERALL: Record<string, [string, string, string]> = {
  looks_healthy: ["Sembra sana", "ok", "check"], mild_symptoms: ["Sintomi lievi", "warn", "alert"],
  marked_symptoms: ["Sintomi evidenti", "bad", "alert"], unclear: ["Non chiaro", "neutral", "info"],
  not_a_plant: ["Foto non valida", "neutral", "camera"],
};
const TIERS: { id: Tier; title: string; hint: string }[] = [
  { id: "probable", title: "Causa probabile", hint: "I sintomi visti corrispondono bene" },
  { id: "possible", title: "Cause possibili", hint: "Alcuni sintomi corrispondono, altri mancano o non si vedono" },
  { id: "unlikely", title: "Cause poco probabili", hint: "Considerate ed escluse per i motivi indicati" },
];
const tierOf = (c: Cause): Tier => c.tier ?? (c.likelihood === "high" ? "probable" : c.likelihood === "medium" ? "possible" : "unlikely");
const ORIGIN_IT: Record<string, string> = { foto: "foto", "tua risposta": "tua risposta", sensore: "sensore",
  "modello addestrato": "modello AGROAI" };
const VERDICT_IT: Record<string, string> = { confirmed: "era giusta", partly: "era giusta in parte", wrong: "era sbagliata" };

export default function Vision() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["vision"], queryFn: () => api.get<Analysis[]>("/api/v1/vision/analyses"), refetchInterval: false });
  const [selected, setSelected] = useState<string | undefined>();
  useEffect(() => { if (!selected && list.data?.length) setSelected(list.data[0].id); }, [list.data, selected]);

  return (
    <>
      <PageHeader icon="camera" title="Salute delle piante" tone="green"
                  subtitle="Fai una foto alle foglie: AGROAI ti dice cosa vede, le cause possibili e come intervenire." />
      <div className="split">
        <div className="stack">
          <div className="card">
            <h3><Icon name="camera" />Controlla una pianta</h3>
            <UploadForm onDone={(id) => { qc.invalidateQueries({ queryKey: ["vision"] }); setSelected(id); }} />
          </div>
          <div className="card">
            <h3><Icon name="info" />Per una foto buona</h3>
            <Steps items={[
              "Luce del giorno, senza flash e senza controluce.",
              "Avvicinati: la foglia malata deve riempire quasi tutta la foto.",
              "Tieni il telefono fermo, a fuoco sulle macchie.",
              "Se puoi, fotografa anche il retro della foglia.",
            ]} />
          </div>
          <div className="card">
            <div className="card-head"><h3>Foto precedenti</h3><span className="muted small">{list.data?.length ?? 0}</span></div>
            <div className="scroll stack" style={{ maxHeight: 520, gap: 4 }}>
              {(list.data ?? []).map((a) => {
                const [label, cls] = OVERALL[a.findings.overall] ?? OVERALL.unclear;
                return (
                  <div key={a.id} className={`list-item ${selected === a.id ? "active" : ""}`} onClick={() => setSelected(a.id)}
                       style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <img src={`${API}/api/v1/vision/analyses/${a.id}/image`} alt="" loading="lazy"
                         style={{ width: 54, height: 54, objectFit: "cover", borderRadius: 10, flexShrink: 0 }} />
                    <div style={{ minWidth: 0 }}>
                      <div className="row small"><b>{a.findings.crop || a.findings.ai?.plant_guess || "Pianta"}</b>
                        <span className={`badge badge-${cls}`}>{label}</span></div>
                      <div className="tiny muted">{dateTime(a.ts)}</div>
                      <div className="tiny" style={{ color: "var(--text-2)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {a.findings.causes[0]?.name ?? "—"}
                      </div>
                    </div>
                  </div>
                );
              })}
              {!list.data?.length && <Empty icon="camera" title="Ancora nessuna foto" text="La prima analisi comparirà qui." />}
            </div>
          </div>
        </div>
        <div className="stack" style={{ gap: 16 }}>
          {selected ? <Detail key={selected} id={selected} history={list.data ?? []}
                              onDeleted={() => { setSelected(undefined); qc.invalidateQueries({ queryKey: ["vision"] }); }} />
            : <div className="card"><Empty icon="leaf" title="Carica una foto per iniziare"
                                            text="Funziona anche dal telefono: si apre direttamente la fotocamera." /></div>}
        </div>
      </div>
    </>
  );
}

function UploadForm({ onDone }: { onDone: (id: string) => void }) {
  const zones = useZones();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [crop, setCrop] = useState("");
  const [zone, setZone] = useState("");
  const [notes, setNotes] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: async () => {
      const form = new FormData();
      form.append("file", file!);
      if (crop) form.append("crop", crop);
      if (zone) form.append("zone_id", zone);
      if (notes) form.append("notes", notes);
      const r = await fetch(`${API}/api/v1/vision/analyze`, { method: "POST", body: form });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Qualcosa è andato storto. Riprova.");
      return (await r.json()) as Analysis;
    },
    onSuccess: (a) => { setErr(null); setFile(null); setPreview(null); setNotes(""); onDone(a.id); },
    onError: (e: any) => setErr(e.message),
  });
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  return (
    <div className="stack">
      <label className="drop-zone">
        <input type="file" accept="image/*" capture="environment"
               onChange={(e) => { const f = e.target.files?.[0] ?? null; setFile(f); setPreview(f ? URL.createObjectURL(f) : null); }} />
        {preview ? <img src={preview} alt="anteprima" style={{ width: "100%", maxHeight: 220, objectFit: "cover", borderRadius: 10 }} />
          : <><Icon name="camera" size={28} /><div style={{ marginTop: 6, fontWeight: 600 }}>Scatta o scegli una foto</div>
              <div className="tiny muted">JPG o PNG, fino a 15 MB</div></>}
      </label>
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <input placeholder="Coltura (es. pomodoro)" value={crop} onChange={(e) => setCrop(e.target.value)} />
        <select value={zone} onChange={(e) => setZone(e.target.value)}>
          <option value="">Zona —</option>
          {(zones.data ?? []).map((z) => <option key={z.id} value={z.id}>{z.name}</option>)}
        </select>
      </div>
      <input placeholder="Note (da quando, quante piante…)" value={notes} onChange={(e) => setNotes(e.target.value)} />
      <button className="btn" disabled={!file || m.isPending} onClick={() => m.mutate()}>
        <Icon name={m.isPending ? "refresh" : "spark"} size={14} className={m.isPending ? "spin" : ""} />
        {m.isPending ? "Sto guardando la foto…" : "Analizza la pianta"}
      </button>
      {err && <div className="callout danger" style={{ margin: 0 }}><Icon name="alert" />{err}</div>}
    </div>
  );
}

function Detail({ id, history, onDeleted }: { id: string; history: Analysis[]; onDeleted: () => void }) {
  const q = useQuery({ queryKey: ["vision", id], queryFn: () => api.get<Analysis>(`/api/v1/vision/analyses/${id}`), refetchInterval: false });
  const [overlay, setOverlay] = useState(false);
  const del = useMutation({ mutationFn: () => api.del(`/api/v1/vision/analyses/${id}`), onSuccess: onDeleted });
  const a = q.data;
  if (!a) return <div className="card"><Empty icon="refresh" title="Caricamento…" /></div>;
  const f = a.findings;
  const [label, cls, icon] = OVERALL[f.overall] ?? OVERALL.unclear;

  return (
    <>
      <div className="grid cols-2">
        <div className="card" style={{ padding: 10 }}>
          <div className="row" style={{ marginBottom: 8 }}>
            <div className="tabs">
              <button className={!overlay ? "on" : ""} onClick={() => setOverlay(false)}>Foto</button>
              <button className={overlay ? "on" : ""} onClick={() => setOverlay(true)}>Mappa dei sintomi</button>
            </div>
            <span className="spacer" />
            <button className="btn danger sm" title="Elimina" onClick={() => confirm("Eliminare questa analisi?") && del.mutate()}><Icon name="trash" size={13} /></button>
          </div>
          <img src={`${API}/api/v1/vision/analyses/${id}/${overlay ? "overlay.png" : "image"}`} alt="pianta"
               style={{ width: "100%", borderRadius: 12, display: "block" }} />
          {overlay && (
            <div className="row tiny" style={{ marginTop: 8 }}>
              <span><span className="legend-swatch" style={{ background: "#33bf66" }} />verde sano</span>
              <span><span className="legend-swatch" style={{ background: "#ffd91a" }} />ingiallito</span>
              <span><span className="legend-swatch" style={{ background: "#f24d40" }} />secco / marrone</span>
              <span><span className="legend-swatch" style={{ background: "#5ccbff" }} />patina biancastra</span>
            </div>
          )}
        </div>
        <div className="card">
          <div className="card-head">
            <h3><Icon name="leaf" />{f.crop || f.ai?.plant_guess || "Pianta"}</h3>
            <span className={`badge badge-${cls}`}><Icon name={icon} size={11} />{label}</span>
          </div>
          {f.ai ? (
            <>
              <div className="lead">{f.ai.summary}</div>
              <div className="row" style={{ marginTop: 10 }}>
                {f.ai.visible_symptoms.map((s) => <span key={s} className="chip">{s}</span>)}
              </div>
              {f.ai.cannot_tell && (
                <div className="callout info" style={{ marginTop: 12, marginBottom: 0 }}><Icon name="info" />
                  <div><b>Cosa non si capisce dalla foto:</b> {f.ai.cannot_tell}</div></div>
              )}
            </>
          ) : (
            <div className="callout" style={{ marginBottom: 0 }}><Icon name="alert" /><div>
              L'intelligenza artificiale non era disponibile: le cause qui sotto vengono solo dai colori della foto.
            </div></div>
          )}
          <h4>Misurato nella foto</h4>
          <Metric label="Foglia verde" v={f.color.healthy_green} color="#34d17f" />
          <Metric label="Parte ingiallita" v={f.color.chlorotic_yellow} color="#e8b23a" />
          <Metric label="Parte secca o marrone" v={f.color.necrotic_brown} color="#ef5d5d" />
          {f.color.whitish_coating !== undefined && <Metric label="Patina biancastra (oidio, polvere o riflesso?)" v={f.color.whitish_coating} color="#5ccbff" />}
          {f.color.warnings.map((w) => <div key={w} className="small" style={{ color: "var(--warn)", marginTop: 6 }}><Icon name="alert" size={13} /> {w}</div>)}
        </div>
      </div>

      {!f.engine && <Reanalyze id={id} />}
      {!!f.questions?.length && <QuestionsCard id={id} questions={f.questions} answers={f.answers ?? {}} />}

      <div className="card">
        <div className="card-head">
          <h3><Icon name="sprout" />Cause possibili e cosa fare</h3>
          {f.ai_model && <span className="chip tiny">AI</span>}
          {!!Object.keys(f.answers ?? {}).length && <span className="chip tiny"><Icon name="check" size={11} /> con le tue risposte</span>}
        </div>
        <div className="stack" style={{ gap: 18 }}>
          {TIERS.map((t) => {
            const list = f.causes.filter((c) => tierOf(c) === t.id);
            if (!list.length) return null;
            return (
              <div key={t.id} className={`tier-group tier-${t.id}`}>
                <div className="tier-head"><span className="tier-dot" /><b>{t.title}</b><span className="tiny muted">{t.hint}</span></div>
                <div className="stack" style={{ gap: 10 }}>
                  {list.map((c) => <CauseCard key={c.id} c={c} open={t.id === "probable" && c === list[0]} />)}
                </div>
              </div>
            );
          })}
          {!f.causes.length && (
            <div className="callout" style={{ margin: 0 }}><Icon name="camera" /><div>
              Dalla foto non si vede bene una pianta vera. Rifalla da vicino, con luce del giorno, con la parte malata che
              riempie quasi tutta l'immagine.
            </div></div>
          )}
        </div>
        <div className="tiny muted" style={{ marginTop: 12 }}>{f.disclaimer}</div>
      </div>

      {f.plant_model && <ModelCard m={f.plant_model} />}
      <div className="grid cols-2">
        <ContextCard f={f} />
        <VerifyCard a={a} />
      </div>
      <TrendCard history={history} crop={f.crop} />
    </>
  );
}

function Metric({ label, v, color }: { label: string; v: number; color: string }) {
  return (
    <div style={{ marginBottom: 9 }}>
      <div className="row small"><span>{label}</span><span className="spacer" /><b>{pct(v, 1)}</b></div>
      <div className="bar"><span style={{ width: `${Math.min(100, v * 100)}%`, background: color }} /></div>
    </div>
  );
}

function CauseCard({ c, open }: { c: Cause; open: boolean }) {
  const tier = tierOf(c);
  const plausible = tier !== "unlikely";
  const [tab, setTab] = useState<"fix" | "natural" | "prevent" | "verify">(plausible ? "fix" : "verify");
  const [expanded, setExpanded] = useState(open);
  const remedies = useRemedies();
  const order = plausible ? remedies.data?.by_cause[c.id] ?? [] : [];
  const natural = order.map((id) => remedies.data?.remedies.find((r) => r.id === id)).filter((r): r is NonNullable<typeof r> => !!r);
  const items = tab === "natural" ? [] : c[tab];
  const pro = (c.evidence ?? []).filter((e) => e.effect === "supports");
  const con = (c.evidence ?? []).filter((e) => e.effect === "weakens");
  const neutral = (c.evidence ?? []).filter((e) => e.effect === "neutral");
  const prob = c.probability ?? { high: 0.7, medium: 0.45, low: 0.2 }[c.likelihood];
  return (
    <div className={`cause-card tier-${tier}`}>
      <div className="row" style={{ cursor: "pointer", flexWrap: "nowrap" }} onClick={() => setExpanded(!expanded)}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <b style={{ fontSize: 15 }}>{c.name}</b>
          <div className="prob-row">
            <div className="prob-bar"><span style={{ width: `${Math.round(prob * 100)}%` }} /></div>
            <span className="small"><b>{Math.round(prob * 100)}%</b> <span className="muted">compatibilità</span></span>
            {plausible && URGENCY[c.urgency] && <span className={`badge badge-${c.urgency === "high" ? "high" : "neutral"}`}>{URGENCY[c.urgency]}</span>}
          </div>
        </div>
        <Icon name={expanded ? "minus" : "plus"} size={16} />
      </div>

      {(pro.length > 0 || con.length > 0) && (
        <div className="evidence-grid">
          {pro.length > 0 && (
            <div>
              <div className="tiny muted ev-title">Cosa lo fa pensare</div>
              {pro.map((e) => <EvidenceRow key={e.text} e={e} />)}
            </div>
          )}
          {con.length > 0 && (
            <div>
              <div className="tiny muted ev-title">Cosa non torna</div>
              {con.map((e) => <EvidenceRow key={e.text} e={e} />)}
            </div>
          )}
        </div>
      )}
      {!c.evidence && c.why && <div className="small" style={{ marginTop: 6, color: "var(--text-2)" }}>{c.why}</div>}

      {expanded && (
        <div style={{ marginTop: 12 }}>
          {c.evidence && c.why && <div className="small muted mb"><b>Parere dell'AI sulla foto:</b> {c.why}</div>}
          {neutral.map((e) => <div key={e.text} className="tiny muted mb"><Icon name="info" size={11} /> {e.text}</div>)}
          <div className="small muted mb"><b>Come si riconosce:</b> {c.signs}</div>
          <div className="tabs" style={{ marginBottom: 10 }}>
            {plausible && <button className={tab === "fix" ? "on" : ""} onClick={() => setTab("fix")}>Cura</button>}
            {natural.length > 0 && <button className={tab === "natural" ? "on" : ""} onClick={() => setTab("natural")}><Icon name="leaf" size={14} /> Rimedi naturali ({natural.length})</button>}
            {plausible && <button className={tab === "prevent" ? "on" : ""} onClick={() => setTab("prevent")}>Prevenzione</button>}
            <button className={tab === "verify" ? "on" : ""} onClick={() => setTab("verify")}>Come esserne sicuri</button>
          </div>
          {tab === "fix" && <div className="tiny muted mb">Interventi da fare solo se la causa è confermata.</div>}
          {tab === "prevent" && <div className="tiny muted mb">Per evitare che il problema si ripeta, anche il prossimo anno.</div>}
          {!plausible && <div className="tiny muted mb">Causa poco probabile: non suggeriamo cure, solo come escluderla del tutto.</div>}
          {tab === "natural" ? (
            <>
              <div className="grid cols-2" style={{ gap: 10 }}>
                {natural.map((r) => <RemedyCard key={r.id} r={r} compact />)}
              </div>
              <div className="tiny muted" style={{ marginTop: 8 }}>Tutti i rimedi sono nella pagina <Link to="/remedies">Rimedi naturali</Link>.</div>
            </>
          ) : (
            <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.65 }}>
              {items.map((t) => <li key={t}>{t}</li>)}
              {!items.length && <li className="muted">—</li>}
            </ul>
          )}
          <div className="tiny" style={{ marginTop: 10 }}>
            Fonte: {c.sources.map((s) => <a key={s.url} href={s.url} target="_blank" rel="noreferrer">{s.title} ↗</a>)}
          </div>
        </div>
      )}
    </div>
  );
}

function EvidenceRow({ e }: { e: Evidence }) {
  return (
    <div className={`ev ev-${e.effect}`}>
      <Icon name={e.effect === "supports" ? "check" : "minus"} size={12} />
      <span>{e.text}</span>
      <span className="ev-origin">{ORIGIN_IT[e.origin] ?? e.origin}</span>
    </div>
  );
}

function QuestionsCard({ id, questions, answers }: { id: string; questions: Question[]; answers: Record<string, string> }) {
  const qc = useQueryClient();
  const [picked, setPicked] = useState<Record<string, string>>({});
  const send = useMutation({
    mutationFn: () => api.post(`/api/v1/vision/analyses/${id}/answers`, { answers: picked }),
    onSuccess: () => { setPicked({}); qc.invalidateQueries({ queryKey: ["vision"] }); },
  });
  const n = Object.keys(picked).length;
  return (
    <div className="card questions-card">
      <div className="card-head">
        <h3><Icon name="info" />La foto non basta: aiutami a capire meglio</h3>
        {!!Object.keys(answers).length && <span className="tiny muted">{Object.keys(answers).length} risposte già date</span>}
      </div>
      <div className="small muted mb">Rispondi solo a quello che sai: ogni risposta rende la diagnosi più precisa.</div>
      <div className="stack" style={{ gap: 12 }}>
        {questions.map((q) => (
          <div key={q.id}>
            <div className="small" style={{ fontWeight: 600, marginBottom: 6 }}>{q.text}</div>
            <div className="row" style={{ gap: 6 }}>
              {q.options.map((o) => (
                <button key={o.value} className={`answer ${picked[q.id] === o.value ? "on" : ""}`}
                        onClick={() => setPicked((p) => ({ ...p, [q.id]: p[q.id] === o.value ? undefined! : o.value }))}>
                  {o.label}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <button className="btn" style={{ marginTop: 14 }} disabled={!n || send.isPending}
              onClick={() => { Object.keys(picked).forEach((k) => picked[k] === undefined && delete picked[k]); send.mutate(); }}>
        <Icon name={send.isPending ? "refresh" : "check"} size={14} className={send.isPending ? "spin" : ""} />
        {send.isPending ? "Ricalcolo…" : n ? `Aggiorna la diagnosi (${n})` : "Scegli almeno una risposta"}
      </button>
    </div>
  );
}

function Reanalyze({ id }: { id: string }) {
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: () => api.post(`/api/v1/vision/analyses/${id}/reanalyze`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["vision"] }),
  });
  return (
    <div className="callout info" style={{ margin: 0 }}>
      <Icon name="refresh" />
      <div style={{ flex: 1 }}>Questa analisi è stata fatta con la versione precedente della diagnosi.</div>
      <button className="btn sm" disabled={m.isPending} onClick={() => m.mutate()}>
        {m.isPending ? "Analizzo…" : "Rianalizza la foto"}
      </button>
    </div>
  );
}

function ModelCard({ m }: { m: PlantModel }) {
  return (
    <div className="card">
      <div className="card-head">
        <h3><Icon name="brain" />Modello AGROAI addestrato sui dataset</h3>
        <span className="chip tiny">{m.version}</span>
      </div>
      {m.applicable && m.notes.length > 0 && (
        <div className="callout" style={{ margin: "0 0 10px" }}><Icon name="info" /><div className="small">{m.notes.join(" ")}</div></div>
      )}
      {m.applicable ? (
        <div className="stack" style={{ gap: 6 }}>
          {m.top.slice(0, 3).map((t) => (
            <div key={t.label}>
              <div className="row small"><span>{t.name}</span><span className="spacer" /><b>{Math.round(t.score * 100)}%</b></div>
              <div className="bar"><span style={{ width: `${t.score * 100}%` }} /></div>
            </div>
          ))}
        </div>
      ) : (
        <div className="small muted">{m.notes.join(" ")} Per questa foto la diagnosi si basa sull'analisi visiva e sulle tue risposte.</div>
      )}
      <div className="tiny muted" style={{ marginTop: 10 }}>
        Su foto reali mai viste durante l'addestramento indovina la classe esatta nel {Math.round(m.real_photo_accuracy * 100)}% dei casi
        (nel {Math.round(m.real_photo_top3 * 100)}% è tra le prime 3) e la causa nel {Math.round(m.cause_accuracy * 100)}%.
        Per questo conta come un indizio in più, non come verdetto. Addestrato su: {m.datasets.join(", ")}.
      </div>
    </div>
  );
}

function ContextCard({ f }: { f: Findings }) {
  const rows: [string, string, string][] = [
    ["soil_moisture", "Umidità del terreno", "%"], ["soil_ph", "pH del terreno", ""],
    ["air_temperature", "Temperatura dell'aria", "°C"], ["air_humidity", "Umidità dell'aria", "%"],
  ];
  return (
    <div className="card">
      <h3><Icon name="sensors" />Dati del campo usati per il controllo</h3>
      <table><tbody>
        {rows.map(([k, label, unit]) => (
          <tr key={k}><td className="muted">{label}</td>
            <td>{f.context[k] != null ? `${num(f.context[k] as number)} ${unit}` : "—"}</td>
            <td>{f.context.sources?.[k] && <ProvenanceBadge source={f.context.sources[k]} />}</td></tr>
        ))}
      </tbody></table>
      {f.soil && (
        <div className={`soil-box soil-${f.soil.usable ? f.soil.status : "unused"}`}>
          <div className="small"><b>Umidità del terreno: {f.soil.status_label}</b></div>
          <div className="tiny muted">
            {f.soil.texture_label ? `Terreno ${f.soil.texture_label}` : "Tipo di terreno non indicato"} · affidabilità del dato: {f.soil.reliability}
          </div>
          <ul className="tiny" style={{ margin: "6px 0 0", paddingLeft: 16, color: "var(--text-2)" }}>
            {f.soil.notes.map((n) => <li key={n}>{n}</li>)}
          </ul>
        </div>
      )}
      <div className="tiny muted" style={{ marginTop: 8 }}>
        I valori «Demo» sono di prova e non vengono usati come prova per la diagnosi.
      </div>
    </div>
  );
}

function VerifyCard({ a }: { a: Analysis }) {
  const qc = useQueryClient();
  const causes = useQuery({ queryKey: ["vision-causes"], queryFn: () => api.get<{ id: string; name: string }[]>("/api/v1/vision/causes"), refetchInterval: false, staleTime: Infinity });
  const [actual, setActual] = useState("");
  const [notes, setNotes] = useState("");
  const m = useMutation({
    mutationFn: (verdict: string) => api.post(`/api/v1/vision/analyses/${a.id}/verify`, { verdict, actual_cause: actual || null, notes: notes || null }),
    onSuccess: () => { setNotes(""); qc.invalidateQueries({ queryKey: ["vision", a.id] }); },
  });
  return (
    <div className="card">
      <h3><Icon name="check" />Com'era davvero?</h3>
      <div className="small muted mb">Dopo il controllo in campo dicci se la valutazione era giusta: così AGROAI impara dalla tua azienda.</div>
      <div className="stack">
        <select value={actual} onChange={(e) => setActual(e.target.value)}>
          <option value="">Causa vera (se la conosci)</option>
          {(causes.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <input placeholder="Note (esito analisi, cosa hai visto…)" value={notes} onChange={(e) => setNotes(e.target.value)} />
        <div className="row">
          <button className="btn sm" onClick={() => m.mutate("confirmed")}>Era giusta</button>
          <button className="btn secondary sm" onClick={() => m.mutate("partly")}>In parte</button>
          <button className="btn ghost sm" onClick={() => m.mutate("wrong")}>Sbagliata</button>
        </div>
      </div>
      {a.verifications?.map((v) => (
        <div key={v.created_at} className="small" style={{ marginTop: 10, color: "var(--text-2)" }}>
          <Icon name="check" size={12} /> {dateTime(v.created_at)}: la valutazione {VERDICT_IT[v.verdict] ?? v.verdict}
          {v.actual_cause ? ` — causa vera: ${causes.data?.find((c) => c.id === v.actual_cause)?.name ?? v.actual_cause}` : ""}
          {v.notes ? ` — ${v.notes}` : ""}
        </div>
      ))}
    </div>
  );
}

function TrendCard({ history, crop }: { history: Analysis[]; crop: string | null }) {
  const data = useMemo(() => history
    .filter((h) => !crop || h.findings.crop === crop)
    .slice().reverse()
    .map((h) => ({
      t: new Date(h.ts).toLocaleDateString("it-IT", { day: "2-digit", month: "short" }),
      giallo: +(h.findings.color.chlorotic_yellow * 100).toFixed(1),
      secco: +(h.findings.color.necrotic_brown * 100).toFixed(1),
    })), [history, crop]);
  if (data.length < 2) return null;
  return (
    <div className="card">
      <h3><Icon name="chart" />Come sta cambiando {crop ? `· ${crop}` : ""}</h3>
      <div style={{ height: 200 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 5, right: 10, left: -15, bottom: 0 }}>
            <CartesianGrid stroke="#e2ebe5" strokeDasharray="3 3" />
            <XAxis dataKey="t" stroke="#7f988a" fontSize={11} />
            <YAxis stroke="#7f988a" fontSize={11} unit="%" />
            <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e2ebe5", borderRadius: 12, boxShadow: "0 8px 24px rgba(16,42,28,.08)" }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line dataKey="giallo" name="Ingiallito %" stroke="#e8b23a" strokeWidth={2} />
            <Line dataKey="secco" name="Secco %" stroke="#ef5d5d" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="tiny muted">Per un confronto utile fotografa le stesse piante, dalla stessa angolazione e con luce simile.</div>
    </div>
  );
}
