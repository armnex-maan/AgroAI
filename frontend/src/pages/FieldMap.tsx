import { useFarms, useLatest, useDevices } from "../api/hooks";
import { BaseMap } from "../components/BaseMap";
import { PageHeader } from "../components/ui";
import { num } from "../lib/it";

export default function FieldMap() {
  const farms = useFarms();
  const latest = useLatest();
  const devices = useDevices();
  const farm = farms.data?.find((f) => f.latitude != null);
  const points = (farms.data ?? []).filter((f) => f.latitude != null).map((f) => {
    const devs = (devices.data ?? []).filter((d) => d.farm_id === f.id);
    const vals = (latest.data ?? []).filter((l) => devs.some((d) => d.id === l.device_id));
    const sm = vals.map((v) => v.values.soil_moisture?.value).filter((x): x is number => x != null);
    const label = `${f.name} — ${devs.length} sensori${sm.length ? `, umidità terreno ${num(sm.reduce((a, b) => a + b, 0) / sm.length)}%` : ""}`;
    return { lat: f.latitude!, lon: f.longitude!, label };
  });
  return (
    <>
      <PageHeader icon="map" title="Mappa" tone="sky" subtitle="Le tue aziende viste dal satellite. Tocca un segnaposto per vedere gli ultimi valori." />
      <div className="card" style={{ padding: 10 }}>
        <BaseMap center={farm ? [farm.longitude!, farm.latitude!] : [9.19, 45.46]} zoom={farm ? 14 : 5} points={points} height={620} />
      </div>
    </>
  );
}
