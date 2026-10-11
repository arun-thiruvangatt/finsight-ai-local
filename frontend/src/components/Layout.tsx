import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { useApi } from "../hooks";

const links = [
  ["/dashboard", "Dashboard"], ["/accounts", "Accounts"], ["/transactions", "Transactions"],
  ["/transactions/import", "Import CSV"], ["/budgets", "Budgets"], ["/goals", "Goals"],
  ["/analytics", "Analytics"], ["/insights", "Insights"], ["/assistant", "Assistant"], ["/settings", "Settings"],
];

export default function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const { data: notes } = useApi<any[]>("/notifications");
  return (
    <div className="shell">
      <button className="burger" onClick={() => setOpen(!open)} aria-label="Menu">☰</button>
      <aside className={open ? "side open" : "side"}>
        <div className="brand">FinSight <span>AI</span></div>
        <nav>
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/transactions"} onClick={() => setOpen(false)}>
              {label}{label === "Insights" && notes?.length ? <b className="badge">{notes.length}</b> : null}
            </NavLink>
          ))}
        </nav>
        <div className="user">
          <div>{user.full_name}</div>
          <small className="muted">{user.email}</small>
          <button className="ghost" onClick={async () => { await logout(); nav("/login"); }}>Sign out</button>
        </div>
      </aside>
      <main><Outlet /></main>
    </div>
  );
}
