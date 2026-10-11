import { useParams } from "react-router-dom";
import { inr } from "../api";
import { Card, Err } from "../components/ui";
import { useApi } from "../hooks";

export default function AccountDetail() {
  const { id } = useParams();
  const acc = useApi<any>(`/accounts/${id}`);
  const tx = useApi<any>(`/transactions?account_id=${id}&page_size=50`);
  return (
    <div className="page">
      <h1>{acc.data?.name || "Account"}</h1>
      <Err msg={acc.error} />
      {acc.data && <p className="muted">{acc.data.account_type} · {acc.data.institution} · balance <strong>{inr(acc.data.current_balance)}</strong></p>}
      <Card title="Transactions">
        <table><tbody>
          {(tx.data?.items || []).map((t: any) => (
            <tr key={t.id}><td>{t.transaction_date}</td><td>{t.merchant || t.description}</td><td>{t.transaction_type}</td>
              <td className="right">{inr(t.amount)}</td></tr>
          ))}
        </tbody></table>
      </Card>
    </div>
  );
}
