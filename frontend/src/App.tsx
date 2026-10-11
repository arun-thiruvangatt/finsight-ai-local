import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import AccountDetail from "./pages/AccountDetail";
import Accounts from "./pages/Accounts";
import Analytics from "./pages/Analytics";
import Assistant from "./pages/Assistant";
import Budgets from "./pages/Budgets";
import Dashboard from "./pages/Dashboard";
import Goals from "./pages/Goals";
import ImportPage from "./pages/ImportPage";
import Insights from "./pages/Insights";
import { Login, Register } from "./pages/AuthPages";
import Settings from "./pages/Settings";
import Transactions from "./pages/Transactions";

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <div className="center muted">Loading…</div>;
  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/accounts" element={<Accounts />} />
        <Route path="/accounts/:id" element={<AccountDetail />} />
        <Route path="/transactions" element={<Transactions />} />
        <Route path="/transactions/import" element={<ImportPage />} />
        <Route path="/budgets" element={<Budgets />} />
        <Route path="/goals" element={<Goals />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/assistant" element={<Assistant />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}
