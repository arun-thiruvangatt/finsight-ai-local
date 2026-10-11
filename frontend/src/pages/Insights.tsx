import { useState } from "react";
import { api, inr } from "../api";
import { Card, Err } from "../components/ui";
import { useApi } from "../hooks";

export default function Insights() {
  const ins = useApi<any[]>("/insights");
  const rec = useApi<any[]>("/insights/recurring");
  const an = useApi<any[]>("/insights/anomalies");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const refresh = async () => {
    setBusy(true);
    try {
      await api("/insights/refresh", { method: "POST" });
      setTimeout(() => { ins.reload(); rec.reload(); an.reload(); setBusy(false); }, 2500);
    } catch (e: any) { setError(e.message); setBusy(false); }
  };
  return (
    <div className="page">
      <div className="between"><h1>Insights</h1><button onClick={refresh} disabled={busy}>{busy ? "Analysing…" : "Refresh analysis"}</button></div>
      <Err msg={error} />
      <p className="muted">Insights are generated from your recorded data by deterministic analysis. Projections are estimates.</p>
      <div className="grid two">
        <Card title="Generated insights">
          {(ins.data || []).map((i) => (
            <div key={i.id} className={`insight ${i.severity.toLowerCase()}`}>
              <strong>{i.title}</strong> <small className="muted">{i.insight_type.replace("_", " ").toLowerCase()}</small>
              <p>{i.description}</p>
            </div>
          ))}
          {!ins.data?.length && <p className="muted">Nothing yet — add data, then refresh the analysis.</p>}
        </Card>
        <div>
          <Card title="Recurring expenses">
            <table><thead><tr><th>Merchant</th><th>Frequency</th><th className="right">Amount</th><th>Next</th></tr></thead><tbody>
              {(rec.data || []).map((r) => <tr key={r.merchant} className={r.is_active === false ? "muted" : ""}><td>{r.merchant}</td><td>{r.frequency}</td><td className="right">{inr(r.average_amount)}</td><td>{r.next_expected_date}</td></tr>)}
            </tbody></table>
          </Card>
          <Card title="Unusual transactions">
            {(an.data || []).map((a) => <div key={a.transaction_id} className="insight warning"><strong>{a.merchant || "Unknown"} · {inr(a.amount)}</strong> <small>{a.date}</small><p>{a.reason}</p></div>)}
            {!an.data?.length && <p className="muted">None flagged.</p>}
          </Card>
        </div>
      </div>
    </div>
  );
}
