import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileUp, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  nextSplitState,
  SPLIT_LABEL,
  SPLIT_TONE,
  toSplitFlags,
  toSplitState,
} from "@/lib/split";
import { Badge, Button, Card, EmptyState, Input, PageHeader, Select, Spinner } from "@/components/ui";
import {
  api,
  formatBRL,
  type ImportCommitRow,
  type ImportPreviewRow,
  type ImportSummary,
  type Source, type StatementType, type Coverage, type Institution,
} from "@/lib/api";
import { useCategories, useUsers } from "@/hooks/useMeta";

type Step = "upload" | "unclassified" | "review";
type Row = ImportPreviewRow & { _key: number };

export function Import() {
  const { data: users } = useUsers();
  const { data: categories } = useCategories();
  const [ownerId, setOwnerId] = useState("");
  const [statementType, setStatementType] = useState<StatementType>("account");
  const [institution, setInstitution] = useState<Institution>("nubank");
  const [statementStart, setStatementStart] = useState("");
  const [statementEnd, setStatementEnd] = useState("");
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
  const queryClient = useQueryClient();
  const coverageQuery = useQuery({
    queryKey: ["import-coverage", effectiveOwner, statementType, institution],
    queryFn: () => api.importCoverage(effectiveOwner, statementType, institution),
    enabled: Boolean(effectiveOwner),
  });

  const previewMutation = useMutation({
    mutationFn: () => api.previewImport(file!, effectiveOwner, statementStart, statementEnd),
    onSuccess: (data) => {
      const withKeys = data.rows.map((r, i) => ({ ...r, _key: i }));
      setBatch({ filename: data.filename, source: data.source, owner_user_id: data.owner_user_id });
      if (!statementStart && data.detected_start) setStatementStart(data.detected_start);
      if (!statementEnd && data.detected_end) setStatementEnd(data.detected_end);
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
        statement_type: statementType,
        institution,
        statement_start: statementStart || undefined,
        statement_end: statementEnd || undefined,
        rows: rows
          .filter((r) => !r.is_duplicate)
          .map(
            (r): ImportCommitRow => ({
              date: r.date,
              description: r.description,
              amount_cents: r.amount_cents,
              category_id: r.category_id,
              is_shared: r.is_shared,
              is_ignored: r.is_ignored,
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
      queryClient.invalidateQueries({ queryKey: ["import-coverage"] });
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
    // Trocar a categoria à mão tira o "ignorado": só regra ou clique no badge marca.
    updateRow(key, {
      category_id: categoryId || null,
      is_shared: cat ? cat.is_shared_default : true,
      is_ignored: false,
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
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
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
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Tipo de extrato</label>
                <Select value={statementType} onChange={(e) => setStatementType(e.target.value as StatementType)}>
                  <option value="account">Conta corrente</option>
                  <option value="credit_card">Cartão de crédito</option>
                </Select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Instituição</label>
                <Select value={institution} onChange={(e) => setInstitution(e.target.value as Institution)}>
                  <option value="nubank">Nubank</option>
                  <option value="itau">Itaú</option>
                  <option value="other">Outra</option>
                </Select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Período coberto</label>
                <div className="flex gap-2">
                  <Input type="date" aria-label="Data inicial" value={statementStart} onChange={(e) => setStatementStart(e.target.value)} />
                  <Input type="date" aria-label="Data final" value={statementEnd} onChange={(e) => setStatementEnd(e.target.value)} />
                </div>
                <p className="mt-1 text-xs text-gray-400">Detectado pelo arquivo; ajuste se necessário.</p>
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

          <CoveragePanel coverage={coverageQuery.data} />

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
                    {formatBRL(r.amount_cents)}
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
                          onClick={() =>
                            updateRow(r._key, toSplitFlags(nextSplitState(toSplitState(r))))
                          }
                          className="cursor-pointer"
                          title="Alternar compartilhado / individual / ignorado"
                        >
                          <Badge tone={SPLIT_TONE[toSplitState(r)]}>
                            {SPLIT_LABEL[toSplitState(r)]}
                          </Badge>
                        </button>
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-right font-medium">
                        {formatBRL(r.amount_cents)}
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

function CoveragePanel({ coverage }: { coverage?: Coverage }) {
  if (!coverage || coverage.batches.length === 0) return null;
  const label = coverage.statement_type === "account" ? "Conta corrente" : "Cartão de crédito";
  const institution = coverage.institution === "itau" ? "Itaú" : coverage.institution === "nubank" ? "Nubank" : "Outra";
  return (
    <Card className="mt-6">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="font-medium text-gray-900">Cobertura — {label} · {institution}</h2>
          <p className="text-xs text-gray-500">Intervalos registrados para evitar gastos faltando ou duplicados.</p>
        </div>
        <div className="flex gap-2">
          <Badge tone={coverage.gaps.length ? "amber" : "green"}>{coverage.gaps.length} lacuna(s)</Badge>
          <Badge tone={coverage.overlaps.length ? "amber" : "green"}>{coverage.overlaps.length} sobreposição(ões)</Badge>
        </div>
      </div>
      {(coverage.gaps.length > 0 || coverage.overlaps.length > 0) && (
        <div className="space-y-2 text-sm">
          {coverage.gaps.map((issue) => (
            <div key={`gap-${issue.start}-${issue.end}`} className="rounded-lg bg-amber-50 px-3 py-2 text-amber-800">
              Lacuna de {issue.start} a {issue.end} entre <span className="font-medium">{issue.previous_filename}</span> e <span className="font-medium">{issue.filename}</span>.
            </div>
          ))}
          {coverage.overlaps.map((issue) => (
            <div key={`overlap-${issue.start}-${issue.end}`} className="rounded-lg bg-amber-50 px-3 py-2 text-amber-800">
              Sobreposição de {issue.start} a {issue.end} entre <span className="font-medium">{issue.previous_filename}</span> e <span className="font-medium">{issue.filename}</span>. Duplicatas idênticas são bloqueadas, mas revise lançamentos diferentes.
            </div>
          ))}
        </div>
      )}
      {coverage.gaps.length === 0 && coverage.overlaps.length === 0 && (
        <p className="text-sm text-emerald-700">Os extratos estão contínuos, sem lacunas ou sobreposições.</p>
      )}
    </Card>
  );
}
