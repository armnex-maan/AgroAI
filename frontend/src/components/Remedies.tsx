import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Icon } from "./Icon";

export interface Remedy {
  id: string; name: string; type: string; evidence: string; against: string; how: string;
  sources: { title: string; url: string }[]; causes: string[];
}

export const REMEDY_TYPE: Record<string, { label: string; icon: string; tone: string }> = {
  "insetto utile": { label: "Insetto utile", icon: "bug", tone: "ok" },
  "microrganismo": { label: "Microrganismo utile", icon: "flask", tone: "info" },
  "prodotto naturale": { label: "Prodotto naturale", icon: "leaf", tone: "neutral" },
  "pratica": { label: "Pratica agricola", icon: "sprout", tone: "neutral" },
  "tradizionale": { label: "Rimedio tradizionale", icon: "book", tone: "warn" },
};
export const EVIDENCE: Record<string, [string, string]> = {
  provato: ["Efficacia provata", "ok"], "alcuni studi": ["Alcuni studi", "info"], tradizionale: ["Tradizione, poco studiato", "warn"],
};

export function useRemedies() {
  return useQuery({
    queryKey: ["remedies"],
    queryFn: () => api.get<{ remedies: Remedy[]; causes: Record<string, string>; by_cause: Record<string, string[]> }>("/api/v1/vision/remedies"),
    refetchInterval: false, staleTime: Infinity,
  });
}

export function RemedyCard({ r, compact = false }: { r: Remedy; compact?: boolean }) {
  const t = REMEDY_TYPE[r.type] ?? { label: r.type, icon: "sprout", tone: "neutral" };
  const [ev, evTone] = EVIDENCE[r.evidence] ?? [r.evidence, "neutral"];
  return (
    <div className="candidate" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div className="row" style={{ flexWrap: "nowrap", alignItems: "flex-start" }}>
        <span className="remedy-icon"><Icon name={t.icon} size={18} /></span>
        <div style={{ flex: 1 }}>
          <b style={{ fontSize: 15 }}>{r.name}</b>
          <div className="small" style={{ color: "var(--accent)" }}>contro: {r.against}</div>
        </div>
      </div>
      <div className="row">
        <span className={`badge badge-${t.tone}`}>{t.label}</span>
        <span className={`badge badge-${evTone}`}>{ev}</span>
      </div>
      {!compact && <div className="small" style={{ color: "var(--text-2)", lineHeight: 1.6 }}>{r.how}</div>}
      {compact && <div className="small" style={{ color: "var(--text-2)", lineHeight: 1.55 }}>{r.how}</div>}
      <details className="tiny">
        <summary style={{ cursor: "pointer", color: "var(--text-dim)" }}>Fonti</summary>
        {r.sources.map((s) => <div key={s.url} style={{ marginTop: 3 }}><a href={s.url} target="_blank" rel="noreferrer">{s.title} ↗</a></div>)}
      </details>
    </div>
  );
}
