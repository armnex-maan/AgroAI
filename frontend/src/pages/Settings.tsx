import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useEngines, useHealth } from "../api/hooks";
import { Icon } from "../components/Icon";
import { PageHeader } from "../components/ui";
import { num } from "../lib/it";

interface AiConfig { provider: string; model: string | null; language: string; key_configured: boolean; }
interface AiTest { ok: boolean; latency_s?: number; error?: string; }

const PROVIDER: Record<string, string> = { none: "Spenta", nvidia: "NVIDIA", anthropic: "Anthropic (Claude)", ollama: "Ollama (sul tuo PC)" };

export default function Settings() {
  const h = useHealth();
  const engines = useEngines();
  const ai = useQuery({ queryKey: ["ai-config"], queryFn: () => api.get<AiConfig>("/api/v1/ai/config"), refetchInterval: false });
  const test = useMutation({ mutationFn: () => api.post<AiTest>("/api/v1/ai/test") });
  const on = (b?: boolean) => <span className={`badge badge-${b ? "ok" : "neutral"}`}>{b ? "attivo" : "spento"}</span>;

  return (
    <>
      <PageHeader icon="settings" title="Impostazioni" tone="sky" subtitle="Lo stato dei servizi di AGROAI." />
      <div className="grid cols-2">
        <div className="card">
          <h3><Icon name="brain" />Intelligenza artificiale</h3>
          <table><tbody>
            <tr><td className="muted">Servizio</td><td><b>{PROVIDER[ai.data?.provider ?? "none"] ?? ai.data?.provider}</b></td></tr>
            <tr><td className="muted">Modello</td><td className="mono">{ai.data?.model ?? "—"}</td></tr>
            <tr><td className="muted">Lingua delle risposte</td><td>{ai.data?.language === "Italian" ? "Italiano" : ai.data?.language}</td></tr>
            <tr><td className="muted">Chiave di accesso</td><td>{ai.data?.key_configured ? <span className="badge badge-ok">inserita</span> : <span className="badge badge-neutral">non inserita</span>}</td></tr>
          </tbody></table>
          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn" disabled={!ai.data || ai.data.provider === "none" || test.isPending} onClick={() => test.mutate()}>
              {test.isPending ? "Provo…" : "Prova il collegamento"}
            </button>
            {test.data?.ok && <span className="badge badge-ok">Funziona · risponde in {num(test.data.latency_s)} s</span>}
            {test.data && !test.data.ok && <span className="small" style={{ color: "var(--danger)" }}>Non risponde: controlla la chiave e la connessione.</span>}
          </div>
          <p className="small muted" style={{ marginTop: 12 }}>
            La chiave è salvata solo sul tuo computer (file <code>backend/.env</code>) e non viene mai mostrata nel browser.
            L'intelligenza artificiale riscrive in parole semplici i risultati di AGROAI: non inventa misure. Se non risponde,
            AGROAI continua a funzionare con i suoi testi.
          </p>
        </div>
        <div className="card">
          <h3><Icon name="settings" />Servizi</h3>
          <table><tbody>
            <tr><td className="muted">Sistema</td><td>{h.data ? <span className="badge badge-ok">attivo</span> : <span className="badge badge-bad">non collegato</span>} <span className="tiny muted">v{h.data?.version}</span></td></tr>
            <tr><td className="muted">Modalità demo (simulatore)</td><td>{on(h.data?.simulation_enabled)}</td></tr>
            <tr><td className="muted">Riconoscimento suoni (YAMNet)</td><td>{on(engines.data?.yamnet.available)}</td></tr>
            <tr><td className="muted">Specie di uccelli (BirdNET)</td><td>{on(engines.data?.birdnet.available)} <span className="tiny muted">uso non commerciale</span></td></tr>
            <tr><td className="muted">Modello suoni della tua azienda</td><td>{engines.data?.farm_model.active ? <span className="badge badge-ok">versione {engines.data.farm_model.version}</span> : on(false)}</td></tr>
          </tbody></table>
          <p className="small muted" style={{ marginTop: 12 }}>
            I sensori ESP32 inviano dati firmati con una chiave segreta personale: dati da dispositivi sconosciuti vengono rifiutati.
          </p>
        </div>
      </div>
    </>
  );
}
