import { useState } from "react";
import { Route, Routes } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { BottomNav, MobileHeader } from "./components/AppShell";
import Overview from "./pages/Overview";
import Sensors from "./pages/Sensors";
import SimulationLab from "./pages/SimulationLab";
import Alerts from "./pages/Alerts";
import Devices from "./pages/Devices";
import Predictions from "./pages/Predictions";
import Farms from "./pages/Farms";
import FieldMap from "./pages/FieldMap";
import Acoustic from "./pages/Acoustic";
import Vision from "./pages/Vision";
import Settings from "./pages/Settings";
import Advisor from "./pages/Advisor";
import Remedies from "./pages/Remedies";

export default function App() {
  const [navOpen, setNavOpen] = useState(false);
  return (
    <div className={`app ${navOpen ? "nav-open" : ""}`}>
      <Sidebar onNavigate={() => setNavOpen(false)} />
      <div className="content">
        <Topbar onMenu={() => setNavOpen((v) => !v)} />
        <MobileHeader />
        <main className="main">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/sensors" element={<Sensors />} />
            <Route path="/simulation" element={<SimulationLab />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/devices" element={<Devices />} />
            <Route path="/predictions" element={<Predictions />} />
            <Route path="/farms" element={<Farms />} />
            <Route path="/map" element={<FieldMap />} />
            <Route path="/acoustic" element={<Acoustic />} />
            <Route path="/advisor" element={<Advisor />} />
            <Route path="/vision" element={<Vision />} />
            <Route path="/remedies" element={<Remedies />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
      <BottomNav />
    </div>
  );
}
