/**
 * «Render fotorealistico»: sends the scene as it is on screen to the backend, which renders it with Blender Cycles
 * (real 3D trees and crops, grass, sky, horizon). Shows progress, then the picture with download.
 * The picture is an illustration of the plan (same parts, crops and framing as the 3D view), labelled as such.
 */
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../../api/client";
import { Icon } from "../../Icon";
import type { RenderMeta } from "./renderExport";

const API = import.meta.env.VITE_API_URL || "";

export interface RenderStatus { available: boolean; reason?: string; note?: string | null; trees: number; trees_total: number }
interface RenderJob {
  id: string; state: "queued" | "running" | "done" | "error"; stage: string; stage_label: string; progress: number;
  error: string | null; seconds: number; image: string | null;
}

export function useRenderStatus() {
  return useQuery({ queryKey: ["render-status"], queryFn: () => api.get<RenderStatus>("/api/v1/render/status"),
    refetchInterval: false, staleTime: 60_000, retry: false });
}

export function RenderPanel({ exportScene, label, onClose, onBusy }: {
  exportScene: () => Promise<{ glb: Blob; meta: RenderMeta }>;
  label: { farm: string; year: number; exag: number };
  onClose: () => void;
  /** true while Blender works: the planner pauses its own drawing to leave the GPU to Cycles */
  onBusy?: (busy: boolean) => void;
}) {
  const [phase, setPhase] = useState<"export" | "upload" | "job" | "error">("export");
  const [jobId, setJobId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        await new Promise((r) => setTimeout(r, 50));          // let the panel paint before the export blocks the page
        const { glb, meta } = await exportScene();
        setPhase("upload");
        const fd = new FormData();
        fd.append("scene", glb, "scene.glb");
        fd.append("meta", new Blob([JSON.stringify(meta)], { type: "application/json" }), "meta.json");
        fd.append("label", JSON.stringify(label));
        const r = await fetch(`${API}/api/v1/render`, { method: "POST", body: fd });
        if (!r.ok) {
          let detail = `${r.status}`;
          try { detail = (await r.json()).detail ?? detail; } catch { /* not JSON */ }
          throw new Error(detail);
        }
        setJobId((await r.json()).id);
        setPhase("job");
      } catch (e) {
        setErr((e as Error).message || "Errore"); setPhase("error");
      }
    })();
  }, [exportScene, label]);

  const job = useQuery({
    queryKey: ["render-job", jobId], enabled: !!jobId,
    queryFn: () => api.get<RenderJob>(`/api/v1/render/${jobId}`),
    refetchInterval: (q) => (q.state.data && (q.state.data.state === "done" || q.state.data.state === "error") ? false : 1200),
  });
  const j = job.data;
  const failed = phase === "error" || j?.state === "error";
  const done = j?.state === "done" && j.image;
  const busy = !failed && !done;
  useEffect(() => { onBusy?.(busy); }, [busy, onBusy]);
  useEffect(() => () => onBusy?.(false), [onBusy]);
  const pct = phase === "export" ? 0.01 : phase === "upload" ? 0.03 : (j?.progress ?? 0.03);
  const stageText = phase === "export" ? "Preparo la scena (geometrie, piante, inquadratura)…" : phase === "upload" ? "Invio la scena al motore di render…"
    : j?.stage_label ?? "In coda";

  return (
    <div className="vp-render" role="dialog" aria-label="Render fotorealistico">
      <div className="vp-render-card">
        <div className="row"><Icon name="camera" size={18} /><b>Render fotorealistico</b><span className="spacer" />
          <button className="icon-btn" onClick={onClose} aria-label="Chiudi"><Icon name="minus" size={14} /></button></div>
        {done ? (
          <>
            <a href={`${API}${j!.image}`} target="_blank" rel="noreferrer" className="vp-render-img" title="Apri a piena risoluzione">
              <img src={`${API}${j!.image}`} alt="Render fotorealistico del piano" />
            </a>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <a className="btn sm" href={`${API}${j!.image}`} download={`agroai-render-${label.year}.png`}><Icon name="download" size={13} />Scarica PNG</a>
              <a className="btn ghost sm" href={`${API}${j!.image}`} target="_blank" rel="noreferrer"><Icon name="expand" size={13} />Piena risoluzione</a>
              <span className="spacer" />
              <span className="tiny muted">Pronto in {Math.round(j!.seconds)} s</span>
            </div>
          </>
        ) : failed ? (
          <div className="vp-render-err"><Icon name="alert" size={16} />{err ?? j?.error ?? "Il render non è riuscito."}</div>
        ) : (
          <div className="vp-render-run">
            <div className="vp-render-bar"><i style={{ width: `${Math.round(pct * 100)}%` }} /></div>
            <div className="row"><span>{stageText}</span><span className="spacer" /><b>{Math.round(pct * 100)}%</b></div>
            <div className="tiny muted">Blender Cycles sulla scheda grafica: di solito meno di un paio di minuti. Puoi continuare a usare il planner.</div>
          </div>
        )}
        <div className="tiny muted">Immagine illustrativa del piano: stesse parti, colture e inquadratura del 3D, con alberi, colture ed erba
          modellati in 3D.{label.exag > 1 ? ` Piante ingrandite ×${label.exag}, come nella vista.` : ""} Il paesaggio intorno è dimostrativo, non sono dati reali.</div>
      </div>
    </div>
  );
}
