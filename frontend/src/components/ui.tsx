import { ReactNode } from "react";

export const Card = ({ title, children, right }: { title?: string; children: ReactNode; right?: ReactNode }) => (
  <section className="card">
    {(title || right) && <header><h3>{title}</h3>{right}</header>}
    {children}
  </section>
);

export const Stat = ({ label, value, tone }: { label: string; value: ReactNode; tone?: "good" | "bad" }) => (
  <div className="card stat"><small className="muted">{label}</small><strong className={tone}>{value}</strong></div>
);

export const Err = ({ msg }: { msg?: string | null }) => (msg ? <p className="error">{msg}</p> : null);

export const Bar = ({ pct, warn }: { pct: number; warn?: boolean }) => (
  <div className="bar"><div className={warn ? "fill warn" : "fill"} style={{ width: `${Math.min(100, pct)}%` }} /></div>
);

export const PALETTE = ["#4f6ef7", "#18a999", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#84cc16", "#ec4899", "#64748b"];
