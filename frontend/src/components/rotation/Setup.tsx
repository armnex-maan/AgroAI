import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { Icon } from "../Icon";
import { CropPicker } from "../Rotation";
import { FarmData, shortName } from "./types";

type Status = "crop" | "rest" | "cover" | "unknown";
interface CropRec { crop: string; area: string; diseases: string; treatments: string; notes: string }
interface PlotDraft {
  id?: string; name: string; unit: "m2" | "ha"; area: string; shape: string; width: string; length: string;
  orientation: string; exposure: string;
}
type Season = { status: Status | null; crops: CropRec[] };
interface Draft {
  region: string; province: string; municipality: string; lat: number | null; lon: number | null;
  plots: PlotDraft[]; history: Record<number, Record<number, Season>>;
  cond: Record<string, string>; problems: string[]; otherProblem: string;
  wanted: Record<string, string>; purpose: string; integrated: string; cap: string;
}

const COND: { id: string; text: string; options: [string, string][] }[] = [
  { id: "texture", text: "Com'è il terreno al tatto?", options: [["sandy", "Sabbioso: sciolto, si asciuga in fretta"], ["clay", "Argilloso: pesante, si attacca alle scarpe"], ["silty", "Limoso: fine e liscio, fa la crosta"], ["mixed", "Misto (medio impasto)"]] },
  { id: "fertility", text: "Quanto è fertile?", options: [["high", "Molto: le piante crescono bene"], ["medium", "Nella media"], ["low", "Poco: le piante crescono poco"]] },
  { id: "compaction", text: "Il terreno è compatto?", options: [["low", "No, è soffice"], ["medium", "Un po'"], ["high", "Sì, è duro e l'acqua ristagna"]] },
  { id: "water", text: "Hai acqua a disposizione per irrigare?", options: [["plenty", "Sì, quanta ne serve"], ["limited", "Poca o solo in certi periodi"], ["none", "No, solo pioggia"]] },
  { id: "irrigation", text: "Che tipo di irrigazione usi?", options: [["drip", "A goccia"], ["sprinkler", "A pioggia (aspersione)"], ["furrow", "Per scorrimento o a solchi"], ["manual", "A mano"], ["none", "Nessuna"]] },
  { id: "manure", text: "Usi letame o compost?", options: [["yearly", "Sì, ogni anno"], ["sometimes", "Ogni tanto"], ["no", "No"]] },
  { id: "cover", text: "Puoi seminare un sovescio tra un raccolto e l'altro?", options: [["yes", "Sì"], ["maybe", "Forse"], ["no", "No"]] },
];
const PROBLEMS: [string, string][] = [
  ["nematodes", "Nematodi (radici con palline o nodi)"], ["wilt", "Avvizzimenti (piante che appassiscono e muoiono)"],
  ["root_rot", "Marciumi delle radici o del colletto"], ["fungi", "Funghi sulle foglie che tornano ogni anno"],
  ["clubroot", "Ernia del cavolo (radici gonfie)"], ["white_rot", "Marciume bianco di cipolla o aglio"],
  ["pests", "Parassiti del terreno (elateridi, larve)"],
];
const STATUS_OPTS: [Status, string][] = [["crop", "Sì, ho coltivato"], ["rest", "No, terreno a riposo"], ["cover", "Sovescio o copertura vegetale"], ["unknown", "Non ricordo"]];

function fromFarm(f: FarmData): Draft {
  const plots: PlotDraft[] = f.plots.map((p) => ({
    id: p.id, name: p.name, unit: (p.area_m2 ?? 0) >= 10000 ? "ha" : "m2",
    area: p.area_m2 ? String((p.area_m2 ?? 0) >= 10000 ? (p.area_m2 / 10000) : Math.round(p.area_m2)) : "",
    shape: p.shape, width: p.width_m ? String(p.width_m) : "", length: p.length_m ? String(p.length_m) : "",
    orientation: String(p.orientation_deg ?? 0), exposure: p.exposure ?? "full_sun",
  }));
  const history: Draft["history"] = {};
  f.plots.forEach((p, i) => {
    history[i] = {};
    p.history.forEach((h) => {
      const s = history[i][h.year] ?? { status: h.status, crops: [] };
      if (h.status === "crop") s.crops.push({ crop: h.crop, area: h.area_m2 ? String(h.area_m2) : "", diseases: h.diseases ?? "", treatments: h.treatments ?? "", notes: h.notes ?? "" });
      history[i][h.year] = s;
    });
  });
  const prof = f.plots[0]?.profile ?? {};
  const g = prof.goals ?? {};
  return {
    region: f.region ?? "", province: f.province ?? "", municipality: f.municipality ?? "", lat: f.latitude, lon: f.longitude,
    plots: plots.length ? plots : [{ name: "Orto", unit: "m2", area: "", shape: "rectangle", width: "", length: "", orientation: "0", exposure: "full_sun" }],
    history, cond: Object.fromEntries(COND.map((c) => [c.id, prof[c.id] ?? ""])), problems: prof.problems ?? [],
    otherProblem: prof.other_problem ?? "", wanted: Object.fromEntries(Object.entries(g.wanted ?? {}).map(([k, v]) => [k, v ? String(v) : ""])),
    purpose: g.purpose ?? "", integrated: g.integrated == null ? "" : g.integrated ? "yes" : "no", cap: g.cap == null ? "" : g.cap ? "yes" : "no",
  };
}

export default function Setup({ farm, onDone }: { farm: FarmData; onDone: () => void }) {
  const qc = useQueryClient();
  const regions = useQuery({ queryKey: ["rot-regions"], queryFn: () => api.get<{ key: string; name: string; level: string }[]>("/api/v1/rotation/regions"), staleTime: Infinity });
  const [d, setD] = useState<Draft>(() => fromFarm(farm));
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const years = Array.from({ length: 6 }, (_, i) => farm.season_year - i);
  const set = (patch: Partial<Draft>) => setD((x) => ({ ...x, ...patch }));

  const steps = useMemo(() => {
    const s: { id: string; group: string; plot?: number; year?: number; cond?: number }[] = [
      { id: "region", group: "Dove" }, { id: "place", group: "Dove" }, { id: "count", group: "Terreni" },
    ];
    d.plots.forEach((_, i) => s.push({ id: "plot", group: "Terreni", plot: i }));
    d.plots.forEach((_, i) => years.forEach((y) => s.push({ id: "year", group: "Storico", plot: i, year: y })));
    COND.forEach((_, k) => s.push({ id: "cond", group: "Terreno", cond: k }));
    s.push({ id: "problems", group: "Problemi" }, { id: "wanted", group: "Obiettivi" }, { id: "purpose", group: "Obiettivi" },
      { id: "integrated", group: "Obiettivi" }, { id: "cap", group: "Obiettivi" });
    return s;
  }, [d.plots.length]); // eslint-disable-line react-hooks/exhaustive-deps
  const st = steps[Math.min(step, steps.length - 1)];
  const next = () => (step < steps.length - 1 ? setStep(step + 1) : finish());
  const pick = (patch: Partial<Draft>) => { set(patch); setTimeout(next, 140); };

  async function finish() {
    setBusy(true); setErr(null);
    try {
      await api.put("/api/v1/rotation/farm", { region: d.region, province: d.province, municipality: d.municipality,
        latitude: d.lat ?? undefined, longitude: d.lon ?? undefined });
      const goals = { wanted: Object.fromEntries(Object.entries(d.wanted).map(([k, v]) => [k, parseFloat(v.replace(",", ".")) || 0])),
        purpose: d.purpose || "family", integrated: d.integrated === "" ? null : d.integrated === "yes",
        cap: d.cap === "" ? null : d.cap === "yes" };
      const soilState = d.cond.compaction === "high" ? "hard" : d.cond.fertility === "low" ? "tired" : d.cond.fertility === "high" ? "good" : "normal";
      const profile = { ...d.cond, problems: d.problems, other_problem: d.otherProblem, soil_state: soilState, goals };
      for (let i = 0; i < d.plots.length; i++) {
        const p = d.plots[i];
        const num = (v: string) => (v ? parseFloat(v.replace(",", ".")) : null);
        const area = num(p.area);
        const body = { name: p.name || `Appezzamento ${i + 1}`, area_m2: area == null ? null : p.unit === "ha" ? area * 10000 : area,
          shape: p.shape, width_m: num(p.width), length_m: num(p.length), orientation_deg: Number(p.orientation) || 0,
          exposure: p.exposure, profile };
        const saved = p.id ? await api.put<{ id: string }>(`/api/v1/rotation/plots/${p.id}`, body)
          : await api.post<{ id: string }>("/api/v1/rotation/plots", body);
        for (const y of years) {
          const s = d.history[i]?.[y];
          if (!s?.status) continue; // no answer: nothing is stored, nothing is invented
          if (s.status === "crop" && !s.crops.length) continue;
          await api.put(`/api/v1/rotation/plots/${saved.id}/history`, { year: y, status: s.status,
            crops: s.crops.map((c) => ({ crop: c.crop, area_m2: num(c.area), diseases: c.diseases || null, treatments: c.treatments || null, notes: c.notes || null })) });
        }
      }
      await qc.invalidateQueries({ queryKey: ["rotation-farm"] });
      onDone();
    } catch (e: any) { setErr(String(e.message ?? e)); } finally { setBusy(false); }
  }

  const plot = st.plot != null ? d.plots[st.plot] : null;
  const updPlot = (patch: Partial<PlotDraft>) => set({ plots: d.plots.map((p, i) => (i === st.plot ? { ...p, ...patch } : p)) });
  const season: Season = st.plot != null && st.year != null ? d.history[st.plot]?.[st.year] ?? { status: null, crops: [] } : { status: null, crops: [] };
  const setSeason = (s: Season) => set({ history: { ...d.history, [st.plot!]: { ...(d.history[st.plot!] ?? {}), [st.year!]: s } } });
  const multi = st.id === "year" && season.status === "crop";
  const canNext = st.id === "region" ? !!d.region : st.id === "plot" ? !!plot?.name : true;

  return (
    <div className="card wizard">
      <div className="wiz-progress"><span style={{ width: `${((step + 1) / steps.length) * 100}%` }} /></div>
      <div className="wiz-groups">{["Dove", "Terreni", "Storico", "Terreno", "Problemi", "Obiettivi"].map((g) => <span key={g} className={st.group === g ? "on" : ""}>{g}</span>)}</div>
      <div className="tiny muted">Domanda {step + 1} di {steps.length}</div>

      {st.id === "region" && (<>
        <h2 className="wiz-q">In che regione si trova l'azienda?</h2>
        <div className="small muted">Serve per applicare solo le regole della tua regione.</div>
        <div className="region-grid">
          {(regions.data ?? []).map((r) => (
            <button key={r.key} className={`opt ${d.region === r.key ? "on" : ""}`} onClick={() => pick({ region: r.key })}>
              <span style={{ flex: 1 }}>{r.name}</span>
              <span className={`cov-dot c-${r.level}`} title={r.level === "crops" ? "regole per coltura" : r.level === "general" ? "solo regola generale" : "disciplinare non ancora letto"} />
            </button>
          ))}
        </div>
        <div className="tiny muted" style={{ marginTop: 8 }}><span className="cov-dot c-crops" /> regole per coltura · <span className="cov-dot c-general" /> solo regola generale · <span className="cov-dot c-none" /> non ancora disponibili</div>
      </>)}

      {st.id === "place" && (<>
        <h2 className="wiz-q">Provincia e comune</h2>
        <div className="form-grid" style={{ marginTop: 12 }}>
          <label className="field">Provincia<input value={d.province} onChange={(e) => set({ province: e.target.value })} placeholder="es. Bologna" /></label>
          <label className="field">Comune<input value={d.municipality} onChange={(e) => set({ municipality: e.target.value })} placeholder="es. Imola" /></label>
        </div>
        <button className="btn ghost sm" style={{ marginTop: 10 }} onClick={() => navigator.geolocation?.getCurrentPosition(
          (pos) => set({ lat: +pos.coords.latitude.toFixed(5), lon: +pos.coords.longitude.toFixed(5) }), () => setErr("Posizione non disponibile."))}>
          <Icon name="pin" size={14} />{d.lat != null ? `Posizione: ${d.lat}, ${d.lon}` : "Usa la mia posizione (facoltativo)"}
        </button>
      </>)}

      {st.id === "count" && (<>
        <h2 className="wiz-q">Quanti appezzamenti vuoi pianificare?</h2>
        <div className="stepper">
          <button className="round-btn" onClick={() => d.plots.length > 1 && set({ plots: d.plots.slice(0, -1) })}><Icon name="minus" size={18} /></button>
          <b>{d.plots.length}</b>
          <button className="round-btn" onClick={() => set({ plots: [...d.plots, { name: `Appezzamento ${d.plots.length + 1}`, unit: "m2", area: "", shape: "rectangle", width: "", length: "", orientation: "0", exposure: "full_sun" }] })}><Icon name="plus" size={18} /></button>
        </div>
      </>)}

      {st.id === "plot" && plot && (<>
        <h2 className="wiz-q">Appezzamento {st.plot! + 1}: com'è fatto?</h2>
        <div className="form-grid" style={{ marginTop: 12 }}>
          <label className="field" style={{ gridColumn: "1 / -1" }}>Nome<input value={plot.name} onChange={(e) => updPlot({ name: e.target.value })} /></label>
          <label className="field">Superficie<input inputMode="decimal" value={plot.area} onChange={(e) => updPlot({ area: e.target.value })} placeholder="es. 800" /></label>
          <label className="field">Unità<select value={plot.unit} onChange={(e) => updPlot({ unit: e.target.value as "m2" | "ha" })}><option value="m2">m²</option><option value="ha">ettari</option></select></label>
          <label className="field">Forma<select value={plot.shape} onChange={(e) => updPlot({ shape: e.target.value })}><option value="rectangle">Rettangolare</option><option value="square">Quadrata</option><option value="irregular">Irregolare</option></select></label>
          <label className="field">Esposizione<select value={plot.exposure} onChange={(e) => updPlot({ exposure: e.target.value })}><option value="full_sun">Pieno sole</option><option value="part_shade">Mezz'ombra</option><option value="shade">Ombra</option></select></label>
          <label className="field">Larghezza (m)<input inputMode="decimal" value={plot.width} onChange={(e) => updPlot({ width: e.target.value })} /></label>
          <label className="field">Lunghezza (m)<input inputMode="decimal" value={plot.length} disabled={plot.shape === "square"} onChange={(e) => updPlot({ length: e.target.value })} /></label>
          <label className="field" style={{ gridColumn: "1 / -1" }}>Orientamento del lato lungo
            <select value={plot.orientation} onChange={(e) => updPlot({ orientation: e.target.value })}>
              <option value="0">Nord–Sud</option><option value="90">Est–Ovest</option><option value="45">Nord-Est – Sud-Ovest</option><option value="135">Nord-Ovest – Sud-Est</option>
            </select></label>
        </div>
        <div className="tiny muted" style={{ marginTop: 6 }}>Se non conosci le misure, scrivi solo la superficie: potrai disegnare il terreno dopo.</div>
      </>)}

      {st.id === "year" && plot && (<>
        <div className="tiny muted">{plot.name}</div>
        <h2 className="wiz-q">{st.year === farm.season_year ? `Hai coltivato qualcosa nel ${st.year}?` : `E nel ${st.year}?`}</h2>
        {!multi ? (
          <div className="opt-list" style={{ marginTop: 12 }}>
            {STATUS_OPTS.map(([v, l]) => (
              <button key={v} className={`opt ${season.status === v ? "on" : ""}`} onClick={() => v === "crop" ? setSeason({ status: "crop", crops: season.crops }) : (setSeason({ status: v, crops: [] }), setTimeout(next, 140))}>{l}</button>
            ))}
          </div>
        ) : (<>
          <div className="small muted">Scegli tutte le colture di quell'anno. Puoi aggiungere superficie, malattie e trattamenti.</div>
          <CropPicker crops={farm.crops} multi values={season.crops.map((c) => c.crop)}
                      onToggle={(k) => setSeason({ status: "crop", crops: season.crops.some((c) => c.crop === k) ? season.crops.filter((c) => c.crop !== k)
                        : [...season.crops, { crop: k, area: "", diseases: "", treatments: "", notes: "" }] })} />
          {season.crops.map((c, ci) => (
            <details key={c.crop} className="crop-detail">
              <summary><b>{shortName(farm.crops.find((x) => x.key === c.crop)?.name ?? c.crop)}</b> <span className="tiny muted">dettagli facoltativi</span></summary>
              <div className="form-grid">
                {(["area", "diseases", "treatments", "notes"] as const).map((k) => (
                  <label key={k} className="field">{{ area: "Superficie (m²)", diseases: "Malattie viste", treatments: "Trattamenti fatti", notes: "Note" }[k]}
                    <input value={c[k]} onChange={(e) => setSeason({ status: "crop", crops: season.crops.map((x, j) => (j === ci ? { ...x, [k]: e.target.value } : x)) })} />
                  </label>
                ))}
              </div>
            </details>
          ))}
          <button className="link-btn" onClick={() => setSeason({ status: null, crops: [] })}>Cambia risposta</button>
        </>)}
      </>)}

      {st.id === "cond" && (() => {
        const c = COND[st.cond!];
        return (<>
          <h2 className="wiz-q">{c.text}</h2>
          <div className="opt-list" style={{ marginTop: 12 }}>
            {c.options.map(([v, l]) => <button key={v} className={`opt ${d.cond[c.id] === v ? "on" : ""}`} onClick={() => pick({ cond: { ...d.cond, [c.id]: v } })}>{l}</button>)}
          </div>
        </>);
      })()}

      {st.id === "problems" && (<>
        <h2 className="wiz-q">Negli ultimi anni hai avuto uno di questi problemi?</h2>
        <div className="opt-list" style={{ marginTop: 12 }}>
          {PROBLEMS.map(([v, l]) => {
            const on = d.problems.includes(v);
            return <button key={v} className={`opt ${on ? "on" : ""}`} onClick={() => set({ problems: on ? d.problems.filter((x) => x !== v) : [...d.problems, v] })}>
              <span className="opt-check"><Icon name={on ? "check" : "plus"} size={14} stroke={2.6} /></span>{l}</button>;
          })}
          <label className="field">Altro problema<input value={d.otherProblem} onChange={(e) => set({ otherProblem: e.target.value })} placeholder="facoltativo" /></label>
        </div>
      </>)}

      {st.id === "wanted" && (<>
        <h2 className="wiz-q">Cosa vuoi coltivare?</h2>
        <div className="small muted">Scegli le colture e, se vuoi, quanta superficie. Se non scegli nulla, decide AGROAI.</div>
        <CropPicker crops={farm.crops} multi values={Object.keys(d.wanted)}
                    onToggle={(k) => { const w = { ...d.wanted }; if (k in w) delete w[k]; else w[k] = ""; set({ wanted: w }); }} />
        {Object.keys(d.wanted).length > 0 && (
          <div className="form-grid" style={{ marginTop: 10 }}>
            {Object.entries(d.wanted).map(([k, v]) => (
              <label key={k} className="field">{shortName(farm.crops.find((c) => c.key === k)?.name ?? k)} (m²)
                <input inputMode="decimal" value={v} placeholder="qualsiasi" onChange={(e) => set({ wanted: { ...d.wanted, [k]: e.target.value } })} /></label>
            ))}
          </div>
        )}
      </>)}
      {st.id === "purpose" && (<>
        <h2 className="wiz-q">A cosa serve la produzione?</h2>
        <div className="opt-list" style={{ marginTop: 12 }}>
          {[["family", "Per la famiglia (orto domestico)"], ["commercial", "Per vendere"]].map(([v, l]) =>
            <button key={v} className={`opt ${d.purpose === v ? "on" : ""}`} onClick={() => pick({ purpose: v })}>{l}</button>)}
        </div>
      </>)}
      {st.id === "integrated" && (<>
        <h2 className="wiz-q">Aderisci alla produzione integrata della tua regione?</h2>
        <div className="small muted">Per esempio con il PSR/CSR, il marchio SQNPI o un'organizzazione di produttori. Le regole del disciplinare sono obbligatorie solo in questo caso.</div>
        <div className="opt-list" style={{ marginTop: 12 }}>
          {[["yes", "Sì"], ["no", "No"], ["", "Non so"]].map(([v, l]) => <button key={l} className={`opt ${d.integrated === v ? "on" : ""}`} onClick={() => pick({ integrated: v })}>{l}</button>)}
        </div>
      </>)}
      {st.id === "cap" && (<>
        <h2 className="wiz-q">Ricevi i contributi della PAC?</h2>
        <div className="opt-list" style={{ marginTop: 12 }}>
          {[["yes", "Sì"], ["no", "No"], ["", "Non so"]].map(([v, l]) => <button key={l} className={`opt ${d.cap === v ? "on" : ""}`} onClick={() => set({ cap: v })}>{l}</button>)}
        </div>
      </>)}

      {err && <div className="callout danger" style={{ marginTop: 12 }}><Icon name="alert" />{err}</div>}
      <div className="wiz-nav">
        <button className="btn ghost" disabled={step === 0} onClick={() => setStep(step - 1)}><Icon name="arrow-left" size={15} />Indietro</button>
        <span className="spacer" />
        {st.id === "year" && !multi && <button className="btn ghost" onClick={next}>Salta</button>}
        <button className="btn" disabled={!canNext || busy} onClick={next}>
          {busy ? "Salvo…" : step === steps.length - 1 ? "Salva e crea il piano" : "Avanti"}<Icon name="arrow-right" size={15} />
        </button>
      </div>
    </div>
  );
}
