import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { Icon } from "../Icon";
import { fmtArea, Plot } from "./types";

/** Split a whole plot into equal-area parts (one per crop of the rotation), with paths in between. */
export default function SplitCard({ plot, compact, onDone }: { plot: Plot; compact?: boolean; onDone?: () => void }) {
  const qc = useQueryClient();
  const area = plot.area_m2 ?? 0;
  const garden = area < 2000;
  const wanted = Object.keys(plot.profile?.goals?.wanted ?? {}).length;
  const [parts, setParts] = useState(Math.min(8, Math.max(3, wanted + 2)));
  const path = garden ? 0.6 : 3;
  const split = useMutation({
    mutationFn: () => api.post(`/api/v1/rotation/plots/${plot.id}/auto-layout`, { parts }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["rotation-farm"] }); onDone?.(); },
  });
  const each = Math.max(0, area - path * Math.min(plot.width_m ?? 0, plot.length_m ?? 0) * (parts - 1)) / parts;
  return (
    <div className={`split-card ${compact ? "compact" : ""}`}>
      <div className="row" style={{ gap: 10, alignItems: "flex-start" }}>
        <Icon name="split" size={20} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <b>Distribuisci le colture</b>
          <div className="small muted">
            Ora il terreno è un blocco unico, quindi ci va una sola coltura. Dividilo in parti uguali: ogni parte avrà la
            sua coltura e ogni anno le colture si spostano tra le parti.
          </div>
        </div>
      </div>
      <div className="split-row">
        <div className="stepper sm">
          <button className="icon-btn" onClick={() => setParts(Math.max(2, parts - 1))} aria-label="Meno parti"><Icon name="minus" size={14} /></button>
          <b>{parts}</b>
          <button className="icon-btn" onClick={() => setParts(Math.min(12, parts + 1))} aria-label="Più parti"><Icon name="plus" size={14} /></button>
        </div>
        <div className="tiny muted" style={{ flex: 1, minWidth: 140 }}>
          {garden ? "aiuole" : "parti"} di circa <b>{fmtArea(each)}</b>, con {garden ? "sentieri da 60 cm" : "capezzagne da 3 m per passare con i mezzi"}.
          {parts < 3 && " Per una rotazione servono almeno 3 colture diverse."}
        </div>
        <button className="btn sm" disabled={split.isPending} onClick={() => split.mutate()}>
          <Icon name="split" size={13} />{split.isPending ? "Divido…" : `Dividi in ${parts}`}
        </button>
      </div>
      {split.isError && <div className="tiny" style={{ color: "var(--danger)" }}>{(split.error as Error).message}</div>}
    </div>
  );
}
