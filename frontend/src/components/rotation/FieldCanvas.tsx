import { useRef, useState } from "react";
import { Icon } from "../Icon";
import { Assignment, cropColor, GROUP_ICON, isGrowing, Kind, KIND_LABEL, RCrop, Section, shortName } from "./types";

/** Top-down drawing of a plot in real metres (x to the east, y to the south). In "edit" mode sections can be
 *  dragged and resized, and the vertices of an irregular outline can be moved. In "view" mode each growing bed
 *  shows the crop assigned for the chosen year. */
export interface CanvasProps {
  width: number; length: number; shape: string; outline: number[][] | null; orientation: number; exposure?: string | null;
  sections: Section[]; mode: "edit" | "view"; selected?: number | null; onSelect?: (i: number | null) => void;
  onChange?: (sections: Section[]) => void; onOutline?: (pts: number[][]) => void;
  crops?: Record<string, Assignment | undefined>; catalog?: RCrop[]; height?: number; compact?: boolean;
}

const SNAP = 0.25;
const snap = (v: number) => Math.round(v / SNAP) * SNAP;
const KIND_FILL: Record<Kind, string> = {
  bed: "#e7f4e4", path: "url(#pathHatch)", access: "#f6d38a", water: "#bfe0f7", no_crop: "url(#noCropHatch)",
  shade: "rgba(40,60,50,.22)", greenhouse: "#e3f1f8",
};

export default function FieldCanvas(p: CanvasProps) {
  const svg = useRef<SVGSVGElement | null>(null);
  const [drag, setDrag] = useState<null | { i: number; mode: "move" | "resize" | "vertex"; dx: number; dy: number }>(null);
  const W = Math.max(p.width, 1), L = Math.max(p.length, 1);
  const pad = Math.max(W, L) * (p.compact ? 0.04 : 0.09);
  const grid = Math.max(W, L) > 60 ? 10 : Math.max(W, L) > 25 ? 5 : 1;
  const fs = Math.max(W, L) / (p.compact ? 14 : 30); // font size in metres

  const toM = (e: React.PointerEvent) => {
    const pt = svg.current!.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const r = pt.matrixTransform(svg.current!.getScreenCTM()!.inverse());
    return { x: r.x, y: r.y };
  };
  const start = (e: React.PointerEvent, i: number, mode: "move" | "resize" | "vertex") => {
    if (p.mode !== "edit") return;
    e.stopPropagation();
    (e.target as Element).setPointerCapture?.(e.pointerId);
    const m = toM(e);
    if (mode === "vertex") setDrag({ i, mode, dx: 0, dy: 0 });
    else {
      const s = p.sections[i];
      setDrag({ i, mode, dx: m.x - (mode === "move" ? s.x : s.x + s.w), dy: m.y - (mode === "move" ? s.y : s.y + s.h) });
      p.onSelect?.(i);
    }
  };
  const move = (e: React.PointerEvent) => {
    if (!drag) return;
    const m = toM(e);
    if (drag.mode === "vertex" && p.outline) {
      const pts = p.outline.map((q, k) => (k === drag.i ? [snap(Math.max(0, m.x)), snap(Math.max(0, m.y))] : q));
      p.onOutline?.(pts);
      return;
    }
    const out = p.sections.map((s, k) => {
      if (k !== drag.i) return s;
      if (drag.mode === "move") {
        const x = Math.min(Math.max(0, snap(m.x - drag.dx)), W - s.w);
        const y = Math.min(Math.max(0, snap(m.y - drag.dy)), L - s.h);
        return { ...s, x, y };
      }
      const w = Math.min(Math.max(SNAP * 2, snap(m.x - drag.dx - s.x)), W - s.x);
      const h = Math.min(Math.max(SNAP * 2, snap(m.y - drag.dy - s.y)), L - s.y);
      return { ...s, w, h };
    });
    p.onChange?.(out);
  };
  const end = () => setDrag(null);
  const byKey = Object.fromEntries((p.catalog ?? []).map((c) => [c.key, c]));
  const outlinePts = p.shape === "irregular" && p.outline && p.outline.length >= 3 ? p.outline : null;

  return (
    <svg ref={svg} className={`field-canvas ${p.mode}`} viewBox={`${-pad} ${-pad} ${W + pad * 2} ${L + pad * 2}`}
         style={{ height: p.height, touchAction: p.mode === "edit" ? "none" : "auto" }}
         onPointerMove={move} onPointerUp={end} onPointerLeave={end} onPointerDown={() => p.onSelect?.(null)}
         role="img" aria-label="Pianta dell'appezzamento vista dall'alto">
      <defs>
        <pattern id="pathHatch" width={0.6} height={0.6} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width={0.6} height={0.6} fill="#efe3c8" /><line x1={0} y1={0} x2={0} y2={0.6} stroke="#d8c59c" strokeWidth={0.18} />
        </pattern>
        <pattern id="noCropHatch" width={0.8} height={0.8} patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
          <rect width={0.8} height={0.8} fill="#eceeed" /><line x1={0} y1={0} x2={0} y2={0.8} stroke="#c3c9c6" strokeWidth={0.2} />
        </pattern>
        <clipPath id="plotClip">
          {outlinePts ? <polygon points={outlinePts.map((q) => q.join(",")).join(" ")} /> : <rect x={0} y={0} width={W} height={L} />}
        </clipPath>
      </defs>
      {/* soil and grid */}
      {outlinePts
        ? <polygon points={outlinePts.map((q) => q.join(",")).join(" ")} fill="#d9c4a3" stroke="#8a6b46" strokeWidth={fs * 0.12} />
        : <rect x={0} y={0} width={W} height={L} fill="#d9c4a3" stroke="#8a6b46" strokeWidth={fs * 0.12} rx={fs * 0.2} />}
      {!p.compact && (
        <g clipPath="url(#plotClip)" stroke="rgba(90,70,40,.18)" strokeWidth={fs * 0.04}>
          {Array.from({ length: Math.floor(W / grid) }, (_, i) => <line key={`v${i}`} x1={(i + 1) * grid} y1={0} x2={(i + 1) * grid} y2={L} />)}
          {Array.from({ length: Math.floor(L / grid) }, (_, i) => <line key={`h${i}`} x1={0} y1={(i + 1) * grid} x2={W} y2={(i + 1) * grid} />)}
        </g>
      )}
      {/* sections */}
      <g clipPath="url(#plotClip)">
        {p.sections.map((s, i) => {
          const a = s.id ? p.crops?.[s.id] : undefined;
          const c = a ? byKey[a.crop] : undefined;
          const fill = isGrowing(s.kind) && a && a.crop !== "cover" ? cropColor(a.crop, a.family) : KIND_FILL[s.kind];
          const sel = p.selected === i;
          const small = Math.min(s.w, s.h);
          return (
            <g key={s.id ?? i} onPointerDown={(e) => start(e, i, "move")} style={{ cursor: p.mode === "edit" ? "move" : "default" }}>
              <rect x={s.x} y={s.y} width={s.w} height={s.h} fill={fill} rx={Math.min(fs * 0.25, small / 4)}
                    stroke={sel ? "#155c32" : isGrowing(s.kind) ? "rgba(21,92,50,.45)" : "rgba(0,0,0,.18)"}
                    strokeWidth={sel ? fs * 0.16 : fs * 0.06} opacity={a?.verdict === "no" ? 0.55 : 1} />
              {isGrowing(s.kind) && a && a.crop === "cover" && (
                <rect x={s.x} y={s.y} width={s.w} height={s.h} fill="url(#pathHatch)" opacity={0.6} />
              )}
              {s.kind === "water" && <circle cx={s.x + s.w / 2} cy={s.y + s.h / 2} r={Math.min(s.w, s.h) / 3} fill="#2f80d1" opacity={0.75} />}
              {s.kind === "access" && (
                <path d={`M${s.x + s.w * 0.2} ${s.y + s.h / 2} L${s.x + s.w * 0.8} ${s.y + s.h / 2} M${s.x + s.w * 0.6} ${s.y + s.h * 0.3} L${s.x + s.w * 0.8} ${s.y + s.h / 2} L${s.x + s.w * 0.6} ${s.y + s.h * 0.7}`}
                      stroke="#7a5a12" strokeWidth={fs * 0.12} fill="none" strokeLinecap="round" />
              )}
              {small > fs * 1.6 && (
                <g pointerEvents="none">
                  {isGrowing(s.kind) && a && c && (
                    <g transform={`translate(${s.x + s.w / 2 - fs * 0.75} ${s.y + s.h / 2 - fs * 1.9}) scale(${fs / 16})`} color="#fff">
                      <circle cx={12} cy={12} r={13} fill="rgba(0,0,0,.18)" />
                      <foreignObject x={0} y={0} width={24} height={24}>
                        <div style={{ color: "#fff", display: "grid", placeItems: "center", width: 24, height: 24 }}>
                          <Icon name={GROUP_ICON[c.group] ?? "leaf"} size={18} stroke={2.2} />
                        </div>
                      </foreignObject>
                    </g>
                  )}
                  <text x={s.x + s.w / 2} y={s.y + s.h / 2 + (a ? fs * 0.7 : fs * 0.2)} textAnchor="middle" fontSize={fs * 0.9}
                        fontWeight={700} fill={isGrowing(s.kind) && a && a.crop !== "cover" ? "#fff" : "#2b3b33"}
                        style={{ paintOrder: "stroke", stroke: isGrowing(s.kind) && a && a.crop !== "cover" ? "rgba(0,0,0,.25)" : "none", strokeWidth: fs * 0.1 }}>
                    {a ? shortName(a.name) : isGrowing(s.kind) ? s.name : KIND_LABEL[s.kind]}
                  </text>
                  {!p.compact && small > fs * 3 && (
                    <text x={s.x + s.w / 2} y={s.y + s.h / 2 + (a ? fs * 1.8 : fs * 1.3)} textAnchor="middle" fontSize={fs * 0.62}
                          fill={isGrowing(s.kind) && a && a.crop !== "cover" ? "rgba(255,255,255,.92)" : "#55655c"}>
                      {a ? s.name + " · " : ""}{(s.w * s.h).toLocaleString("it-IT", { maximumFractionDigits: 1 })} m²
                    </text>
                  )}
                </g>
              )}
              {p.mode === "edit" && sel && (
                <rect x={s.x + s.w - fs * 0.7} y={s.y + s.h - fs * 0.7} width={fs * 0.9} height={fs * 0.9} rx={fs * 0.2}
                      fill="#155c32" stroke="#fff" strokeWidth={fs * 0.08} style={{ cursor: "nwse-resize" }}
                      onPointerDown={(e) => start(e, i, "resize")} />
              )}
            </g>
          );
        })}
      </g>
      {/* irregular outline vertices */}
      {p.mode === "edit" && outlinePts && outlinePts.map((q, k) => (
        <circle key={k} cx={q[0]} cy={q[1]} r={fs * 0.45} fill="#fff" stroke="#8a6b46" strokeWidth={fs * 0.12}
                style={{ cursor: "grab" }} onPointerDown={(e) => start(e, k, "vertex")} />
      ))}
      {/* dimensions */}
      {!p.compact && (
        <g fontSize={fs * 0.8} fill="#55655c">
          <text x={W / 2} y={-pad * 0.35} textAnchor="middle">{W.toLocaleString("it-IT")} m</text>
          <text x={-pad * 0.35} y={L / 2} textAnchor="middle" transform={`rotate(-90 ${-pad * 0.35} ${L / 2})`}>{L.toLocaleString("it-IT")} m</text>
        </g>
      )}
      {/* north arrow */}
      <g transform={`translate(${W + pad * 0.5} ${-pad * 0.5}) rotate(${p.orientation})`} pointerEvents="none">
        <circle r={pad * 0.38} fill="#fff" stroke="#c5d3ca" strokeWidth={fs * 0.06} />
        <path d={`M0 ${-pad * 0.3} L${pad * 0.12} ${pad * 0.1} L0 ${pad * 0.02} L${-pad * 0.12} ${pad * 0.1}Z`} fill="#dc4136" />
        <text y={pad * 0.3} textAnchor="middle" fontSize={pad * 0.2} fontWeight={800} fill="#2b3b33">N</text>
      </g>
    </svg>
  );
}
