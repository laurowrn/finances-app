import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { PeriodPicker } from "@/components/PeriodPicker";
import { Badge, Button, Card, EmptyState, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { api, currentPeriod, formatBRL, type Transaction } from "@/lib/api";
import { categoryMap, useCategories, userMap, useUsers } from "@/hooks/useMeta";

export function Transactions() {
  const qc = useQueryClient();
  const [period, setPeriod] = useState(currentPeriod());
  const [ownerFilter, setOwnerFilter] = useState("");
  const [showForm, setShowForm] = useState(false);

  const { data: users } = useUsers();
  const { data: categories } = useCategories();
  const uMap = userMap(users);
  const cMap = categoryMap(categories);

  const { data: txs, isLoading } = useQuery({
    queryKey: ["transactions", period, ownerFilter],
    queryFn: () => api.transactions({ period, owner_user_id: ownerFilter || undefined }),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["transactions"] });
    qc.invalidateQueries({ queryKey: ["report"] });
  };

  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<Transaction> }) =>
      api.updateTransaction(id, body),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteTransaction(id),
    onSuccess: invalidate,
  });

  return (
    <div>
      <PageHeader
        title="Gastos"
        subtitle="Edite categoria e se é compartilhado ou individual"
        action={
          <div className="flex items-center gap-2">
            <PeriodPicker period={period} onChange={setPeriod} />
            <Button onClick={() => setShowForm((s) => !s)}>
              <Plus className="h-4 w-4" />
              Lançar
            </Button>
          </div>
        }
      />

      {showForm && (
        <ManualForm
          users={users ?? []}
          categories={categories ?? []}
          period={period}
          onDone={() => {
            setShowForm(false);
            invalidate();
          }}
        />
      )}

      <div className="mb-4 flex items-center gap-2">
        <span className="text-sm text-gray-500">Filtrar por:</span>
        <Select
          className="w-48"
          value={ownerFilter}
          onChange={(e) => setOwnerFilter(e.target.value)}
        >
          <option value="">Todos</option>
          {(users ?? []).map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </Select>
      </div>

      {isLoading && <Spinner />}
      {txs && txs.length === 0 && <EmptyState>Nenhum gasto neste período.</EmptyState>}

      {txs && txs.length > 0 && (
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-gray-100 bg-gray-50 text-left text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3">Data</th>
                  <th className="px-4 py-3">Descrição</th>
                  <th className="px-4 py-3">Quem</th>
                  <th className="px-4 py-3">Categoria</th>
                  <th className="px-4 py-3">Divisão</th>
                  <th className="px-4 py-3 text-right">Valor</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {txs.map((t) => (
                  <tr key={t.id} className="border-b border-gray-50 hover:bg-gray-50/50">
                    <td className="whitespace-nowrap px-4 py-2 text-gray-500">{t.date}</td>
                    <td className="max-w-56 truncate px-4 py-2" title={t.description}>
                      {t.description}
                      {!t.category_id && (
                        <Badge tone="amber">
                          <span className="ml-1">sem categoria</span>
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-2 text-gray-600">{uMap[t.owner_user_id] ?? "—"}</td>
                    <td className="px-4 py-2">
                      <Select
                        className="w-40"
                        value={t.category_id ?? ""}
                        onChange={(e) =>
                          update.mutate({
                            id: t.id,
                            body: { category_id: e.target.value || null },
                          })
                        }
                      >
                        <option value="">—</option>
                        {(categories ?? []).map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </Select>
                    </td>
                    <td className="px-4 py-2">
                      <button
                        onClick={() =>
                          update.mutate({ id: t.id, body: { is_shared: !t.is_shared } })
                        }
                        className="cursor-pointer"
                        title="Alternar compartilhado/individual"
                      >
                        <Badge tone={t.is_shared ? "indigo" : "gray"}>
                          {t.is_shared ? "Compartilhado" : "Individual"}
                        </Badge>
                      </button>
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-right font-medium">
                      {formatBRL(t.amount)}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={() => remove.mutate(t.id)}
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
  );
}

function ManualForm({
  users,
  categories,
  period,
  onDone,
}: {
  users: { id: string; name: string }[];
  categories: { id: string; name: string; is_shared_default: boolean }[];
  period: string;
  onDone: () => void;
}) {
  const [date, setDate] = useState(`${period}-01`);
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [owner, setOwner] = useState(users[0]?.id ?? "");
  const [categoryId, setCategoryId] = useState("");
  const [isShared, setIsShared] = useState(true);

  const create = useMutation({
    mutationFn: () =>
      api.createTransaction({
        date,
        description,
        amount: Number(amount),
        owner_user_id: owner,
        category_id: categoryId || null,
        is_shared: isShared,
      }),
    onSuccess: () => {
      setDescription("");
      setAmount("");
      onDone();
    },
  });

  const valid = description && Number(amount) > 0 && owner;

  return (
    <Card className="mb-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
        <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        <Input
          className="col-span-2"
          placeholder="Descrição"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <Input
          type="number"
          step="0.01"
          placeholder="Valor"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        <Select value={owner} onChange={(e) => setOwner(e.target.value)}>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </Select>
        <Select
          value={categoryId}
          onChange={(e) => {
            setCategoryId(e.target.value);
            const c = categories.find((x) => x.id === e.target.value);
            if (c) setIsShared(c.is_shared_default);
          }}
        >
          <option value="">Sem categoria</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={isShared}
            onChange={(e) => setIsShared(e.target.checked)}
          />
          Compartilhado
        </label>
        <Button onClick={() => create.mutate()} disabled={!valid || create.isPending}>
          Adicionar gasto
        </Button>
      </div>
    </Card>
  );
}
