import { useEffect } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAppData } from "../context/AppData";
import { IconBook, IconCompare, IconForecast, IconGrid, IconTable, IconWind } from "./Icons";
import { StationSelect } from "./StationSelect";

const LINKS = [
  { to: "/", label: "Overview", end: true, Icon: IconGrid },
  { to: "/data", label: "Air Quality Data", end: false, Icon: IconTable },
  { to: "/models", label: "Model Comparison", end: false, Icon: IconCompare },
  { to: "/forecast", label: "Predictions", end: false, Icon: IconForecast },
  { to: "/methodology", label: "Methodology", end: false, Icon: IconBook },
];

function connectionLabel(status: string, stages: { status: string }[]): { text: string; tone: string } {
  if (status === "loading") return { text: "Checking backend", tone: "neutral" };
  if (status === "not_configured") return { text: "Awaiting backend", tone: "neutral" };
  if (status === "not_connected") return { text: "Not connected", tone: "warn" };
  if (status === "error") return { text: "Backend error", tone: "bad" };
  if (stages.some((stage) => stage.status === "failed")) return { text: "Failure reported", tone: "bad" };
  if (stages.some((stage) => stage.status === "delayed")) return { text: "Delayed", tone: "warn" };
  return { text: "Status received", tone: "neutral" };
}

export function Layout() {
  const { pipeline, refresh } = useAppData();
  const location = useLocation();
  const stages = pipeline.status === "ready" ? pipeline.data.stages : [];
  const connection = connectionLabel(pipeline.status, stages);

  useEffect(() => {
    const main = document.getElementById("main");
    if (main instanceof HTMLElement) main.focus({ preventScroll: true });
  }, [location.pathname]);

  return (
    <div className="shell">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <aside className="rail">
        <div className="rail-brand" aria-hidden="true">
          <IconWind />
        </div>
        <nav aria-label="Primary">
          {LINKS.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end} title={link.label}>
              <link.Icon />
              <span>{link.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="brand-copy">
            <p className="brand-name">AirCast India</p>
            <p className="brand-sub">Air quality intelligence</p>
          </div>
          <StationSelect compact />
          <div className="topbar-actions">
            <p className={`status-chip tone-${connection.tone}`} aria-live="polite">
              <span className="status-mark" aria-hidden="true" />
              {connection.text}
            </p>
            <button type="button" className="secondary" onClick={refresh}>
              Refresh
            </button>
          </div>
        </header>
        <main id="main" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
      <nav className="dock" aria-label="Primary mobile">
        {LINKS.map((link) => (
          <NavLink key={link.to} to={link.to} end={link.end}>
            <link.Icon />
            <span>{link.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
