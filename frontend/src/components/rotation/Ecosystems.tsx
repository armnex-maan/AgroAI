import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { Icon } from "../Icon";
import { LEVEL, Plot } from "./types";

interface Src { id: string; title: string; url: string; year: number | null }
interface Eco {
  key: string; icon: string; title: string; summary: string; pairs: string[]; where: string; benefits: string[];
  cautions: string[]; fit: boolean; why: string[]; sources: Src[]; level: string; calculator?: boolean;
}
interface Aqua {
  bed_m2: number; feed_g_day: [number, number]; fish_kg: [number, number]; water_l_min: number; note: string;
  fish: { key: string; name: string; temp: string; fit: string }[]; source: Src;
}

export default function Ecosystems({ plot }: { plot: Plot }) {
  const q = useQuery({ queryKey: ["ecosystems", plot.id, JSON.stringify(plot.profile)], refetchInterval: false,
    queryFn: () => api.get<{ items: Eco[] }>(`/api/v1/rotation/plots/${plot.id}/ecosystems`) });
  const [open, setOpen] = useState<string | null>(null);
  if (q.isError) return <div className="callout danger"><Icon name="alert" /><div style={{ flex: 1 }}>Non riesco a caricare i suggerimenti.</div><button className="btn sm" onClick={() => q.refetch()}>Riprova</button></div>;
  if (!q.data) return <div className="card muted">Caricamento…</div>;
  return (
    <div className="stack">
      <div className="card">
        <h3><Icon name="leaf" />Ecosistemi da costruire</h3>
        <div className="small muted">Idee per far lavorare insieme piante, animali e acqua in questo appezzamento. Sono buone pratiche, non obblighi: ognuna indica la sua fonte.</div>
      </div>
      {q.data.items.map((e) => (
        <div key={e.key} className={`card eco-card ${e.fit ? "" : "eco-off"}`}>
          <button className="eco-head" onClick={() => setOpen(open === e.key ? null : e.key)}>
            <span className="eco-ic"><Icon name={e.icon} size={20} /></span>
            <span style={{ flex: 1, minWidth: 0, textAlign: "left" }}>
              <b>{e.title}</b>
              <span className="small muted eco-sum">{e.summary}</span>
            </span>
            <span className={`pill ${e.fit ? "ok" : "warn"}`}>{e.fit ? "Adatto" : "Da valutare"}</span>
            <Icon name="chevron" size={16} />
          </button>
          {e.why.length > 0 && <ul className="eco-why">{e.why.map((w) => <li key={w} className="small"><Icon name="info" size={13} />{w}</li>)}</ul>}
          {open === e.key && (
            <div className="eco-body">
              <div className="eco-sec"><div className="tiny muted">Cosa mettere insieme</div><ul>{e.pairs.map((x) => <li key={x}>{x}</li>)}</ul></div>
              <div className="eco-sec"><div className="tiny muted">Dove</div><div className="small">{e.where}</div></div>
              <div className="eco-sec"><div className="tiny muted">Vantaggi</div><ul>{e.benefits.map((x) => <li key={x}>{x}</li>)}</ul></div>
              <div className="eco-sec"><div className="tiny muted">Attenzione</div><ul>{e.cautions.map((x) => <li key={x}>{x}</li>)}</ul></div>
              {e.calculator && <AquaCalc />}
              <div className="tiny muted" style={{ marginTop: 8 }}>
                <span className={`lv ${LEVEL[e.level]?.cls}`} style={{ marginLeft: 0 }}>{LEVEL[e.level]?.label}</span>{" "}
                Fonti: {e.sources.map((s, i) => <span key={s.id}>{i ? " · " : ""}<a href={s.url} target="_blank" rel="noreferrer">{s.title}</a></span>)}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function AquaCalc() {
  const [m2, setM2] = useState("2");
  const [fruit, setFruit] = useState(false);
  const v = parseFloat(m2.replace(",", "."));
  const ok = v > 0 && v <= 1000;
  const q = useQuery({ queryKey: ["aqua", v, fruit], enabled: ok, refetchInterval: false,
    queryFn: () => api.get<Aqua>(`/api/v1/rotation/aquaponics?bed_m2=${v}&fruiting=${fruit}`) });
  const a = q.data;
  return (
    <div className="aqua">
      <div className="tiny muted mb">Quanti pesci per quante piante</div>
      <div className="form-grid">
        <label className="field">Superficie coltivata (m²)<input inputMode="decimal" value={m2} onChange={(e) => setM2(e.target.value)} /></label>
        <label className="field">Cosa coltivi<select value={fruit ? "1" : "0"} onChange={(e) => setFruit(e.target.value === "1")}>
          <option value="0">Insalate ed erbe</option><option value="1">Ortaggi da frutto</option></select></label>
      </div>
      {ok && a && (<>
        <div className="aqua-nums">
          <div><span className="tiny muted">Mangime al giorno</span><b>{a.feed_g_day[0]}–{a.feed_g_day[1]} g</b></div>
          <div><span className="tiny muted">Pesce nella vasca</span><b>{a.fish_kg[0]}–{a.fish_kg[1]} kg</b></div>
          <div><span className="tiny muted">Acqua minima</span><b>{a.water_l_min.toLocaleString("it-IT")} L</b></div>
        </div>
        <div className="tiny muted">{a.note}</div>
        <div className="aqua-fish">
          {a.fish.map((f) => <div key={f.key} className="small"><Icon name="fish" size={14} /><b>{f.name}</b> — {f.fit} <span className="tiny muted">({f.temp})</span></div>)}
        </div>
      </>)}
      {!ok && <div className="tiny muted">Indica una superficie tra 0 e 1000 m².</div>}
    </div>
  );
}
