import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, FileUp, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { Badge, Button, Card, EmptyState, PageHeader, Select, Spinner } from "@/components/ui";
import {
  api,
  formatBRL,
  type ImportCommitRow,
  type ImportPreviewRow,
  type ImportSummary,
  type Source,
} from "@/lib/api";
import { useCategories, useUsers } from "@/hooks/useMeta";

type Step = "upload" | "unclassified" | "review";
type Row = ImportPreviewRow & { _key: number };

export function Import() {
  const { data: users } = useUsers();
  const { data: categories } = useCategories();
  const [ownerId, setOwnerId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<Step>("upload");
  const [batch, setBatch] = useState<{
    filename: string;
    source: Source;
    owner_user_id: string;
  } | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [summary, setSummary] = useState<ImportSummary | null>(null);

  const effectiveOwner = ownerId || users?.[0]?.id || "";

  const previewMutation = useMutation({
    mutationFn: () => api.previewImport(file!, effectiveOwner),
    onSuccess: (data) => {
      const withKeys = data.rows.map((r, i) => ({ ...r, _key: i }));
      setBatch({ filename: data.filename, source: data.source, owner_user_id: data.owner_user_id });
      setRows(withKeys);
      setSummary(null);
      setError("");
      setStep(withKeys.some((r) => !r.is_duplicate && !r.category_id) ? "unclassified" : "review");
    },
    onError: (e: Error) => setError(e.message),
  });

  const commitMutation = useMutation({
    mutationFn: () =>
      api.commitImport({
        filename: batch!.filename,
        source: batch!.source,
        owner_user_id: batch!.owner_user_id,
        rows: rows
          .filter((r) => !r.is_duplicate)
          .map(
            (r): ImportCommitRow => ({
              date: r.date,
              description: r.description,
              amount: r.amount,
              category_id: r.category_id,
              is_shared: r.is_shared,
              classified_by: r.classified_by,
              rule_id: r.rule_id,
            }),
          ),
      }),
    onSuccess: (data) => {
      setSummary(data);
      setStep("upload");
      setBatch(null);
      setRows([]);
      setFile(null);
      setError("");
      if (inputRef.current) inputRef.current.value = "";
    },
    onError: (e: Error) => setError(e.message),
  });

  function updateRow(key: number, changes: Partial<Row>) {
    setRows((rs) =>
      rs.map((r) =>
        r._key === key ? { ...r, ...changes, classified_by: "manual", rule_id: null } : r,
      ),
    );
  }

  function setCategory(key: number, categoryId: string) {
    const cat = (categories ?? []).find((c) => c.id === categoryId);
    updateRow(key, {
      category_id: categoryId || null,
      is_shared: cat ? cat.is_shared_default : true,
    });
  }

  function reset() {
    setStep("upload");
    setBatch(null);
    setRows([]);
    setError("");
  }

  const pending = rows.filter((r) => !r.is_duplicate && !r.category_id);
  const duplicateCount = rows.filter((r) => r.is_duplicate).length;
  const reviewRows = rows.filter((r) => !r.is_duplicate);

  const subtitle =
    step === "unclassified"
      ? "Escolha uma categoria para cada gasto sem classificação para continuar."
      : step === "review"
        ? "Revise a categoria e a divisão de cada gasto antes de confirmar."
        : "OFX, CSV ou PDF de conta/fatura. Débitos viram gastos automaticamente.";

  return (
    <div>
      <PageHeader title="Importar extrato" subtitle={subtitle} />

      {step === "upload" && (
        <>
          <Card>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Titular do extrato
                </label>
                <Select value={effectiveOwner} onChange={(e) => setOwnerId(e.target.value)}>
                  {(users ?? []).map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Arquivo</label>
                <input
                  ref={inputRef}
                  type="file"
                  accept=".ofx,.csv,.pdf"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-indigo-50 file:px-3 file:py-1.5 file:text-indigo-700"
                />
              </div>
            </div>
            <div className="mt-4 flex items-center gap-3">
              <Button
                onClick={() => previewMutation.mutate()}
                disabled={!file || previewMutation.isPending}
              >
                <UploadCloud className="h-4 w-4" />
                {previewMutation.isPending ? "Lendo arquivo..." : "Importar"}
              </Button>
              {error && <span className="text-sm text-red-600">{error}</span>}
            </div>
          </Card>

          {previewMutation.isPending && <Spinner />}

          {summary && !previewMutation.isPending && (
            <Card className="mt-6">
              <div className="mb-4 flex items-center gap-2 text-emerald-600">
                <CheckCircle2 className="h-5 w-5" />
                <span className="font-medium">Importação concluída — {summary.filename}</span>
              </div>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Stat label="Total lido" value={summary.total} />
                <Stat label="Classificados" value={summary.matched} tone="text-emerald-600" />
                <Stat label="Sem categoria" value={summary.unmatched} tone="text-amber-600" />
                <Stat label="Duplicados (ignorados)" value={summary.duplicates} tone="text-gray-400" />
              </div>
              {summary.unmatched > 0 && (
                <p className="mt-4 text-sm text-gray-600">
                  {summary.unmatched} gasto(s) sem categoria.{" "}
                  <Link to="/rules" className="font-medium text-indigo-600 hover:underline">
                    Crie regras (ou use a IA)
                  </Link>{" "}
                  ou classifique em{" "}
                  <Link to="/transactions" className="font-medium text-indigo-600 hover:underline">
                    Gastos
                  </Link>
                  .
                </p>
              )}
            </Card>
          )}

          {!summary && !previewMutation.isPending && (
            <div className="mt-6">
              <EmptyState>
                <FileUp className="mx-auto mb-2 h-8 w-8 text-gray-300" />
                Selecione um arquivo para começar. Dica: exporte o OFX do seu banco — é o formato
                mais confiável.
              </EmptyState>
            </div>
          )}
        </>
      )}

      {step === "unclassified" && (
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <span className="text-sm text-gray-600">
              {pending.length} gasto(s) sem categoria — escolha uma para cada um
            </span>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={reset}>
                Cancelar importação
              </Button>
              <Button size="sm" disabled={pending.length > 0} onClick={() => setStep("review")}>
                Continuar
              </Button>
            </div>
          </div>
          <div className="divide-y divide-gray-50">
            {rows
              .filter((r) => !r.is_duplicate && !r.category_id)
              .map((r) => (
                <div key={r._key} className="flex flex-wrap items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-gray-900" title={r.description}>
                      {r.description}
                    </p>
                    <p className="text-xs text-gray-400">{r.date}</p>
                  </div>
                  <span className="whitespace-nowrap text-sm font-medium text-gray-700">
                    {formatBRL(r.amount)}
                  </span>
                  <Select
                    className="w-48"
                    value=""
                    onChange={(e) => setCategory(r._key, e.target.value)}
                  >
                    <option value="" disabled>
                      Selecione a categoria
                    </option>
                    {(categories ?? []).map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </Select>
                </div>
              ))}
          </div>
        </Card>
      )}

      {step === "review" && (
        <>
          {duplicateCount > 0 && (
            <p className="mb-3 text-sm text-gray-500">
              {duplicateCount} transação(ões) já importada(s) antes foram detectadas como
              duplicadas e serão ignoradas.
            </p>
          )}
          <Card className="overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-gray-100 bg-gray-50 text-left text-xs uppercase text-gray-500">
                  <tr>
                    <th className="px-4 py-3">Data</th>
                    <th className="px-4 py-3">Descrição</th>
                    <th className="px-4 py-3">Categoria</th>
                    <th className="px-4 py-3">Divisão</th>
                    <th className="px-4 py-3 text-right">Valor</th>
                  </tr>
                </thead>
                <tbody>
                  {reviewRows.map((r) => (
                    <tr key={r._key} className="border-b border-gray-50 hover:bg-gray-50/50">
                      <td className="whitespace-nowrap px-4 py-2 text-gray-500">{r.date}</td>
                      <td className="max-w-56 truncate px-4 py-2" title={r.description}>
                        {r.description}
                      </td>
                      <td className="px-4 py-2">
                        <Select
                          className="w-40"
                          value={r.category_id ?? ""}
                          onChange={(e) => setCategory(r._key, e.target.value)}
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
                          onClick={() => updateRow(r._key, { is_shared: !r.is_shared })}
                          className="cursor-pointer"
                          title="Alternar compartilhado/individual"
                        >
                          <Badge tone={r.is_shared ? "indigo" : "gray"}>
                            {r.is_shared ? "Compartilhado" : "Individual"}
                          </Badge>
                        </button>
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-right font-medium">
                        {formatBRL(r.amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          <div className="mt-4 flex items-center gap-3">
            <Button variant="secondary" onClick={reset}>
              Cancelar importação
            </Button>
            <Button onClick={() => commitMutation.mutate()} disabled={commitMutation.isPending}>
              {commitMutation.isPending ? "Importando..." : "Confirmar importação"}
            </Button>
            {error && <span className="text-sm text-red-600">{error}</span>}
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div className="rounded-lg bg-gray-50 p-3">
      <div className={`text-2xl font-semibold ${tone ?? "text-gray-900"}`}>{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}
