import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Scale, TrendingUp, Wallet } from "lucide-react";
import { useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PeriodPicker } from "@/components/PeriodPicker";
import { Card, EmptyState, PageHeader, Spinner } from "@/components/ui";
import { api, currentPeriod, formatBRL, type UserReport } from "@/lib/api";

const COLORS = ["#4f46e5", "#06b6d4", "#f59e0b", "#10b981", "#ec4899", "#8b5cf6", "#94a3b8"];

export function Report() {
  const [period, setPeriod] = useState(currentPeriod());
  const { data, isLoading } = useQuery({
    queryKey: ["report", period],
    queryFn: () => api.report(period),
  });

  const topSpender = data
    ? [...data.users].sort((a, b) => b.total_spent - a.total_spent)[0]
    : null;

  return (
    <div>
      <PageHeader
        title="Relatório do mês"
        subtitle="Quem gastou mais e o acerto proporcional ao salário"
        action={<PeriodPicker period={period} onChange={setPeriod} />}
      />

      {isLoading && <Spinner />}
      {data && data.users.length === 0 && (
        <EmptyState>Cadastre os usuários (rode o seed) para ver o relatório.</EmptyState>
      )}

      {data && data.users.length > 0 && (
        <div className="flex flex-col gap-6">
          <SettlementCard report={data} />

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <StatCard
              icon={<Wallet className="h-5 w-5 text-indigo-600" />}
              label="Total compartilhado"
              value={formatBRL(data.shared_total)}
            />
            <StatCard
              icon={<TrendingUp className="h-5 w-5 text-amber-600" />}
              label="Quem gastou mais"
              value={topSpender ? topSpender.name : "—"}
              hint={topSpender ? formatBRL(topSpender.total_spent) : undefined}
            />
            <StatCard
              icon={<Scale className="h-5 w-5 text-emerald-600" />}
              label="Gasto total do casal"
              value={formatBRL(data.users.reduce((s, u) => s + u.total_spent, 0))}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {data.users.map((u) => (
              <UserCard key={u.user_id} u={u} />
            ))}
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <h3 className="mb-4 text-sm font-semibold text-gray-700">Gastos por categoria</h3>
              {data.by_category.length === 0 ? (
                <EmptyState>Sem gastos neste mês.</EmptyState>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart
                    data={data.by_category}
                    layout="vertical"
                    margin={{ left: 10, right: 20 }}
                  >
                    <CartesianGrid horizontal={false} stroke="#f1f5f9" />
                    <XAxis type="number" tickFormatter={(v) => formatBRL(v)} fontSize={11} />
                    <YAxis
                      type="category"
                      dataKey="category_name"
                      width={110}
                      fontSize={11}
                      tickLine={false}
                    />
                    <Tooltip formatter={(v) => formatBRL(Number(v))} />
                    <Legend />
                    <Bar dataKey="shared" name="Compartilhado" stackId="a" fill="#4f46e5" radius={[0, 0, 0, 0]} />
                    <Bar dataKey="individual" name="Individual" stackId="a" fill="#f59e0b" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Card>

            <Card>
              <h3 className="mb-4 text-sm font-semibold text-gray-700">
                Distribuição por categoria
              </h3>
              {data.by_category.length === 0 ? (
                <EmptyState>Sem gastos neste mês.</EmptyState>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={data.by_category}
                      dataKey="total"
                      nameKey="category_name"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={2}
                    >
                      {data.by_category.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v) => formatBRL(Number(v))} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

function SettlementCard({ report }: { report: { settlement: MonthlyReportSettlement } }) {
  const s = report.settlement;
  if (!s.amount || !s.from_user_name) {
    return (
      <Card className="bg-emerald-50">
        <p className="text-center text-sm font-medium text-emerald-700">
          Tudo certo — ninguém deve nada neste mês. 🎉
        </p>
      </Card>
    );
  }
  return (
    <Card className="border-indigo-100 bg-gradient-to-br from-indigo-50 to-white">
      <p className="mb-3 text-sm font-medium text-gray-500">Acerto do mês</p>
      <div className="flex flex-wrap items-center justify-center gap-3 text-center">
        <span className="text-lg font-semibold text-gray-900">{s.from_user_name}</span>
        <span className="flex items-center gap-2 rounded-full bg-indigo-600 px-4 py-1.5 text-lg font-bold text-white">
          {formatBRL(s.amount)}
          <ArrowRight className="h-5 w-5" />
        </span>
        <span className="text-lg font-semibold text-gray-900">{s.to_user_name}</span>
      </div>
    </Card>
  );
}

interface MonthlyReportSettlement {
  from_user_name: string | null;
  to_user_name: string | null;
  amount: number;
}

function StatCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <Card>
      <div className="mb-2 flex items-center gap-2 text-sm text-gray-500">
        {icon}
        {label}
      </div>
      <div className="text-xl font-semibold text-gray-900">{value}</div>
      {hint && <div className="mt-0.5 text-sm text-gray-400">{hint}</div>}
    </Card>
  );
}

function UserCard({ u }: { u: UserReport }) {
  const positive = u.balance >= 0;
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <span className="font-semibold text-gray-900">{u.name}</span>
        <span className="text-xs text-gray-400">
          {(u.proportion * 100).toFixed(1)}% da renda
        </span>
      </div>
      <dl className="space-y-1.5 text-sm">
        <Row label="Pagou (compartilhado)" value={formatBRL(u.shared_paid)} />
        <Row label="Cota justa" value={formatBRL(u.fair_share)} />
        <Row label="Gastos individuais" value={formatBRL(u.individual_spent)} />
        <Row label="Gasto total" value={formatBRL(u.total_spent)} bold />
        <div className="flex items-center justify-between pt-1">
          <dt className="text-gray-500">Saldo</dt>
          <dd className={positive ? "font-medium text-emerald-600" : "font-medium text-red-600"}>
            {positive ? "+" : ""}
            {formatBRL(u.balance)}
          </dd>
        </div>
      </dl>
    </Card>
  );
}

function Row({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-gray-500">{label}</dt>
      <dd className={bold ? "font-semibold text-gray-900" : "text-gray-800"}>{value}</dd>
    </div>
  );
}
