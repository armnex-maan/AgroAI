import { useActivateScenario, useDevices, useScenarios, useLatest } from "../api/hooks";
import { Icon } from "../components/Icon";
import { PageHeader } from "../components/ui";
import { num, time } from "../lib/it";

const SCENARIO_ICON: Record<string, [string, string]> = {
  healthy: ["check", "green"], water_stress: ["sun", "amber"], underground_activity: ["mic", "violet"], bird_activity: ["wave", "sky"],
};

export default function SimulationLab() {
  const scenarios = useScenarios();
  const activate = useActivateScenario();
  const devices = useDevices();
  const latest = useLatest();
  const demo = (latest.data ?? []).filter((d) => d.source === "simulation");

  return (
    <>
      <PageHeader icon="flask" title="Modalità demo" tone="violet"
                  subtitle="Prova AGROAI senza sensori: il simulatore crea dati realistici. Scegli una situazione e guarda come reagiscono avvisi e consigli." />
      <div className="callout info"><Icon name="info" /><div>
        I dati demo hanno sempre l'etichetta <span className="badge badge-simulation">Demo</span> e non vengono mai mescolati
        con quelli dei sensori veri. I valori cambiano ogni pochi secondi.
      </div></div>

      <div className="grid cols-2 mb">
        {scenarios.data?.map((s) => {
          const [icon, tone] = SCENARIO_ICON[s.name] ?? ["flask", "green"];
          return (
            <div key={s.name} className="card" style={{ borderColor: s.active ? "var(--accent)" : undefined, boxShadow: s.active ? "0 0 0 1px var(--accent), var(--shadow)" : undefined }}>
              <div className="row" style={{ flexWrap: "nowrap", alignItems: "flex-start" }}>
                <div className={`page-icon tone-${tone}`}><Icon name={icon} size={22} /></div>
                <div style={{ flex: 1 }}>
                  <div className="row"><b style={{ fontSize: 16 }}>{s.title}</b>{s.active && <span className="badge badge-ok">in corso</span>}</div>
                  <div className="small muted" style={{ margin: "4px 0 12px" }}>{s.description}</div>
                  <button className={`btn ${s.active ? "secondary" : ""} sm`} disabled={s.active || activate.isPending} onClick={() => activate.mutate(s.name)}>
                    {s.active ? "Situazione in corso" : "Prova questa situazione"}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="card">
        <h3><Icon name="chip" />Sensori demo ({(devices.data ?? []).filter((d) => d.source === "simulation").length})</h3>
        <div className="table-wrap"><table>
          <thead><tr><th>Sensore</th><th>Terreno</th><th>Aria</th><th>Umidità aria</th><th>pH</th><th>Ora</th></tr></thead>
          <tbody>
            {demo.map((d) => (
              <tr key={d.device_id}>
                <td>{devices.data?.find((x) => x.id === d.device_id)?.name ?? d.device_id}</td>
                <td>{num(d.values.soil_moisture?.value)}%</td>
                <td>{num(d.values.air_temperature?.value)} °C</td>
                <td>{num(d.values.air_humidity?.value)}%</td>
                <td>{num(d.values.soil_ph?.value)}</td>
                <td className="muted small">{time(d.last_seen)}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </div>
    </>
  );
}
