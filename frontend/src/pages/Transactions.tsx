import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { api, inr } from "../api";
import { Card, Err } from "../components/ui";
import { useApi } from "../hooks";

export default function Transactions() {
  const [q, setQ] = useState({ search: "", transaction_type: "", from_date: "", to_date: "", is_anomaly: false });
  const [page, setPage] = useState(1);
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  Object.entries(q).forEach(([k, v]) => v && params.set(k, String(v)));
  const tx = useApi<any>(`/transactions?${params}`);
  const accounts = useApi<any[]>("/accounts");
  const cats = useApi<any[]>("/categories");
  const catName = (id: number) => cats.data?.find((c) => c.id === id)?.name ?? "—";

  const [f, setF] = useState<any>({ account_id: "", amount: "", transaction_type: "EXPENSE", merchant: "", transaction_date: new Date().toISOString().slice(0, 10), category_id: "" });
  const [error, setError] = useState<string | null>(null);
  const add = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api("/transactions", { method: "POST", body: { ...f, account_id: Number(f.account_id || accounts.data?.[0]?.id), category_id: f.category_id ? Number(f.category_id) : null, merchant: f.merchant || null } });
      setF({ ...f, amount: "", merchant: "" }); setError(null); tx.reload();
    } catch (err: any) { setError(err.message); }
  };
  const del = async (id: number) => { if (confirm("Delete this transaction?")) { await api(`/transactions/${id}`, { method: "DELETE" }); tx.reload(); } };
  const pages = Math.max(1, Math.ceil((tx.data?.total || 0) / 20));

  return (
    <div className="page">
      <div className="between"><h1>Transactions</h1><Link to="/transactions/import" className="btn">Import CSV</Link></div>
      <Card title="Add transaction">
        <form onSubmit={add} className="inline-form">
          <select value={f.account_id} onChange={(e) => setF({ ...f, account_id: e.target.value })}>{(accounts.data || []).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select>
          <select value={f.transaction_type} onChange={(e) => setF({ ...f, transaction_type: e.target.value })}><option>EXPENSE</option><option>INCOME</option><option>TRANSFER</option></select>
          <input type="number" step="0.01" min="0.01" placeholder="Amount" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} required />
          <input placeholder="Merchant" value={f.merchant} onChange={(e) => setF({ ...f, merchant: e.target.value })} />
          <select value={f.category_id} onChange={(e) => setF({ ...f, category_id: e.target.value })}><option value="">Auto-categorise</option>{(cats.data || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
          <input type="date" value={f.transaction_date} onChange={(e) => setF({ ...f, transaction_date: e.target.value })} required />
          <button>Add</button>
        </form>
        <Err msg={error} />
      </Card>
      <Card title="History" right={
        <div className="inline-form">
          <input placeholder="Search…" value={q.search} onChange={(e) => { setPage(1); setQ({ ...q, search: e.target.value }); }} />
          <select value={q.transaction_type} onChange={(e) => { setPage(1); setQ({ ...q, transaction_type: e.target.value }); }}><option value="">All types</option><option>EXPENSE</option><option>INCOME</option><option>TRANSFER</option></select>
          <input type="date" value={q.from_date} onChange={(e) => setQ({ ...q, from_date: e.target.value })} />
          <input type="date" value={q.to_date} onChange={(e) => setQ({ ...q, to_date: e.target.value })} />
          <label className="check"><input type="checkbox" checked={q.is_anomaly} onChange={(e) => setQ({ ...q, is_anomaly: e.target.checked })} />Unusual only</label>
        </div>}>
        <div className="scroll"><table>
          <thead><tr><th>Date</th><th>Merchant</th><th>Category</th><th>Type</th><th className="right">Amount</th><th /></tr></thead>
          <tbody>
            {(tx.data?.items || []).map((t: any) => (
              <tr key={t.id} className={t.is_anomaly ? "anomaly" : ""}>
                <td>{t.transaction_date}</td>
                <td>{t.merchant || t.description}{t.is_anomaly && <span title={t.anomaly_reason} className="tag warn">unusual</span>}{t.is_recurring && <span className="tag">recurring</span>}</td>
                <td>{catName(t.category_id)}{t.ai_category_source === "llm" && <span className="tag">AI</span>}</td>
                <td>{t.transaction_type}</td>
                <td className={t.transaction_type === "INCOME" ? "good right" : "right"}>{inr(t.amount)}</td>
                <td><button className="ghost" onClick={() => del(t.id)}>✕</button></td>
              </tr>
            ))}
          </tbody>
        </table></div>
        <div className="between pager">
          <small className="muted">{tx.data?.total ?? 0} transactions</small>
          <span><button className="ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>‹ Prev</button> {page} / {pages} <button className="ghost" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next ›</button></span>
        </div>
      </Card>
    </div>
  );
}
