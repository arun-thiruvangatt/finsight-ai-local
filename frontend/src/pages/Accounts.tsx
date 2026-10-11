import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { api, inr } from "../api";
import { Card, Err } from "../components/ui";
import { useApi } from "../hooks";

const TYPES = ["BANK", "CREDIT_CARD", "CASH", "WALLET", "INVESTMENT", "LOAN", "OTHER"];

export default function Accounts() {
  const { data, reload } = useApi<any[]>("/accounts");
  const [f, setF] = useState({ name: "", account_type: "BANK", institution: "", current_balance: "0" });
  const [error, setError] = useState<string | null>(null);
  const add = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api("/accounts", { method: "POST", body: { ...f, institution: f.institution || null } });
      setF({ ...f, name: "", institution: "", current_balance: "0" });
      setError(null); reload();
    } catch (err: any) { setError(err.message); }
  };
  return (
    <div className="page">
      <h1>Accounts</h1>
      <div className="grid two">
        <Card title="Your accounts">
          <table><thead><tr><th>Name</th><th>Type</th><th className="right">Balance</th></tr></thead><tbody>
            {(data || []).map((a) => (
              <tr key={a.id}><td><Link to={`/accounts/${a.id}`}>{a.name}</Link><br /><small className="muted">{a.institution}</small></td>
                <td>{a.account_type}</td><td className="right">{inr(a.current_balance)}</td></tr>
            ))}
          </tbody></table>
        </Card>
        <Card title="Add account">
          <form onSubmit={add} className="form">
            <input placeholder="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required />
            <select value={f.account_type} onChange={(e) => setF({ ...f, account_type: e.target.value })}>{TYPES.map((t) => <option key={t}>{t}</option>)}</select>
            <input placeholder="Institution" value={f.institution} onChange={(e) => setF({ ...f, institution: e.target.value })} />
            <input type="number" step="0.01" placeholder="Opening balance" value={f.current_balance} onChange={(e) => setF({ ...f, current_balance: e.target.value })} />
            <Err msg={error} /><button>Add</button>
          </form>
        </Card>
      </div>
    </div>
  );
}
