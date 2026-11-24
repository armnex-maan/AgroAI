import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useDevices, useHistory, useLatest } from "../api/hooks";
import { ProvenanceBadge } from "../components/ProvenanceBadge";
import { Icon } from "../components/Icon";
import { Empty, PageHeader } from "../components/ui";
import { ago, num, SENSOR, sensorLabel, STATUS, time } from "../lib/it";

export default function Sensors() {
  const devices = useDevices();
  const latest = useLatest();
  const [sensorId, setSensorId] = useState<string | undefined>();
  const history = useHistory(sensorId, 300);

  const all = useMemo(() => (devices.data ?? []).flatMap((d) =>
    d.sensors.map((s) => ({ ...s, device: d, value: latest.data?.find((l) => l.device_id === d.id)?.values[s.type]?.value }))
  ), [devices.data, latest.data]);

  useEffect(() => { if (!sensorId && all.length) setSensorId(all[0].id); }, [all, sensorId]);
  const selected = all.find((s) => s.id === sensorId);
  const chart = useMemo(() => [...(history.data ?? [])].reverse().map((r) => ({ t: time(r.ts), v: r.value })), [history.data]);
  const values = chart.map((c) => c.v);

  return (
    <>
      <PageHeader icon="sensors" title="Sensori" tone="sky"
                  subtitle="Tutte le misure dei tuoi sensori. Tocca un sensore per vedere come è cambiato nel tempo." />
      <div className="split">
        <div className="card">
          <h3>I tuoi sensori ({all.length})</h3>
          <div className="stack scroll" style={{ maxHeight: 620, gap: 4 }}>
            {all.map((s) => {
              const info = SENSOR[s.type];
              return (
                <div key={s.id} className={`list-item ${s.id === sensorId ? "active" : ""}`} onClick={() => setSensorId(s.id)}>
                  <div className="row" style={{ flexWrap: "nowrap" }}>
                    <Icon name={info?.icon ?? "sensors"} size={16} />
                    <b className="small">{sensorLabel(s.type)}</b>
                    <span className="spacer" />
                    <b>{num(s.value)}</b><span className="tiny muted">{info?.unit || s.unit}</span>
                  </div>
                  <div className="row tiny muted" style={{ marginTop: 4 }}>{s.device.name} <ProvenanceBadge source={s.device.source} /></div>
                </div>
              );
            })}
            {!all.length && <Empty icon="sensors" title="Nessun sensore" text="Aggiungi una scheda ESP32 in Dispositivi." />}
          </div>
        </div>

        <div className="card">
          {selected ? (
            <>
              <div className="card-head">
                <div>
                  <h3 style={{ margin: 0 }}><Icon name={SENSOR[selected.type]?.icon ?? "sensors"} />{sensorLabel(selected.type)}</h3>
                  <div className="small muted" style={{ marginTop: 4 }}>{selected.device.name}</div>
                </div>
                <ProvenanceBadge source={selected.device.source} />
              </div>
              <div className="grid cols-4 mb">
                <Mini label="Adesso" value={`${num(selected.value)} ${SENSOR[selected.type]?.unit || selected.unit}`} />
                <Mini label="Minimo" value={values.length ? num(Math.min(...values)) : "—"} />
                <Mini label="Massimo" value={values.length ? num(Math.max(...values)) : "—"} />
                <Mini label="Stato" value={STATUS[selected.device.status] ?? selected.device.status} sub={`ultimo dato ${ago(selected.device.last_seen)}`} />
              </div>
              <div style={{ height: 320 }}>
                <ResponsiveContainer>
                  <AreaChart data={chart} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="sens" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#34d17f" stopOpacity={0.45} />
                        <stop offset="100%" stopColor="#34d17f" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="#e2ebe5" strokeDasharray="3 3" />
                    <XAxis dataKey="t" stroke="#7f988a" fontSize={11} minTickGap={40} />
                    <YAxis stroke="#7f988a" fontSize={11} domain={["auto", "auto"]} />
                    <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #e2ebe5", borderRadius: 12, boxShadow: "0 8px 24px rgba(16,42,28,.08)" }}
                             formatter={(v: number) => [num(v), sensorLabel(selected.type)]} />
                    <Area type="monotone" dataKey="v" stroke="#34d17f" strokeWidth={2} fill="url(#sens)" isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <div className="tiny muted">Ultime {history.data?.length ?? 0} misure.</div>
            </>
          ) : <Empty icon="chart" title="Scegli un sensore" text="Il grafico mostra come è cambiato il valore nel tempo." />}
        </div>
      </div>
    </>
  );
}

function Mini({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="candidate">
      <div className="tiny muted">{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700 }}>{value}</div>
      {sub && <div className="tiny muted">{sub}</div>}
    </div>
  );
}
