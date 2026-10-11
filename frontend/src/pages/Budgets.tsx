import { FormEvent, useState } from "react";
import { api, inr } from "../api";
import { Bar, Card, Err } from "../components/ui";
import { useApi } from "../hooks";

export default function Budgets() {
  const st = useApi<any[]>("/budgets/status");
  const cats = useApi<any[]>("/categories");
  const [f, setF] = useState({ name: "", category_id: "", amount: "", period: "MONTHLY", alert_threshold: "80" });
  const [error, setError] = useState<string | null>(null);
  const add = async (e: FormEvent) => {
    e.preventDefault();
    const today = new Date().toISOString().slice(0, 10);
    try {
      await api("/budgets", { method: "POST", body: { ...f, category_id: f.category_id ? Number(f.category_id) : null, start_date: today, end_date: f.period === "CUSTOM" ? today : null } });
      setF({ ...f, name: "", amount: "" }); setError(null); st.reload();
    } catch (err: any) { setError(err.message); }
  };
  const del = async (id: number) => { await api(`/budgets/${id}`, { method: "DELETE" }); st.reload(); };
  return (
    <div className="page">
      <h1>Budgets</h1>
      <div className="grid two">
        <Card title="Status">
          {(st.data || []).map((b) => (
            <div key={b.budget_id} className="row-gap">
              <div className="between"><strong>{b.name}</strong><button className="ghost" onClick={() => del(b.budget_id)}>✕</button></div>
              <Bar pct={b.usage_percentage} warn={b.warnings.length > 0} />
              <small>{inr(b.spent)} of {inr(b.budget)} ({b.usage_percentage}%) · {inr(b.remaining)} left · projected {inr(b.projected_spending)} <em className="muted">(estimate)</em></small>
              {b.warnings.map((w: string, i: number) => <p key={i} className="warn-text">⚠ {w}</p>)}
            </div>
          ))}
          {!st.data?.length && <p className="muted">No budgets yet.</p>}
        </Card>
        <Card title="New budget">
          <form className="form" onSubmit={add}>
            <input placeholder="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required />
            <select value={f.category_id} onChange={(e) => setF({ ...f, category_id: e.target.value })}><option value="">All spending</option>{(cats.data || []).filter((c) => c.category_type === "EXPENSE").map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
            <input type="number" step="0.01" min="1" placeholder="Amount" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} required />
            <select value={f.period} onChange={(e) => setF({ ...f, period: e.target.value })}><option>MONTHLY</option><option>WEEKLY</option></select>
            <input type="number" min="1" max="100" value={f.alert_threshold} onChange={(e) => setF({ ...f, alert_threshold: e.target.value })} title="Alert threshold %" />
            <Err msg={error} /><button>Create</button>
          </form>
        </Card>
      </div>
    </div>
  );
}
