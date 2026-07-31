import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, FileUp, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { Button, Card, EmptyState, PageHeader, Select, Spinner } from "@/components/ui";
import { api, type ImportSummary } from "@/lib/api";
import { useUsers } from "@/hooks/useMeta";

export function Import() {
  const { data: users } = useUsers();
  const [ownerId, setOwnerId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const effectiveOwner = ownerId || users?.[0]?.id || "";

  const mutation = useMutation({
    mutationFn: () => api.importFile(file!, effectiveOwner),
    onSuccess: (data) => {
      setSummary(data);
      setError("");
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <div>
      <PageHeader
        title="Importar extrato"
        subtitle="OFX, CSV ou PDF de conta/fatura. Débitos viram gastos automaticamente."
      />

      <Card>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Titular do extrato</label>
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
          <Button onClick={() => mutation.mutate()} disabled={!file || mutation.isPending}>
            <UploadCloud className="h-4 w-4" />
            {mutation.isPending ? "Importando..." : "Importar"}
          </Button>
          {error && <span className="text-sm text-red-600">{error}</span>}
        </div>
      </Card>

      {mutation.isPending && <Spinner />}

      {summary && (
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

      {!summary && !mutation.isPending && (
        <div className="mt-6">
          <EmptyState>
            <FileUp className="mx-auto mb-2 h-8 w-8 text-gray-300" />
            Selecione um arquivo para começar. Dica: exporte o OFX do seu banco — é o formato mais
            confiável.
          </EmptyState>
        </div>
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
