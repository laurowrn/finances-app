import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { SettlementCard } from "@/components/SettlementCard";
import { Button, Card, EmptyState, Input, PageHeader, Select, Spinner } from "@/components/ui";
import {
  api,
  centsToInput,
  formatBRL,
  parseBRLToCents,
  type CumulativeBalance,
} from "@/lib/api";
import { useUsers, userMap } from "@/hooks/useMeta";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function Payments() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const { data: users } = useUsers();
  const uMap = userMap(users);

  const { data: balance, isLoading: loadingBalance } = useQuery({
    queryKey: ["cumulative-balance"],
    queryFn: api.cumulativeBalance,
  });
  const { data: payments, isLoading: loadingPayments } = useQuery({
    queryKey: ["payments"],
    queryFn: () => api.payments(),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["payments"] });
    qc.invalidateQueries({ queryKey: ["cumulative-balance"] });
    qc.invalidateQueries({ queryKey: ["report"] });
  };

  const remove = useMutation({
    mutationFn: (id: string) => api.deletePayment(id),
    onSuccess: invalidate,
  });

  return (
    <div>
      <PageHeader
        title="Pagamentos"
        subtitle="Registre pagamentos entre vocês para abater o saldo devedor"
        action={
          <Button onClick={() => setShowForm((s) => !s)}>
            <Plus className="h-4 w-4" />
            Registrar pagamento
          </Button>
        }
      />

      {loadingBalance && <Spinner />}
      {balance && <SettlementCard title="Saldo acumulado" settlement={balance.settlement} />}

      {showForm && users && users.length > 0 && (
        <PaymentForm
          users={users}
          balance={balance ?? null}
          onDone={() => {
            setShowForm(false);
            invalidate();
          }}
        />
      )}

      <div className="mt-6">
        {loadingPayments && <Spinner />}
        {payments && payments.length === 0 && (
          <EmptyState>Nenhum pagamento registrado ainda.</EmptyState>
        )}
        {payments && payments.length > 0 && (
          <Card className="overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-gray-100 bg-gray-50 text-left text-xs uppercase text-gray-500">
                  <tr>
                    <th className="px-4 py-3">Data</th>
                    <th className="px-4 py-3">De</th>
                    <th className="px-4 py-3">Para</th>
                    <th className="px-4 py-3">Nota</th>
                    <th className="px-4 py-3 text-right">Valor</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {payments.map((p) => (
                    <tr key={p.id} className="border-b border-gray-50 hover:bg-gray-50/50">
                      <td className="whitespace-nowrap px-4 py-2 text-gray-500">{p.date}</td>
                      <td className="px-4 py-2 text-gray-800">{uMap[p.from_user_id] ?? "—"}</td>
                      <td className="px-4 py-2 text-gray-800">{uMap[p.to_user_id] ?? "—"}</td>
                      <td
                        className="max-w-56 truncate px-4 py-2 text-gray-500"
                        title={p.note ?? undefined}
                      >
                        {p.note ?? "—"}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-right font-medium">
                        {formatBRL(p.amount_cents)}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <button
                          onClick={() => remove.mutate(p.id)}
                          className="text-gray-300 hover:text-red-500"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

function PaymentForm({
  users,
  balance,
  onDone,
}: {
  users: { id: string; name: string }[];
  balance: CumulativeBalance | null;
  onDone: () => void;
}) {
  const debtorId = balance?.settlement.from_user_id ?? users[0]?.id ?? "";
  const creditorId = balance?.settlement.to_user_id ?? users[1]?.id ?? users[0]?.id ?? "";
  const [date, setDate] = useState(today());
  const [fromId, setFromId] = useState(debtorId);
  const [toId, setToId] = useState(creditorId);
  // Pré-preenche com o que falta acertar, em reais (o input é decimal).
  const [amount, setAmount] = useState(centsToInput(balance?.settlement.amount_cents || null));
  const [note, setNote] = useState("");

  const create = useMutation({
    mutationFn: () =>
      api.createPayment({
        date,
        from_user_id: fromId,
        to_user_id: toId,
        amount_cents: amountCents ?? 0,
        note: note || undefined,
      }),
    onSuccess: () => {
      setNote("");
      onDone();
    },
  });

  const amountCents = parseBRLToCents(amount);
  const valid = fromId && toId && fromId !== toId && (amountCents ?? 0) > 0;

  return (
    <Card className="mb-4 mt-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        <Select value={fromId} onChange={(e) => setFromId(e.target.value)}>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </Select>
        <Select value={toId} onChange={(e) => setToId(e.target.value)}>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </Select>
        <Input
          type="number"
          step="0.01"
          placeholder="Valor"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        <Input
          placeholder="Nota (opcional)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>
      {fromId === toId && (
        <p className="mt-2 text-sm text-red-600">
          Quem paga e quem recebe precisam ser diferentes.
        </p>
      )}
      <div className="mt-3 flex justify-end">
        <Button onClick={() => create.mutate()} disabled={!valid || create.isPending}>
          Registrar pagamento
        </Button>
      </div>
    </Card>
  );
}
