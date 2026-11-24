import { useMemo, useState } from "react";
import { Icon } from "../components/Icon";
import { Empty, PageHeader } from "../components/ui";
import { REMEDY_TYPE, RemedyCard, useRemedies } from "../components/Remedies";

export default function Remedies() {
  const q = useRemedies();
  const [type, setType] = useState("");
  const [cause, setCause] = useState("");
  const [text, setText] = useState("");

  const list = useMemo(() => (q.data?.remedies ?? []).filter((r) =>
    (!type || r.type === type) &&
    (!cause || r.causes.includes(cause)) &&
    (!text || `${r.name} ${r.against} ${r.how}`.toLowerCase().includes(text.toLowerCase()))
  ), [q.data, type, cause, text]);

  const usedCauses = useMemo(() => {
    const ids = new Set((q.data?.remedies ?? []).flatMap((r) => r.causes));
    return Object.entries(q.data?.causes ?? {}).filter(([id]) => ids.has(id) && id !== "healthy");
  }, [q.data]);

  return (
    <>
      <PageHeader icon="bug" title="Rimedi naturali" tone="green"
                  subtitle="Insetti utili, microrganismi, prodotti ammessi in biologico e buone pratiche: cosa usare contro ogni problema, con le fonti." />
      <div className="callout info"><Icon name="info" /><div>
        Gli insetti utili si comprano dalle <b>biofabbriche</b> e rendono meglio in serra; in campo aperto conviene soprattutto
        <b> attirare quelli che ci sono già</b> con fiori e siepi. Microrganismi e prodotti naturali sono comunque prodotti
        fitosanitari: usa prodotti autorizzati e segui l'etichetta.
      </div></div>

      <div className="card mb">
        <div className="row">
          <input placeholder="Cerca (es. afidi, lumache, oidio…)" value={text} onChange={(e) => setText(e.target.value)} style={{ flex: "1 1 220px" }} />
          <select value={cause} onChange={(e) => setCause(e.target.value)} style={{ flex: "1 1 220px" }}>
            <option value="">Tutti i problemi</option>
            {usedCauses.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select>
        </div>
        <div className="row" style={{ marginTop: 10 }}>
          <button className={`btn sm ${type === "" ? "" : "ghost"}`} onClick={() => setType("")}>Tutti</button>
          {Object.entries(REMEDY_TYPE).map(([k, t]) => (
            <button key={k} className={`btn sm ${type === k ? "" : "ghost"}`} onClick={() => setType(k)}>{t.icon} {t.label}</button>
          ))}
        </div>
      </div>

      <div className="grid cols-3">
        {list.map((r) => <RemedyCard key={r.id} r={r} />)}
      </div>
      {q.data && !list.length && <div className="card"><Empty icon="bug" title="Nessun rimedio trovato" text="Prova a cambiare i filtri." /></div>}
    </>
  );
}
