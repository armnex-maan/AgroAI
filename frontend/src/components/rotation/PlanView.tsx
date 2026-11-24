import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { Icon } from "../Icon";
import FieldCanvas from "./FieldCanvas";
import SplitCard from "./SplitCard";
import { Assignment, cropColor, FarmData, fmtArea, isGrowing, LEVEL, MONTHS, PlanResult, Plot, Reason, shortName, VERDICT } from "./types";

export default function PlanView({ plot, farm, goals }: { plot: Plot; farm: FarmData; goals: any }) {
  const qc = useQueryClient();
  const [res, setRes] = useState<PlanResult | null>(null);
  const [view, setView] = useState<number | "now" | "compare">(0);
  const [years, setYears] = useState<{ year: number; assignments: Assignment[] }[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const compute = useMutation({
    mutationFn: () => api.post<PlanResult>(`/api/v1/rotation/plots/${plot.id}/plan`, goals ?? {}),
    onSuccess: (r) => {
      setRes(r);
      // a saved plan for a year replaces the proposal for that year
      setYears(r.years.map((y) => {
        const sp = plot.plans.find((p) => p.year === y.year);
        return sp ? { year: y.year, assignments: mergeSaved(y.assignments, sp.assignments) } : { year: y.year, assignments: y.assignments };
      }));
    },
  });
  useEffect(() => { compute.mutate(); }, [plot.id, JSON.stringify(goals), plot.sections.length, plot.history.length]); // eslint-disable-line

  type Judged = { verdict: Assignment["verdict"]; reasons: Reason[]; name: string; family: string };
  const check = useMutation({
    // the changed year is checked, then every later year of the same bed, because its history has changed
    mutationFn: async (v: { yi: number; section_id: string | null; crop: string }) => {
      const out: { yi: number; crop: string; j: Judged }[] = [];
      const planned: Record<string, string> = {};
      for (let i = 0; i < years.length; i++) {
        const own = years[i].assignments.find((x) => x.section_id === v.section_id);
        const crop = i === v.yi ? v.crop : own?.crop;
        if (i >= v.yi && crop && crop !== "cover") {
          const j = await api.post<Judged>(`/api/v1/rotation/plots/${plot.id}/check`,
            { section_id: v.section_id, crop, year: years[i].year, planned, integrated: goals?.integrated ?? null });
          out.push({ yi: i, crop, j });
        }
        if (crop) planned[String(years[i].year)] = crop;
      }
      return out;
    },
    onSuccess: (res, v) => setYears((ys) => ys.map((y, i) => {
      const r = res.find((x) => x.yi === i);
      if (!r) return y;
      const note: Reason = i === v.yi
        ? { effect: "warn", text: "Coltura scelta da te: controllata con le stesse regole.", rule: false, level: "suggerimento", source: null }
        : { effect: r.j.verdict === "ok" ? "good" : "warn", text: "Ricontrollata dopo la tua modifica a un anno precedente.", rule: false, level: "suggerimento", source: null };
      return { ...y, assignments: y.assignments.map((a) => a.section_id !== v.section_id ? a : {
        ...a, crop: r.crop, name: r.j.name, family: r.j.family, verdict: r.j.verdict, manual: i === v.yi ? true : a.manual,
        reasons: [note, ...r.j.reasons],
      }) };
    })),
  });
  const save = useMutation({
    mutationFn: async () => {
      for (const y of years) await api.put(`/api/v1/rotation/plots/${plot.id}/plans/${y.year}`, { assignments: y.assignments, goals });
    },
    onSuccess: () => { setSaved(`Piano ${years[0]?.year}–${years[years.length - 1]?.year} salvato.`); qc.invalidateQueries({ queryKey: ["rotation-farm"] }); },
  });

  const byYearSection = (as: Assignment[]) => Object.fromEntries(as.filter((a) => a.section_id).map((a) => [a.section_id!, a]));
  const current = res?.current.assignments ?? [];
  const W = plot.width_m ?? 10, L = plot.length_m ?? 10;
  const sel = typeof view === "number" ? years[view] : null;
  const unplaced = typeof view === "number" ? res?.years[view]?.unplaced ?? [] : [];
  const cropsInYear = useMemo(() => {
    const m = new Map<string, Assignment>();
    (sel?.assignments ?? []).forEach((a) => a.crop !== "cover" && m.set(a.crop, a));
    return [...m.values()];
  }, [sel]);

  if (!res) return <div className="card muted">{compute.isPending ? "Calcolo il piano di rotazione…" : compute.isError ? "Non riesco a calcolare il piano." : "…"}</div>;
  const canvas = (as: Assignment[], compact = false, h?: number) => (
    <FieldCanvas width={W} length={L} shape={plot.shape} outline={plot.outline} orientation={plot.orientation_deg}
                 sections={plot.sections} mode="view" crops={byYearSection(as)} catalog={farm.crops} compact={compact} height={h} />
  );
  const noBeds = !plot.sections.some((s) => isGrowing(s.kind));

  return (
    <div className="stack">
      <div className={`coverage cov-${res.coverage.level}`}>
        <Icon name={res.coverage.level === "none" ? "alert" : "book"} size={18} />
        <div className="small">{res.coverage.text}
          {res.general_rule && <div className="tiny" style={{ marginTop: 4 }}><b>Regola generale:</b> {res.general_rule.text}{" "}
            <a href={res.general_rule.source.url} target="_blank" rel="noreferrer">fonte ({res.general_rule.source.year})</a></div>}
        </div>
      </div>
      {noBeds && <div className="card"><SplitCard plot={plot} /></div>}

      <div className="year-tabs">
        <button className={view === "now" ? "on" : ""} onClick={() => setView("now")}>Oggi<small>{res.current.year}</small></button>
        {years.map((y, i) => <button key={y.year} className={view === i ? "on" : ""} onClick={() => setView(i)}>Piano<small>{y.year}</small></button>)}
        <button className={view === "compare" ? "on" : ""} onClick={() => setView("compare")}><Icon name="layers" size={14} />Confronta</button>
      </div>

      {view === "compare" ? (
        <div className="compare-grid">
          {[{ year: res.current.year, assignments: current, label: "Oggi" }, ...years.map((y) => ({ ...y, label: "Piano" }))].map((y) => (
            <div key={y.year} className="card compare-cell">
              <div className="small"><b>{y.label} {y.year}</b></div>
              {canvas(y.assignments, true)}
              <div className="legend">{uniq(y.assignments).map((a) => <Legend key={a.crop} a={a} />)}</div>
            </div>
          ))}
        </div>
      ) : view === "now" ? (
        <div className="plan-grid">
          <div className="card" style={{ padding: 10 }}>{canvas(current)}</div>
          <div className="card">
            <h3><Icon name="book" />Stagione {res.current.year}</h3>
            {current.length ? current.map((a, i) => (
              <div key={i} className="bed-row"><span className="swatch" style={{ background: cropColor(a.crop, a.family) }} />
                <b>{shortName(a.name)}</b><span className="muted small">{a.area_m2 ? fmtArea(a.area_m2) : ""}</span></div>
            )) : <div className="small muted">Nessuna coltura registrata per quest'anno: compila lo storico.</div>}
          </div>
        </div>
      ) : sel && (
        <div className="plan-grid">
          <div className="card" style={{ padding: 10 }}>
            {canvas(sel.assignments)}
            <div className="legend">{uniq(sel.assignments).map((a) => <Legend key={a.crop} a={a} />)}</div>
          </div>
          <div className="stack">
            <div className="card">
              <h3><Icon name="sprout" />Cosa mettere nel {sel.year}</h3>
              <div className="stack" style={{ gap: 8 }}>
                {sel.assignments.map((a) => {
                  const k = `${sel.year}-${a.section_id}`;
                  const v = VERDICT[a.verdict] ?? VERDICT.care; // a plan saved without a verdict is shown as "to check"
                  return (
                    <div key={k} className={`bed-card v-${a.verdict}`}>
                      <div className="bed-row" onClick={() => setOpen(open === k ? null : k)} style={{ cursor: "pointer" }}>
                        <span className="swatch" style={{ background: a.crop === "cover" ? "#c9b98f" : cropColor(a.crop, a.family) }} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <b>{shortName(a.name)}</b>
                          <div className="tiny muted">{a.section} · {fmtArea(a.area_m2)}</div>
                        </div>
                        <span className={`status-pill s-${v.cls}`}><Icon name={v.icon} size={12} stroke={2.6} />{v.label}</span>
                      </div>
                      {open === k && (
                        <div className="bed-detail">
                          <label className="field">Cambia coltura
                            <select value={a.crop} onChange={(e) => check.mutate({ yi: view as number, section_id: a.section_id, crop: e.target.value })}>
                              {a.crop === "cover" && <option value="cover">Sovescio</option>}
                              {farm.crops.filter((c) => c.season !== "pluriennale").map((c) => <option key={c.key} value={c.key}>{shortName(c.name)}</option>)}
                            </select>
                          </label>
                          <ul className="reason-list">{(a.reasons ?? []).map((r, i) => <ReasonLi key={i} r={r} />)}</ul>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              {unplaced.length > 0 && (
                <div className="callout danger" style={{ marginTop: 12 }}><Icon name="alert" />
                  <div className="small"><b>Non è stato possibile inserire:</b>
                    <ul style={{ margin: "4px 0 0", paddingLeft: 16 }}>{unplaced.map((u) => <li key={u.crop}><b>{shortName(u.name)}</b>: {u.why}</li>)}</ul></div></div>
              )}
            </div>
            <div className="card">
              <h3><Icon name="calendar" />Calendario {sel.year}</h3>
              <div className="cal">
                <div className="cal-row head"><span />{MONTHS.map((m, i) => <span key={i}>{m}</span>)}</div>
                {cropsInYear.map((a) => (
                  <div key={a.crop} className="cal-row">
                    <span className="cal-name">{shortName(a.name)}</span>
                    {MONTHS.map((_, i) => {
                      const m = i + 1, c = a.calendar ?? {};
                      const t = c.raccolta?.includes(m) ? "h" : c.trapianto?.includes(m) ? "t" : c.semina?.includes(m) ? "s" : "";
                      return <span key={i} className={`cal-cell c-${t}`} title={{ s: "semina", t: "trapianto", h: "raccolta", "": "" }[t]} />;
                    })}
                  </div>
                ))}
              </div>
              <div className="row tiny muted" style={{ gap: 12, marginTop: 8 }}>
                <span><i className="cal-cell c-s" /> semina</span><span><i className="cal-cell c-t" /> trapianto</span><span><i className="cal-cell c-h" /> raccolta</span>
              </div>
              <div className="tiny muted" style={{ marginTop: 4 }}>Indicativo per il pieno campo nel Centro-Nord: cambia con zona e varietà.</div>
            </div>
          </div>
        </div>
      )}

      <div className="row" style={{ gap: 8 }}>
        <button className="btn" onClick={() => save.mutate()} disabled={save.isPending}><Icon name="check" size={15} />{save.isPending ? "Salvo…" : "Salva il piano pluriennale"}</button>
        <button className="btn ghost" onClick={() => compute.mutate()}><Icon name="refresh" size={14} />Ricalcola</button>
        {saved && <span className="small" style={{ color: "var(--accent)" }}>{saved}</span>}
      </div>
      {res.notes.length > 1 && <ul className="tips">{res.notes.slice(1).map((n) => <li key={n}>{n}</li>)}</ul>}
      <div className="level-legend tiny">
        {Object.values(LEVEL).map((l) => <span key={l.label} className={`lv ${l.cls}`}>{l.label}</span>)}
        <span className="muted">· ogni motivazione indica il suo tipo e, quando c'è, la fonte</span>
      </div>
    </div>
  );
}

function mergeSaved(proposed: Assignment[], saved: Assignment[]): Assignment[] {
  return proposed.map((a) => {
    const s = saved.find((x) => x.section_id === a.section_id);
    if (!s || s.crop === a.crop) return s?.manual ? { ...a, manual: true } : a;
    const text = s.manual ? "Coltura scelta da te nel piano salvato." : "Coltura del piano salvato.";
    return { ...a, ...s, reasons: [{ effect: s.manual ? "warn" : "good", text, rule: false, level: "suggerimento", source: null }] };
  });
}
function uniq(as: Assignment[]) {
  const m = new Map<string, Assignment>();
  as.forEach((a) => !m.has(a.crop) && m.set(a.crop, a));
  return [...m.values()];
}
function Legend({ a }: { a: Assignment }) {
  return <span className="legend-item"><span className="swatch" style={{ background: a.crop === "cover" ? "#c9b98f" : cropColor(a.crop, a.family) }} />{shortName(a.name)}</span>;
}
export function ReasonLi({ r }: { r: Reason }) {
  const lv = LEVEL[r.level] ?? LEVEL.buona_pratica;
  return (
    <li className={`reason r-${r.effect}`}>
      <Icon name={r.effect === "good" ? "check" : r.effect === "bad" ? "ban" : "alert"} size={14} />
      <span>{r.text} <span className={`lv ${lv.cls}`}>{lv.label}</span>
        {r.source && <> <a className="tiny" href={r.source.url} target="_blank" rel="noreferrer">fonte{r.source.year ? ` ${r.source.year}` : ""}</a></>}
      </span>
    </li>
  );
}
