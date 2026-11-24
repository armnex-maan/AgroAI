/** Irrigation advice for the selected part: Kc (FAO-56), monthly water need from the local climate, suggested vs
 *  declared system, sources; button for the 3D demonstration. Advice only, nothing is saved. */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../../api/client";
import { Icon } from "../../Icon";

const MONTH = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];
const DEMO_OK = ["drip", "sprinkler", "furrow"];

interface Row { month: number; stage_name: string; kc: number; et0_mm?: number; etc_mm?: number; rain_eff_mm?: number; net_mm?: number; liters_week?: number; gross_liters_week?: number | null }
interface Bed {
  section_id: string | null; name: string; area_m2: number; kc: number[] | null; season: number[]; months: Row[]; peak: Row | null;
  season_net_mm?: number; efficiency?: { system: string; value: number } | null;
  system: { suggested: string; suggested_name: string; why: string; declared: string | null; declared_name: string | null };
}
interface Res { beds: Bed[]; climate: { source: string; period: string } | null; sources: { title: string; url: string }[]; notes: string[] }
const n0 = (v: number) => Math.round(v).toLocaleString("it-IT");

export function IrrigationPanel({ plotId, year, sectionId, section, crop, area, demoOn, onDemo }: {
  plotId: string; year: number; sectionId: string | null; section: string; crop: string; area: number;
  demoOn: boolean; onDemo: (system: string | null) => void;
}) {
  const q = useQuery({
    queryKey: ["irrigation", plotId, year, sectionId, crop, Math.round(area)], refetchInterval: false, staleTime: 10 * 60_000,
    queryFn: () => api.post<Res>(`/api/v1/rotation/plots/${plotId}/irrigation`, { year, assignments: [{ section_id: sectionId, section, crop, area_m2: area }] }),
  });
  const b = q.data?.beds[0];
  if (q.isLoading) return <div className="tiny muted">Calcolo il fabbisogno d'acqua…</div>;
  if (q.isError || !b) return <div className="tiny muted">{q.isError ? (q.error as Error).message : "Coltura senza dati di irrigazione."}</div>;
  const demoSys = b.system.declared && DEMO_OK.includes(b.system.declared) ? b.system.declared : DEMO_OK.includes(b.system.suggested) ? b.system.suggested : null;
  const max = Math.max(1, ...b.months.map((m) => m.net_mm ?? 0));
  return (
    <div className="vp-irr">
      <div className="vp-imp"><Icon name="drop" size={15} />Sistema dichiarato<span className="spacer" />{b.system.declared_name ?? "non indicato"}</div>
      <div className="vp-imp"><Icon name="spark" size={15} />Suggerito da AgroAI<span className="spacer" />{b.system.suggested_name}</div>
      <div className="tiny muted">{b.system.why} <span className="lv lv-ai">Suggerimento</span></div>
      {b.kc && <div className="tiny">Coefficiente colturale Kc: iniziale {b.kc[0]}, piena crescita {b.kc[1]}, finale {b.kc[2]}.</div>}
      {b.peak ? <>
        <div className="small" style={{ marginTop: 6 }}>Mese di punta: <b>{MONTH[b.peak.month - 1]}</b> · {n0(b.peak.net_mm!)} mm nel mese ·
          circa <b>{n0(b.peak.liters_week!)} litri a settimana</b> per questa parte{b.peak.gross_liters_week ? ` (${n0(b.peak.gross_liters_week)} da erogare con l'impianto ${b.efficiency?.system === "drip" ? "a goccia" : b.efficiency?.system === "sprinkler" ? "a pioggia" : "a scorrimento"}, efficienza ${Math.round((b.efficiency?.value ?? 1) * 100)}%)` : ""}.</div>
        <div className="vp-irr-bars" aria-label="Acqua da dare per mese">
          {b.months.map((m) => <div key={m.month} title={`${MONTH[m.month - 1]}: Kc ${m.kc} (${m.stage_name}), ET0 ${m.et0_mm} mm, pioggia utile ${m.rain_eff_mm} mm, da irrigare ${m.net_mm} mm`}>
            <i style={{ height: `${((m.net_mm ?? 0) / max) * 100}%` }} /><small>{MONTH[m.month - 1]}</small></div>)}
        </div>
        <div className="tiny muted">Stagione: circa {n0(b.season_net_mm ?? 0)} mm da irrigare (1 mm = 1 litro per m²).</div>
      </> : b.months.length && q.data?.climate ? <div className="tiny">Con la pioggia media del luogo questa coltura non ha bisogno di irrigazione nei suoi mesi.</div>
        : <div className="tiny muted">{q.data?.notes[1] ?? "Calendario non disponibile per questa coltura."}</div>}
      <div className="row" style={{ gap: 6, marginTop: 6, flexWrap: "wrap" }}>
        {demoSys && <button className={`btn sm ${demoOn ? "" : "ghost"}`} onClick={() => onDemo(demoOn ? null : demoSys)}>
          <Icon name={demoOn ? "stop" : "play"} size={13} />{demoOn ? "Ferma la dimostrazione" : `Dimostrazione ${demoSys === "drip" ? "a goccia" : demoSys === "sprinkler" ? "a pioggia" : "a solchi"}`}</button>}
      </div>
      <div className="tiny muted">{q.data?.notes[0]} {q.data?.climate && `Clima: ${q.data.climate.source}, ${q.data.climate.period}.`}{" "}
        Fonti: {q.data?.sources.map((s, i) => <a key={i} href={s.url} target="_blank" rel="noreferrer">{s.title}{i === 0 ? "; " : ""}</a>)}</div>
    </div>
  );
}
