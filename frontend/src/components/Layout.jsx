import { useEffect, useRef } from "react";

const NAV = [
  { id: "overview", label: "Overview", icon: "M4 13h6V4H4zm10 7h6V11h-6zM4 20h6v-4H4zm10-11h6V4h-6z" },
  { id: "transactions", label: "Transactions", icon: "M4 6h16M4 12h16M4 18h10" },
  { id: "receipt", label: "Add receipt", icon: "M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6" },
  { id: "ask", label: "Ask", icon: "M5 5h14v10H9l-4 4z" },
  { id: "forecast", label: "Forecast", icon: "M4 18l5-6 4 3 7-9" },
];

function Icon({ d }) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

export default function Layout({ page, go, user, onSignOut, children }) {
  const mainRef = useRef(null);
  const firstRender = useRef(true);
  // After switching screens, move keyboard and screen-reader focus to the new page's heading.
  // Skipped on first load so the first Tab still lands on "Skip to content".
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    const t = setTimeout(() => {
      const h1 = mainRef.current?.querySelector("h1");
      if (h1) {
        h1.setAttribute("tabindex", "-1");
        h1.focus({ preventScroll: true });
      }
    }, 50);
    return () => clearTimeout(t);
  }, [page]);

  return (
    <div className="shell">
      <a href="#main" className="skip-link" onClick={(e) => { e.preventDefault(); mainRef.current?.querySelector("h1")?.focus(); }}>
        Skip to content
      </a>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          CashPilot
        </div>
        <nav aria-label="Main">
          {NAV.map((n) => (
            <button key={n.id} className={`nav-item ${page === n.id ? "active" : ""}`} onClick={() => go(n.id)} aria-current={page === n.id ? "page" : undefined}>
              <Icon d={n.icon} />
              {n.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="who">{user.name || user.email}</div>
          <button className="link" onClick={onSignOut}>Sign out</button>
        </div>
      </aside>

      <main className="main" id="main" ref={mainRef}>{children}</main>

      <nav className="tabbar" aria-label="Main">
        {NAV.map((n) => (
          <button key={n.id} className={page === n.id ? "active" : ""} onClick={() => go(n.id)} aria-current={page === n.id ? "page" : undefined}>
            <Icon d={n.icon} />
            <span>{n.label === "Add receipt" ? "Receipt" : n.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
