import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Icon } from "./Icon";

type Option = { value: string; label: string };
type Question = { id: string; type: "crop" | "crops" | "multi" | "single"; text: string; hint?: string; options?: Option[] };
type RCrop = { key: string; name: string; family: string; group: string; gap: number; season: string };
type Reason = { effect: "good" | "warn" | "bad"; text: string; rule: boolean };
type Judged = { key: string; name: string; family: string; verdict: "ok" | "care" | "no"; score: number; reasons: Reason[]; note: string };
type PlanStep = Judged & { year: number };
interface Setup {
  questions: Question[]; crops: RCrop[]; families: Record<string, string>;
  fields: { id: string; name: string; soil_type: string | null }[]; field_id: string | null; season_year: number;
  history: { id: string; year: number; crop: string; name: string; family: string | null }[];
  prefill: { last: string | null; before: string | null; problems: string[]; detected: string[] };
}
interface Advice {
  wished: Judged[]; best_next: Judged[]; plan: PlanStep[]; plan_years: number[];
  cover_crop: { name: string; why: string; when: string } | null; tips: string[];
  sources: { title: string; url: string }[]; legal_note: string; saved?: boolean; season_year: number;
}
type Answers = { last: string | null; before: string | null; wanted: string[]; problems: string[];
  soil: string | null; manure: string | null; cover: string | null };

const FAMILY_COLOR: Record<string, string> = {
  solanacee: "#e5533d", cucurbitacee: "#f0a020", crucifere: "#2f9e6e", leguminose: "#7b5cd6", liliacee: "#c46fb0",
  ombrellifere: "#f07f3c", composite: "#5fae3e", chenopodiacee: "#b5476a", graminacee: "#c9a227", rosacee: "#e0607e",
  lamiacee: "#3aa39a",
};
const VERDICT = {
  ok: { label: "Va bene", cls: "ok", icon: "check" },
  care: { label: "Con attenzione", cls: "warn", icon: "alert" },
  no: { label: "Meglio di no", cls: "bad", icon: "ban" },
} as const;
// most common crops first in the pickers
const POPULAR = ["tomato", "potato", "zucchini", "pepper", "eggplant", "lettuce", "bean", "cabbage", "onion", "garlic",
  "carrot", "wheat", "maize", "melon", "watermelon", "strawberry", "pea", "fennel", "chard", "spinach"];

export default function Rotation() {
  const [fieldId, setFieldId] = useState<string | undefined>();
  const setup = useQuery({
    queryKey: ["rotation-setup", fieldId],
    queryFn: () => api.get<Setup>(`/api/v1/rotation/setup${fieldId ? `?field_id=${fieldId}` : ""}`),
    refetchInterval: false, staleTime: 60000,
  });
  const s = setup.data;
  const [step, setStep] = useState(0);
  const [ans, setAns] = useState<Answers>({ last: null, before: null, wanted: [], problems: [], soil: null, manure: null, cover: null });
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (!s) return;
    setAns((a) => ({ ...a, last: s.prefill.last ?? a.last, before: s.prefill.before ?? a.before,
                     problems: a.problems.length ? a.problems : s.prefill.problems }));
  }, [s]);

  const advise = useMutation({
    mutationFn: (save: boolean) => api.post<Advice>("/api/v1/rotation/advise", { field_id: s?.field_id, ...ans, save }),
  });
  const finish = () => { setDone(true); advise.mutate(false); };

  if (!s) {
    return setup.isError ? (
      <div className="callout danger" style={{ margin: 0 }}><Icon name="alert" />
        <div style={{ flex: 1 }}>Non riesco a caricare le domande.</div>
        <button className="btn sm" onClick={() => setup.refetch()}>Riprova</button></div>
    ) : <div className="card muted">Caricamento…</div>;
  }
  const q = s.questions[step];

  if (done) {
    return <Result s={s} a={advise.data} loading={advise.isPending} ans={ans}
                   onRestart={() => { setDone(false); setStep(0); }}
                   onSave={() => advise.mutate(true)} saving={advise.isPending} />;
  }

  const set = (patch: Partial<Answers>) => setAns((a) => ({ ...a, ...patch }));
  const next = () => (step < s.questions.length - 1 ? setStep(step + 1) : finish());
  return (
    <div className="stack">
      {s.fields.length > 1 && (
        <div className="row" style={{ gap: 6 }}>
          <span className="small muted">Campo:</span>
          {s.fields.map((f) => (
            <button key={f.id} className={`answer ${s.field_id === f.id ? "on" : ""}`} onClick={() => { setFieldId(f.id); setStep(0); }}>{f.name}</button>
          ))}
        </div>
      )}
      <div className="card wizard">
        <div className="wiz-progress"><span style={{ width: `${((step + 1) / s.questions.length) * 100}%` }} /></div>
        <div className="tiny muted">Domanda {step + 1} di {s.questions.length}{s.fields.length === 1 && s.field_id ? ` · ${s.fields[0].name}` : ""}</div>
        <h2 className="wiz-q">{q.text}</h2>
        {q.hint && <div className="small muted">{q.hint}</div>}
        {step === 0 && s.prefill.detected.length > 0 && (
          <div className="callout info" style={{ margin: "10px 0 0" }}><Icon name="info" />
            <div className="small">AGROAI sa già: {s.prefill.detected.join(" · ")}</div></div>
        )}
        <div style={{ marginTop: 14 }}>
          {q.type === "crop" && (
            <CropPicker crops={s.crops} value={q.id === "last" ? ans.last : ans.before}
                        onPick={(k) => { set(q.id === "last" ? { last: k } : { before: k }); setTimeout(next, 150); }} />
          )}
          {q.type === "crops" && (
            <CropPicker crops={s.crops} multi values={ans.wanted}
                        onToggle={(k) => set({ wanted: ans.wanted.includes(k) ? ans.wanted.filter((x) => x !== k) : [...ans.wanted, k] })} />
          )}
          {q.type === "multi" && (
            <div className="opt-list">
              {q.options!.map((o) => {
                const on = o.value === "none" ? ans.problems.length === 0 : ans.problems.includes(o.value);
                return (
                  <button key={o.value} className={`opt ${on ? "on" : ""}`}
                          onClick={() => set({ problems: o.value === "none" ? [] :
                            on ? ans.problems.filter((x) => x !== o.value) : [...ans.problems, o.value] })}>
                    <span className="opt-check"><Icon name={on ? "check" : "plus"} size={14} stroke={2.6} /></span>{o.label}
                  </button>
                );
              })}
            </div>
          )}
          {q.type === "single" && (
            <div className="opt-list">
              {q.options!.map((o) => {
                const key = q.id as "soil" | "manure" | "cover";
                return (
                  <button key={o.value} className={`opt ${ans[key] === o.value ? "on" : ""}`}
                          onClick={() => { set({ [key]: o.value } as Partial<Answers>); setTimeout(next, 150); }}>
                    {o.label}
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <div className="wiz-nav">
          <button className="btn ghost" disabled={step === 0} onClick={() => setStep(step - 1)}><Icon name="arrow-left" size={15} />Indietro</button>
          <span className="spacer" />
          {(q.type === "crop" || q.type === "single") && <button className="btn ghost" onClick={next}>Salta</button>}
          {(q.type === "crops" || q.type === "multi") && (
            <button className="btn" onClick={next}>
              {q.type === "crops" && !ans.wanted.length ? "Scegli tu" : step === s.questions.length - 1 ? "Vedi il piano" : "Avanti"}
              <Icon name="arrow-right" size={15} />
            </button>
          )}
        </div>
      </div>
      {s.history.length > 0 && <History s={s} />}
    </div>
  );
}

export function CropPicker({ crops, value, values, multi, onPick, onToggle }: {
  crops: RCrop[]; value?: string | null; values?: string[]; multi?: boolean;
  onPick?: (k: string | null) => void; onToggle?: (k: string) => void;
}) {
  const [q, setQ] = useState("");
  const [all, setAll] = useState(false);
  const list = useMemo(() => {
    const byKey = Object.fromEntries(crops.map((c) => [c.key, c]));
    const popular = POPULAR.map((k) => byKey[k]).filter(Boolean);
    const rest = crops.filter((c) => !POPULAR.includes(c.key));
    const ordered = [...popular, ...rest];
    const f = q.trim().toLowerCase();
    if (f) return ordered.filter((c) => c.name.toLowerCase().includes(f));
    return all ? ordered : popular.slice(0, 16);
  }, [crops, q, all]);
  return (
    <div>
      <div className="search-box"><Icon name="leaf" size={16} />
        <input placeholder="Cerca una coltura (es. finocchio)" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="crop-chips">
        {list.map((c) => {
          const on = multi ? values?.includes(c.key) : value === c.key;
          return (
            <button key={c.key} className={`crop-chip ${on ? "on" : ""}`} style={{ ["--fam" as any]: FAMILY_COLOR[c.family] ?? "#7a8d81" }}
                    onClick={() => (multi ? onToggle!(c.key) : onPick!(c.key))}>
              <span className="fam-dot" />{c.name.split(" (")[0]}
            </button>
          );
        })}
        {!multi && (
          <>
            <button className={`crop-chip neutral ${value === "rest" ? "on" : ""}`} onClick={() => onPick!("rest")}>Niente / riposo</button>
            <button className="crop-chip neutral" onClick={() => onPick!(null)}>Non lo so</button>
          </>
        )}
      </div>
      {!q && <button className="link-btn" onClick={() => setAll(!all)}>{all ? "Mostra solo le più comuni" : "Mostra tutte le colture"}</button>}
    </div>
  );
}

function VerdictPill({ v }: { v: Judged["verdict"] }) {
  const m = VERDICT[v];
  return <span className={`status-pill s-${m.cls}`}><Icon name={m.icon} size={13} stroke={2.6} />{m.label}</span>;
}

function Result({ s, a, loading, ans, onRestart, onSave, saving }: {
  s: Setup; a: Advice | undefined; loading: boolean; ans: Answers;
  onRestart: () => void; onSave: () => void; saving: boolean;
}) {
  const qc = useQueryClient();
  useEffect(() => { if (a?.saved) qc.invalidateQueries({ queryKey: ["rotation-setup"] }); }, [a?.saved, qc]);
  if (!a) return <div className="card muted">{loading ? "Preparo il piano…" : "Nessun risultato."}</div>;
  const first = a.plan[0];
  const nameOf = (k: string | null) => (k ? s.crops.find((c) => c.key === k)?.name.split(" (")[0] ?? (k === "rest" ? "Riposo" : k) : "—");
  return (
    <div className="stack">
      <div className="card rot-hero">
        <div className="tiny muted">Dopo {nameOf(ans.last)}{ans.before ? ` e ${nameOf(ans.before).toLowerCase()}` : ""}, per la stagione {a.plan_years[0]}</div>
        <div className="rot-best">
          <span className="rot-best-dot" style={{ background: FAMILY_COLOR[first?.family] ?? "#7a8d81" }} />
          <div>
            <div className="tiny muted">La scelta migliore</div>
            <div className="rot-best-name">{first?.name.split(" (")[0]}</div>
            <div className="small muted">{s.families[first?.family]?.split(" (")[0]}</div>
          </div>
        </div>
        <ul className="reason-list">
          {first?.reasons.filter((r) => r.effect !== "bad").slice(0, 3).map((r) => <ReasonLi key={r.text} r={r} />)}
        </ul>
      </div>

      {a.wished.length > 0 && (
        <div className="card">
          <h3><Icon name="sprout" />Le colture che volevi</h3>
          <div className="stack" style={{ gap: 10 }}>
            {a.wished.map((w) => (
              <details key={w.key} className={`wish wish-${w.verdict}`} open={w.verdict !== "ok"}>
                <summary><span className="fam-dot" style={{ background: FAMILY_COLOR[w.family] }} /><b>{w.name.split(" (")[0]}</b>
                  <span className="spacer" /><VerdictPill v={w.verdict} /></summary>
                <ul className="reason-list">{w.reasons.map((r) => <ReasonLi key={r.text} r={r} />)}</ul>
                {w.note && <div className="tiny muted">{w.note}</div>}
              </details>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <h3><Icon name="clock" />Il piano per i prossimi 4 anni</h3>
        <div className="timeline">
          {a.plan.map((p, i) => (
            <div key={i} className="tl-step" style={{ ["--fam" as any]: FAMILY_COLOR[p.family] ?? "#9aa9a0" }}>
              <div className="tl-year">{a.plan_years[i]}</div>
              <div className="tl-card">
                <div className="tl-name">{p.name.split(" (")[0]}</div>
                <div className="tiny muted">{s.families[p.family]?.split(" (")[0] ?? ""}</div>
                <div className="tiny" style={{ marginTop: 4, color: "var(--text-2)" }}>
                  {p.reasons.find((r) => r.effect === "good")?.text ?? p.reasons[0]?.text}
                </div>
              </div>
            </div>
          ))}
        </div>
        {a.cover_crop && (
          <div className="cover-box">
            <Icon name="leaf" size={18} />
            <div><b>Tra un raccolto e l'altro: {a.cover_crop.name}</b>
              <div className="small muted">{a.cover_crop.why}. Quando: {a.cover_crop.when}.</div></div>
          </div>
        )}
      </div>

      <div className="card">
        <h3><Icon name="bulb" />Altre buone scelte per il {a.plan_years[0]}</h3>
        <div className="crop-chips">
          {a.best_next.map((b) => (
            <span key={b.key} className="crop-chip static" style={{ ["--fam" as any]: FAMILY_COLOR[b.family] }}>
              <span className="fam-dot" />{b.name.split(" (")[0]}
            </span>
          ))}
        </div>
        <ul className="tips">{a.tips.map((t) => <li key={t}>{t}</li>)}</ul>
      </div>

      <div className="row" style={{ gap: 8 }}>
        <button className="btn ghost" onClick={onRestart}><Icon name="refresh" size={14} />Rifai le domande</button>
        {s.field_id && (ans.last || ans.before) && (
          <button className="btn" onClick={onSave} disabled={saving || a.saved}>
            <Icon name="check" size={14} />{a.saved ? "Salvato nello storico" : "Salva nello storico del campo"}
          </button>
        )}
      </div>

      <details className="card more">
        <summary><Icon name="book" size={15} />Da dove vengono queste regole</summary>
        <div className="small" style={{ marginTop: 10 }}>{a.legal_note}</div>
        <ul className="tiny" style={{ paddingLeft: 18 }}>
          {a.sources.map((x) => <li key={x.url}><a href={x.url} target="_blank" rel="noreferrer">{x.title}</a></li>)}
        </ul>
      </details>
      {s.history.length > 0 && <History s={s} />}
    </div>
  );
}

function ReasonLi({ r }: { r: Reason }) {
  return (
    <li className={`reason r-${r.effect}`}>
      <Icon name={r.effect === "good" ? "check" : r.effect === "bad" ? "ban" : "alert"} size={14} />
      <span>{r.text}{r.rule && <span className="rule-tag">regola</span>}</span>
    </li>
  );
}

function History({ s }: { s: Setup }) {
  const qc = useQueryClient();
  const del = useMutation({
    mutationFn: (id: string) => api.del(`/api/v1/rotation/history/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rotation-setup"] }),
  });
  return (
    <div className="card">
      <h3><Icon name="book" />Storico del campo</h3>
      <div className="stack" style={{ gap: 6 }}>
        {s.history.map((h) => (
          <div key={h.id} className="hist-row">
            <b>{h.year}</b>
            <span className="fam-dot" style={{ background: FAMILY_COLOR[h.family ?? ""] ?? "#9aa9a0" }} />
            <span style={{ flex: 1 }}>{h.name.split(" (")[0]}</span>
            <button className="icon-btn" title="Elimina" onClick={() => del.mutate(h.id)}><Icon name="trash" size={14} /></button>
          </div>
        ))}
      </div>
    </div>
  );
}
