import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { PeriodPicker } from "@/components/PeriodPicker";
import { Button, Card, Input, PageHeader, Spinner } from "@/components/ui";
import { api, centsToInput, currentPeriod, formatBRL, parseBRLToCents } from "@/lib/api";
import { useUsers } from "@/hooks/useMeta";

export function SettingsPage() {
  const qc = useQueryClient();
  const [period, setPeriod] = useState(currentPeriod());
  const { data: users, isLoading } = useUsers();
  const { data: incomes } = useQuery({
    queryKey: ["incomes", period],
    queryFn: () => api.incomes(period),
  });

  const incomeMap: Record<string, number> = Object.fromEntries(
    (incomes ?? []).map((i) => [i.user_id, i.amount_cents]),
  );

  return (
    <div>
      <PageHeader
        title="Configurações"
        subtitle="Salários do casal — base e ajuste por mês (usado no rateio proporcional)"
        action={<PeriodPicker period={period} onChange={setPeriod} />}
      />

      {isLoading && <Spinner />}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {(users ?? []).map((u) => (
          <UserSettings
            key={u.id}
            user={u}
            period={period}
            monthIncome={incomeMap[u.id]}
            onSaved={() => {
              qc.invalidateQueries({ queryKey: ["users"] });
              qc.invalidateQueries({ queryKey: ["incomes"] });
              qc.invalidateQueries({ queryKey: ["report"] });
            }}
          />
        ))}
      </div>
    </div>
  );
}

function UserSettings({
  user,
  period,
  monthIncome,
  onSaved,
}: {
  user: { id: string; name: string; base_salary_cents: number };
  period: string;
  monthIncome?: number;
  onSaved: () => void;
}) {
  const [name, setName] = useState(user.name);
  const [baseSalary, setBaseSalary] = useState(centsToInput(user.base_salary_cents));
  const [income, setIncome] = useState(centsToInput(monthIncome ?? user.base_salary_cents));

  const saveUser = useMutation({
    mutationFn: () => api.updateUser(user.id, { name, base_salary_cents: parseBRLToCents(baseSalary) ?? 0 }),
    onSuccess: onSaved,
  });
  const saveIncome = useMutation({
    mutationFn: () => api.upsertIncome(user.id, period, parseBRLToCents(income) ?? 0),
    onSuccess: onSaved,
  });

  return (
    <Card>
      <h3 className="mb-3 font-semibold text-gray-900">{user.name}</h3>
      <div className="flex flex-col gap-3">
        <Field label="Nome">
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Salário base (padrão)">
          <Input
            type="number"
            step="0.01"
            value={baseSalary}
            onChange={(e) => setBaseSalary(e.target.value)}
          />
        </Field>
        <Button variant="secondary" size="sm" onClick={() => saveUser.mutate()}>
          Salvar base
        </Button>

        <div className="mt-2 border-t border-gray-100 pt-3">
          <Field label={`Renda deste mês (${period})`}>
            <Input
              type="number"
              step="0.01"
              value={income}
              onChange={(e) => setIncome(e.target.value)}
            />
          </Field>
          <p className="mb-2 text-xs text-gray-400">
            Sem ajuste, o relatório usa o salário base ({formatBRL(user.base_salary_cents)}).
          </p>
          <Button size="sm" onClick={() => saveIncome.mutate()}>
            Salvar renda do mês
          </Button>
        </div>
      </div>
    </Card>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-gray-700">{label}</span>
      {children}
    </label>
  );
}
