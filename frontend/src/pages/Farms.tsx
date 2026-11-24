import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useFarms, useFields, useZones } from "../api/hooks";
import { Icon } from "../components/Icon";
import { Empty, PageHeader } from "../components/ui";
import { num } from "../lib/it";

export default function Farms() {
  const qc = useQueryClient();
  const farms = useFarms();
  const [farmId, setFarmId] = useState<string | undefined>();
  const [fieldId, setFieldId] = useState<string | undefined>();
  const fields = useFields(farmId);
  const zones = useZones(fieldId);
  useEffect(() => { if (!farmId && farms.data?.length) setFarmId(farms.data[0].id); }, [farms.data, farmId]);
  useEffect(() => { if (!fieldId && fields.data?.length) setFieldId(fields.data[0].id); }, [fields.data, fieldId]);

  const add = useMutation({
    mutationFn: ({ path, body }: { path: string; body: object }) => api.post(path, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["farms"] }); qc.invalidateQueries({ queryKey: ["fields"] }); qc.invalidateQueries({ queryKey: ["zones"] }); },
  });

  return (
    <>
      <PageHeader icon="farm" title="Aziende e campi" tone="green"
                  subtitle="Organizza la tua azienda in campi e zone: ogni sensore, foto e registrazione può essere collegato a una zona." />
      <div className="grid cols-3">
        <Column title="Aziende" icon="farm" empty="Nessuna azienda"
                items={(farms.data ?? []).map((f) => ({ id: f.id, name: f.name, sub: f.latitude != null ? `${num(f.latitude, 3)}, ${num(f.longitude, 3)}` : "posizione non indicata" }))}
                selected={farmId} onSelect={(id) => { setFarmId(id); setFieldId(undefined); }}
                onAdd={(name) => add.mutate({ path: "/api/v1/farms", body: { name, timezone: "Europe/Rome" } })} addLabel="Nome dell'azienda" />
        <Column title="Campi" icon="map" empty={farmId ? "Nessun campo in questa azienda" : "Scegli un'azienda"}
                items={(fields.data ?? []).map((f) => ({ id: f.id, name: f.name, sub: f.area_ha ? `${num(f.area_ha)} ettari` : "superficie non indicata" }))}
                selected={fieldId} onSelect={setFieldId}
                onAdd={farmId ? (name) => add.mutate({ path: "/api/v1/fields", body: { farm_id: farmId, name } }) : undefined} addLabel="Nome del campo (es. Campo Nord)" />
        <Column title="Zone" icon="pin" empty={fieldId ? "Nessuna zona in questo campo" : "Scegli un campo"}
                items={(zones.data ?? []).map((z) => ({ id: z.id, name: z.name, sub: "" }))}
                onAdd={fieldId ? (name) => add.mutate({ path: "/api/v1/zones", body: { field_id: fieldId, name } }) : undefined} addLabel="Nome della zona (es. Filari 1-10)" />
      </div>
    </>
  );
}

function Column({ title, icon, items, selected, onSelect, onAdd, addLabel, empty }: {
  title: string; icon: string; items: { id: string; name: string; sub: string }[]; selected?: string;
  onSelect?: (id: string) => void; onAdd?: (name: string) => void; addLabel: string; empty: string;
}) {
  const [name, setName] = useState("");
  return (
    <div className="card">
      <h3><Icon name={icon} />{title}</h3>
      <div className="stack" style={{ gap: 4 }}>
        {items.map((it) => (
          <div key={it.id} className={`list-item ${selected === it.id ? "active" : ""}`} onClick={() => onSelect?.(it.id)} style={{ cursor: onSelect ? "pointer" : "default" }}>
            <b>{it.name}</b>{it.sub && <div className="tiny muted">{it.sub}</div>}
          </div>
        ))}
        {!items.length && <Empty icon={icon} title={empty} />}
      </div>
      {onAdd && (
        <div className="row" style={{ marginTop: 12, flexWrap: "nowrap" }}>
          <input placeholder={addLabel} value={name} onChange={(e) => setName(e.target.value)} style={{ flex: 1 }} />
          <button className="btn sm" disabled={!name.trim()} onClick={() => { onAdd(name.trim()); setName(""); }}><Icon name="plus" size={13} />Aggiungi</button>
        </div>
      )}
    </div>
  );
}
