import { useQuery } from "@tanstack/react-query";
import { Scale, TrendingUp, Wallet } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
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
import { SettlementCard } from "@/components/SettlementCard";
import { Card, EmptyState, PageHeader, Spinner } from "@/components/ui";
import { api, formatBRL, previousPeriod, type UserReport } from "@/lib/api";
import { AXIS_TEXT, formatBRLAxis, GRID, seriesColor, SERIES } from "@/lib/chartPalette";
import { TrendSection } from "@/components/TrendSection";



export function Report() {
  // Abre no mês fechado, não no corrente: o acerto é sempre sobre o mês anterior.
  const [period, setPeriod] = useState(previousPeriod());
  const { data, isLoading } = useQuery({
    queryKey: ["report", period],
    queryFn: () => api.report(period),
  });

  const topSpender = data
    ? [...data.users].sort((a, b) => b.total_spent_cents - a.total_spent_cents)[0]
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
          <SettlementCard
            title="Acerto do mês"
            settlement={data.settlement}
            hint="Calculado só com os gastos do mês. O que já foi pago aparece no saldo acumulado, em Pagamentos."
            action={
              <Link to="/payments" className="text-sm font-medium text-indigo-600 hover:underline">
                Registrar pagamento →
              </Link>
            }
          />

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <StatCard
              icon={<Wallet className="h-5 w-5 text-indigo-600" />}
              label="Total compartilhado"
              value={formatBRL(data.shared_total_cents)}
            />
            <StatCard
              icon={<TrendingUp className="h-5 w-5 text-amber-600" />}
              label="Quem gastou mais"
              value={topSpender ? topSpender.name : "—"}
              hint={topSpender ? formatBRL(topSpender.total_spent_cents) : undefined}
            />
            <StatCard
              icon={<Scale className="h-5 w-5 text-emerald-600" />}
              label="Gasto total do casal"
              value={formatBRL(data.users.reduce((s, u) => s + u.total_spent_cents, 0))}
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
                    <CartesianGrid horizontal={false} stroke={GRID} />
                    <XAxis type="number" tickFormatter={formatBRLAxis} fontSize={11} stroke={AXIS_TEXT} />
                    <YAxis
                      type="category"
                      dataKey="category_name"
                      width={110}
                      fontSize={11}
                      tickLine={false}
                    />
                    <Tooltip formatter={(v) => formatBRL(Number(v))} />
                    <Legend />
                    <Bar dataKey="shared_cents" name="Compartilhado" stackId="a" fill={SERIES[0]} radius={[0, 0, 0, 0]} />
                    <Bar dataKey="individual_cents" name="Individual" stackId="a" fill={SERIES[1]} radius={[0, 4, 4, 0]} />
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
                      dataKey="total_cents"
                      nameKey="category_name"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={2}
                    >
                      {data.by_category.map((_, i) => (
                        <Cell key={i} fill={seriesColor(i)} />
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

      <TrendSection />
    </div>
  );
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
  const positive = u.balance_cents >= 0;
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <span className="font-semibold text-gray-900">{u.name}</span>
        <span className="text-xs text-gray-400">
          {(u.proportion * 100).toFixed(1)}% da renda
        </span>
      </div>
      <dl className="space-y-1.5 text-sm">
        <Row label="Pagou (compartilhado)" value={formatBRL(u.shared_paid_cents)} />
        <Row label="Cota justa" value={formatBRL(u.fair_share_cents)} />
        <Row label="Gastos individuais" value={formatBRL(u.individual_spent_cents)} />
        <Row label="Gasto total" value={formatBRL(u.total_spent_cents)} bold />
        <div className="flex items-center justify-between pt-1">
          <dt className="text-gray-500">Saldo</dt>
          <dd className={positive ? "font-medium text-emerald-600" : "font-medium text-red-600"}>
            {positive ? "+" : ""}
            {formatBRL(u.balance_cents)}
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
