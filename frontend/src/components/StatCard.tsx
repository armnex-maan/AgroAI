import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts";
import { ProvenanceBadge } from "./ProvenanceBadge";
import { Source } from "../api/types";
import { Icon } from "./Icon";
import { num } from "../lib/it";

interface Props {
  label: string;
  value: number | string | undefined;
  unit?: string;
  source?: Source;
  meta?: string;
  icon?: string;
  spark?: number[];
  color?: string;
  digits?: number;
}

export function StatCard({ label, value, unit, source, meta, icon, spark, color = "var(--accent)", digits = 1 }: Props) {
  const shown = typeof value === "number" ? num(value, digits) : value;
  const gid = `g-${label.replace(/\W/g, "")}`;
  return (
    <div className="card kpi">
      <div className="label">{icon && <Icon name={icon} size={14} />}{label}</div>
      <div className="value">
        {shown ?? "—"}
        {unit && shown !== undefined && <span className="unit">{unit}</span>}
      </div>
      <div className="meta">
        <span>{meta ?? ""}</span>
        {source && <ProvenanceBadge source={source} />}
      </div>
      {spark && spark.length > 2 && (
        <div className="spark">
          <ResponsiveContainer>
            <AreaChart data={spark.map((v, i) => ({ i, v }))} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.45} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <YAxis hide domain={["dataMin", "dataMax"]} />
              <Area dataKey="v" type="monotone" stroke={color} strokeWidth={1.5} fill={`url(#${gid})`}
                    isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
