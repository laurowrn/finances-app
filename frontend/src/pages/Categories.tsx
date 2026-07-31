import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge, Button, Card, EmptyState, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { api } from "@/lib/api";

export function Categories() {
  const qc = useQueryClient();
  const { data: categories, isLoading } = useQuery({
    queryKey: ["categories"],
    queryFn: api.categories,
  });
  const [name, setName] = useState("");
  const [shared, setShared] = useState("shared");

  const invalidate = () => qc.invalidateQueries({ queryKey: ["categories"] });

  const create = useMutation({
    mutationFn: () =>
      api.createCategory({ name, icon: "tag", is_shared_default: shared === "shared" }),
    onSuccess: () => {
      setName("");
      invalidate();
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteCategory(id),
    onSuccess: invalidate,
  });
  const update = useMutation({
    mutationFn: ({ id, is_shared_default }: { id: string; is_shared_default: boolean }) =>
      api.updateCategory(id, { is_shared_default }),
    onSuccess: invalidate,
  });

  return (
    <div>
      <PageHeader title="Categorias" subtitle="Organize os tipos de gasto do casal" />

      <Card className="mb-6">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1">
            <label className="mb-1 block text-sm font-medium text-gray-700">Nome</label>
            <Input
              placeholder="Ex.: Mercado"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="w-48">
            <label className="mb-1 block text-sm font-medium text-gray-700">Padrão</label>
            <Select value={shared} onChange={(e) => setShared(e.target.value)}>
              <option value="shared">Compartilhado</option>
              <option value="individual">Individual</option>
            </Select>
          </div>
          <Button onClick={() => create.mutate()} disabled={!name || create.isPending}>
            <Plus className="h-4 w-4" />
            Adicionar
          </Button>
        </div>
      </Card>

      {isLoading && <Spinner />}
      {categories && categories.length === 0 && <EmptyState>Nenhuma categoria ainda.</EmptyState>}
      {categories && categories.length > 0 && (
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {categories.map((c) => (
            <Card key={c.id} className="flex items-center justify-between py-3">
              <span className="font-medium text-gray-900">{c.name}</span>
              <div className="flex items-center gap-3">
                <button
                  onClick={() =>
                    update.mutate({ id: c.id, is_shared_default: !c.is_shared_default })
                  }
                >
                  <Badge tone={c.is_shared_default ? "indigo" : "gray"}>
                    {c.is_shared_default ? "Compartilhado" : "Individual"}
                  </Badge>
                </button>
                <button
                  onClick={() => remove.mutate(c.id)}
                  className="text-gray-300 hover:text-red-500"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
