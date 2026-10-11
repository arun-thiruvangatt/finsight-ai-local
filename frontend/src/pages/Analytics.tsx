import { useState } from "react";
import { Bar as RBar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { inr, thisMonth } from "../api";
import { Card, Err, PALETTE, Stat } from "../components/ui";
import { useApi } from "../hooks";

const prev = (m: string) => { const [y, mo] = m.split("-").map(Number); const d = new Date(y, mo - 2, 1); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; };

export default function Analytics() {
  const [month, setMonth] = useState(thisMonth());
  const sum = useApi<any>(`/analytics/monthly?month=${month}`);
  const cats = useApi<any[]>(`/analytics/categories?month=${month}`);
  const merch = useApi<any[]>(`/analytics/merchants?month=${month}&limit=8`);
  const cmp = useApi<any>(`/analytics/compare?previous=${prev(month)}&current=${month}`);
  const cash = useApi<any[]>("/analytics/cashflow?months=12");
  return (
    <div className="page">
      <div className="between"><h1>Analytics</h1><input type="month" value={month} onChange={(e) => e.target.value && setMonth(e.target.value)} /></div>
      <Err msg={sum.error} />
      <div className="grid stats">
        <Stat label="Income" value={inr(sum.data?.income)} tone="good" />
        <Stat label="Expenses" value={inr(sum.data?.expenses)} tone="bad" />
        <Stat label="Savings" value={inr(sum.data?.savings)} />
        <Stat label="Savings rate" value={`${sum.data?.savings_rate ?? 0}%`} />
      </div>
      <div className="grid two">
        <Card title="Category breakdown">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart><Pie data={cats.data || []} dataKey="amount" nameKey="category" outerRadius={95}>{(cats.data || []).map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}</Pie><Tooltip formatter={(v: any) => inr(v)} /><Legend /></PieChart>
          </ResponsiveContainer>
          <table><tbody>{(cats.data || []).map((c) => <tr key={c.category}><td>{c.category}</td><td className="right">{inr(c.amount)}</td><td className="right muted">{c.percentage}%</td></tr>)}</tbody></table>
        </Card>
        <Card title="Top merchants">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={merch.data || []} layout="vertical" margin={{ left: 40 }}>
              <CartesianGrid strokeDasharray="3 3" /><XAxis type="number" /><YAxis type="category" dataKey="merchant" width={110} /><Tooltip formatter={(v: any) => inr(v)} />
              <RBar dataKey="amount" fill="#4f6ef7" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title={`${prev(month)} → ${month}`}>
          {cmp.data && (<>
            <p>Expenses {inr(cmp.data.previous_month.expenses)} → <strong>{inr(cmp.data.current_month.expenses)}</strong>{" "}
              <span className={cmp.data.difference > 0 ? "bad" : "good"}>({cmp.data.difference > 0 ? "+" : ""}{inr(cmp.data.difference)}{cmp.data.percentage_change != null ? `, ${cmp.data.percentage_change}%` : ""})</span></p>
            <h4>Biggest increases</h4>
            <table><tbody>{cmp.data.top_increases.map((c: any) => <tr key={c.category}><td>{c.category}</td><td className="right bad">+{inr(c.difference)}</td></tr>)}</tbody></table>
            <h4>Biggest decreases</h4>
            <table><tbody>{cmp.data.top_decreases.map((c: any) => <tr key={c.category}><td>{c.category}</td><td className="right good">{inr(c.difference)}</td></tr>)}</tbody></table>
          </>)}
        </Card>
        <Card title="Cash flow (12 months)">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={cash.data || []}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="month" /><YAxis /><Tooltip formatter={(v: any) => inr(v)} /><Legend />
              <RBar dataKey="income" fill="#18a999" /><RBar dataKey="expenses" fill="#ef4444" /><RBar dataKey="net" fill="#4f6ef7" /></BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}
