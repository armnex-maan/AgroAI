import { useEffect, useId, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Icon } from "./Icon";
import { NAV } from "./Sidebar";

/** AgroAI mark: two leaves with circuit lines. */
export function Logo({ size = 44 }: { size?: number }) {
  // unique gradient ids: two logos on the page (one inside a hidden sidebar) must not share them
  const uid = useId().replace(/:/g, "");
  const g1 = `lg1${uid}`, g2 = `lg2${uid}`;
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
      <defs>
        <linearGradient id={g1} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#4cc96f" /><stop offset="1" stopColor="#178a44" />
        </linearGradient>
        <linearGradient id={g2} x1="1" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#7fd85a" /><stop offset="1" stopColor="#26a650" />
        </linearGradient>
      </defs>
      <path d="M30 56C14 50 6 36 10 12c14 2 24 10 24 26 0 7-1.5 13-4 18z" fill={`url(#${g1})`} />
      <path d="M30 56c-4-10-6-22 0-36" stroke="#fff" strokeWidth="2.4" fill="none" strokeLinecap="round" opacity=".85" />
      <path d="M34 50c2-16 10-28 24-32-1 14-8 26-24 32z" fill={`url(#${g2})`} />
      <g stroke="#178a44" strokeWidth="2.2" fill="none" strokeLinecap="round">
        <path d="M44 40h8l4-4" /><path d="M40 46h12" /><path d="M46 34l4-6h6" />
      </g>
      <g fill="#fff" stroke="#178a44" strokeWidth="2">
        <circle cx="57" cy="35" r="2.6" /><circle cx="54" cy="46" r="2.6" /><circle cx="58" cy="28" r="2.6" />
      </g>
    </svg>
  );
}

export function Brand() {
  return (
    <Link to="/" className="brand-m">
      <Logo />
      <div>
        <div className="brand-m-name">Agro<span>AI</span></div>
        <div className="brand-m-sub">Coltivazioni più intelligenti</div>
      </div>
    </Link>
  );
}

function useOpenAlerts() {
  return useQuery({
    queryKey: ["alerts-open"],
    queryFn: () => api.get<{ acknowledged: boolean }[]>("/api/v1/alerts"),
    select: (a) => a.filter((x) => !x.acknowledged).length,
    refetchInterval: 30000,
  });
}

/** Top bar on phones: brand on Home, back arrow + page title elsewhere. */
export function MobileHeader() {
  const loc = useLocation();
  const nav = useNavigate();
  const alerts = useOpenAlerts();
  const page = NAV.find((n) => "to" in n && n.to === loc.pathname) as { label: string } | undefined;
  const home = loc.pathname === "/";
  return (
    <header className="m-header">
      {home ? <Brand /> : (
        <div className="m-title">
          <button className="round-btn" onClick={() => nav(-1)} aria-label="Indietro"><Icon name="arrow-left" size={20} /></button>
          <span>{page?.label ?? "AgroAI"}</span>
        </div>
      )}
      <div className="m-actions">
        <Link to="/alerts" className="round-btn" aria-label="Avvisi">
          <Icon name="bell" size={21} />
          {!!alerts.data && <span className="badge-dot" />}
        </Link>
        <Link to="/settings" className="round-btn avatar" aria-label="Profilo e impostazioni"><Icon name="user" size={21} /></Link>
      </div>
    </header>
  );
}

const TABS = [
  { to: "/", label: "Home", icon: "home" },
  { to: "/sensors", label: "Analisi", icon: "chart" },
  { to: "/advisor", label: "Consigli", icon: "bulb" },
  { to: "/map", label: "Mappa", icon: "pin" },
];

export function BottomNav() {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);
  const inTabs = TABS.some((t) => t.to === loc.pathname);
  return (
    <>
      <nav className="bottom-nav" aria-label="Navigazione principale">
        {TABS.map((t) => (
          <NavLink key={t.to} to={t.to} end={t.to === "/"} className="tab">
            <Icon name={t.icon} size={24} stroke={2} />
            <span>{t.label}</span>
          </NavLink>
        ))}
        <button className={`tab ${open || !inTabs ? "active" : ""}`} onClick={() => setOpen(true)}>
          <Icon name="more" size={26} stroke={3.2} />
          <span>Altro</span>
        </button>
      </nav>
      {open && (
        <div className="sheet-backdrop" onClick={() => setOpen(false)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Altre sezioni">
            <div className="sheet-handle" />
            {NAV.map((n, i) =>
              "section" in n ? <div key={i} className="sheet-section">{n.section}</div> : (
                <NavLink key={n.to} to={n.to} end={n.to === "/"} className="sheet-item">
                  <span className="sheet-icon"><Icon name={n.icon} size={19} /></span>
                  {n.label}
                  <Icon name="chevron" size={16} className="sheet-chev" />
                </NavLink>
              ),
            )}
          </div>
        </div>
      )}
    </>
  );
}
