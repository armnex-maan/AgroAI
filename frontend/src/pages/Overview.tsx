import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useHistory } from "../api/hooks";
import { Icon } from "../components/Icon";
import { ago, num } from "../lib/it";

interface Metric { value: number; unit: string; source: string; device_id: string; status?: string; tone?: string;
  detail?: string; texture?: string | null }
interface Home {
  farm: { name: string | null; owner: string | null }; crop: string | null;
  soil_moisture: Metric | null; air_temperature: Metric | null; soil_ph: Metric | null; air_humidity: Metric | null;
  weather: null | { temperature: number; humidity: number; wind_kmh: number; label: string; icon: string;
    t_max: number; t_min: number; rain_mm: number; rain_prob: number | null; source: string };
  tip: { title: string; text: string; to: string };
  alerts: { id: string; ts: string; severity: string; category: string; message: string }[];
  alerts_open: number; demo: boolean;
}

const SLIDES = [
  { title: ["Monitoraggio", "in tempo reale"], accent: "del tuo campo", text: "Dati precisi, consigli intelligenti per un'agricoltura più produttiva.",
    cta: "Visualizza analisi", to: "/sensors", icon: "chart" },
  { title: ["Fotografa", "una pianta,"], accent: "scopri cos'ha", text: "Foglie e frutti: cause probabili e rimedi, anche naturali.",
    cta: "Controlla una pianta", to: "/vision", icon: "camera" },
  { title: ["Allontana", "gli uccelli"], accent: "senza danni", text: "Richiami veri, a ondate, come indicano gli studi.",
    cta: "Apri i suoni", to: "/acoustic", icon: "volume" },
];

export default function Overview() {
  const home = useQuery({ queryKey: ["home"], queryFn: () => api.get<Home>("/api/v1/home"), refetchInterval: 30000 });
  const h = home.data;
  return (
    <div className="home">
      <Hero />
      <div className="metric-grid">
        <MetricCard icon="sprout" tone="green" title="Umidità del suolo" m={h?.soil_moisture} unit="%" type="soil_moisture"
/>
        <MetricCard icon="thermo" tone="orange" title="Temperatura" m={h?.air_temperature} unit="°C" type="air_temperature" />
        <MetricCard icon="flaskph" tone="brown" title="pH del terreno" m={h?.soil_ph} unit="" type="soil_ph" digits={1} />
        <WeatherCard w={h?.weather} />
      </div>
      {h?.demo && (
        <div className="demo-note"><Icon name="flask" size={14} />Valori di prova del simulatore: collega un sensore per i dati veri.</div>
      )}
      {h && <TipCard tip={h.tip} />}
      <QuickActions />
      <Notifications h={h} />
    </div>
  );
}

function Hero() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((x) => (x + 1) % SLIDES.length), 6000);
    return () => clearInterval(t);
  }, []);
  const s = SLIDES[i];
  return (
    <section className="hero-card">
      <FieldArt />
      <div className="hero-body" key={i}>
        <h1>{s.title[0]}<br />{s.title[1]}<br /><span>{s.accent}</span></h1>
        <p>{s.text}</p>
        <Link to={s.to} className="hero-cta"><Icon name={s.icon} size={18} />{s.cta}<Icon name="arrow-right" size={16} /></Link>
      </div>
      <div className="hero-dots">
        {SLIDES.map((_, k) => <button key={k} className={k === i ? "on" : ""} onClick={() => setI(k)} aria-label={`Slide ${k + 1}`} />)}
      </div>
    </section>
  );
}

/** Illustrated field at sunrise with a sensor node (no external images). */
function FieldArt() {
  const rows = Array.from({ length: 7 }, (_, r) => r);
  return (
    <svg className="hero-art" viewBox="0 0 400 260" preserveAspectRatio="xMidYMid slice" aria-hidden>
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#8fb7a0" /><stop offset=".55" stopColor="#f3d9a4" /><stop offset="1" stopColor="#e9c47a" />
        </linearGradient>
        <radialGradient id="sun" cx=".5" cy=".5" r=".5">
          <stop offset="0" stopColor="#fff8dc" /><stop offset=".35" stopColor="#ffe9a8" stopOpacity=".9" /><stop offset="1" stopColor="#ffd27a" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="soil" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#5d7f3a" /><stop offset=".35" stopColor="#4a3b2a" /><stop offset="1" stopColor="#2e2319" />
        </linearGradient>
        <linearGradient id="shade" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#0d2a1a" stopOpacity=".92" /><stop offset=".55" stopColor="#0d2a1a" stopOpacity=".55" /><stop offset="1" stopColor="#0d2a1a" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="pole" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#c9d1cd" /><stop offset="1" stopColor="#8c9792" /></linearGradient>
      </defs>
      <rect width="400" height="260" fill="url(#sky)" />
      <circle cx="250" cy="118" r="70" fill="url(#sun)" />
      <path d="M0 118 Q60 104 120 112 T240 110 T400 106 V140 H0Z" fill="#6f9a52" opacity=".8" />
      <path d="M0 128 H400 V260 H0Z" fill="url(#soil)" />
      {rows.map((r) => {
        const y = 136 + r * r * 2.8 + r * 6;
        const s = 0.35 + r * 0.17;
        return (
          <g key={r}>
            {Array.from({ length: 14 }, (_, c) => {
              const x = (c - 7) * (24 + r * 9) + 230 + (r % 2) * 10;
              return (
                <g key={c} transform={`translate(${x} ${y}) scale(${s})`}>
                  <path d="M0 0 C-14 -6 -20 -22 -12 -30 C-4 -20 -2 -10 0 0Z" fill="#5fae3e" />
                  <path d="M0 0 C14 -8 22 -24 12 -32 C4 -22 2 -10 0 0Z" fill="#79c24c" />
                  <path d="M0 0 C-3 -14 2 -26 0 -36" stroke="#4d9433" strokeWidth="2.2" fill="none" />
                </g>
              );
            })}
          </g>
        );
      })}
      <g transform="translate(300 62) scale(.92)">
        <path d="M14 -18 A22 22 0 0 1 46 -18" stroke="#7ee0ff" strokeWidth="3" fill="none" opacity=".9" strokeLinecap="round" />
        <path d="M20 -10 A14 14 0 0 1 40 -10" stroke="#7ee0ff" strokeWidth="3" fill="none" opacity=".9" strokeLinecap="round" />
        <circle cx="30" cy="-2" r="3" fill="#7ee0ff" />
        <rect x="40" y="2" width="3" height="26" rx="1.5" fill="#3a3f3c" />
        <rect x="6" y="22" width="48" height="44" rx="9" fill="#f4f6f5" stroke="#c9d1cd" />
        <path d="M24 50c-6-3-8-9-6-16 6 1 9 6 9 11M30 51c1-7 5-12 11-13 0 7-4 11-11 13" fill="#2fa65a" />
        <rect x="24" y="66" width="12" height="60" fill="url(#pole)" />
      </g>
      <rect width="400" height="260" fill="url(#shade)" />
    </svg>
  );
}

function Wave({ values, color }: { values: number[]; color: string }) {
  if (values.length < 3) {
    return (
      <svg className="wave" viewBox="0 0 200 50" preserveAspectRatio="none" aria-hidden>
        <path d="M0 30 C25 18 50 42 75 30 S125 18 150 30 S190 42 200 26 V50 H0Z" fill={color} opacity=".12" />
        <path d="M0 30 C25 18 50 42 75 30 S125 18 150 30 S190 42 200 26" stroke={color} strokeWidth="2.2" fill="none" opacity=".55" />
      </svg>
    );
  }
  // smooth trend: average the last readings into ~10 points so the line reads like a gentle curve
  const raw = values.slice(-60);
  const step = Math.max(1, Math.floor(raw.length / 10));
  const v: number[] = [];
  for (let i = 0; i < raw.length; i += step) {
    const chunk = raw.slice(i, i + step);
    v.push(chunk.reduce((a, b) => a + b, 0) / chunk.length);
  }
  const lo = Math.min(...v), hi = Math.max(...v), span = Math.max(hi - lo, Math.abs(hi) * 0.04, 1e-6);
  const pts = v.map((y, i) => [(i / (v.length - 1)) * 200, 40 - ((y - lo) / span) * 26]);
  const d = pts.reduce((acc, [x, y], i) => {
    if (i === 0) return `M${x} ${y}`;
    const [px, py] = pts[i - 1];
    const cx = (px + x) / 2;
    return `${acc} C${cx} ${py} ${cx} ${y} ${x} ${y}`;
  }, "");
  return (
    <svg className="wave" viewBox="0 0 200 50" preserveAspectRatio="none" aria-hidden>
      <path d={`${d} V50 H0Z`} fill={color} opacity=".13" />
      <path d={d} stroke={color} strokeWidth="2.4" fill="none" strokeLinecap="round" />
    </svg>
  );
}

const TONE_COLOR: Record<string, string> = { green: "#2fae5c", orange: "#f08a24", brown: "#9a6b3f", blue: "#2f8fd1" };

function MetricCard({ icon, tone, title, m, unit, type, digits = 0, hint }: {
  icon: string; tone: string; title: string; m: Metric | null | undefined; unit: string; type: string; digits?: number; hint?: string;
}) {
  const series = useSeries(m?.device_id, type);
  return (
    <Link to="/sensors" className={`metric-card tone-${tone}`}>
      <div className="mc-top">
        <span className="mc-icon"><Icon name={icon} size={24} /></span>
        <div style={{ minWidth: 0 }}>
          <div className="mc-title">{title}</div>
          <div className="mc-value">{m ? num(m.value, digits) : "—"}<small>{m ? unit : ""}</small></div>
        </div>
      </div>
      <Wave values={series} color={TONE_COLOR[tone]} />
      <div className="mc-foot">
        {m?.status ? (
          <span className={`status-pill s-${m.tone}`}><Icon name={m.tone === "ok" ? "check" : "info"} size={13} stroke={2.6} />{m.status}</span>
        ) : <span className="status-pill s-neutral">Nessun sensore</span>}
        {hint && <span className="mc-hint">{hint}</span>}
      </div>
    </Link>
  );
}

function useSeries(deviceId: string | undefined, type: string): number[] {
  const dev = useQuery({
    queryKey: ["device", deviceId], enabled: !!deviceId,
    queryFn: () => api.get<{ sensors: { id: string; type: string }[] }>(`/api/v1/devices/${deviceId}`),
    staleTime: 600000,
  });
  const sensorId = dev.data?.sensors.find((s) => s.type === type)?.id;
  const h = useHistory(sensorId, 60);
  return (h.data ?? []).slice().reverse().map((r) => r.value);
}

function WeatherCard({ w }: { w: Home["weather"] | undefined }) {
  const icon = w?.icon ?? "sun";
  return (
    <Link to="/advisor" className="metric-card weather-card">
      <div className="mc-top">
        <span className={`mc-icon wx-${icon}`}><Icon name={icon} size={30} /></span>
        <div style={{ minWidth: 0 }}>
          <div className="mc-title">Meteo oggi</div>
          <div className="mc-value">{w ? num(w.temperature, 0) : "—"}<small>{w ? "°C" : ""}</small></div>
          <div className="wx-label">{w?.label ?? "Previsione non disponibile"}</div>
        </div>
        <Icon name="chevron" size={20} className="wx-chev" />
      </div>
      {w && (
        <div className="wx-row">
          <span><Icon name="thermo" size={13} />{num(w.t_min, 0)}° / {num(w.t_max, 0)}°</span>
          <span><Icon name="drop" size={13} />{w.rain_prob != null ? `${w.rain_prob}%` : `${num(w.rain_mm, 1)} mm`}</span>
          <span><Icon name="wind" size={13} />{num(w.wind_kmh, 0)} km/h</span>
        </div>
      )}
    </Link>
  );
}

function TipCard({ tip }: { tip: Home["tip"] }) {
  return (
    <section className="tip-card">
      <svg className="tip-art" viewBox="0 0 120 120" aria-hidden>
        <path d="M58 112C30 100 18 74 26 30c26 4 42 22 40 52-.6 12-3 22-8 30z" fill="#47b863" />
        <path d="M58 112c-6-18-10-40-2-66" stroke="#2c8c46" strokeWidth="3" fill="none" />
        <path d="M64 100c4-30 22-52 48-58-2 26-18 48-48 58z" fill="#6ccf6d" />
        <path d="M64 100c10-20 22-34 40-50" stroke="#3aa65a" strokeWidth="3" fill="none" />
      </svg>
      <div className="tip-body">
        <div className="tip-label"><Icon name="spark" size={15} stroke={2.4} />Consiglio AI</div>
        <div className="tip-title">{tip.title}</div>
        <div className="tip-text">{tip.text}</div>
        <Link to={tip.to} className="tip-cta">Scopri di più <Icon name="arrow-right" size={15} /></Link>
      </div>
    </section>
  );
}

const ACTIONS = [
  { to: "/vision", icon: "camera", label: "Foto pianta" },
  { to: "/acoustic", icon: "mic", label: "Suoni" },
  { to: "/remedies", icon: "leaf", label: "Rimedi" },
  { to: "/advisor?tab=rotazione", icon: "refresh", label: "Rotazione" },
];

function QuickActions() {
  return (
    <div className="quick-actions">
      {ACTIONS.map((a) => (
        <Link key={a.to} to={a.to} className="qa">
          <span className="qa-icon"><Icon name={a.icon} size={22} /></span>
          <span>{a.label}</span>
        </Link>
      ))}
    </div>
  );
}

const SEV_ICON: Record<string, [string, string]> = {
  high: ["alert", "bad"], medium: ["alert", "warn"], low: ["info", "info"], info: ["info", "info"],
};

function Notifications({ h }: { h: Home | undefined }) {
  return (
    <section>
      <div className="section-title"><Icon name="bell" size={20} />Notifiche
        {!!h?.alerts_open && <span className="count">{h.alerts_open}</span>}
        <Link to="/alerts" className="see-all">Vedi tutte</Link>
      </div>
      <div className="notif-list">
        {(h?.alerts ?? []).slice(0, 3).map((a) => {
          const [icon, tone] = SEV_ICON[a.severity] ?? SEV_ICON.info;
          return (
            <Link key={a.id} to="/alerts" className="notif">
              <span className={`notif-icon n-${tone}`}><Icon name={icon} size={22} stroke={2.2} /></span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div className="notif-title">{a.message}</div>
                <div className="notif-time">{ago(a.ts)}</div>
              </div>
              <Icon name="chevron" size={18} className="muted" />
            </Link>
          );
        })}
        {h && !h.alerts.length && <div className="notif empty"><Icon name="check" size={18} />Nessun avviso: tutto tranquillo.</div>}
      </div>
    </section>
  );
}
