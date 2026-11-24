import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useDevices, useFarms, useZones } from "../api/hooks";
import { Device } from "../api/types";
import { Icon } from "../components/Icon";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { PageHeader, Steps } from "../components/ui";
import { ago, sensorLabel, STATUS } from "../lib/it";

const SENSOR_PRESETS: { type: string; unit: string; label: string }[] = [
  { type: "soil_moisture", unit: "%", label: "Umidità del terreno (sonda capacitiva v1.2)" },
  { type: "air_temperature", unit: "C", label: "Temperatura dell'aria (DHT22)" },
  { type: "air_humidity", unit: "%", label: "Umidità dell'aria (DHT22)" },
  { type: "soil_temperature", unit: "C", label: "Temperatura del terreno (DS18B20)" },
  { type: "rainfall", unit: "mm", label: "Pluviometro a bascula" },
  { type: "light_intensity", unit: "%", label: "Luce (fotoresistenza, valore relativo)" },
  { type: "soil_ph", unit: "pH", label: "pH del terreno (sonda RS485)" },
  { type: "soil_ec", unit: "mS/cm", label: "Salinità del terreno (sonda RS485)" },
];

// AgroAI Node v1 (hardware/agroai-node-v1, firmware/agroai_node_v1)
const NODE_V1_PRESETS: { type: string; unit: string; label: string }[] = [
  { type: "soil_moisture", unit: "%", label: "Umidità del terreno (sonda capacitiva)" },
  { type: "soil_temperature", unit: "C", label: "Temperatura del terreno (DS18B20)" },
  { type: "air_temperature", unit: "C", label: "Temperatura dell'aria (SHT40)" },
  { type: "air_humidity", unit: "%", label: "Umidità dell'aria (SHT40)" },
  { type: "light_intensity", unit: "lx", label: "Luce in lux (BH1750)" },
  { type: "rainfall", unit: "mm", label: "Pluviometro a bascula" },
  { type: "battery_voltage", unit: "V", label: "Tensione batteria" },
  { type: "irrigation_time", unit: "min", label: "Valvola di irrigazione (tempo)" },
  { type: "irrigation_water", unit: "L", label: "Flussimetro (litri irrigati)" },
];
const HARDWARE: Record<string, { label: string; presets: typeof SENSOR_PRESETS; defaults: string[] }> = {
  esp32: { label: "ESP32 generico (DevKit)", presets: SENSOR_PRESETS, defaults: ["soil_moisture", "air_temperature", "air_humidity"] },
  "agroai-node-v1": { label: "AgroAI Node v1 (Heltec LoRa V3, solare)", presets: NODE_V1_PRESETS,
    defaults: ["soil_moisture", "soil_temperature", "air_temperature", "air_humidity", "light_intensity", "battery_voltage"] },
};

interface Provision {
  device_id: string; secret: string; server_url: string; telemetry_endpoint: string;
  audio_endpoint: string; mqtt_topic: string; config_h: string; warning: string;
}

export default function Devices() {
  const devices = useDevices();
  const [adding, setAdding] = useState(false);
  const [prov, setProv] = useState<Provision | null>(null);
  const net = useQuery({ queryKey: ["netinfo"], queryFn: () => api.get<{ lan_ip: string; suggested_server_url: string }>("/api/v1/devices/network/info"), refetchInterval: false });
  const real = (devices.data ?? []).filter((d) => d.source === "device");
  const sim = (devices.data ?? []).filter((d) => d.source !== "device");

  return (
    <>
      <PageHeader icon="chip" title="Dispositivi ESP32" tone="violet"
                  subtitle="Collega le schede ESP32 con i sensori nel campo: le misure arrivano da sole ogni minuto.">
        <button className="btn" onClick={() => setAdding(true)}><Icon name="plus" size={14} />Aggiungi una scheda</button>
      </PageHeader>

      <div className="grid cols-3 mb">
        <div className="card kpi"><div className="label"><Icon name="chip" size={14} />Schede reali</div>
          <div className="value">{real.length}</div><div className="meta">{real.filter((d) => d.status === "online").length} collegate ora</div></div>
        <div className="card kpi"><div className="label"><Icon name="flask" size={14} />Schede demo</div>
          <div className="value">{sim.length}</div><div className="meta">dati di prova del simulatore</div></div>
        <div className="card kpi"><div className="label"><Icon name="wifi" size={14} />Indirizzo da usare sulla scheda</div>
          <div className="value mono" style={{ fontSize: 17, wordBreak: "break-all" }}>{net.data?.suggested_server_url ?? "…"}</div>
          <div className="meta">PC e scheda devono essere sulla stessa rete Wi-Fi</div></div>
      </div>

      <div className="card mb">
        <h3>Le tue schede</h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Scheda</th><th>Tipo</th><th>Stato</th><th>Sensori</th><th>Ultimo dato</th><th></th></tr></thead>
            <tbody>{(devices.data ?? []).map((d) => <DeviceRow key={d.id} d={d} onProvisioned={setProv} />)}</tbody>
          </table>
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3><Icon name="chip" />Come collegare una scheda vera</h3>
          <Steps items={[
            <>Premi <b>Aggiungi una scheda</b> e spunta i sensori che hai collegato.</>,
            <>Premi <b>Crea chiave</b>: AGROAI prepara il file <code>config.h</code> con una chiave segreta solo per quella scheda.</>,
            <>Metti <code>config.h</code> nella cartella <code>firmware/esp32_agroai</code> e scrivi nome e password del tuo Wi-Fi.</>,
            <>Apri Arduino IDE, scegli la scheda <i>ESP32 Dev Module</i> e premi <b>Carica</b>.</>,
            <>Entro un minuto la scheda compare qui come <span className="badge badge-device">Sensore</span> collegata.</>,
          ]} />
          <div className="small muted" style={{ marginTop: 12 }}>
            Il programma per la scheda non è ancora stato provato su hardware vero: fai una prova sul tavolo prima di metterla nel campo.
            Se non si collega, controlla che Windows permetta le connessioni sulla porta 8000.
          </div>
        </div>
        <div className="card">
          <h3>Dove collegare i fili</h3>
          <table><tbody>
            <tr><td>Sonda umidità terreno (uscita AOUT)</td><td className="mono">GPIO 34</td></tr>
            <tr><td>DHT22 (temperatura e umidità aria)</td><td className="mono">GPIO 4</td></tr>
            <tr><td>DS18B20 (temperatura terreno) + resistenza 4,7 kΩ</td><td className="mono">GPIO 5</td></tr>
            <tr><td>Pluviometro (contatto reed verso GND)</td><td className="mono">GPIO 27</td></tr>
            <tr><td>Microfono INMP441 (SCK / WS / SD)</td><td className="mono">26 / 25 / 33</td></tr>
          </tbody></table>
          <div className="tiny muted" style={{ marginTop: 8 }}>Per i sensori analogici usa i pin 32–39: gli altri non funzionano mentre il Wi-Fi è acceso.</div>
        </div>
      </div>

      {adding && <AddDevice onClose={() => setAdding(false)} />}
      {prov && <ProvisionModal p={prov} onClose={() => setProv(null)} />}
    </>
  );
}

function DeviceRow({ d, onProvisioned }: { d: Device; onProvisioned: (p: Provision) => void }) {
  const qc = useQueryClient();
  const provision = useMutation({
    mutationFn: () => api.post<Provision>(`/api/v1/devices/${d.id}/provision`),
    onSuccess: (p) => { onProvisioned(p); qc.invalidateQueries({ queryKey: ["devices"] }); },
  });
  const del = useMutation({
    mutationFn: () => api.del(`/api/v1/devices/${d.id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["devices"] }),
  });
  const statusCls = d.status === "online" ? "ok" : d.status === "stale" ? "warn" : "bad";
  return (
    <tr>
      <td><b>{d.name}</b><div className="tiny muted mono">{d.id}</div></td>
      <td><ProvenanceBadge source={d.source} /></td>
      <td><span className="row small"><span className={`dot ${statusCls}`} />{STATUS[d.status] ?? d.status}</span></td>
      <td className="small">{d.sensors.map((s) => sensorLabel(s.type)).join(", ") || "—"}</td>
      <td className="small">{ago(d.last_seen)}</td>
      <td>
        <div className="row" style={{ flexWrap: "nowrap" }}>
          {d.source === "device" && (
            <button className="btn secondary sm" onClick={() => (!d.provisioned || confirm("Una nuova chiave sostituisce quella vecchia: dovrai ricaricare il programma sulla scheda. Continuare?")) && provision.mutate()}>
              <Icon name="key" size={13} />{d.provisioned ? "Nuova chiave" : "Crea chiave"}
            </button>
          )}
          <button className="btn danger sm" title="Elimina" onClick={() => confirm(`Eliminare «${d.name}» e tutte le sue misure?`) && del.mutate()}><Icon name="trash" size={13} /></button>
        </div>
      </td>
    </tr>
  );
}

function AddDevice({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const farms = useFarms();
  const zones = useZones();
  const [id, setId] = useState("AGRO-ESP32-001");
  const [name, setName] = useState("Scheda campo 1");
  const [zone, setZone] = useState("");
  const [hw, setHw] = useState("esp32");
  const [transport, setTransport] = useState("wifi");
  const [sensors, setSensors] = useState<string[]>(HARDWARE.esp32.defaults);
  const presets = HARDWARE[hw].presets;
  const pickHw = (h: string) => { setHw(h); setSensors(HARDWARE[h].defaults); };
  const [err, setErr] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: () => api.post("/api/v1/devices", {
      id, name, source: "device", hardware_type: hw, farm_id: farms.data?.[0]?.id ?? null, zone_id: zone || null,
      config: hw === "agroai-node-v1" ? { transport } : null,
      sensors: presets.filter((s) => sensors.includes(s.type)).map((s) => ({ type: s.type, unit: s.unit, enabled: true })),
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["devices"] }); onClose(); },
    onError: (e: any) => { try { setErr(JSON.parse(e.message.slice(e.message.indexOf("{"))).detail); } catch { setErr(e.message || "Non riesco a creare la scheda."); } },
  });
  return (
    <div className="modal-back" onClick={onClose}>
      <div className="card modal" onClick={(e) => e.stopPropagation()}>
        <h3><Icon name="chip" />Aggiungi una scheda ESP32</h3>
        <div className="grid cols-2">
          <label className="field">Codice della scheda<input value={id} onChange={(e) => setId(e.target.value.toUpperCase().replace(/[^A-Z0-9-]/g, ""))} /></label>
          <label className="field">Nome<input value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label className="field">Zona del campo<select value={zone} onChange={(e) => setZone(e.target.value)}>
            <option value="">—</option>{(zones.data ?? []).map((z) => <option key={z.id} value={z.id}>{z.name}</option>)}
          </select></label>
          <label className="field">Tipo di scheda<select value={hw} onChange={(e) => pickHw(e.target.value)}>
            {Object.entries(HARDWARE).map(([k, h]) => <option key={k} value={k}>{h.label}</option>)}
          </select></label>
          {hw === "agroai-node-v1" && (
            <label className="field">Collegamento<select value={transport} onChange={(e) => setTransport(e.target.value)}>
              <option value="wifi">WiFi (il router arriva fino al campo)</option>
              <option value="lora">LoRa (tramite gateway in casa)</option>
            </select></label>
          )}
        </div>
        <h4>Sensori collegati alla scheda</h4>
        <div className="grid cols-2" style={{ gap: 8 }}>
          {presets.map((s) => (
            <label key={s.type} className="row small" style={{ cursor: "pointer", flexWrap: "nowrap" }}>
              <input type="checkbox" checked={sensors.includes(s.type)}
                     onChange={(e) => setSensors(e.target.checked ? [...sensors, s.type] : sensors.filter((x) => x !== s.type))} />
              {s.label}
            </label>
          ))}
        </div>
        {err && <div className="callout danger" style={{ marginTop: 12 }}><Icon name="alert" />{err}</div>}
        <div className="row" style={{ marginTop: 16, justifyContent: "flex-end" }}>
          <button className="btn ghost" onClick={onClose}>Annulla</button>
          <button className="btn" disabled={!id || create.isPending} onClick={() => create.mutate()}>Crea</button>
        </div>
      </div>
    </div>
  );
}

function ProvisionModal({ p, onClose }: { p: Provision; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const download = () => {
    const url = URL.createObjectURL(new Blob([p.config_h], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url; a.download = "config.h"; a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="modal-back">
      <div className="card modal">
        <h3><Icon name="key" />Chiave creata per {p.device_id}</h3>
        <div className="callout"><Icon name="alert" />{p.warning}</div>
        <div className="small muted mb">La scheda invierà i dati a <span className="mono">{p.telemetry_endpoint}</span></div>
        <pre className="code">{p.config_h}</pre>
        <div className="row" style={{ marginTop: 14, justifyContent: "flex-end" }}>
          <button className="btn secondary" onClick={() => { navigator.clipboard.writeText(p.config_h); setCopied(true); }}>{copied ? "Copiato" : "Copia"}</button>
          <button className="btn" onClick={download}><Icon name="download" size={14} />Scarica config.h</button>
          <button className="btn ghost" onClick={onClose}>L'ho salvato, chiudi</button>
        </div>
      </div>
    </div>
  );
}
