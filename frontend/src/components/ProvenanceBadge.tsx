import { SOURCE, SOURCE_HELP } from "../lib/it";

export function ProvenanceBadge({ source }: { source: string }) {
  return <span className={`badge badge-${source}`} title={SOURCE_HELP[source]}>{SOURCE[source] ?? source}</span>;
}
