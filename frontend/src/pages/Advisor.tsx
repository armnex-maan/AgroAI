import { Fragment, useEffect, useMemo, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useFarms, useSiteAssessment } from "../api/hooks";
import { CropResult, SiteAssessment, SourceRef } from "../api/types";
import { BaseMap } from "../components/BaseMap";
import { Icon } from "../components/Icon";
import { PageHeader } from "../components/ui";
import RotationHub from "../components/rotation/RotationHub";
import { useSearchParams } from "react-router-dom";
import { IMPACT, LEGAL, num, SEASON, SUIT_CLASS, TEXTURE, TIP_CATEGORY } from "../lib/it";

const TEXTURES = ["", ...Object.keys(TEXTURE)];
const COUNTRIES = [["IT", "Italia"], ["FR", "Francia"], ["ES", "Spagna"], ["PT", "Portogallo"], ["DE", "Germania"],
  ["GR", "Grecia"], ["CH", "Svizzera"], ["GB", "Regno Unito"], ["US", "Stati Uniti"], ["CN", "Cina"],
  ["IN", "India"], ["BR", "Brasile"], ["", "Altro / non indicato"]];
const MONTHS = ["G", "F", "M", "A", "M", "G", "L", "A", "S", "O", "N", "D"];

export default function Advisor() {
  const farms = useFarms();
  const farm = farms.data?.[0];
  const [point, setPoint] = useState<{ lat: number; lon: number } | null>(null);
  const [country, setCountry] = useState("IT");
  const [ph, setPh] = useState("");
  const [texture, setTexture] = useState("");
  const m = useSiteAssessment();

  useEffect(() => {
    if (!point && farm?.latitude != null && farm.longitude != null) setPoint({ lat: farm.latitude, lon: farm.longitude });
  }, [farm, point]);

  const req = point ? {
    lat: point.lat, lon: point.lon, country_code: country || undefined, farm_id: farm?.id,
    ph: ph ? parseFloat(ph.replace(",", ".")) : undefined, texture: texture || undefined,
  } : null;

  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "rotazione" ? "rotation" : "where";
  const tabs = (
    <div className="tabs advisor-tabs">
      <button className={tab === "where" ? "on" : ""} onClick={() => setParams({})}><Icon name="pin" size={14} /> Cosa coltivare qui</button>
      <button className={tab === "rotation" ? "on" : ""} onClick={() => setParams({ tab: "rotazione" })}><Icon name="refresh" size={14} /> Rotazione colturale</button>
    </div>
  );
  if (tab === "rotation") {
    return (
      <>
        <PageHeader icon="refresh" title="Rotazione colturale" tone="green"
                    subtitle="Disegna i tuoi appezzamenti, racconta cosa hai coltivato e ottieni un piano anno per anno, aiuola per aiuola." />
        {tabs}
        <RotationHub />
      </>
    );
  }
  return (
    <>
      <PageHeader icon="sprout" title="Cosa posso coltivare?" tone="amber"
                  subtitle="Tocca il tuo campo sulla mappa: AGROAI guarda 5 anni di clima e il tipo di terreno, e ti dice quali colture sono più adatte e come risparmiare." />
      {tabs}
      <div className="split mb" style={{ gridTemplateColumns: "minmax(0, 1.4fr) minmax(300px, 1fr)" }}>
        <div className="card" style={{ padding: 10 }}>
          <BaseMap center={point ? [point.lon, point.lat] : [9.19, 45.46]} zoom={point ? 13 : 5}
                   picked={point} onPick={setPoint} height={380}
                   points={(farms.data ?? []).filter((f) => f.latitude != null).map((f) => ({ lat: f.latitude!, lon: f.longitude!, label: f.name }))} />
        </div>
        <div className="card">
          <h3><Icon name="pin" />Il tuo campo</h3>
          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <CoordInput label="Latitudine" value={point?.lat} min={-90} max={90} onChange={(lat) => setPoint({ lat, lon: point?.lon ?? 0 })} />
            <CoordInput label="Longitudine" value={point?.lon} min={-180} max={180} onChange={(lon) => setPoint({ lon, lat: point?.lat ?? 0 })} />
            <label className="field">Paese (per le regole di legge)
              <select value={country} onChange={(e) => setCountry(e.target.value)}>
                {COUNTRIES.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
              </select>
            </label>
            <label className="field">pH da analisi (facoltativo)<input placeholder="es. 6,8" value={ph} onChange={(e) => setPh(e.target.value)} /></label>
            <label className="field" style={{ gridColumn: "1 / -1" }}>Tipo di terreno (facoltativo)
              <select value={texture} onChange={(e) => setTexture(e.target.value)}>
                {TEXTURES.map((t) => <option key={t} value={t}>{t ? TEXTURE[t] : "Non lo so — usa la mappa dei suoli"}</option>)}
              </select>
            </label>
          </div>
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn" onClick={() => req && m.mutate(req)} disabled={!req || m.isPending}>
              <Icon name={m.isPending ? "refresh" : "spark"} size={14} className={m.isPending ? "spin" : ""} />
              {m.isPending ? "Studio clima e terreno…" : "Analizza questo campo"}
            </button>
            {farm?.latitude != null && (
              <button className="btn ghost sm" onClick={() => setPoint({ lat: farm.latitude!, lon: farm.longitude! })}>Vai a {farm.name}</button>
            )}
          </div>
          {m.isError && <div className="callout danger" style={{ marginTop: 12 }}><Icon name="alert" />Analisi non riuscita. Controlla la connessione a internet e riprova.</div>}
        </div>
      </div>
      {m.data && req && (
        <>
          <AiAdvice key={m.data.generated_at} request={req} />
          <Results a={m.data} />
        </>
      )}
    </>
  );
}

function AiAdvice({ request }: { request: Record<string, unknown> }) {
  const cfg = useQuery({ queryKey: ["ai-config"], queryFn: () => api.get<{ provider: string; model: string | null }>("/api/v1/ai/config"), refetchInterval: false });
  const advice = useMutation({
    mutationFn: () => api.post<{ advice: string; model: string }>("/api/v1/agronomy/ai-advice", request),
  });
  if (!cfg.data || cfg.data.provider === "none") return null;
  return (
    <div className="card mb" style={{ borderColor: "rgba(157,140,242,.45)", background: "linear-gradient(135deg, rgba(122,98,216,.10), var(--panel))" }}>
      <div className="row" style={{ flexWrap: "nowrap", alignItems: "flex-start" }}>
        <div className="page-icon tone-violet"><Icon name="brain" size={22} /></div>
        <div style={{ flex: 1 }}>
          <h3 style={{ marginBottom: 4 }}>Il consiglio dell'assistente</h3>
          {!advice.data && !advice.isPending && (
            <>
              <div className="small muted mb">L'intelligenza artificiale riassume i risultati qui sotto in consigli pratici, senza aggiungere dati.</div>
              <button className="btn" onClick={() => advice.mutate()}><Icon name="spark" size={14} />Dammi un consiglio</button>
            </>
          )}
          {advice.isPending && <div className="row small muted"><Icon name="refresh" className="spin" />Sto scrivendo il consiglio…</div>}
          {advice.isError && <div className="callout danger"><Icon name="alert" />L'assistente non risponde in questo momento. Riprova tra poco.</div>}
          {advice.data && (
            <>
              <div className="lead" style={{ whiteSpace: "pre-wrap" }}>{advice.data.advice}</div>
              <div className="row tiny muted" style={{ marginTop: 12 }}>
                Scritto dall'intelligenza artificiale partendo dai dati qui sotto: può sbagliare, controlla sempre le tabelle.
                <span className="spacer" />
                <button className="btn ghost sm" onClick={() => advice.mutate()}><Icon name="refresh" size={13} />Rigenera</button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function CoordInput({ label, value, min, max, onChange }: {
  label: string; value?: number; min: number; max: number; onChange: (v: number) => void;
}) {
  const [text, setText] = useState(value?.toString() ?? "");
  useEffect(() => {
    if (value !== undefined && parseFloat(text.replace(",", ".")) !== value) setText(value.toString());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  const v = parseFloat(text.replace(",", "."));
  const bad = text !== "" && (Number.isNaN(v) || v < min || v > max);
  return (
    <label className="field">{label}
      <input value={text} inputMode="decimal" style={bad ? { borderColor: "var(--danger)" } : undefined}
             onChange={(e) => {
               setText(e.target.value);
               const n = parseFloat(e.target.value.replace(",", "."));
               if (!Number.isNaN(n) && n >= min && n <= max) onChange(n);
             }} />
    </label>
  );
}

function Results({ a }: { a: SiteAssessment }) {
  const c = a.climate;
  const monthly = c.monthly.map((x, i) => ({ m: MONTHS[i], pioggia: x.precip_mm, consumo: x.et0_mm, t: x.t_mean }));
  const best = a.crops.filter((x) => x.class_irrigated === "S1").slice(0, 4).map((x) => x.name);
  return (
    <div className="stack" style={{ gap: 16 }}>
      {a.warnings.map((w) => <div key={w} className="callout"><Icon name="alert" />{w}</div>)}

      {best.length > 0 && (
        <div className="callout ok"><Icon name="sprout" /><div>
          <b>In breve:</b> qui crescono molto bene {best.join(", ")}. Scorri per vedere tutte le colture, il clima e come risparmiare.
        </div></div>
      )}

      <div className="grid cols-4">
        <Kpi icon="thermo" label="Temperatura media" value={`${num(c.annual.t_mean)} °C`} sub={`media degli anni ${c.period}`} />
        <Kpi icon="drop" label="Pioggia in un anno" value={`${num(c.annual.precip_mm, 0)} mm`} sub={`le piante ne consumerebbero ${num(c.annual.et0_mm, 0)}`} />
        <Kpi icon="sun" label="Giorni senza gelate" value={`${c.annual.frost_free_days}`} sub={`notte più fredda ≈ ${num(c.annual.mean_annual_min_c)} °C`} />
        <Kpi icon="drop" label="Pioggia d'estate" value={`${num(c.seasons.summer.precip_mm, 0)} mm`} sub="da aprile a settembre" />
      </div>

      <div className="grid cols-2">
        <div className="card">
          <div className="card-head"><h3>Il clima mese per mese</h3><span className="badge badge-forecast">dati storici</span></div>
          <div style={{ height: 240 }}>
            <ResponsiveContainer>
              <ComposedChart data={monthly} margin={{ top: 5, right: 0, left: -15, bottom: 0 }}>
                <CartesianGrid stroke="#e2ebe5" strokeDasharray="3 3" />
                <XAxis dataKey="m" stroke="#7f988a" fontSize={11} />
                <YAxis yAxisId="mm" stroke="#7f988a" fontSize={11} />
                <YAxis yAxisId="t" orientation="right" stroke="#7f988a" fontSize={11} unit="°" />
                <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e2ebe5", borderRadius: 12, boxShadow: "0 8px 24px rgba(16,42,28,.08)" }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar yAxisId="mm" dataKey="pioggia" name="Pioggia (mm)" fill="#5ca8ef" radius={[4, 4, 0, 0]} />
                <Bar yAxisId="mm" dataKey="consumo" name="Acqua consumata dalle piante (mm)" fill="#e8b23a" radius={[4, 4, 0, 0]} opacity={0.8} />
                <Line yAxisId="t" dataKey="t" name="Temperatura (°C)" stroke="#34d17f" strokeWidth={2} dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="small muted">Nei mesi in cui la barra arancione supera quella blu, la pioggia non basta e serve irrigare.</div>
        </div>
        <SoilCard a={a} />
      </div>

      <CropTable crops={a.crops} />

      <div className="card">
        <h3><Icon name="coins" />Come risparmiare su questo campo</h3>
        <div className="grid cols-3">
          {a.cost_tips.map((t) => (
            <div key={t.id} className="candidate">
              <div className="row"><span className="badge badge-neutral">{TIP_CATEGORY[t.category] ?? t.category}</span>
                <span className={`badge badge-${t.impact === "high" ? "ok" : t.impact === "medium" ? "medium" : "info"}`}>{IMPACT[t.impact]}</span></div>
              <div style={{ fontWeight: 700, margin: "10px 0 4px", fontSize: 15 }}>{t.title}</div>
              <div className="small muted">{t.why}</div>
              <div className="small" style={{ marginTop: 8, color: "var(--text-2)", lineHeight: 1.55 }}>{t.action}</div>
              <Sources list={t.sources} />
            </div>
          ))}
        </div>
      </div>

      <RiceCard a={a} />

      <div className="card">
        <h3>Come funziona e quali dati usa</h3>
        <ul className="small" style={{ color: "var(--text-2)", marginTop: 0, lineHeight: 1.6 }}>
          {Object.entries(a.method).map(([k, v]) => <li key={k}><b>{k}:</b> {v}</li>)}
        </ul>
        <Sources list={a.sources} />
      </div>
    </div>
  );
}

function Kpi({ icon, label, value, sub }: { icon: string; label: string; value: string; sub: string }) {
  return <div className="card kpi"><div className="label"><Icon name={icon} size={14} />{label}</div><div className="value" style={{ fontSize: 26 }}>{value}</div><div className="meta">{sub}</div></div>;
}

function SoilCard({ a }: { a: SiteAssessment }) {
  const p = a.soil.properties;
  const frac = [["sand", "sabbia"], ["silt", "limo"], ["clay", "argilla"]].map(([k, l]) => ({ k, l, v: p[k]?.value ?? 0 }));
  const colors: Record<string, string> = { sand: "#e8b23a", silt: "#b8e05c", clay: "#c49a6c" };
  const LABEL: Record<string, string> = { soc: "Carbonio organico", nitrogen: "Azoto totale", cec: "Capacità di trattenere nutrienti (CSC)", bdod: "Densità del terreno" };
  return (
    <div className="card">
      <div className="card-head"><h3>Il terreno (primi 30 cm)</h3><span className="badge badge-forecast">{a.soil.texture_source === "inserito da te" ? "inserito da te" : "stima da mappa"}</span></div>
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <div><div className="muted tiny">Tipo di terreno</div><div style={{ fontSize: 19, fontWeight: 700 }}>{a.soil.texture ? TEXTURE[a.soil.texture] ?? a.soil.texture : "—"}</div></div>
        <div><div className="muted tiny">pH</div><div style={{ fontSize: 19, fontWeight: 700 }}>{a.soil.ph != null ? num(a.soil.ph) : "—"}</div><div className="tiny muted">{a.soil.ph_source}</div></div>
      </div>
      {p.sand && (
        <>
          <div style={{ display: "flex", height: 14, borderRadius: 7, overflow: "hidden", margin: "14px 0 6px" }}>
            {frac.map((f) => <div key={f.k} style={{ width: `${f.v}%`, background: colors[f.k] }} title={`${f.l} ${num(f.v, 0)}%`} />)}
          </div>
          <div className="row tiny">{frac.map((f) => <span key={f.k}><span className="legend-swatch" style={{ background: colors[f.k] }} />{f.l} {num(f.v, 0)}%</span>)}</div>
        </>
      )}
      <table style={{ marginTop: 10 }}><tbody>
        {Object.entries(p).filter(([k]) => LABEL[k]).map(([k, v]) => (
          <tr key={k}><td className="muted">{LABEL[k]}</td><td>{num(v.value)} {v.unit}</td></tr>
        ))}
      </tbody></table>
      <div className="tiny muted" style={{ marginTop: 8 }}>È una stima da mappa, non una misura nel tuo campo: per decidere i concimi fai un'analisi del terreno.</div>
    </div>
  );
}

function CropTable({ crops }: { crops: CropResult[] }) {
  const [open, setOpen] = useState<string | null>(null);
  const [mode, setMode] = useState<"irrigated" | "rainfed">("irrigated");
  const sorted = useMemo(() => [...crops].sort((x, y) =>
    mode === "irrigated" ? y.score_irrigated - x.score_irrigated : y.score_rainfed - x.score_rainfed), [crops, mode]);
  return (
    <div className="card">
      <div className="card-head">
        <h3><Icon name="leaf" />Quali colture sono adatte</h3>
        <div className="tabs">
          <button className={mode === "irrigated" ? "on" : ""} onClick={() => setMode("irrigated")}>Se posso irrigare</button>
          <button className={mode === "rainfed" ? "on" : ""} onClick={() => setMode("rainfed")}>Solo con la pioggia</button>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Coltura</th><th>Giudizio</th><th style={{ width: "26%" }}>Punteggio</th><th>Acqua da aggiungere</th><th>Cosa la limita</th></tr></thead>
          <tbody>
            {sorted.map((c) => {
              const s = mode === "irrigated" ? c.score_irrigated : c.score_rainfed;
              const cls = mode === "irrigated" ? c.class_irrigated : c.class_rainfed;
              return (
                <Fragment key={c.key}>
                  <tr className="selectable" onClick={() => setOpen(open === c.key ? null : c.key)}>
                    <td><b>{c.name}</b> {c.legume && <span className="badge badge-ok">leguminosa</span>}<div className="tiny muted">{SEASON[c.season]}</div></td>
                    <td><span className={`badge badge-${cls}`}>{SUIT_CLASS[cls]}</span></td>
                    <td><div className={`bar ${s < 0.4 ? "bad" : s < 0.6 ? "warn" : ""}`}><span style={{ width: `${s * 100}%` }} /></div><div className="tiny muted">{Math.round(s * 100)} su 100</div></td>
                    <td>{c.irrigation_need_mm > 0 ? `${num(c.irrigation_need_mm, 0)} mm a stagione` : <span className="muted">non serve</span>}</td>
                    <td className="small">{c.limiting_factor ?? <span className="muted">niente di importante</span>}</td>
                  </tr>
                  {open === c.key && (
                    <tr><td colSpan={5} style={{ background: "var(--bg-2)" }}>
                      <table><thead><tr><th>Fattore</th><th>Nel tuo campo</th><th>La coltura vuole</th><th>Voto</th></tr></thead><tbody>
                        {c.factors.map((f) => <tr key={f.factor}><td>{f.factor}</td><td>{f.value}</td><td className="muted">{f.requirement}</td><td>{Math.round(f.score * 100)}</td></tr>)}
                      </tbody></table>
                      {c.notes && <div className="small" style={{ marginTop: 8, color: "var(--text-2)" }}><Icon name="bulb" size={13} /> {c.notes}</div>}
                    </td></tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="tiny muted" style={{ marginTop: 8 }}>Tocca una coltura per vedere il perché del giudizio.</div>
    </div>
  );
}

function RiceCard({ a }: { a: SiteAssessment }) {
  const r = a.rice;
  const rs = r.rice_suitability;
  return (
    <div className="card">
      <div className="card-head">
        <h3><Icon name="bug" />Riso e difesa naturale dai parassiti</h3>
        {rs && <span className={`badge badge-${rs.class_irrigated}`}>riso: {SUIT_CLASS[rs.class_irrigated].toLowerCase()}</span>}
      </div>
      {r.in_eu && (
        <div className="callout danger"><Icon name="alert" /><div>
          In Italia e nell'UE il <b>granchio cinese</b> e il <b>gambero della Louisiana</b> sono specie invasive vietate:
          <b> non si possono allevare in risaia</b>. Le alternative consentite sono le anatre, i pesci autoctoni e la risaia ecologica.
        </div></div>
      )}
      <div className="grid cols-2">
        {r.systems.map((s) => (
          <div key={s.id} className="candidate" style={{ opacity: s.legal.status === "prohibited" ? 0.72 : 1 }}>
            <div className="row"><b style={{ fontSize: 15 }}>{s.name}</b><span className="spacer" /><span className={`badge badge-${s.legal.status}`}>{LEGAL[s.legal.status]}</span></div>
            <div className="small" style={{ margin: "8px 0", color: "var(--text-2)", lineHeight: 1.55 }}>{s.what}</div>
            <div className="row">{s.benefits.map((b) => <span key={b} className="chip"><Icon name="check" size={12} /> {b}</span>)}</div>
            <div className="small muted" style={{ marginTop: 8 }}><b>Serve:</b> {s.requirements.join(" · ")}</div>
            <div className="small" style={{ marginTop: 6 }}><b>Regole:</b> {s.legal.note}</div>
            <Sources list={s.sources} />
          </div>
        ))}
      </div>
      {r.water_saving.map((w) => (
        <div key={w.title} className="callout info" style={{ marginTop: 12 }}><Icon name="drop" /><div><b>{w.title}.</b> {w.text}<Sources list={w.sources} /></div></div>
      ))}
      <div className="tiny muted">{r.disclaimer}</div>
    </div>
  );
}

function Sources({ list }: { list: SourceRef[] }) {
  if (!list?.length) return null;
  return (
    <details className="tiny" style={{ marginTop: 8 }}>
      <summary style={{ cursor: "pointer", color: "var(--text-dim)" }}>Fonti ({list.length})</summary>
      {list.map((s) => <div key={s.url} style={{ marginTop: 4 }}><a href={s.url} target="_blank" rel="noreferrer">{s.title} ↗</a></div>)}
    </details>
  );
}
