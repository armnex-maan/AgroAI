import { useEffect, useRef, useState } from "react";
import maplibregl, { Map as MlMap, Marker, StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

export const style = (satellite: boolean): StyleSpecification => ({
  version: 8,
  sources: {
    base: satellite
      ? {
          type: "raster", tileSize: 256,
          tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
          attribution: "Imagery © Esri, Maxar, Earthstar Geographics, GIS User Community",
          maxzoom: 19,
        }
      : {
          type: "raster", tileSize: 256,
          tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
          attribution: "© OpenStreetMap contributors",
          maxzoom: 19,
        },
  },
  layers: [{ id: "base", type: "raster", source: "base" }],
});

export interface MapPoint { lat: number; lon: number; label?: string; color?: string; }

export function BaseMap({ center, zoom = 12, points = [], picked, onPick, height = 420 }: {
  center: [number, number]; zoom?: number; points?: MapPoint[]; picked?: MapPoint | null;
  onPick?: (p: { lat: number; lon: number }) => void; height?: number;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const markers = useRef<Marker[]>([]);
  const pickMarker = useRef<Marker | null>(null);
  const [satellite, setSatellite] = useState(true);
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;

  useEffect(() => {
    if (!el.current) return;
    const m = new maplibregl.Map({ container: el.current, style: style(satellite), center, zoom, attributionControl: { compact: true } });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.on("click", (e) => onPickRef.current?.({ lat: +e.lngLat.lat.toFixed(5), lon: +e.lngLat.lng.toFixed(5) }));
    map.current = m;
    return () => { m.remove(); map.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { map.current?.setStyle(style(satellite)); }, [satellite]);

  useEffect(() => {
    if (!map.current) return;
    markers.current.forEach((mk) => mk.remove());
    markers.current = points.map((p) =>
      new maplibregl.Marker({ color: p.color ?? "#34d17f" })
        .setLngLat([p.lon, p.lat])
        .setPopup(p.label ? new maplibregl.Popup({ offset: 18 }).setText(p.label) : undefined)
        .addTo(map.current!)
    );
  }, [points]);

  useEffect(() => {
    if (!map.current) return;
    pickMarker.current?.remove();
    if (picked) {
      pickMarker.current = new maplibregl.Marker({ color: "#e8b23a" }).setLngLat([picked.lon, picked.lat]).addTo(map.current);
    }
  }, [picked]);

  useEffect(() => { map.current?.flyTo({ center, zoom, essential: true }); }, [center[0], center[1]]);

  return (
    <div style={{ position: "relative", borderRadius: 12, overflow: "hidden", border: "1px solid var(--border)" }}>
      <div ref={el} style={{ height }} />
      <div className="tabs" style={{ position: "absolute", top: 10, left: 10 }}>
        <button className={satellite ? "on" : ""} onClick={() => setSatellite(true)}>Satellite</button>
        <button className={!satellite ? "on" : ""} onClick={() => setSatellite(false)}>Mappa</button>
      </div>
    </div>
  );
}
