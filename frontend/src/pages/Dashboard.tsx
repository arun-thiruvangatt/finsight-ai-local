import { Bar as RBar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { inr, thisMonth } from "../api";
import { Bar, Card, Err, PALETTE, Stat } from "../components/ui";
import { useApi } from "../hooks";

export default function Dashboard() {
  const m = thisMonth();
  const bal = useApi<any>("/analytics/balance");
  const sum = useApi<any>(`/analytics/monthly?month=${m}`);
  const cash = useApi<any[]>("/analytics/cashflow?months=6");
  const cats = useApi<any[]>(`/analytics/categories?month=${m}`);
  const trend = useApi<any[]>("/analytics/trends?months=6");
  const budgets = useApi<any[]>("/budgets/status");
  const recent = useApi<any>("/transactions?page_size=6");
  const insights = useApi<any[]>("/insights?limit=4");

  const used = budgets.data?.length
    ? (budgets.data.reduce((a, b) => a + b.spent, 0) / budgets.data.reduce((a, b) => a + b.budget, 0)) * 100 : 0;

  return (
    <div className="page">
      <h1>Dashboard <small className="muted">{m}</small></h1>
      <Err msg={sum.error || bal.error} />
      <div className="grid stats">
        <Stat label="Total balance" value={inr(bal.data?.total_balance)} />
        <Stat label="Income" value={inr(sum.data?.income)} tone="good" />
        <Stat label="Expenses" value={inr(sum.data?.expenses)} tone="bad" />
        <Stat label="Savings" value={inr(sum.data?.savings)} />
        <Stat label="Savings rate" value={`${sum.data?.savings_rate ?? 0}%`} />
        <Stat label="Budget usage" value={`${used.toFixed(0)}%`} />
      </div>
      <div className="grid two">
        <Card title="Income vs expenses">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={cash.data || []}>
              <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="month" /><YAxis /><Tooltip formatter={(v: any) => inr(v)} /><Legend />
              <RBar dataKey="income" fill="#18a999" radius={[4, 4, 0, 0]} /><RBar dataKey="expenses" fill="#ef4444" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Spending by category">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={cats.data || []} dataKey="amount" nameKey="category" innerRadius={55} outerRadius={95}>
                {(cats.data || []).map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
              </Pie>
              <Tooltip formatter={(v: any) => inr(v)} /><Legend />
            </PieChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Monthly trend">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={trend.data || []}>
              <CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="month" /><YAxis /><Tooltip formatter={(v: any) => inr(v)} />
              <Line dataKey="expenses" stroke="#4f6ef7" strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Budgets">
          {(budgets.data || []).map((b) => (
            <div key={b.budget_id} className="row-gap">
              <div className="between"><span>{b.name}</span><small>{inr(b.spent)} / {inr(b.budget)}</small></div>
              <Bar pct={b.usage_percentage} warn={b.warnings.length > 0} />
            </div>
          ))}
          {!budgets.data?.length && <p className="muted">No budgets yet.</p>}
        </Card>
        <Card title="Recent transactions">
          <table><tbody>
            {(recent.data?.items || []).map((t: any) => (
              <tr key={t.id}><td>{t.transaction_date}</td><td>{t.merchant || t.description}</td>
                <td className={t.transaction_type === "INCOME" ? "good right" : "right"}>{inr(t.amount)}</td></tr>
            ))}
          </tbody></table>
        </Card>
        <Card title="AI insights">
          {(insights.data || []).map((i) => (
            <div key={i.id} className={`insight ${i.severity.toLowerCase()}`}><strong>{i.title}</strong><p>{i.description}</p></div>
          ))}
          {!insights.data?.length && <p className="muted">No insights yet. Open Insights and press “Refresh analysis”.</p>}
        </Card>
      </div>
    </div>
  );
}
