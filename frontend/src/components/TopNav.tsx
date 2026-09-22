import { useState } from "react";
import { NavLink } from "react-router-dom";

const LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/search", label: "Search" },
  { to: "/deals", label: "Best Deals" },
  { to: "/insights", label: "Insights" },
  { to: "/how-it-works", label: "How It Works" },
];

export default function TopNav() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <header className="top-nav">
        <NavLink to="/" className="top-nav__brand" onClick={() => setOpen(false)}>
          <span className="top-nav__brand-mark">🔍</span>
          BikroyLens
        </NavLink>

        <nav className="top-nav__links">
          {LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) => "top-nav__link" + (isActive ? " top-nav__link--active" : "")}
            >
              {link.label}
            </NavLink>
          ))}
          <span className="top-nav__live">
            <span className="top-nav__live-dot" />
            Live data
          </span>
        </nav>

        <button className="top-nav__mobile-toggle" onClick={() => setOpen((v) => !v)} aria-label="Menu">
          {open ? "✕" : "☰"}
        </button>
      </header>

      {open && (
        <div className="mobile-menu">
          {LINKS.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end} onClick={() => setOpen(false)}>
              {link.label}
            </NavLink>
          ))}
        </div>
      )}
    </>
  );
}
