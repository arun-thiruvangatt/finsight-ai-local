import { FormEvent, useRef, useState } from "react";
import { api } from "../api";
import { Bar, Card, Err } from "../components/ui";
import { useApi } from "../hooks";

const DONE = ["COMPLETED", "FAILED", "PARTIAL"];

export default function ImportPage() {
  const accounts = useApi<any[]>("/accounts");
  const jobs = useApi<any[]>("/imports");
  const [account, setAccount] = useState("");
  const [mapping, setMapping] = useState("");
  const [job, setJob] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);

  const poll = async (id: number) => {
    for (let i = 0; i < 300; i++) {
      const j = await api(`/imports/${id}`);
      setJob(j);
      if (DONE.includes(j.status)) { jobs.reload(); return; }
      await new Promise((r) => setTimeout(r, 1500));
    }
  };
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const f = file.current?.files?.[0];
    if (!f) return;
    const form = new FormData();
    form.append("file", f);
    form.append("account_id", account || String(accounts.data?.[0]?.id));
    if (mapping.trim()) form.append("column_mapping", mapping.trim());
    try { setError(null); const j = await api("/imports/csv", { method: "POST", form }); setJob(j); poll(j.id); }
    catch (err: any) { setError(err.message); }
  };
  const pct = job?.total_rows ? (job.processed_rows / job.total_rows) * 100 : DONE.includes(job?.status) ? 100 : 5;

  return (
    <div className="page">
      <h1>Import transactions</h1>
      <div className="grid two">
        <Card title="Upload CSV">
          <form className="form" onSubmit={submit}>
            <select value={account} onChange={(e) => setAccount(e.target.value)}>{(accounts.data || []).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select>
            <input type="file" accept=".csv,.txt" ref={file} required />
            <textarea rows={3} placeholder={'Optional column mapping JSON, e.g. {"date":"Txn Date","description":"Narration","amount":"Amt"}'} value={mapping} onChange={(e) => setMapping(e.target.value)} />
            <small className="muted">Columns are auto-detected (Date, Description, Amount, Type, Reference, or Debit/Credit). Duplicates are skipped automatically.</small>
            <Err msg={error} /><button>Upload</button>
          </form>
        </Card>
        <Card title="Progress">
          {job ? (<>
            <p><strong>{job.filename}</strong> — {job.status}</p>
            <Bar pct={pct} />
            <p className="muted">{job.processed_rows}/{job.total_rows} rows · {job.successful_rows} imported · {job.duplicate_rows} duplicates · {job.failed_rows} failed</p>
            {job.error_message && <pre className="error">{job.error_message}</pre>}
          </>) : <p className="muted">No import running.</p>}
        </Card>
      </div>
      <Card title="Recent imports">
        <table><tbody>{(jobs.data || []).map((j) => <tr key={j.id}><td>{j.filename}</td><td>{j.status}</td><td>{j.successful_rows} imported</td><td>{j.duplicate_rows} dup</td><td>{j.failed_rows} failed</td></tr>)}</tbody></table>
      </Card>
    </div>
  );
}
