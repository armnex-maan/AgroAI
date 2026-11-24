import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { Icon } from "../Icon";
import FieldCanvas from "./FieldCanvas";
import { fmtArea, isGrowing, Kind, KIND_LABEL, Plot, Section } from "./types";

const ORIENT = [["0", "Nord in alto"], ["45", "Nord-Est in alto"], ["90", "Est in alto"], ["135", "Sud-Est in alto"],
  ["180", "Sud in alto"], ["225", "Sud-Ovest in alto"], ["270", "Ovest in alto"], ["315", "Nord-Ovest in alto"]];
const EXPOSURE = [["full_sun", "Pieno sole"], ["part_shade", "Mezz'ombra"], ["shade", "Ombra"]];
const TOOLS: { kind: Kind; icon: string }[] = [
  { kind: "bed", icon: "sprout" }, { kind: "path", icon: "move" }, { kind: "access", icon: "arrow-right" },
  { kind: "water", icon: "drop" }, { kind: "no_crop", icon: "ban" }, { kind: "shade", icon: "cloud" },
  { kind: "greenhouse", icon: "home" },
];

export default function PlotEditor({ plot, onDone }: { plot: Plot; onDone?: () => void }) {
  const qc = useQueryClient();
  const [W, setW] = useState(plot.width_m ?? 10);
  const [L, setL] = useState(plot.length_m ?? 10);
  const [shape, setShape] = useState(plot.shape ?? "rectangle");
  const [outline, setOutline] = useState<number[][] | null>(plot.outline);
  const [orientation, setOrientation] = useState(plot.orientation_deg ?? 0);
  const [exposure, setExposure] = useState(plot.exposure ?? "full_sun");
  const [secs, setSecs] = useState<Section[]>(plot.sections);
  const [sel, setSel] = useState<number | null>(null);
  const [nBeds, setNBeds] = useState(4);
  const [pathW, setPathW] = useState(0.5);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    if (shape === "irregular" && (!outline || outline.length < 3)) setOutline([[0, 0], [W, 0], [W, L], [0, L]]);
  }, [shape]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = useMutation({
    mutationFn: () => api.put(`/api/v1/rotation/plots/${plot.id}/layout`, {
      width_m: W, length_m: L, shape, outline: shape === "irregular" ? outline : null,
      orientation_deg: orientation, exposure, sections: secs,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["rotation-farm"] }); setMsg("Disegno salvato."); onDone?.(); },
    onError: (e: any) => setMsg(String(e.message ?? e)),
  });

  const add = (kind: Kind) => {
    const size = { bed: [Math.min(3, W), Math.min(5, L)], path: [Math.min(W, 10), 0.6], access: [1.5, 1], water: [0.8, 0.8],
      no_crop: [2, 2], shade: [3, 3], greenhouse: [Math.min(5, W), Math.min(10, L)] }[kind];
    const n = secs.filter((s) => s.kind === kind).length + 1;
    const s: Section = { name: kind === "bed" ? `Aiuola ${n}` : `${KIND_LABEL[kind]} ${n}`, kind,
      x: 0, y: 0, w: Math.min(size[0], W), h: Math.min(size[1], L) };
    setSecs([...secs, s]);
    setSel(secs.length);
  };
  /** Split the plot into N parallel beds along its longest side, with paths in between. */
  const split = () => {
    const keep = secs.filter((s) => s.kind !== "bed" && s.kind !== "path");
    const along = W >= L ? "x" : "y";
    const total = along === "x" ? W : L;
    const bedW = Math.max(0.5, (total - pathW * (nBeds - 1)) / nBeds);
    const out: Section[] = [];
    for (let i = 0; i < nBeds; i++) {
      const pos = Math.round((i * (bedW + pathW)) * 100) / 100;
      out.push(along === "x" ? { name: `Aiuola ${i + 1}`, kind: "bed", x: pos, y: 0, w: bedW, h: L }
        : { name: `Aiuola ${i + 1}`, kind: "bed", x: 0, y: pos, w: W, h: bedW });
      if (i < nBeds - 1 && pathW > 0) {
        const pp = Math.round((pos + bedW) * 100) / 100;
        out.push(along === "x" ? { name: `Sentiero ${i + 1}`, kind: "path", x: pp, y: 0, w: pathW, h: L }
          : { name: `Sentiero ${i + 1}`, kind: "path", x: 0, y: pp, w: W, h: pathW });
      }
    }
    // existing beds keep their id (and their history) in order
    const oldBeds = secs.filter((s) => s.kind === "bed");
    out.filter((s) => s.kind === "bed").forEach((s, i) => { if (oldBeds[i]?.id) { s.id = oldBeds[i].id; s.name = oldBeds[i].name; } });
    setSecs([...out, ...keep]);
    setSel(null);
  };
  const upd = (patch: Partial<Section>) => sel != null && setSecs(secs.map((s, i) => (i === sel ? { ...s, ...patch } : s)));
  const s = sel != null ? secs[sel] : null;
  const bedArea = secs.filter((x) => isGrowing(x.kind)).reduce((a, x) => a + x.w * x.h, 0);

  return (
    <div className="editor">
      <div className="editor-main card" style={{ padding: 10 }}>
        <div className="tool-row">
          {TOOLS.map((t) => (
            <button key={t.kind} className="tool" onClick={() => add(t.kind)} title={`Aggiungi ${KIND_LABEL[t.kind].toLowerCase()}`}>
              <Icon name={t.icon} size={16} /><span>{KIND_LABEL[t.kind]}</span>
            </button>
          ))}
        </div>
        <FieldCanvas width={W} length={L} shape={shape} outline={outline} orientation={orientation} exposure={exposure}
                     sections={secs} mode="edit" selected={sel} onSelect={setSel} onChange={setSecs} onOutline={setOutline} />
        <div className="tiny muted" style={{ textAlign: "center", marginTop: 4 }}>
          Trascina le aree per spostarle; con il quadratino verde le ridimensioni. Griglia e misure sono in metri reali.
        </div>
      </div>

      <div className="editor-side stack">
        <div className="card">
          <h3><Icon name="grid" />Appezzamento</h3>
          <div className="form-grid">
            <label className="field">Forma
              <select value={shape} onChange={(e) => setShape(e.target.value as Plot["shape"])}>
                <option value="rectangle">Rettangolare</option><option value="square">Quadrato</option><option value="irregular">Irregolare</option>
              </select>
            </label>
            <label className="field">Esposizione
              <select value={exposure} onChange={(e) => setExposure(e.target.value)}>
                {EXPOSURE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label className="field">Larghezza (m)
              <input type="number" min={1} step={0.5} value={W} onChange={(e) => { const v = +e.target.value || 1; setW(v); if (shape === "square") setL(v); }} />
            </label>
            <label className="field">Lunghezza (m)
              <input type="number" min={1} step={0.5} value={L} disabled={shape === "square"} onChange={(e) => setL(+e.target.value || 1)} />
            </label>
            <label className="field" style={{ gridColumn: "1 / -1" }}>Orientamento
              <select value={String(orientation)} onChange={(e) => setOrientation(+e.target.value)}>
                {ORIENT.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
          </div>
          {shape === "irregular" && outline && (
            <div className="row" style={{ gap: 6, marginTop: 8 }}>
              <button className="btn ghost sm" onClick={() => {
                // add a vertex in the middle of the longest side
                let best = 0, len = -1;
                outline.forEach((q, i) => { const n = outline[(i + 1) % outline.length]; const d = Math.hypot(n[0] - q[0], n[1] - q[1]); if (d > len) { len = d; best = i; } });
                const a = outline[best], b = outline[(best + 1) % outline.length];
                const pts = [...outline]; pts.splice(best + 1, 0, [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]); setOutline(pts);
              }}><Icon name="plus" size={13} />Aggiungi vertice</button>
              {outline.length > 3 && <button className="btn ghost sm" onClick={() => setOutline(outline.slice(0, -1))}>Togli vertice</button>}
              <span className="tiny muted">Trascina i punti bianchi sul bordo.</span>
            </div>
          )}
          <div className="kv"><span>Superficie</span><b>{fmtArea(W * L)}</b></div>
          <div className="kv"><span>Coltivabile (aiuole)</span><b>{fmtArea(bedArea)}</b></div>
        </div>

        <div className="card">
          <h3><Icon name="split" />Dividi in aiuole</h3>
          <div className="form-grid">
            <label className="field">Numero di aiuole<input type="number" min={1} max={30} value={nBeds} onChange={(e) => setNBeds(Math.max(1, +e.target.value || 1))} /></label>
            <label className="field">Sentieri (m)<input type="number" min={0} max={3} step={0.1} value={pathW} onChange={(e) => setPathW(Math.max(0, +e.target.value || 0))} /></label>
          </div>
          <button className="btn secondary" style={{ width: "100%", marginTop: 8 }} onClick={split}>Dividi il terreno</button>
        </div>

        {s && (
          <div className="card">
            <div className="card-head"><h3 style={{ margin: 0 }}>{KIND_LABEL[s.kind]}</h3>
              <button className="icon-btn" title="Elimina" onClick={() => { setSecs(secs.filter((_, i) => i !== sel)); setSel(null); }}><Icon name="trash" size={15} /></button>
            </div>
            <div className="form-grid">
              <label className="field" style={{ gridColumn: "1 / -1" }}>Nome<input value={s.name} onChange={(e) => upd({ name: e.target.value })} /></label>
              <label className="field">Tipo
                <select value={s.kind} onChange={(e) => upd({ kind: e.target.value as Kind })}>
                  {Object.entries(KIND_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
              </label>
              <label className="field">Superficie<input disabled value={fmtArea(s.w * s.h)} /></label>
              {(["x", "y", "w", "h"] as const).map((k) => (
                <label key={k} className="field">{{ x: "Da ovest (m)", y: "Da nord (m)", w: "Larghezza (m)", h: "Lunghezza (m)" }[k]}
                  <input type="number" step={0.25} min={0} value={s[k]} onChange={(e) => upd({ [k]: Math.max(0, +e.target.value || 0) } as Partial<Section>)} />
                </label>
              ))}
            </div>
          </div>
        )}
        <button className="btn" onClick={() => save.mutate()} disabled={save.isPending}>
          <Icon name="check" size={15} />{save.isPending ? "Salvo…" : "Salva il disegno"}
        </button>
        {msg && <div className="small muted">{msg}</div>}
      </div>
    </div>
  );
}
