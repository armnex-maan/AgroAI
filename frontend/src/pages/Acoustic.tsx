import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Area, CartesianGrid, Line, ComposedChart, ResponsiveContainer, Tooltip, XAxis, YAxis, ReferenceLine,
} from "recharts";
import { api } from "../api/client";
import {
  useAnalyze, useDetections, useEngines, useLabels, useLabelSummary, useModels, useProfiles,
  useRecordings, useSpectrum, useWaveform,
} from "../api/hooks";
import { Detection, Identification, Label, MLModelInfo, Recording, Waveform } from "../api/types";
import { Icon } from "../components/Icon";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { Empty, PageHeader, Steps } from "../components/ui";
import BirdDeterrent from "../components/BirdDeterrent";
import { ago, dateTime, num, pct, SOUND_GROUP, VERDICT } from "../lib/it";

const API = import.meta.env.VITE_API_URL || "";
const TAXON_ICON: Record<string, string> = { bird: "bird", insect: "bug", amphibian: "drop", mammal: "paw", reptile: "leaf" };
const GROUP_COLORS: Record<string, string> = {
  bird: "#34d17f", poultry_waterfowl: "#b8e05c", insect: "#e8b23a", amphibian: "#5cb8e0", rodent: "#ef8f5d",
  dog_canid: "#ef5d5d", cat_feline: "#e07aa8", livestock: "#c49a6c", wild_animal: "#9d8cf2",
  water_irrigation: "#5ca8ef", wind_vegetation: "#7f988a", machinery_vehicle: "#a0a0a0", human: "#d0d0d0",
  silence: "#2a3a33", other: "#3a4a43",
};

export default function Acoustic() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | undefined>();
  const [tab, setTab] = useState<"analysis" | "model" | "birds">("analysis");
  const recordings = useRecordings();
  const engines = useEngines();

  useEffect(() => {
    if (!selected && recordings.data?.length) setSelected(recordings.data[0].id);
  }, [recordings.data, selected]);

  const refresh = (id?: string) => {
    qc.invalidateQueries({ queryKey: ["recordings"] });
    if (id) setSelected(id);
  };

  return (
    <>
      <PageHeader icon="mic" title="Suoni e animali" tone="sky"
                  subtitle="Carica una registrazione del campo: AGROAI riconosce oltre 14.000 specie (uccelli, insetti, rane, mammiferi) e distingue i rumori come irrigazione o trattori.">
        <a className="btn ghost sm" href={`${API}/api/v1/audio/export/dataset.csv`}><Icon name="download" size={14} />Scarica etichette</a>
      </PageHeader>
      <EngineBar />
      <div className="tabs mb">
        <button className={tab === "analysis" ? "on" : ""} onClick={() => setTab("analysis")}>Registrazioni</button>
        <button className={tab === "model" ? "on" : ""} onClick={() => setTab("model")}>Insegna ad AGROAI (es. talpe)</button>
        <button className={tab === "birds" ? "on" : ""} onClick={() => setTab("birds")}><Icon name="bird" size={14} /> Allontana uccelli</button>
      </div>

      {tab === "birds" ? <BirdDeterrent /> : tab === "model" ? <ModelPanel /> : (
        <div className="split">
          <div className="stack">
            <div className="card">
              <h3><Icon name="upload" />Carica una registrazione</h3>
              <UploadForm onDone={refresh} />
            </div>
            <div className="card">
              <h3><Icon name="spark" />Non hai un file? Prova un suono di esempio</h3>
              <GenerateForm onDone={refresh} />
            </div>
            <div className="card">
              <div className="card-head"><h3>Registrazioni</h3><span className="muted small">{recordings.data?.length ?? 0}</span></div>
              <div className="scroll stack" style={{ maxHeight: 520, gap: 4 }}>
                {(recordings.data ?? []).map((r) => (
                  <div key={r.id} className={`list-item ${selected === r.id ? "active" : ""}`} onClick={() => setSelected(r.id)}>
                    <div className="row">
                      <b className="small">{dateTime(r.ts)}</b><span className="spacer" />
                      <ProvenanceBadge source={r.source} />
                    </div>
                    <div className="small" style={{ marginTop: 4, color: "var(--text-2)" }}>
                      {r.summary ?? r.notes ?? `${num(r.duration_s)} secondi`}
                    </div>
                    {!r.verdict && <span className="badge badge-neutral" style={{ marginTop: 4 }}>da analizzare</span>}
                  </div>
                ))}
                {!recordings.data?.length && <Empty icon="mic" title="Nessuna registrazione" text="Carica un file o prova un suono di esempio." />}
              </div>
            </div>
          </div>
          <div className="stack" style={{ gap: 16 }}>
            {selected
              ? <RecordingDetail key={selected} id={selected} all={recordings.data ?? []}
                                 onDeleted={() => { setSelected(undefined); refresh(); }} />
              : <div className="card"><Empty icon="mic" title="Scegli una registrazione" /></div>}
          </div>
        </div>
      )}
      {engines.data && !engines.data.yamnet.available && (
        <div className="callout info" style={{ marginTop: 16 }}><Icon name="info" /><div>
          Il riconoscimento dei suoni (YAMNet) non è disponibile in questo momento. L'analisi delle frequenze e del sottosuolo funziona lo stesso.
        </div></div>
      )}
    </>
  );
}

function EngineBar() {
  const e = useEngines().data;
  if (!e) return null;
  const chip = (ok: boolean, name: string, detail: string) => (
    <span className="chip"><span className={`dot ${ok ? "ok" : ""}`} />{name}<span className="muted tiny">{detail}</span></span>
  );
  return (
    <div className="row mb">
      {chip(!!e.perch?.available, "Specie animali (Perch 2.0)", e.perch?.available ? `${(e.perch.species ?? 0).toLocaleString("it-IT")} specie` : "spento")}
      {chip(e.yamnet.available, "Tipo di suono (YAMNet)", e.yamnet.available ? "attivo" : "spento")}
      {e.birdnet.available && chip(true, "BirdNET", "attivo")}
      {chip(e.farm_model.active, "Modello della tua azienda", e.farm_model.active ? `attivo: ${e.farm_model.labels.join(", ")}` : "non ancora addestrato")}
      {chip(true, "Sottosuolo", "sperimentale")}
    </div>
  );
}

function GenerateForm({ onDone }: { onDone: (id: string) => void }) {
  const profiles = useProfiles();
  const [profile, setProfile] = useState("bird");
  const m = useMutation({
    mutationFn: () => api.post<Recording>("/api/v1/audio/generate-sample", { profile, duration_s: 4 }),
    onSuccess: (r) => onDone(r.id),
  });
  return (
    <div className="stack">
      <select value={profile} onChange={(e) => setProfile(e.target.value)}>
        {(profiles.data ?? []).map((p) => <option key={p.name} value={p.name}>{p.description}</option>)}
      </select>
      <button className="btn secondary" onClick={() => m.mutate()} disabled={m.isPending}>
        {m.isPending ? "Creo il suono…" : "Crea suono di esempio"}
      </button>
      <div className="tiny muted">Sono suoni artificiali (etichetta «Demo»), servono solo a provare il sistema.</div>
    </div>
  );
}

function UploadForm({ onDone }: { onDone: (id: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [notes, setNotes] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!file) return;
    setBusy(true); setErr(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("source", "manual");
      if (notes) form.append("notes", notes);
      const r = await fetch(`${API}/api/v1/audio/upload`, { method: "POST", body: form });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? "Caricamento non riuscito.");
      onDone(((await r.json()) as Recording).id);
      setFile(null); setNotes("");
    } catch (e: any) { setErr(String(e.message ?? e)); } finally { setBusy(false); }
  };
  return (
    <div className="stack">
      <label className="drop-zone">
        <input type="file" accept=".wav,.flac,.ogg,audio/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <Icon name="mic" size={26} />
        <div style={{ marginTop: 6, fontWeight: 600 }}>{file ? file.name : "Scegli un file audio"}</div>
        <div className="tiny muted">WAV, FLAC o OGG — anche dal registratore del telefono</div>
      </label>
      <input placeholder="Note (dove, a che ora, vicino a cosa…)" value={notes} onChange={(e) => setNotes(e.target.value)} />
      <button className="btn" onClick={submit} disabled={!file || busy}>{busy ? "Carico…" : "Carica"}</button>
      {err && <div className="callout danger" style={{ margin: 0 }}><Icon name="alert" />{err}</div>}
      <div className="tiny muted">Registrazioni di uccelli gratuite e legali: xeno-canto.org</div>
    </div>
  );
}

function RecordingDetail({ id, all, onDeleted }: { id: string; all: Recording[]; onDeleted: () => void }) {
  const qc = useQueryClient();
  const rec = all.find((r) => r.id === id);
  const detections = useDetections(id);
  const waveform = useWaveform(id);
  const labels = useLabels(id);
  const analyze = useAnalyze();
  const [sel, setSel] = useState<[number, number] | null>(null);
  const [details, setDetails] = useState(false);
  const del = useMutation({ mutationFn: () => api.del(`/api/v1/audio/recordings/${id}`), onSuccess: onDeleted });

  const byModel = useMemo(() => {
    const m: Record<string, Detection> = {};
    for (const d of detections.data ?? []) m[d.model] = d;
    return m;
  }, [detections.data]);
  const ident = byModel["identification"]?.evidence as Identification | undefined;
  const refreshLabels = () => { qc.invalidateQueries({ queryKey: ["labels", id] }); qc.invalidateQueries({ queryKey: ["label-summary"] }); };

  if (!rec) return null;
  return (
    <>
      <div className="card">
        <div className="card-head">
          <div>
            <h3 style={{ margin: 0 }}>{rec.notes ?? "Registrazione"}</h3>
            <div className="row small muted" style={{ marginTop: 4 }}>
              {num(rec.duration_s)} secondi · {dateTime(rec.ts)} <ProvenanceBadge source={rec.source} />
            </div>
          </div>
          <div className="row">
            <button className="btn" onClick={() => analyze.mutate(id)} disabled={analyze.isPending}>
              <Icon name={analyze.isPending ? "refresh" : "play"} size={14} className={analyze.isPending ? "spin" : ""} />
              {analyze.isPending ? "Sto ascoltando…" : ident ? "Analizza di nuovo" : "Riconosci i suoni"}
            </button>
            <button className="btn danger sm" title="Elimina" onClick={() => confirm("Eliminare questa registrazione e le sue etichette?") && del.mutate()}>
              <Icon name="trash" size={14} />
            </button>
          </div>
        </div>
        <audio controls src={`${API}/api/v1/audio/recordings/${id}/file`} style={{ width: "100%", height: 36 }} />
        {analyze.isError && <div className="callout danger" style={{ marginTop: 12 }}><Icon name="alert" />Analisi non riuscita, riprova.</div>}
      </div>

      {ident ? <IdentificationCard ident={ident} /> : (
        <div className="callout info"><Icon name="info" />Premi <b>Riconosci i suoni</b> per scoprire cosa si sente in questa registrazione.</div>
      )}

      <div className="card">
        <div className="card-head">
          <h3>Forma del suono ed etichette</h3>
          <span className="tiny muted">Trascina sul grafico per scegliere un pezzo da etichettare</span>
        </div>
        <WaveformCanvas wf={waveform.data} labels={labels.data ?? []} selection={sel} onSelect={setSel} />
        <LabelForm recordingId={id} duration={rec.duration_s} selection={sel} onSaved={() => { setSel(null); refreshLabels(); }} />
        <div className="row" style={{ marginTop: 8 }}>
          {(labels.data ?? []).map((l) => (
            <span key={l.id} className="chip">
              <b>{l.label}</b> {num(l.start_s)}–{num(l.end_s ?? rec.duration_s)} s
              <a href="#" title="Elimina etichetta" onClick={async (e) => { e.preventDefault(); await api.del(`/api/v1/audio/labels/${l.id}`); refreshLabels(); }}>×</a>
            </span>
          ))}
        </div>
      </div>

      <div className="card">
        <h3>Spettrogramma <span className="tiny muted" style={{ fontWeight: 400 }}>— in alto i suoni acuti, in basso i gravi; più chiaro = più forte</span></h3>
        <img src={`${API}/api/v1/audio/recordings/${id}/spectrogram.png`} alt="spettrogramma" style={{ width: "100%", borderRadius: 12, display: "block" }} />
      </div>

      <SpectrumCard id={id} all={all} spectral={byModel["spectral"]?.evidence} />

      <button className="btn ghost" onClick={() => setDetails(!details)}>
        {details ? "Nascondi i dettagli tecnici ▴" : "Mostra i dettagli tecnici dei modelli ▾"}
      </button>
      {details && (
        <div className="grid cols-2">
          {byModel["perch"] && <PerchCard det={byModel["perch"]} />}
          {byModel["yamnet"] && <YamnetCard det={byModel["yamnet"]} duration={rec.duration_s} />}
          {byModel["underground-experimental"] && <UndergroundCard det={byModel["underground-experimental"]} />}
          {byModel["birdnet"] && <BirdnetCard det={byModel["birdnet"]} />}
          {byModel["farm-model"] && <FarmModelCard det={byModel["farm-model"]} />}
        </div>
      )}
    </>
  );
}

function IdentificationCard({ ident }: { ident: Identification }) {
  const tone = ident.verdict === "probable" ? "green" : ident.verdict === "possible" ? "amber" : "sky";
  const icon = ident.verdict === "other_sound" ? "mic" : ident.verdict === "unknown" ? "info" : "check";
  return (
    <div className="card">
      <div className="row" style={{ flexWrap: "nowrap", alignItems: "flex-start" }}>
        <div className={`page-icon tone-${tone}`}><Icon name={icon} size={22} /></div>
        <div>
          <div className="tiny muted">Cosa si sente</div>
          <div className="verdict">{ident.summary}</div>
          {ident.verdict === "other_sound" && <div className="small muted" style={{ marginTop: 4 }}>Nessun verso animale abbastanza chiaro: il suono principale è un rumore dell'ambiente.</div>}
          {!!ident.deterrents_triggered?.length && <div className="small" style={{ marginTop: 6, color: "var(--warn)" }}><Icon name="bell" size={13} /> Attivati {ident.deterrents_triggered.length} dissuasori simulati (nessun suono reale emesso).</div>}
        </div>
      </div>
      <div className="grid cols-2" style={{ marginTop: 14 }}>
        {ident.candidates.map((c, i) => (
          <div key={i} className={`candidate ${c.level}`}>
            <div className="row" style={{ alignItems: "flex-start", flexWrap: "nowrap" }}>
              <div style={{ flex: 1 }}>
                <b style={{ fontSize: 16 }}>{c.common_name ?? c.label}</b>
                {c.scientific_name && <div className="small muted"><i>{c.scientific_name}</i></div>}
              </div>
              <span className={`badge badge-${c.level}`}>{VERDICT[c.level]}</span>
            </div>
            <div className="row" style={{ marginTop: 6 }}>
              {c.taxon_group_it && <span className="chip tiny"><Icon name={TAXON_ICON[c.taxon_group ?? ""] ?? "paw"} size={12} /> {c.taxon_group_it}</span>}
              <span className="chip tiny">{c.source}</span>
            </div>
            <div className="bar" style={{ margin: "8px 0" }}><span style={{ width: `${Math.min(100, c.score * 100)}%` }} /></div>
            <div className="small" style={{ color: "var(--text-2)" }}>{c.evidence}</div>
            <div className="small" style={{ marginTop: 8 }}><b style={{ color: "var(--accent)" }}>Come verificare:</b> {c.verification}</div>
          </div>
        ))}
      </div>
      {ident.species_model?.available && (
        <div className="small muted" style={{ marginTop: 10 }}>
          {ident.species_model.local_filter
            ? <>Confrontato con le <b>{ident.species_model.local_species?.toLocaleString("it-IT")} specie osservate nella tua zona</b> (iNaturalist, raggio 250 km)
                {ident.species_model.excluded_not_local ? `; escluse ${ident.species_model.excluded_not_local} specie che qui non vivono` : ""}.</>
            : "Lista delle specie della zona non disponibile (serve internet la prima volta): confrontato con tutte le specie del mondo."}
        </div>
      )}
      {!!ident.rejected?.length && (
        <details className="small" style={{ marginTop: 8 }}>
          <summary style={{ cursor: "pointer", color: "var(--text-dim)" }}>Ipotesi scartate ({ident.rejected.length}) e perché</summary>
          <ul style={{ margin: "6px 0 0", paddingLeft: 18, color: "var(--text-2)" }}>
            {ident.rejected.map((r, i) => <li key={i}><b>{r.label}</b>: {r.reason}</li>)}
          </ul>
        </details>
      )}
      {ident.context.length > 0 && (
        <div className="row" style={{ marginTop: 12 }}>
          <span className="small muted">Altri suoni:</span>
          {ident.context.map((c) => <span key={c.group} className="chip">{c.description}</span>)}
        </div>
      )}
      <div className="tiny muted" style={{ marginTop: 10 }}>
        «Probabile» e «Possibile» si basano sui punteggi dei modelli, che non sono probabilità vere: conferma sempre sul campo.
      </div>
    </div>
  );
}

function WaveformCanvas({ wf, labels, selection, onSelect }: {
  wf?: Waveform; labels: Label[]; selection: [number, number] | null; onSelect: (s: [number, number] | null) => void;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const drag = useRef<number | null>(null);
  useEffect(() => {
    const c = ref.current;
    if (!c || !wf) return;
    const dpr = window.devicePixelRatio || 1;
    const w = c.clientWidth, h = 130;
    c.width = w * dpr; c.height = h * dpr;
    const ctx = c.getContext("2d")!;
    ctx.scale(dpr, dpr);
    ctx.fillStyle = "#050c09"; ctx.fillRect(0, 0, w, h);
    const x = (t: number) => (t / wf.duration_s) * w;
    for (const l of labels) {
      ctx.fillStyle = "rgba(92,168,239,.16)";
      ctx.fillRect(x(l.start_s), 0, x(l.end_s ?? wf.duration_s) - x(l.start_s), h);
      ctx.fillStyle = "#5ca8ef"; ctx.font = "11px Inter, sans-serif"; ctx.fillText(l.label, x(l.start_s) + 4, 13);
    }
    if (selection) {
      ctx.fillStyle = "rgba(52,209,127,.2)";
      ctx.fillRect(x(selection[0]), 0, x(selection[1]) - x(selection[0]), h);
    }
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, "#34d17f"); grad.addColorStop(.5, "#1fa463"); grad.addColorStop(1, "#34d17f");
    ctx.strokeStyle = grad; ctx.lineWidth = 1;
    ctx.beginPath();
    const n = wf.min_max.length / 2;
    for (let i = 0; i < n; i++) {
      const px = (i / n) * w;
      ctx.moveTo(px, h / 2 - wf.min_max[i * 2 + 1] * (h / 2 - 6));
      ctx.lineTo(px, h / 2 - wf.min_max[i * 2] * (h / 2 - 6));
    }
    ctx.stroke();
    ctx.fillStyle = "#7f988a"; ctx.font = "10px Inter, sans-serif";
    for (let s = 0; s <= wf.duration_s; s += Math.max(1, Math.round(wf.duration_s / 8))) ctx.fillText(`${s}s`, x(s) + 2, h - 4);
  }, [wf, labels, selection]);

  const toT = (clientX: number) => {
    const r = ref.current!.getBoundingClientRect();
    return Math.max(0, Math.min(wf?.duration_s ?? 0, ((clientX - r.left) / r.width) * (wf?.duration_s ?? 0)));
  };
  const move = (clientX: number) => {
    if (drag.current !== null) { const t = toT(clientX); onSelect([Math.min(drag.current, t), Math.max(drag.current, t)]); }
  };
  return (
    <canvas ref={ref} style={{ width: "100%", height: 130, borderRadius: 12, cursor: "crosshair", display: "block", touchAction: "none" }}
            onPointerDown={(e) => { drag.current = toT(e.clientX); onSelect(null); }}
            onPointerMove={(e) => move(e.clientX)}
            onPointerUp={() => { drag.current = null; }}
            onPointerLeave={() => { drag.current = null; }} />
  );
}

const SUGGESTED = ["talpa", "uccello", "insetto", "roditore", "irrigazione", "macchinario", "vento", "pioggia", "persone", "rumore di fondo"];

function LabelForm({ recordingId, duration, selection, onSaved }: {
  recordingId: string; duration: number; selection: [number, number] | null; onSaved: () => void;
}) {
  const [label, setLabel] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const start = selection?.[0] ?? 0;
  const end = selection?.[1] ?? duration;
  const save = async () => {
    setErr(null);
    try {
      await api.post(`/api/v1/audio/recordings/${recordingId}/labels`, { label, start_s: +start.toFixed(2), end_s: +end.toFixed(2) });
      setLabel(""); onSaved();
    } catch (e: any) {
      try { setErr(JSON.parse(e.message.slice(e.message.indexOf("{"))).detail); } catch { setErr(e.message || "Etichetta non salvata."); }
    }
  };
  return (
    <div className="row" style={{ marginTop: 10 }}>
      <input list="label-suggestions" placeholder="Cosa si sente? (es. talpa)" value={label} onChange={(e) => setLabel(e.target.value)} style={{ width: 210 }} />
      <datalist id="label-suggestions">{SUGGESTED.map((s) => <option key={s} value={s} />)}</datalist>
      <span className="small muted">{selection ? `dal secondo ${num(start)} al ${num(end)}` : "tutta la registrazione"}</span>
      <button className="btn secondary sm" disabled={!label.trim()} onClick={save}><Icon name="plus" size={13} />Aggiungi etichetta</button>
      {err && <span className="small" style={{ color: "var(--danger)" }}>{err}</span>}
    </div>
  );
}

function SpectrumCard({ id, all, spectral }: { id: string; all: Recording[]; spectral?: any }) {
  const [other, setOther] = useState("");
  const a = useSpectrum(id);
  const b = useSpectrum(other || undefined);
  const data = useMemo(() => {
    if (!a.data) return [];
    return a.data.freqs.map((f, i) => ({ f, a: a.data!.db[i], b: b.data?.db[i] }));
  }, [a.data, b.data]);
  const peaks: { frequency_hz: number; relative: number }[] = spectral?.dominant_frequencies ?? [];
  return (
    <div className="card">
      <div className="card-head">
        <h3><Icon name="wave" />Frequenze del suono</h3>
        <select value={other} onChange={(e) => setOther(e.target.value)} style={{ maxWidth: 260 }}>
          <option value="">Confronta con un'altra registrazione…</option>
          {all.filter((r) => r.id !== id).map((r) => <option key={r.id} value={r.id}>{dateTime(r.ts)} {r.notes ? `– ${r.notes.slice(0, 30)}` : ""}</option>)}
        </select>
      </div>
      <div style={{ height: 240 }}>
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 6, right: 10, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id="psd" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#34d17f" stopOpacity={0.5} />
                <stop offset="100%" stopColor="#34d17f" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#e2ebe5" strokeDasharray="3 3" />
            <XAxis dataKey="f" type="number" scale="log" domain={[20, 8000]} ticks={[20, 50, 100, 200, 500, 1000, 2000, 4000, 8000]}
                   tickFormatter={(v) => (v >= 1000 ? `${v / 1000}k` : v)} stroke="#7f988a" fontSize={11} unit=" Hz" />
            <YAxis stroke="#7f988a" fontSize={11} width={55} tickFormatter={(v) => `${v}`} />
            <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e2ebe5", borderRadius: 12, boxShadow: "0 8px 24px rgba(16,42,28,.08)" }}
                     labelFormatter={(v) => `${Math.round(Number(v))} Hz`} formatter={(v: number, n) => [`${num(v)} dB`, n === "a" ? "questa" : "confronto"]} />
            <Area dataKey="a" type="monotone" stroke="#34d17f" fill="url(#psd)" isAnimationActive={false} />
            {b.data && <Line dataKey="b" type="monotone" stroke="#5ca8ef" dot={false} isAnimationActive={false} />}
            {peaks.slice(0, 3).map((p) => (
              <ReferenceLine key={p.frequency_hz} x={Math.max(20, p.frequency_hz)} stroke="#e8b23a" strokeDasharray="4 3"
                             label={{ value: `${Math.round(p.frequency_hz)} Hz`, fill: "#e8b23a", fontSize: 10, position: "top" }} />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="tiny muted">A sinistra i suoni gravi (motori, vibrazioni del terreno), a destra quelli acuti (uccelli, insetti). Più alta la curva, più forte quella frequenza.</div>
      {spectral && (
        <>
          <h4>Dove si concentra il suono</h4>
          {spectral.band_energy?.map((b: any) => (
            <div key={b.band} style={{ marginBottom: 7 }}>
              <div className="row small"><span>{b.band}</span><span className="spacer" /><b>{pct(b.fraction, 1)}</b></div>
              <div className="bar"><span style={{ width: `${b.fraction * 100}%` }} /></div>
            </div>
          ))}
          <div className="tiny muted">La frequenza da sola non basta per dire che animale è: per questo usiamo anche i modelli di riconoscimento.</div>
        </>
      )}
    </div>
  );
}

function YamnetCard({ det, duration }: { det: Detection; duration: number }) {
  const ev = det.evidence ?? {};
  if (!ev.available) return <div className="card"><h3>Riconoscimento suoni</h3><div className="muted small">Non disponibile.</div></div>;
  const tl: { t: number; group: string; label: string; score: number }[] = ev.timeline ?? [];
  return (
    <div className="card">
      <h3>Riconoscimento suoni (YAMNet)</h3>
      <div style={{ display: "flex", height: 16, borderRadius: 6, overflow: "hidden", marginBottom: 6 }}>
        {tl.map((f, i) => (
          <div key={i} title={`${num(f.t)} s: ${SOUND_GROUP[f.group] ?? f.group}`}
               style={{ flex: 1, background: GROUP_COLORS[f.group] ?? GROUP_COLORS.other, opacity: 0.35 + 0.65 * f.score }} />
        ))}
      </div>
      <div className="row tiny muted mb"><span>0 s</span><span className="spacer" /><span>{num(duration)} s</span></div>
      <table>
        <thead><tr><th>Suono riconosciuto</th><th>Tipo</th><th>Punteggio</th></tr></thead>
        <tbody>
          {ev.top_classes?.map((c: any) => (
            <tr key={c.label}>
              <td><span className="legend-swatch" style={{ background: GROUP_COLORS[c.group] ?? GROUP_COLORS.other }} />{c.label}</td>
              <td className="muted small">{SOUND_GROUP[c.group] ?? c.group}</td><td>{num(c.max_score, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="tiny muted" style={{ marginTop: 6 }}>I nomi dei suoni sono quelli originali del modello (in inglese).</div>
    </div>
  );
}

function PerchCard({ det }: { det: Detection }) {
  const ev = det.evidence ?? {};
  if (!ev.available) return <div className="card"><h3>Specie animali (Perch 2.0)</h3><div className="muted small">Non disponibile.</div></div>;
  return (
    <div className="card">
      <h3>Specie animali (Perch 2.0)</h3>
      <div className="tiny muted mb">Proposte grezze del modello, prima del controllo «c'è davvero un animale?».</div>
      <table>
        <thead><tr><th>Specie</th><th>Dove</th><th>Punteggio</th></tr></thead>
        <tbody>
          {ev.species?.map((s: any) => (
            <tr key={s.scientific_name}><td><i>{s.scientific_name}</i></td><td className="small muted">{num(s.start_s)}–{num(s.end_s)} s</td><td>{num(s.score, 2)}</td></tr>
          ))}
          {!ev.species?.length && <tr><td className="muted" colSpan={3}>Nessuna specie della tua zona.</td></tr>}
        </tbody>
      </table>
      {ev.gate && (
        <div className="small muted" style={{ marginTop: 8 }}>
          Suono animale: <b>{pct(ev.gate.animal)}</b> · rumori (macchine, acqua, vento): <b>{pct(ev.gate.noise)}</b>
        </div>
      )}
    </div>
  );
}

function UndergroundCard({ det }: { det: Detection }) {
  const ev = det.evidence ?? {};
  const CAT: Record<string, string> = {
    repetitive_low_freq_pattern: "Colpi ripetuti", transient_low_freq: "Colpo isolato", noise: "Solo rumore", unknown: "Non chiaro",
  };
  return (
    <div className="card">
      <div className="card-head"><h3>Sottosuolo (sperimentale)</h3><span className="badge badge-info">{CAT[det.category] ?? det.category}</span></div>
      <table><tbody>
        <tr><td className="muted">Colpi trovati</td><td>{ev.envelope_peaks ?? "—"}</td></tr>
        <tr><td className="muted">Si ripetono ogni</td><td>{ev.periodicity?.period_s ? `${num(ev.periodicity.period_s)} s` : "—"}</td></tr>
        <tr><td className="muted">Regolarità</td><td>{ev.periodicity ? pct(ev.periodicity.strength) : "—"}</td></tr>
      </tbody></table>
      <div className="tiny muted" style={{ marginTop: 8 }}>{ev.note ?? ev.reason}</div>
    </div>
  );
}

function BirdnetCard({ det }: { det: Detection }) {
  const ev = det.evidence ?? {};
  return (
    <div className="card">
      <h3>Specie di uccelli (BirdNET)</h3>
      {!ev.available ? <div className="muted small">Non disponibile.</div> : (
        <table><tbody>
          {ev.detections?.map((d: any, i: number) => (
            <tr key={i}><td><b>{d.common_name}</b> <i className="muted">{d.scientific_name}</i></td><td>{num(d.confidence, 2)}</td></tr>
          ))}
          {!ev.detections?.length && <tr><td className="muted">Nessuna specie riconosciuta.</td></tr>}
        </tbody></table>
      )}
    </div>
  );
}

function FarmModelCard({ det }: { det: Detection }) {
  const ev = det.evidence ?? {};
  return (
    <div className="card">
      <div className="card-head"><h3>Modello della tua azienda</h3><span className={`badge badge-${det.category === "unknown" ? "unknown" : "probable"}`}>{det.category === "unknown" ? "non sicuro" : det.category}</span></div>
      {ev.reason && <div className="small muted mb">{ev.reason}</div>}
      {ev.ranking?.map((r: any) => (
        <div key={r.label} style={{ marginBottom: 6 }}>
          <div className="row small"><span>{r.label}</span><span className="spacer" /><b>{pct(r.probability)}</b></div>
          <div className="bar"><span style={{ width: `${r.probability * 100}%` }} /></div>
        </div>
      ))}
    </div>
  );
}

function ModelPanel() {
  const qc = useQueryClient();
  const summary = useLabelSummary();
  const models = useModels();
  const [err, setErr] = useState<string | null>(null);
  const train = useMutation({
    mutationFn: () => api.post<MLModelInfo>("/api/v1/ml/models/train", {}),
    onSuccess: () => { setErr(null); qc.invalidateQueries({ queryKey: ["models"] }); },
    onError: (e: any) => { try { setErr(JSON.parse(e.message.slice(e.message.indexOf("{"))).detail); } catch { setErr(e.message || "Addestramento non riuscito."); } },
  });
  const act = async (m: MLModelInfo, on: boolean) => {
    setErr(null);
    try {
      await api.post(`/api/v1/ml/models/${m.id}/${on ? "activate" : "deactivate"}`);
      qc.invalidateQueries({ queryKey: ["models"] }); qc.invalidateQueries({ queryKey: ["engines"] });
    } catch (e: any) { try { setErr(JSON.parse(e.message.slice(e.message.indexOf("{"))).detail); } catch { setErr(e.message || "Operazione non riuscita."); } }
  };
  const s = summary.data;
  return (
    <div className="stack" style={{ gap: 16 }}>
      <div className="grid cols-2">
        <div className="card">
          <h3><Icon name="info" />Come insegnare ad AGROAI a riconoscere le talpe</h3>
          <Steps items={[
            "Metti un microfono a contatto o un geofono nel terreno vicino a cumuli freschi, e anche dove non ci sono talpe.",
            "Registra in orari diversi; annota se c'erano irrigazione, vento o trattori.",
            <>Etichetta i pezzi solo quando hai <b>verificato in campo</b> (terra smossa, gallerie): es. «talpa».</>,
            <>Etichetta anche i suoni che ingannano: «irrigazione», «macchinario», «vento», «rumore di fondo».</>,
            "Premi «Allena» e guarda quanto spesso indovina, poi attivalo.",
          ]} />
          <div className="small muted" style={{ marginTop: 10 }}>Il modello impara solo dai tuoi esempi. Quando un suono non assomiglia a niente che conosce, risponde «non sicuro» invece di inventare.</div>
        </div>
        <div className="card">
          <div className="card-head">
            <h3>I tuoi esempi</h3>
            <button className="btn" onClick={() => train.mutate()} disabled={train.isPending}>{train.isPending ? "Sto imparando…" : "Allena il modello"}</button>
          </div>
          {err && <div className="callout danger"><Icon name="alert" />{err}</div>}
          <table>
            <thead><tr><th>Etichetta</th><th>Esempi</th><th>Pronto?</th></tr></thead>
            <tbody>
              {s?.labels.map((l) => (
                <tr key={l.label}>
                  <td><b>{l.label}</b>{l.simulated > 0 && <span className="badge badge-simulation" style={{ marginLeft: 6 }}>{l.simulated} demo</span>}</td>
                  <td>{l.count}</td>
                  <td style={{ minWidth: 140 }}>
                    <div className={`bar ${l.count < s.min_per_class_train ? "bad" : l.count < s.min_per_class_activate ? "warn" : ""}`}>
                      <span style={{ width: `${Math.min(100, (l.count / s.min_per_class_activate) * 100)}%` }} />
                    </div>
                    <div className="tiny muted">{l.count >= s.min_per_class_activate ? "pronto" : `ne servono ${s.min_per_class_activate - l.count} in più`}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!s?.labels.length && <Empty icon="mic" title="Nessun esempio ancora" text="Etichetta le registrazioni nella scheda «Registrazioni»." />}
          {s && <div className="tiny muted" style={{ marginTop: 8 }}>Servono almeno 2 etichette diverse e {s.min_per_class_activate} esempi per ognuna.</div>}
        </div>
      </div>
      <div className="card">
        <h3>Versioni del modello</h3>
        {(models.data ?? []).map((m) => <ModelRow key={m.id} m={m} onToggle={act} />)}
        {!models.data?.length && <Empty icon="brain" title="Nessun modello ancora" text="Dopo il primo addestramento lo trovi qui." />}
      </div>
    </div>
  );
}

function ModelRow({ m, onToggle }: { m: MLModelInfo; onToggle: (m: MLModelInfo, on: boolean) => void }) {
  const mt = m.metrics ?? {};
  return (
    <div className="candidate" style={{ marginBottom: 12 }}>
      <div className="row">
        <b>Versione {m.version}</b>
        <span className={`badge badge-${m.status === "active" ? "active" : "neutral"}`}>{m.status === "active" ? "in uso" : m.status === "archived" ? "archiviato" : "pronto da provare"}</span>
        {mt.contains_simulated_data && <span className="badge badge-simulation">contiene suoni demo</span>}
        <span className="muted small">{ago(m.created_at)} · {m.n_samples} esempi</span>
        <span className="spacer" />
        {m.status === "active"
          ? <button className="btn ghost sm" onClick={() => onToggle(m, false)}>Disattiva</button>
          : <button className="btn sm" disabled={!mt.can_activate} title={mt.can_activate ? "" : `Servono ${mt.activation_rule}`} onClick={() => onToggle(m, true)}>Usa questo modello</button>}
      </div>
      <div className="row" style={{ marginTop: 10 }}>
        <div className="big-number">{pct(mt.accuracy)}</div>
        <div className="small muted">di risposte giuste su esempi che il modello<br />non aveva visto durante l'addestramento</div>
      </div>
      <div className="grid cols-2" style={{ marginTop: 10 }}>
        <table>
          <thead><tr><th>Etichetta</th><th>Quante ne trova</th><th>Quando dice così, ha ragione</th></tr></thead>
          <tbody>{Object.entries(mt.per_class ?? {}).map(([c, v]: [string, any]) => (
            <tr key={c}><td>{c}</td><td>{pct(v.recall)}</td><td>{pct(v.precision)}</td></tr>
          ))}</tbody>
        </table>
        <div>
          <div className="tiny muted mb">Errori: righe = cosa era davvero, colonne = cosa ha detto il modello</div>
          <table>
            <thead><tr><th></th>{mt.labels?.map((l: string) => <th key={l}>{l}</th>)}</tr></thead>
            <tbody>{mt.confusion_matrix?.map((row: number[], i: number) => {
              const tot = row.reduce((a, b) => a + b, 0) || 1;
              return (
                <tr key={i}><th>{mt.labels[i]}</th>{row.map((v, j) => (
                  <td key={j} style={{ background: `rgba(${i === j ? "52,209,127" : "239,93,93"},${(v / tot) * 0.6})`, textAlign: "center" }}>{v}</td>
                ))}</tr>
              );
            })}</tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
