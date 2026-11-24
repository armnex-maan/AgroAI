import { useLocation } from "react-router-dom";
import { useHealth, useDevices } from "../api/hooks";
import { NAV } from "./Sidebar";
import { Icon } from "./Icon";

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const loc = useLocation();
  const health = useHealth();
  const devices = useDevices();
  const page = NAV.find((n) => "to" in n && n.to === loc.pathname) as { label: string } | undefined;
  const real = (devices.data ?? []).filter((d) => d.source === "device");
  const realOnline = real.filter((d) => d.status === "online").length;
  const demo = (devices.data ?? []).some((d) => d.source === "simulation");

  return (
    <header className="topbar">
      <div className="row">
        <button className="btn ghost sm mobile-toggle" onClick={onMenu} aria-label="Apri il menu">
          <Icon name="menu" />
        </button>
        <div>
          <div className="topbar-title">{page?.label ?? "AGROAI"}</div>
          <div className="topbar-sub">{new Date().toLocaleDateString("it-IT", { weekday: "long", day: "numeric", month: "long" })}</div>
        </div>
      </div>
      <div className="topbar-right">
        <span className="pill" title="Collegamento con il programma AGROAI">
          <span className={`dot ${health.isError ? "bad" : health.data ? "ok" : ""}`} />
          {health.isError ? "Non collegato" : health.data ? "Sistema attivo" : "Avvio…"}
        </span>
        {demo && <span className="pill" title="Sono presenti dati di prova del simulatore"><Icon name="flask" size={13} />Demo attiva</span>}
        <span className="pill" title="Sensori ESP32 reali collegati">
          <span className={`dot ${realOnline ? "ok" : real.length ? "warn" : ""}`} />
          Sensori {realOnline}/{real.length}
        </span>
        <span className="pill" title="Intelligenza artificiale per i consigli">
          <Icon name="brain" size={13} />{health.data?.ai_provider && health.data.ai_provider !== "none" ? "AI attiva" : "AI spenta"}
        </span>
      </div>
    </header>
  );
}
