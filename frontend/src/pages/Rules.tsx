import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Sparkles, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge, Button, Card, EmptyState, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { api, type MatchOp, type RuleSuggestion, type Split } from "@/lib/api";
import { categoryMap, useCategories } from "@/hooks/useMeta";

export function Rules() {
  const qc = useQueryClient();
  const { data: categories } = useCategories();
  const cMap = categoryMap(categories);
  const [msg, setMsg] = useState("");

  const { data: rules, isLoading } = useQuery({ queryKey: ["rules"], queryFn: api.rules });
  const { data: suggestions } = useQuery({
    queryKey: ["suggestions"],
    queryFn: api.suggestions,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["rules"] });
    qc.invalidateQueries({ queryKey: ["suggestions"] });
    qc.invalidateQueries({ queryKey: ["transactions"] });
    qc.invalidateQueries({ queryKey: ["report"] });
  };

  const suggest = useMutation({
    mutationFn: api.suggest,
    onSuccess: (res) => {
      setMsg(
        res.ai_enabled
          ? `${res.created} grupo(s) sem categoria prontos para virar regra.`
          : `IA desabilitada (sem API key). ${res.created} grupo(s) listados — escolha a categoria manualmente.`,
      );
      invalidate();
    },
  });
  const reclassify = useMutation({
    mutationFn: api.reclassify,
    onSuccess: (res) => {
      setMsg(`${res.reclassified} gasto(s) reclassificado(s).`);
      invalidate();
    },
  });
  const removeRule = useMutation({
    mutationFn: (id: string) => api.deleteRule(id),
    onSuccess: invalidate,
  });

  return (
    <div>
      <PageHeader
        title="Regras de classificação"
        subtitle="A IA ajuda a criar as regras; depois tudo roda só por regras"
        action={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => reclassify.mutate()}>
              <RefreshCw className="h-4 w-4" />
              Reprocessar
            </Button>
            <Button onClick={() => suggest.mutate()} disabled={suggest.isPending}>
              <Sparkles className="h-4 w-4" />
              {suggest.isPending ? "Analisando..." : "Sugerir regras"}
            </Button>
          </div>
        }
      />

      {msg && (
        <div className="mb-4 rounded-lg bg-indigo-50 px-4 py-2 text-sm text-indigo-700">{msg}</div>
      )}

      {suggestions && suggestions.length > 0 && (
        <div className="mb-6">
          <h2 className="mb-2 text-sm font-semibold text-gray-700">
            Sugestões pendentes ({suggestions.length})
          </h2>
          <div className="flex flex-col gap-2">
            {suggestions.map((s) => (
              <SuggestionRow
                key={s.id}
                s={s}
                categories={categories ?? []}
                onDone={invalidate}
              />
            ))}
          </div>
        </div>
      )}

      <NewRuleForm categories={categories ?? []} onDone={invalidate} />

      <h2 className="mb-2 mt-6 text-sm font-semibold text-gray-700">Regras ativas</h2>
      {isLoading && <Spinner />}
      {rules && rules.length === 0 && (
        <EmptyState>Nenhuma regra ainda. Clique em "Sugerir regras" ou crie uma acima.</EmptyState>
      )}
      {rules && rules.length > 0 && (
        <Card className="overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead className="border-b border-gray-100 bg-gray-50 text-left text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Prioridade</th>
                <th className="px-4 py-3">Se a descrição</th>
                <th className="px-4 py-3">Categoria</th>
                <th className="px-4 py-3">Divisão</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id} className="border-b border-gray-50">
                  <td className="px-4 py-2 text-gray-500">{r.priority}</td>
                  <td className="px-4 py-2">
                    <span className="text-gray-500">{opLabel(r.matcher.op)}</span>{" "}
                    <span className="font-medium">"{r.matcher.value}"</span>
                  </td>
                  <td className="px-4 py-2">{cMap[r.category_id] ?? "—"}</td>
                  <td className="px-4 py-2">
                    <Badge tone={r.split_default === "shared" ? "indigo" : "gray"}>
                      {r.split_default === "shared" ? "Compartilhado" : "Individual"}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => removeRule.mutate(r.id)}
                      className="text-gray-300 hover:text-red-500"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

function opLabel(op: MatchOp): string {
  return op === "contains" ? "contém" : op === "equals" ? "é igual a" : "casa regex";
}

function SuggestionRow({
  s,
  categories,
  onDone,
}: {
  s: RuleSuggestion;
  categories: { id: string; name: string }[];
  onDone: () => void;
}) {
  const [categoryId, setCategoryId] = useState(s.suggested_category_id ?? "");
  const [split, setSplit] = useState<Split>(s.suggested_split);

  const accept = useMutation({
    mutationFn: () => api.acceptSuggestion(s.id, categoryId, split),
    onSuccess: onDone,
  });
  const reject = useMutation({
    mutationFn: () => api.rejectSuggestion(s.id),
    onSuccess: onDone,
  });

  return (
    <Card className="flex flex-wrap items-center gap-3">
      <div className="min-w-48 flex-1">
        <div className="font-medium text-gray-900">{s.merchant_key}</div>
        <div className="truncate text-xs text-gray-400">
          {s.count}x · {s.sample_descriptions.slice(0, 2).join(", ")}
        </div>
      </div>
      <Select className="w-44" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
        <option value="">Escolha a categoria</option>
        {categories.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </Select>
      <Select className="w-36" value={split} onChange={(e) => setSplit(e.target.value as Split)}>
        <option value="shared">Compartilhado</option>
        <option value="individual">Individual</option>
      </Select>
      <Button size="sm" onClick={() => accept.mutate()} disabled={!categoryId || accept.isPending}>
        Criar regra
      </Button>
      <Button size="sm" variant="ghost" onClick={() => reject.mutate()}>
        Ignorar
      </Button>
    </Card>
  );
}

function NewRuleForm({
  categories,
  onDone,
}: {
  categories: { id: string; name: string }[];
  onDone: () => void;
}) {
  const [op, setOp] = useState<MatchOp>("contains");
  const [value, setValue] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [split, setSplit] = useState<Split>("shared");

  const create = useMutation({
    mutationFn: () =>
      api.createRule({
        matcher: { field: "description", op, value },
        category_id: categoryId,
        split_default: split,
        priority: 100,
        enabled: true,
      }),
    onSuccess: () => {
      setValue("");
      onDone();
    },
  });

  return (
    <Card>
      <h2 className="mb-3 text-sm font-semibold text-gray-700">Nova regra</h2>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Select value={op} onChange={(e) => setOp(e.target.value as MatchOp)}>
          <option value="contains">Descrição contém</option>
          <option value="equals">Descrição é igual a</option>
          <option value="regex">Descrição casa regex</option>
        </Select>
        <Input
          className="col-span-2"
          placeholder="Ex.: uber, ifood, netflix"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <Select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
          <option value="">Categoria</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        <Select value={split} onChange={(e) => setSplit(e.target.value as Split)}>
          <option value="shared">Compartilhado</option>
          <option value="individual">Individual</option>
        </Select>
      </div>
      <div className="mt-3 text-right">
        <Button onClick={() => create.mutate()} disabled={!value || !categoryId || create.isPending}>
          Criar regra
        </Button>
      </div>
    </Card>
  );
}
