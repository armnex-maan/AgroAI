/** Properties of a farm element (building, tank, road, orchard...) and the palette to add new ones. */
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../../api/client";
import { Icon } from "../../Icon";
import { fmtArea } from "../types";
import { Feature } from "./Structures";

export interface KindSpec { label: string; geom: "Point" | "LineString" | "Polygon"; props: Record<string, string[] | boolean[] | string | { min: number; max: number }> }
export interface FeaturesData { features: Feature[]; kinds: Record<string, KindSpec>; trees: Record<string, { name: string; height_m: number[] }>;
  height_source: { title: string; url: string } }

export const KIND_ICON: Record<string, string> = { building: "home", tank: "drop", well: "drop", road: "move", pipe: "wave", hedge: "leaf",
  orchard: "sprout", vineyard: "grain", pond: "drop", sprinkler: "rain", greenhouse: "home", net: "grid", fence: "lock",
  equipment: "settings", beehive: "bug", compost: "leaf", solar: "sun" };
const PROP_LABEL: Record<string, string> = { type: "Tipo", width_m: "Larghezza (m)", length_m: "Lunghezza (m)", floors: "Piani", rotation_deg: "Rotazione (°)",
  diameter_m: "Diametro (m)", height_m: "Altezza (m)", capacity_l: "Capacità (litri)", depth_m: "Profondità (m)", width_m_road: "Larghezza (m)",
  surface: "Fondo", diameter_mm: "Diametro (mm)", buried: "Interrata", species: "Specie", row_spacing_m: "Distanza tra le file (m)",
  tree_spacing_m: "Distanza sulla fila (m)", plant_spacing_m: "Distanza sulla fila (m)", planted_year: "Anno d'impianto",
  radius_m: "Raggio di bagnatura (m)", flow_l_h: "Portata (l/h)", heated: "Riscaldata", count: "Numero di arnie",
  volume_m3: "Volume (m³)", power_kw: "Potenza (kW)", model: "Modello (facoltativo)" };
const VALUE_LABEL: Record<string, string> = { casale: "Casale", fienile: "Fienile", magazzino: "Magazzino", stalla: "Stalla", ricovero_attrezzi: "Ricovero attrezzi",
  sterrato: "Sterrato", ghiaia: "Ghiaia", asfalto: "Asfalto", cemento: "Cemento", true: "Sì", false: "No",
  statico: "Statico", dinamico: "Dinamico (rotante)", a_impulsi: "A impulsi", microirrigatore: "Microirrigatore",
  tunnel: "Tunnel in film plastico", vetro: "Serra in vetro", ombraio: "Ombraio", antigrandine: "Antigrandine", ombreggiante: "Ombreggiante",
  antinsetto: "Antinsetto", rete_metallica: "Rete metallica", staccionata: "Staccionata in legno", elettrica: "Elettrica",
  trattore: "Trattore", motocoltivatore: "Motocoltivatore", atomizzatore: "Atomizzatore", rimorchio: "Rimorchio", pompa: "Pompa",
  centralina_irrigazione: "Centralina irrigazione" };

export function Palette({ kinds, onPick, onClose, sections, onPickSection }: { kinds: Record<string, KindSpec>; onPick: (k: string) => void; onClose: () => void;
  sections?: { kind: string; label: string; icon: string }[]; onPickSection?: (k: string) => void }) {
  return (
    <div className="vp-palette">
      <div className="row"><b>Aggiungi alla mappa</b><span className="spacer" /><button className="icon-btn" onClick={onClose} aria-label="Chiudi"><Icon name="minus" size={13} /></button></div>
      {sections && onPickSection && <>
        <div className="tiny muted" style={{ margin: "6px 0 4px" }}>Parti di un appezzamento (aiuole, serre, sentieri…): tocca due angoli</div>
        <div className="vp-palette-grid">
          {sections.map((x) => (
            <button key={x.kind} onClick={() => onPickSection(x.kind)}><Icon name={x.icon} size={18} /><span>{x.label}</span><small>un rettangolo</small></button>
          ))}
        </div>
        <div className="tiny muted" style={{ margin: "8px 0 4px" }}>Elementi dell'azienda</div>
      </>}
      <div className="vp-palette-grid">
        {Object.entries(kinds).map(([k, s]) => (
          <button key={k} onClick={() => onPick(k)}><Icon name={KIND_ICON[k] ?? "plus"} size={18} /><span>{s.label}</span>
            <small>{s.geom === "Point" ? "un punto" : s.geom === "LineString" ? "una linea" : "un'area"}</small></button>
        ))}
      </div>
    </div>
  );
}

export function FeatureProps({ feature, data, onClose, onFocus }: { feature: Feature; data: FeaturesData; onClose: () => void; onFocus: () => void }) {
  const qc = useQueryClient();
  const spec = data.kinds[feature.kind];
  const [name, setName] = useState(feature.name);
  const [props, setProps] = useState<Record<string, any>>(feature.props);
  useEffect(() => { setName(feature.name); setProps(feature.props); }, [feature.id, feature.name, feature.props]);
  const save = useMutation({
    mutationFn: () => api.put(`/api/v1/rotation/features/${feature.id}`, { name, props }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rotation-features"] }),
  });
  const del = useMutation({
    mutationFn: () => api.del(`/api/v1/rotation/features/${feature.id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["rotation-features"] }); onClose(); },
  });
  const plant = feature.kind === "orchard" || feature.kind === "vineyard";
  const spacingMissing = plant && !(props.row_spacing_m && (props.tree_spacing_m || props.plant_spacing_m));
  return (
    <div className="vp-props">
      <div className="row"><b>{spec?.label ?? feature.kind}</b><span className="spacer" /><button className="icon-btn" onClick={onClose} aria-label="Chiudi"><Icon name="minus" size={14} /></button></div>
      <label className="field">Nome<input value={name} onChange={(e) => setName(e.target.value)} /></label>
      <dl className="vp-kv">
        {feature.area_m2 != null && <><dt>Superficie</dt><dd>{fmtArea(feature.area_m2)}</dd></>}
        {feature.length_m != null && <><dt>Lunghezza</dt><dd>{Math.round(feature.length_m).toLocaleString("it-IT")} m</dd></>}
        {feature.height_m && <><dt>Altezza (FAO-56)</dt><dd>{feature.height_m[0] === feature.height_m[1] ? feature.height_m[0] : feature.height_m.join("–")} m</dd></>}
      </dl>
      <div className="form-grid">
        {spec && Object.entries(spec.props).map(([k, rule]) => {
          const label = PROP_LABEL[k] ?? k;
          if (Array.isArray(rule)) return (
            <label key={k} className="field">{label}
              <select value={props[k] === undefined ? "" : String(props[k])} onChange={(e) => setProps({ ...props, [k]: e.target.value === "" ? undefined
                : rule.find((r) => String(r) === e.target.value) })}>
                <option value="">— non indicato —</option>
                {rule.map((r) => <option key={String(r)} value={String(r)}>{k === "species" ? data.trees[String(r)]?.name ?? String(r) : VALUE_LABEL[String(r)] ?? String(r)}</option>)}
              </select>
            </label>
          );
          if (rule === "text") return <label key={k} className="field">{label}<input value={props[k] ?? ""} onChange={(e) => setProps({ ...props, [k]: e.target.value || undefined })} /></label>;
          const r = rule as { min: number; max: number };
          return <label key={k} className="field">{label}
            <input inputMode="decimal" placeholder={`${r.min}–${r.max}`} value={props[k] ?? ""} onChange={(e) => setProps({ ...props, [k]: e.target.value === "" ? undefined : e.target.value.replace(",", ".") })} />
          </label>;
        })}
      </div>
      {spacingMissing && <div className="tiny muted">Distanze tra file e piante non indicate: la disposizione nel 3D è indicativa.</div>}
      {plant && <div className="tiny muted">Altezze: <a href={data.height_source.url} target="_blank" rel="noreferrer">{data.height_source.title}</a>. Fioritura e frutti per mese non sono disponibili: con un mese scelto i frutti non vengono mostrati.</div>}
      {(save.isError || del.isError) && <div className="tiny" style={{ color: "var(--danger)" }}>{((save.error || del.error) as Error).message}</div>}
      <div className="row" style={{ gap: 6, marginTop: 8, flexWrap: "wrap" }}>
        <button className="btn sm" disabled={save.isPending || !name.trim()} onClick={() => save.mutate()}><Icon name="check" size={13} />{save.isPending ? "Salvo…" : "Salva"}</button>
        <button className="btn ghost sm" onClick={onFocus}><Icon name="locate" size={13} />Inquadra</button>
        <button className="btn ghost sm" disabled={del.isPending} onClick={() => { if (window.confirm(`Eliminare «${feature.name}»?`)) del.mutate(); }}><Icon name="trash" size={13} />Elimina</button>
      </div>
      {save.isSuccess && <div className="tiny muted">Salvato.</div>}
    </div>
  );
}
