import { NavLink } from "react-router-dom";
import { Icon } from "./Icon";
import { Logo } from "./AppShell";

export const NAV = [
  { section: "Il mio campo" },
  { to: "/", label: "Home", icon: "home" },
  { to: "/sensors", label: "Analisi dei sensori", icon: "chart" },
  { to: "/map", label: "Mappa", icon: "map" },
  { to: "/alerts", label: "Avvisi", icon: "bell" },
  { section: "Assistente" },
  { to: "/vision", label: "Salute delle piante", icon: "camera" },
  { to: "/remedies", label: "Rimedi naturali", icon: "bug" },
  { to: "/acoustic", label: "Suoni e animali", icon: "mic" },
  { to: "/advisor", label: "Consigli di coltivazione", icon: "bulb" },
  { to: "/predictions", label: "Valutazione del campo", icon: "brain" },
  { section: "Gestione" },
  { to: "/farms", label: "Aziende e campi", icon: "farm" },
  { to: "/devices", label: "Dispositivi ESP32", icon: "chip" },
  { to: "/simulation", label: "Modalità demo", icon: "flask" },
  { to: "/settings", label: "Impostazioni", icon: "settings" },
] as const;

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <Logo size={38} />
        <div>
          <div className="brand-m-name" style={{ fontSize: 20 }}>Agro<span>AI</span></div>
          <div className="brand-sub">Coltivazioni più intelligenti</div>
        </div>
      </div>
      <nav>
        {NAV.map((n, i) =>
          "section" in n ? (
            <div key={i} className="nav-section">{n.section}</div>
          ) : (
            <NavLink key={n.to} to={n.to} end={n.to === "/"} onClick={onNavigate}>
              <Icon name={n.icon} size={17} />
              {n.label}
            </NavLink>
          )
        )}
      </nav>
      <div className="sidebar-foot">
        Ogni valore indica da dove arriva:{" "}
        <span className="badge badge-simulation">Demo</span> dato di prova,{" "}
        <span className="badge badge-device">Sensore</span> misurato nel campo.
      </div>
    </aside>
  );
}
