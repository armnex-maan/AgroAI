/**
 * AI Farm Layout Generator (phase 6): alternative layouts of a plot, each with the plan the rotation engine makes
 * for it, compared with plain figures and explained. «Prova nel 3D» loads one as an unsaved change (undo/redo,
 * «Salva progetto»). Nothing is written by the generator itself.
 */
import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "../../../api/client";
import { Icon } from "../../Icon";
import { Assignment, cropColor, FarmData, fmtArea, KIND_LABEL, Section, shortName } from "../types";

export interface AiVariant {
  key: string; title: string; best?: boolean; score: number; why: string[];
  sections: (Section & { id: string; area_m2: number })[];
  plan: { year: number; assignments: Assignment[]; unplaced: { crop: string; name: string; why: string }[] }[];
  metrics: { parts: number; growing_m2: number; path_m2: number; path_share: number; bed_m2: number;
    verdicts: { ok: number; care: number; no: number }; wanted_cover: number | null; unplaced: string[] };
}
interface AiResult { plot_id: string; years: number[]; wanted: string[]; variants: AiVariant[]; notes: string[] }

const KIND_FILL: Record<string, string> = { path: "#d9c8a4", water: "#7fb6dc", greenhouse: "#e8eef2", access: "#cdb68c", no_crop: "#b9c7a8", shade: "#9fb88a" };

/** Plan of the layout seen from above (north up), beds coloured with the crop of the first year. */
function Sketch({ v, W, L }: { v: AiVariant; W: number; L: number }) {
  const s = 150 / Math.max(W, L);
  const first = v.plan[0]?.assignments ?? [];
  return (
    <svg width={W * s + 2} height={L * s + 2} viewBox={`-1 -1 ${W * s + 2} ${L * s + 2}`} role="img" aria-label={`Schema: ${v.title}`}>
      <rect x={0} y={0} width={W * s} height={L * s} fill="#eef1e8" stroke="#b9c2b3" />
      {v.sections.map((x) => {
        const a = first.find((q) => q.section_id === x.id);
        const fill = a ? cropColor(a.crop, a.family) : KIND_FILL[x.kind] ?? "#c9b896";
        return <rect key={x.id} x={x.x * s} y={x.y * s} width={x.w * s} height={x.h * s} fill={fill} stroke={x.kind === "greenhouse" ? "#7d8b94" : "#fff"} strokeWidth={0.8}>
          <title>{x.name}{a ? ` – ${shortName(a.name)}` : ""}</title></rect>;
      })}
    </svg>
  );
}

export default function AiGenerator({ farm, onClose, onApply }: {
  farm: FarmData; onClose: () => void; onApply: (plotId: string, v: AiVariant) => void;
}) {
  const plots = farm.plots.filter((p) => p.width_m && p.length_m);
  const [pid, setPid] = useState(plots[0]?.id ?? "");
  const [parts, setParts] = useState("");
  const [path, setPath] = useState("");
  const [gh, setGh] = useState("");
  const [water, setWater] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const plot = plots.find((p) => p.id === pid);
  const wanted = useMemo(() => Object.keys(plot?.profile?.goals?.wanted ?? {}), [plot]);
  const names = useMemo(() => Object.fromEntries(farm.crops.map((c) => [c.key, shortName(c.name)])), [farm.crops]);
  const gen = useMutation({
    mutationFn: () => api.post<AiResult>(`/api/v1/rotation/plots/${pid}/layout-ai`, {
      parts: parts ? +parts : null, path_m: path === "" ? null : +path, greenhouse_m2: gh ? +gh : null, water_point: water }),
  });
  const res = gen.data?.plot_id === pid ? gen.data : null;
  const sections = plot?.sections.length ?? 0;
  return (
    <div className="vp-props vp-ai">
      <div className="row"><b><Icon name="spark" size={16} /> Generatore AI di layout</b><span className="spacer" />
        <button className="icon-btn" onClick={onClose} aria-label="Chiudi"><Icon name="minus" size={14} /></button></div>
      <div className="tiny muted">Propone più modi di dividere un appezzamento. Per ognuno il motore di rotazione sceglie le colture {farm.season_year + 1}–{farm.season_year + 4}
        con le regole della tua regione. Niente viene salvato finché non premi «Salva progetto».</div>
      {!plots.length ? <div className="small" style={{ marginTop: 8 }}>Serve un appezzamento con le misure o tracciato sulla mappa.</div> : <>
        <div className="vp-form">
          <label className="field" style={{ gridColumn: "1 / -1" }}>Appezzamento
            <select value={pid} onChange={(e) => { setPid(e.target.value); gen.reset(); }}>
              {plots.map((p) => <option key={p.id} value={p.id}>{p.name} · {fmtArea(p.area_m2 ?? (p.width_m! * p.length_m!))}</option>)}
            </select></label>
          <label className="field">Parti<select value={parts} onChange={(e) => setParts(e.target.value)}>
            <option value="">Automatico</option>{Array.from({ length: 11 }, (_, i) => i + 2).map((n) => <option key={n} value={n}>{n}</option>)}</select></label>
          <label className="field">Passaggi (m)<input type="number" min={0} max={12} step={0.1} placeholder="automatico" value={path} onChange={(e) => setPath(e.target.value)} /></label>
          <label className="field">Serra (m²)<input type="number" min={0} step={10} placeholder="nessuna" value={gh} onChange={(e) => setGh(e.target.value)} /></label>
          <label className="field vp-check"><input type="checkbox" checked={water} onChange={(e) => setWater(e.target.checked)} />Punto d'acqua</label>
        </div>
        <div className="tiny muted">Colture che vuoi: {wanted.length ? wanted.map((k) => names[k] ?? k).join(", ") : "nessuna indicata (sceglie il motore)"} — si cambiano nel Questionario.</div>
        {sections > 0 && <div className="tiny" style={{ color: "var(--warn, #b7791f)" }}>Questo appezzamento è già diviso in {sections} parti: se provi una proposta, sostituisce il disegno (solo dopo «Salva progetto»; lo storico resta).</div>}
        <button className="btn sm" style={{ marginTop: 8 }} disabled={gen.isPending || !pid} onClick={() => gen.mutate()}>
          <Icon name="spark" size={13} />{gen.isPending ? "Genero le proposte…" : res ? "Rigenera" : "Genera proposte"}</button>
        {gen.isError && <div className="tiny" style={{ color: "var(--danger)", marginTop: 6 }}>{(gen.error as Error).message}</div>}
      </>}

      {res && plot && <div className="vp-ai-list">
        {res.variants.map((v) => {
          const m = v.metrics, tot = m.verdicts.ok + m.verdicts.care + m.verdicts.no;
          return (
            <div key={v.key} className={`vp-ai-card ${v.best ? "best" : ""}`}>
              <div className="row" style={{ gap: 6 }}><b>{v.title}</b><span className="spacer" />
                {v.best && <span className="vp-badge">Consigliata</span>}<span className="vp-score" title="Punteggio di confronto">{v.score}</span></div>
              <div className="row" style={{ gap: 10, alignItems: "flex-start", marginTop: 6 }}>
                <Sketch v={v} W={plot.width_m!} L={plot.length_m!} />
                <dl className="vp-kv" style={{ flex: 1, margin: 0 }}>
                  <dt>Parti</dt><dd>{m.parts} · in media {fmtArea(m.bed_m2)}</dd>
                  <dt>Coltivabile</dt><dd>{fmtArea(m.growing_m2)}</dd>
                  <dt>Passaggi</dt><dd>{Math.round(m.path_share * 100)}%</dd>
                  <dt>Regole</dt><dd><span className="vp-st ok" />{m.verdicts.ok} <span className="vp-st warn" />{m.verdicts.care} <span className="vp-st bad" />{m.verdicts.no} <small>su {tot}</small></dd>
                  {m.wanted_cover != null && <><dt>Colture richieste</dt><dd>{Math.round(m.wanted_cover * 100)}% trovano posto</dd></>}
                </dl>
              </div>
              {m.unplaced.length > 0 && <div className="tiny" style={{ color: "var(--warn, #b7791f)" }}>Non trovano posto in qualche anno: {m.unplaced.map(shortName).join(", ")}.</div>}
              <div className="tiny muted" style={{ marginTop: 4 }}>{res.years[0]}: {v.plan[0]?.assignments.map((a) => `${a.section} ${a.crop === "cover" ? "sovescio" : shortName(a.name)}`).join(" · ")}</div>
              <button className="btn ghost sm" onClick={() => setOpen(open === v.key ? null : v.key)}><Icon name="info" size={13} />{open === v.key ? "Nascondi i motivi" : "Perché"}</button>
              {open === v.key && <ul className="vp-reasons">{v.why.map((w, i) => <li key={i}>{w}</li>)}
                {v.sections.filter((x) => x.kind !== "bed" && x.kind !== "path").map((x) => <li key={x.id}>{KIND_LABEL[x.kind]}: {fmtArea(x.area_m2)}</li>)}</ul>}
              <button className="btn sm" onClick={() => onApply(plot.id, v)}><Icon name="layers" size={13} />Prova nel 3D</button>
            </div>
          );
        })}
        <div className="tiny muted">{res.notes.join(" ")}</div>
      </div>}
    </div>
  );
}
