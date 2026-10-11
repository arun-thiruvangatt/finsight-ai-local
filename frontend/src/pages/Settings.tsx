import { FormEvent, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Card, Err } from "../components/ui";
import { useApi } from "../hooks";

export default function Settings() {
  const { user, setUser } = useAuth();
  const [f, setF] = useState({ full_name: user.full_name, currency: user.currency, timezone: user.timezone });
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const docs = useApi<any[]>("/documents");
  const save = async (e: FormEvent) => {
    e.preventDefault();
    try { setUser(await api("/users/me", { method: "PATCH", body: f })); setMsg("Saved."); setError(null); }
    catch (err: any) { setError(err.message); setMsg(null); }
  };
  const upload = async (e: FormEvent<HTMLInputElement>) => {
    const file = e.currentTarget.files?.[0];
    if (!file) return;
    const form = new FormData(); form.append("file", file);
    try { await api("/documents", { method: "POST", form }); docs.reload(); } catch (err: any) { setError(err.message); }
  };
  const del = async (id: number) => { await api(`/documents/${id}`, { method: "DELETE" }); docs.reload(); };
  return (
    <div className="page">
      <h1>Settings</h1>
      <div className="grid two">
        <Card title="Profile">
          <form className="form" onSubmit={save}>
            <input value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} required />
            <input value={f.currency} maxLength={3} onChange={(e) => setF({ ...f, currency: e.target.value.toUpperCase() })} />
            <input value={f.timezone} onChange={(e) => setF({ ...f, timezone: e.target.value })} />
            <Err msg={error} />{msg && <p className="good">{msg}</p>}<button>Save</button>
          </form>
        </Card>
        <Card title="Documents for the assistant (RAG)">
          <p className="muted">Upload notes, insurance or loan documents (txt, md, pdf). They are private to you.</p>
          <input type="file" accept=".txt,.md,.pdf" onChange={upload} />
          <table><tbody>{(docs.data || []).map((d) => <tr key={d.id}><td>{d.title}</td><td>{d.status}{d.status === "READY" && ` · ${d.chunk_count} chunks`}</td><td><button className="ghost" onClick={() => del(d.id)}>✕</button></td></tr>)}</tbody></table>
        </Card>
      </div>
    </div>
  );
}
