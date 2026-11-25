import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect } from "react";
import Backdrop from "../components/Backdrop";
import { ChartIcon, ChatIcon, LayersIcon } from "../components/icons";

const SUB = [
  { to: "/overview/feedback", label: "Feedback", hint: "How people feel" },
  { to: "/overview/analysis", label: "Analysis", hint: "What to fix first" },
  { to: "/overview/evidence", label: "AI Evidence Log", hint: "Can we trust it?" },
  { to: "/overview/golden", label: "Golden data set", hint: "Engine vs human labels" },
];

/** Sidebar + content frame used by every screen after the home page. */
export default function AppShell() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo({ top: 0 }); }, [pathname]);
  return (
    <div className="shell">
      <Backdrop variant="app" />
      <aside className="side" aria-label="Sections">
        <NavLink to="/" className="side__brand" aria-label="Back to the home screen">
          <strong>Urban Company</strong><span>Discovery Engine</span>
        </NavLink>
        <nav className="side__nav">
          <div className="side__group"><span className="side__icon side__icon--violet"><ChartIcon /></span>Overview</div>
          <div className="side__sub">
            {SUB.map((s) => (
              <NavLink key={s.to} to={s.to} className={({ isActive }) => `side__item ${isActive ? "is-active" : ""}`}>
                <span>{s.label}</span><small>{s.hint}</small>
              </NavLink>
            ))}
          </div>
          <NavLink to="/workflow" className={({ isActive }) => `side__link side__link--amber ${isActive ? "is-active" : ""}`}><span className="side__icon side__icon--amber"><LayersIcon /></span>See the workflow</NavLink>
          <NavLink to="/ask" className={({ isActive }) => `side__link side__link--blue ${isActive ? "is-active" : ""}`}><span className="side__icon side__icon--blue"><ChatIcon /></span>Ask questions</NavLink>
        </nav>
        <NavLink to="/" className="side__home">← Back to home</NavLink>
      </aside>
      <main className="main"><Outlet /></main>
    </div>
  );
}
