import { FormEvent, useState } from "react";
import { api, inr } from "../api";
import { Bar, Card, Err } from "../components/ui";
import { useApi } from "../hooks";

export default function Goals() {
  const prog = useApi<any[]>("/goals/progress");
  const [f, setF] = useState({ name: "", target_amount: "", current_amount: "0", target_date: "", priority: "MEDIUM" });
  const [error, setError] = useState<string | null>(null);
  const add = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api("/goals", { method: "POST", body: { ...f, target_date: f.target_date || null } });
      setF({ ...f, name: "", target_amount: "" }); setError(null); prog.reload();
    } catch (err: any) { setError(err.message); }
  };
  const contribute = async (g: any) => {
    const v = prompt("Amount to add to this goal (₹)");
    if (!v) return;
    try { await api(`/goals/${g.goal_id}`, { method: "PATCH", body: { current_amount: String(Number(g.current_amount) + Number(v)) } }); prog.reload(); }
    catch (e: any) { alert(e.message); }
  };
  return (
    <div className="page">
      <h1>Goals</h1>
      <div className="grid two">
        <Card title="Progress">
          {(prog.data || []).map((g) => (
            <div key={g.goal_id} className="row-gap">
              <div className="between"><strong>{g.name}</strong><button className="ghost" onClick={() => contribute(g)}>+ Add funds</button></div>
              <Bar pct={g.progress_percentage} />
              <small>{inr(g.current_amount)} of {inr(g.target_amount)} ({g.progress_percentage}%) · {inr(g.remaining_amount)} remaining</small>
              {g.required_monthly_contribution != null && <small>Needed per month for target date: <strong>{inr(g.required_monthly_contribution)}</strong></small>}
              <small>Average monthly savings: {inr(g.avg_monthly_savings)} · cautious allocation estimate: {inr(g.safe_allocation_estimate)}</small>
              {g.projected_completion && <small>Projected completion: {g.projected_completion} {g.on_track === false && <span className="warn-text">(behind target date)</span>}</small>}
              <small className="muted">{g.projection_note}</small>
            </div>
          ))}
          {!prog.data?.length && <p className="muted">No active goals.</p>}
        </Card>
        <Card title="New goal">
          <form className="form" onSubmit={add}>
            <input placeholder="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required />
            <input type="number" step="0.01" min="1" placeholder="Target amount" value={f.target_amount} onChange={(e) => setF({ ...f, target_amount: e.target.value })} required />
            <input type="number" step="0.01" min="0" placeholder="Already saved" value={f.current_amount} onChange={(e) => setF({ ...f, current_amount: e.target.value })} />
            <input type="date" value={f.target_date} onChange={(e) => setF({ ...f, target_date: e.target.value })} />
            <select value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}><option>LOW</option><option>MEDIUM</option><option>HIGH</option></select>
            <Err msg={error} /><button>Create</button>
          </form>
        </Card>
      </div>
    </div>
  );
}
