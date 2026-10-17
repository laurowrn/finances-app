import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "@/components/Layout";
import { useAuth } from "@/lib/auth";
import { Categories } from "@/pages/Categories";
import { Import } from "@/pages/Import";
import { Login } from "@/pages/Login";
import { Payments } from "@/pages/Payments";
import { AiReportPage } from "@/pages/AiReport";
import { Report } from "@/pages/Report";
import { Rules } from "@/pages/Rules";
import { SettingsPage } from "@/pages/Settings";
import { Transactions } from "@/pages/Transactions";

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return null;

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Report />} />
        <Route path="ai" element={<AiReportPage />} />
        <Route path="import" element={<Import />} />
        <Route path="transactions" element={<Transactions />} />
        <Route path="rules" element={<Rules />} />
        <Route path="payments" element={<Payments />} />
        <Route path="categories" element={<Categories />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
