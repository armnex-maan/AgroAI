import { useAssessment } from "../api/hooks";
import { Icon } from "../components/Icon";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { Empty, PageHeader } from "../components/ui";
import { ago, num, pct, SENSOR, sensorLabel, SEVERITY } from "../lib/it";

const STATUS: Record<string, [string, string, string]> = {
  nominal: ["Tutto sotto controllo", "green", "check"],
  watch: ["Da tenere d'occhio", "amber", "alert"],
  attention: ["Serve attenzione", "amber", "alert"],
};

export default function Predictions() {
  const q = useAssessment();
  const a = q.data;
  const [label, tone, icon] = STATUS[a?.status ?? "nominal"] ?? STATUS.nominal;
  return (
    <>
      <PageHeader icon="brain" title="Valutazione del campo" tone="violet"
                  subtitle="AGROAI controlla le misure dei sensori con regole agronomiche e ti dice cosa fare. Ogni consiglio mostra su quali dati si basa." />
      {q.isLoading && <div className="card"><Empty icon="refresh" title="Sto analizzando i dati…" /></div>}
      {a && (
        <div className="stack" style={{ gap: 16 }}>
          <div className="card">
            <div className="row" style={{ flexWrap: "nowrap", alignItems: "flex-start" }}>
              <div className={`page-icon tone-${tone}`}><Icon name={icon} size={22} /></div>
              <div style={{ flex: 1 }}>
                <div className="verdict">{label}</div>
                {a.narrative
                  ? <div className="lead" style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>{a.narrative}</div>
                  : a.findings.map((f, i) => <div key={i} className="lead" style={{ marginTop: 4 }}>{f}</div>)}
                <div className="row tiny muted" style={{ marginTop: 10 }}>
                  Aggiornato {ago(a.generated_at)} · dati usati: {a.sources.map((s) => <ProvenanceBadge key={s} source={s} />)}
                </div>
              </div>
            </div>
          </div>

          {a.recommendations.length > 0 && (
            <div className="card">
              <h3><Icon name="check" />Cosa fare</h3>
              <div className="stack">
                {a.recommendations.map((r, i) => <div key={i} className="candidate"><b>{i + 1}.</b> {r}</div>)}
              </div>
            </div>
          )}

          <div className="card">
            <h3><Icon name="chart" />Perché te lo diciamo</h3>
            {a.predictions.map((p) => (
              <div key={p.id} className="candidate" style={{ marginBottom: 10 }}>
                <div className="row">
                  <b style={{ fontSize: 15 }}>{p.summary}</b>
                  <span className={`badge badge-${p.severity}`}>Priorità {SEVERITY[p.severity]?.toLowerCase()}</span>
                  <span className="spacer" />
                  <span className="small muted">affidabilità {pct(p.confidence)}</span>
                </div>
                <div className="row" style={{ marginTop: 8 }}>
                  {p.supporting.map((s: any, i: number) => (
                    <span key={i} className="chip">
                      {sensorLabel(s.metric)}: <b>{num(s.value)} {SENSOR[s.metric]?.unit ?? s.unit}</b> <ProvenanceBadge source={s.source} />
                    </span>
                  ))}
                </div>
                {p.explanation && <div className="small muted" style={{ marginTop: 8 }}>{p.explanation}</div>}
              </div>
            ))}
            {!a.predictions.length && <Empty icon="check" title="Nessun problema rilevato" text="Le misure attuali sono tutte nella norma." />}
          </div>
        </div>
      )}
    </>
  );
}
