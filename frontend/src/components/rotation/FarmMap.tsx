import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl, { GeoJSONSource, Map as MlMap, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { style } from "../BaseMap";
import { Icon } from "../Icon";
import { clipToRect, cropsFor, LL, ringOf, XY } from "./plotGeo";
import SplitCard from "./SplitCard";
import { cropColor, FarmData, fmtArea, isGrowing, PlanResult, Plot, shortName } from "./types";

const R = 6378137;
const UNPLANNED = "#c9cfca";

/** Spherical area of a lon/lat ring, same formula as the server (and Turf.js). */
export function ringArea(pts: LL[]): number {
  if (pts.length < 3) return 0;
  let t = 0;
  for (let i = 0; i < pts.length; i++) {
    const [lo1, la1] = pts[i], [lo2, la2] = pts[(i + 1) % pts.length];
    t += ((lo2 - lo1) * Math.PI / 180) * (2 + Math.sin(la1 * Math.PI / 180) + Math.sin(la2 * Math.PI / 180));
  }
  return Math.abs(t * R * R / 2);
}
function ringPerimeter(pts: LL[], closed: boolean): number {
  let t = 0;
  const n = closed ? pts.length : pts.length - 1;
  for (let i = 0; i < n; i++) {
    const [lo1, la1] = pts[i].map((v) => v * Math.PI / 180), [lo2, la2] = pts[(i + 1) % pts.length].map((v) => v * Math.PI / 180);
    const a = Math.sin((la2 - la1) / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin((lo2 - lo1) / 2) ** 2;
    t += 2 * R * Math.asin(Math.sqrt(a));
  }
  return t;
}

function sectionRing(p: Plot, s: { x: number; y: number; w: number; h: number }): LL[] | null {
  const o = p.polygon?.origin, k = p.polygon?.k;
  if (!o || !k) return null;
  let pts: XY[] = [[s.x, s.y], [s.x + s.w, s.y], [s.x + s.w, s.y + s.h], [s.x, s.y + s.h]];
  const ol = p.outline as XY[] | null;
  if (p.shape === "irregular" && ol && ol.length >= 3) pts = clipToRect(ol, s.x, s.y, s.x + s.w, s.y + s.h);
  if (pts.length < 3) return null;
  return pts.map(([x, y]) => [o[0] + x / k[0], o[1] - y / k[1]] as LL);
}
const centroid = (r: LL[]): LL => [r.reduce((a, q) => a + q[0], 0) / r.length, r.reduce((a, q) => a + q[1], 0) / r.length];
const poly = (r: LL[], props: Record<string, unknown>) =>
  ({ type: "Feature" as const, properties: props, geometry: { type: "Polygon" as const, coordinates: [[...r, r[0]]] } });

/** Update a GeoJSON source only if the map still has it (style reloads and hot reloads drop sources). */
function setSrc(m: MlMap, id: string, data: any) {
  (m.getSource(id) as GeoJSONSource | undefined)?.setData(data);
}

export default function FarmMap({ farm, draw, onDrawn, onOpen }: {
  farm: FarmData; draw: { plotId: string | null } | null; onDrawn: () => void; onOpen: (id: string) => void;
}) {
  const qc = useQueryClient();
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const labels = useRef<Marker[]>([]);
  const me = useRef<Marker | null>(null);
  const [ready, setReady] = useState(false);
  const [year, setYear] = useState(farm.season_year);
  const [sel, setSel] = useState<string | null>(null);
  const [pts, setPts] = useState<LL[]>([]);
  const [drawing, setDrawing] = useState<{ plotId: string | null } | null>(draw);
  const [name, setName] = useState(`Appezzamento ${farm.plots.length + 1}`);
  const [geoMsg, setGeoMsg] = useState<string | null>(null);
  const drawingRef = useRef(drawing);
  drawingRef.current = drawing;
  useEffect(() => { if (draw) { setDrawing(draw); setPts([]); } }, [draw]);

  const years = useMemo(() => Array.from({ length: 5 }, (_, i) => farm.season_year + i), [farm.season_year]);
  const mapped = farm.plots.filter((p) => ringOf(p));

  // ---- map setup ----
  useEffect(() => {
    if (!el.current) return;
    const start: LL = farm.longitude != null && farm.latitude != null ? [farm.longitude, farm.latitude] : [12.5, 42.5];
    const m = new maplibregl.Map({ container: el.current, style: style(true), center: start,
      zoom: farm.latitude != null ? 15 : 5, attributionControl: { compact: true } });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.on("load", () => {
      const empty = { type: "FeatureCollection" as const, features: [] };
      for (const id of ["plots", "sections", "draft-area", "draft-line", "draft-pts"]) m.addSource(id, { type: "geojson", data: empty });
      m.addLayer({ id: "plots-fill", type: "fill", source: "plots", paint: { "fill-color": ["get", "color"], "fill-opacity": ["get", "opacity"] } });
      m.addLayer({ id: "sections-fill", type: "fill", source: "sections", paint: { "fill-color": ["get", "color"], "fill-opacity": ["get", "opacity"] } });
      m.addLayer({ id: "sections-line", type: "line", source: "sections", paint: { "line-color": "#ffffff", "line-width": 1.5, "line-opacity": 0.9 } });
      m.addLayer({ id: "plots-line", type: "line", source: "plots", paint: { "line-color": ["get", "stroke"], "line-width": ["get", "width"] } });
      m.addLayer({ id: "draft-area", type: "fill", source: "draft-area", paint: { "fill-color": "#ffd24a", "fill-opacity": 0.25 } });
      m.addLayer({ id: "draft-line", type: "line", source: "draft-line", paint: { "line-color": "#ffd24a", "line-width": 2.5, "line-dasharray": [2, 1] } });
      m.addLayer({ id: "draft-pts", type: "circle", source: "draft-pts", paint: { "circle-radius": 6, "circle-color": "#ffd24a", "circle-stroke-color": "#1d2a22", "circle-stroke-width": 2 } });
      setReady(true);
    });
    m.on("click", (e) => {
      if (drawingRef.current) { setPts((p) => [...p, [+e.lngLat.lng.toFixed(7), +e.lngLat.lat.toFixed(7)]]); return; }
      const hit = m.queryRenderedFeatures(e.point, { layers: ["plots-fill"] })[0];
      setSel(hit ? String(hit.properties?.id) : null);
    });
    m.on("mouseenter", "plots-fill", () => { if (!drawingRef.current) m.getCanvas().style.cursor = "pointer"; });
    m.on("mouseleave", "plots-fill", () => { m.getCanvas().style.cursor = ""; });
    map.current = m;
    return () => { setReady(false); m.remove(); map.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { if (map.current) map.current.getCanvas().style.cursor = drawing ? "crosshair" : ""; }, [drawing]);

  // first view: all traced plots, otherwise the farmer's position
  const framed = useRef(false);
  useEffect(() => {
    if (!ready || framed.current) return;
    framed.current = true;
    const all = mapped.flatMap((p) => ringOf(p)!);
    if (all.length) {
      const b = new maplibregl.LngLatBounds(all[0], all[0]);
      all.forEach((q) => b.extend(q));
      map.current!.fitBounds(b, { padding: 50, maxZoom: 18, duration: 0 });
    } else if (farm.latitude == null || drawing) locate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  function locate() {
    if (!navigator.geolocation) { setGeoMsg("Il browser non permette di leggere la posizione."); return; }
    setGeoMsg("Cerco la tua posizione…");
    navigator.geolocation.getCurrentPosition((pos) => {
      const c: LL = [pos.coords.longitude, pos.coords.latitude];
      setGeoMsg(`Posizione trovata (precisione circa ${Math.round(pos.coords.accuracy)} m).`);
      map.current?.flyTo({ center: c, zoom: 17 });
      me.current?.remove();
      const dot = document.createElement("div");
      dot.className = "me-dot";
      me.current = new maplibregl.Marker({ element: dot }).setLngLat(c).addTo(map.current!);
    }, () => setGeoMsg("Posizione non disponibile: sposta la mappa a mano fino al tuo terreno."),
    { enableHighAccuracy: true, timeout: 10000 });
  }

  // ---- data for the chosen year ----
  const future = year > farm.season_year;
  const proposals = useQueries({ queries: farm.plots.map((p) => ({
    queryKey: ["plan-proposal", p.id, p.sections.map((x) => x.id).join(), p.history.length, JSON.stringify(p.profile?.goals ?? {})],
    queryFn: () => api.post<PlanResult>(`/api/v1/rotation/plots/${p.id}/plan`, p.profile?.goals ?? {}),
    enabled: future && !!ringOf(p) && !p.plans.some((x) => x.year === year), staleTime: 5 * 60_000, refetchInterval: false,
  })) });
  const propKey = proposals.map((q) => q.dataUpdatedAt).join();
  const perPlot = useMemo(() => farm.plots.map((p, i) => ({ p, crops: cropsFor(p, year, farm.season_year, proposals[i]?.data) })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [farm, year, propKey]);
  const anyProposed = perPlot.some((x) => x.crops.some((c) => c.proposed));
  const legend = useMemo(() => {
    const m = new Map<string, { name: string; color: string; area: number }>();
    let unplanned = 0, total = 0;
    for (const { p, crops } of perPlot) {
      const a = p.area_m2 ?? 0;
      total += a;
      const used = crops.reduce((s, c) => s + c.area, 0);
      if (!crops.length) { unplanned += a; continue; }
      crops.forEach((c) => {
        const e = m.get(c.crop) ?? { name: shortName(c.name), color: cropColor(c.crop, c.family), area: 0 };
        e.area += c.area;
        m.set(c.crop, e);
      });
      unplanned += Math.max(0, a - used);
    }
    const rows = [...m.entries()].map(([k, v]) => ({ key: k, ...v })).sort((x, y) => y.area - x.area);
    return { rows, unplanned, total };
  }, [perPlot]);

  useEffect(() => {
    if (!ready || !map.current) return;
    const m = map.current;
    const plots: ReturnType<typeof poly>[] = [], secs: ReturnType<typeof poly>[] = [];
    labels.current.forEach((x) => x.remove());
    labels.current = [];
    for (const { p, crops } of perPlot) {
      const r = ringOf(p);
      if (!r) continue;
      const main = [...crops].sort((a, b) => b.area - a.area)[0];
      const bySection = crops.filter((c) => c.section_id);
      const color = main ? cropColor(main.crop, main.family) : UNPLANNED;
      plots.push(poly(r, { id: p.id, color, opacity: bySection.length ? 0.18 : main ? 0.55 : 0.4,
        stroke: p.id === sel ? "#ffd24a" : main ? color : "#ffffff", width: p.id === sel ? 4 : 2.5 }));
      for (const s of p.sections.filter((x) => isGrowing(x.kind))) {
        const c = bySection.find((x) => x.section_id === s.id);
        const sr = sectionRing(p, s);
        if (sr) secs.push(poly(sr, { color: c ? cropColor(c.crop, c.family) : "#ffffff", opacity: c ? (c.proposed ? 0.6 : 0.78) : 0.12 }));
      }
      const lab = document.createElement("div");
      lab.className = "map-label";
      lab.innerHTML = `<b></b><span></span>`;
      lab.querySelector("b")!.textContent = p.name;
      lab.querySelector("span")!.textContent = main ? [...new Set(crops.map((c) => shortName(c.name)))].slice(0, 3).join(", ") : "Non pianificato";
      lab.onclick = (e) => { e.stopPropagation(); if (!drawingRef.current) setSel(p.id); };
      labels.current.push(new maplibregl.Marker({ element: lab }).setLngLat(centroid(r)).addTo(m));
    }
    setSrc(m, "plots", { type: "FeatureCollection", features: plots });
    setSrc(m, "sections", { type: "FeatureCollection", features: secs });
  }, [ready, perPlot, sel]);

  // ---- drawing ----
  useEffect(() => {
    if (!ready || !map.current) return;
    const m = map.current;
    const fc = (features: any[]) => ({ type: "FeatureCollection" as const, features });
    setSrc(m, "draft-pts", fc(pts.map((q) => ({ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: q } }))));
    setSrc(m, "draft-line", fc(pts.length > 1 ? [{ type: "Feature", properties: {},
      geometry: { type: "LineString", coordinates: pts.length > 2 ? [...pts, pts[0]] : pts } }] : []));
    setSrc(m, "draft-area", fc(pts.length > 2 ? [poly(pts, {})] : []));
  }, [ready, pts]);

  const save = useMutation({
    mutationFn: async () => {
      let id = drawing?.plotId ?? null;
      if (!id) {
        const p = await api.post<Plot>("/api/v1/rotation/plots", { name: name.trim() || "Appezzamento", profile: farm.plots[0]?.profile ?? {} });
        id = p.id;
      }
      await api.put(`/api/v1/rotation/plots/${id}/boundary`, { ring: pts });
      return id;
    },
    onSuccess: (id) => {
      qc.invalidateQueries({ queryKey: ["rotation-farm"] });
      setDrawing(null); setPts([]); setSel(id); onDrawn();
    },
  });
  const area = ringArea(pts);
  const target = drawing?.plotId ? farm.plots.find((p) => p.id === drawing.plotId) : null;
  const selected = sel ? perPlot.find((x) => x.p.id === sel) : null;

  return (
    <div className="farm-map-wrap">
      <div className="card farm-map-card">
        <div className="year-tabs" style={{ marginBottom: 8 }}>
          {years.map((y) => (
            <button key={y} className={year === y ? "on" : ""} onClick={() => setYear(y)}>
              {y === farm.season_year ? "Oggi" : "Piano"}<small>{y}</small>
            </button>
          ))}
        </div>
        <div className="farm-map">
          <div ref={el} className="farm-map-canvas" />
          <div className="map-tools">
            <button className="btn sm map-btn" onClick={locate}><Icon name="locate" size={14} />La mia posizione</button>
            {!drawing && <button className="btn sm" onClick={() => { setDrawing({ plotId: null }); setPts([]); setSel(null); setName(`Appezzamento ${farm.plots.length + 1}`); }}>
              <Icon name="pen" size={14} />Traccia un terreno</button>}
          </div>
          {drawing && (
            <div className="draw-panel">
              <div className="small"><b>{target ? `Ridisegna «${target.name}»` : "Nuovo appezzamento"}</b></div>
              <div className="tiny muted">{pts.length < 3 ? "Tocca la mappa sugli angoli del terreno, uno dopo l'altro." : "Continua ad aggiungere angoli o salva."}</div>
              <div className="draw-nums">
                <div><span className="tiny muted">Superficie</span><b>{pts.length > 2 ? fmtArea(area) : "—"}</b></div>
                <div><span className="tiny muted">Perimetro</span><b>{pts.length > 1 ? `${Math.round(ringPerimeter(pts, pts.length > 2)).toLocaleString("it-IT")} m` : "—"}</b></div>
                <div><span className="tiny muted">Punti</span><b>{pts.length}</b></div>
              </div>
              {!target && <label className="field">Nome<input value={name} onChange={(e) => setName(e.target.value)} /></label>}
              {save.isError && <div className="tiny" style={{ color: "var(--danger)" }}>{(save.error as Error).message}</div>}
              <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                <button className="btn ghost sm" disabled={!pts.length} onClick={() => setPts((p) => p.slice(0, -1))}><Icon name="undo" size={13} />Togli punto</button>
                <button className="btn ghost sm" onClick={() => { setDrawing(null); setPts([]); onDrawn(); }}>Annulla</button>
                <button className="btn sm" disabled={pts.length < 3 || save.isPending} onClick={() => save.mutate()}><Icon name="check" size={13} />{save.isPending ? "Salvo…" : "Salva"}</button>
              </div>
            </div>
          )}
        </div>
        {geoMsg && <div className="tiny muted" style={{ marginTop: 6 }}>{geoMsg}</div>}
        {farm.plots.length > mapped.length && !drawing && (
          <div className="tiny muted" style={{ marginTop: 6 }}>
            {farm.plots.length - mapped.length} {farm.plots.length - mapped.length === 1 ? "appezzamento non è ancora tracciato" : "appezzamenti non sono ancora tracciati"} sulla mappa:
            {" "}{farm.plots.filter((p) => !ringOf(p)).map((p) => (
              <button key={p.id} className="link-btn" onClick={() => { setDrawing({ plotId: p.id }); setPts([]); }}>{p.name}</button>
            ))}
          </div>
        )}
      </div>

      <div className="card map-legend">
        <div className="row"><b>{year === farm.season_year ? `Colture ${year}` : anyProposed ? `Proposta ${year}` : `Piano ${year}`}</b><span className="spacer" /><span className="tiny muted">{fmtArea(legend.total)}</span></div>
        <div className="legend-rows">
          <LegendRow color={UNPLANNED} name="Non pianificato" area={legend.unplanned} total={legend.total} />
          {legend.rows.map((r) => <LegendRow key={r.key} color={r.color} name={r.name} area={r.area} total={legend.total} />)}
        </div>
        {anyProposed && <div className="tiny muted" style={{ marginTop: 6 }}>Proposta di AgroAI, non ancora salvata: aprila da «Apri il piano» per vedere i motivi, cambiarla e salvarla.</div>}
        {future && !legend.rows.length && <div className="tiny muted">Dividi gli appezzamenti in parti per vedere come distribuire le colture.</div>}
        {selected && (
          <div className="map-sel">
            <div className="row"><b>{selected.p.name}</b><span className="spacer" /><span className="small muted">{fmtArea(selected.p.area_m2)}</span></div>
            <div className="chips-line">
              {selected.crops.length ? [...new Map(selected.crops.map((c) => [c.crop, c])).values()].map((c) =>
                <span key={c.crop} className="mini-chip" style={{ ["--c" as any]: cropColor(c.crop, c.family) }}>{shortName(c.name)}</span>)
                : <span className="tiny muted">Non pianificato</span>}
            </div>
            {!selected.p.sections.some((x) => isGrowing(x.kind)) && <SplitCard plot={selected.p} compact onDone={() => setYear(farm.season_year + 1)} />}
            <div className="row" style={{ gap: 6, marginTop: 8, flexWrap: "wrap" }}>
              <button className="btn sm" onClick={() => onOpen(selected.p.id)}><Icon name="layers" size={13} />Apri il piano</button>
              <button className="btn ghost sm" onClick={() => { setDrawing({ plotId: selected.p.id }); setPts([]); }}><Icon name="pen" size={13} />Ridisegna</button>
            </div>
          </div>
        )}
        <div className="tiny muted" style={{ marginTop: 8 }}>La superficie è calcolata dai punti che segni: la precisione dipende da quanto sono esatti.</div>
      </div>
    </div>
  );
}

function LegendRow({ color, name, area, total }: { color: string; name: string; area: number; total: number }) {
  const pct = total > 0 ? (area / total) * 100 : 0;
  return (
    <div className="legend-row">
      <span className="swatch" style={{ background: color }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="small" style={{ fontWeight: 650 }}>{name}</div>
        <div className="tiny muted">{fmtArea(area)} · {pct.toLocaleString("it-IT", { maximumFractionDigits: 1 })}%</div>
      </div>
    </div>
  );
}
