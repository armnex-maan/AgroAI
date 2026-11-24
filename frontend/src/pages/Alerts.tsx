import { useState } from "react";
import { useAckAlert, useAlerts } from "../api/hooks";
import { Icon } from "../components/Icon";
import { Empty, PageHeader } from "../components/ui";
import { ago, dateTime, SEVERITY } from "../lib/it";

export default function Alerts() {
  const alerts = useAlerts();
  const ack = useAckAlert();
  const [showDone, setShowDone] = useState(false);
  const list = (alerts.data ?? []).filter((a) => showDone || !a.acknowledged);
  const open = (alerts.data ?? []).filter((a) => !a.acknowledged).length;

  return (
    <>
      <PageHeader icon="bell" title="Avvisi" tone="amber"
                  subtitle="Quando un valore esce dalla norma, AGROAI ti avvisa qui. Segna «Fatto» quando hai controllato.">
        <div className="tabs">
          <button className={!showDone ? "on" : ""} onClick={() => setShowDone(false)}>Da gestire ({open})</button>
          <button className={showDone ? "on" : ""} onClick={() => setShowDone(true)}>Tutti</button>
        </div>
      </PageHeader>
      <div className="stack" style={{ gap: 10 }}>
        {list.map((a) => (
          <div key={a.id} className="card" style={{ padding: 14, opacity: a.acknowledged ? 0.6 : 1 }}>
            <div className="row" style={{ flexWrap: "nowrap" }}>
              <div className={`page-icon tone-${a.severity === "high" ? "amber" : "sky"}`} style={{ width: 40, height: 40 }}>
                <Icon name="alert" size={18} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="row"><b>{a.message}</b><span className={`badge badge-${a.severity}`}>Priorità {SEVERITY[a.severity]?.toLowerCase()}</span></div>
                <div className="tiny muted" style={{ marginTop: 3 }}>{dateTime(a.ts)} · {ago(a.ts)}</div>
              </div>
              {!a.acknowledged ? (
                <button className="btn secondary sm" onClick={() => ack.mutate(a.id)}><Icon name="check" size={13} />Fatto</button>
              ) : <span className="badge badge-ok">Gestito</span>}
            </div>
          </div>
        ))}
        {!list.length && <div className="card"><Empty icon="check" title="Nessun avviso da gestire" text="Tutto tranquillo nel campo." /></div>}
      </div>
    </>
  );
}
