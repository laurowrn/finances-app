import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Clock3, KeyRound, RefreshCw, Rocket, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge, Button, Card, Input, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";

const statusLabel: Record<string, string> = {
  idle: "Aguardando",
  queued: "Na fila",
  running: "Executando",
  success: "Concluído",
  failed: "Falhou",
  unknown: "Desconhecido",
};

export function AdminPage() {
  const qc = useQueryClient();
  const status = useQuery({
    queryKey: ["admin-status"],
    queryFn: api.adminStatus,
    refetchInterval: 5000,
  });
  const config = useQuery({ queryKey: ["admin-config"], queryFn: api.adminConfig });
  const secrets = useQuery({ queryKey: ["admin-secrets"], queryFn: api.secrets });
  const deploy = useMutation({
    mutationFn: api.triggerAdminDeploy,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-status"] }),
  });
  const saveConfig = useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) => api.updateAdminConfig(key, { value }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-config"] }),
  });
  const saveSecret = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { name?: string; value?: string; description?: string } }) =>
      api.updateSecret(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-secrets"] }),
  });
  const createSecret = useMutation({
    mutationFn: api.createSecret,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-secrets"] }),
  });
  const deleteSecret = useMutation({
    mutationFn: api.deleteSecret,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-secrets"] }),
  });

  const current = status.data;
  const tone = current?.status === "success" ? "green" : current?.status === "failed" ? "amber" : "indigo";

  return (
    <div>
      <PageHeader
        title="Administração"
        subtitle="Deploy e configurações operacionais do serviço"
        action={
          <Button variant="secondary" onClick={() => status.refetch()} disabled={status.isFetching}>
            <RefreshCw className="h-4 w-4" /> Atualizar
          </Button>
        }
      />

      {status.isLoading ? <Spinner /> : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card>
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Rocket className="h-5 w-5 text-indigo-600" />
                <h2 className="font-semibold text-gray-900">Deploy</h2>
              </div>
              <Badge tone={tone}>{statusLabel[current?.status ?? "unknown"]}</Badge>
            </div>
            <p className="mb-4 text-sm text-gray-500">
              O servidor verifica o Git automaticamente a cada 5 minutos. Você também pode solicitar uma execução agora.
            </p>
            <Button
              onClick={() => deploy.mutate()}
              disabled={deploy.isPending || current?.status === "running"}
            >
              <Rocket className="h-4 w-4" />
              {deploy.isPending ? "Solicitando…" : "Executar deploy agora"}
            </Button>
            {deploy.isError && <p className="mt-3 text-sm text-red-600">{deploy.error.message}</p>}
            {current?.updated_at && (
              <p className="mt-4 flex items-center gap-2 text-xs text-gray-400">
                <Clock3 className="h-3.5 w-3.5" /> {new Date(current.updated_at).toLocaleString("pt-BR")}
              </p>
            )}
            {current?.commit && <p className="mt-1 font-mono text-xs text-gray-400">commit {current.commit.slice(0, 8)}</p>}
            {current?.message && <p className="mt-2 text-sm text-amber-700">{current.message}</p>}
          </Card>

          <Card>
            <div className="mb-4 flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-indigo-600" />
              <h2 className="font-semibold text-gray-900">Configuração</h2>
            </div>
            {config.isLoading ? <Spinner /> : config.data && (
              <div className="space-y-3 text-sm">
                <Row label="Ambiente" value={config.data.environment} />
                <Row label="IA habilitada" value={config.data.ai_enabled ? `Sim (${config.data.ai_model})` : "Não"} />
                {Object.entries(config.data.values).map(([key, item]) => (
                  <ConfigField key={key} name={key} item={item} onSave={(value) => saveConfig.mutate({ key, value })} />
                ))}
                <p className="flex gap-2 border-t border-gray-100 pt-3 text-xs text-gray-400">
                  <CheckCircle2 className="h-4 w-4 shrink-0" /> {config.data.note}
                </p>
              </div>
            )}
          </Card>
        </div>
      )}

      <Card className="mt-4 border-amber-100 bg-amber-50/50">
        <p className="flex gap-2 text-sm text-amber-800">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Segredos nunca são exibidos nesta tela. Seus valores ficam criptografados no Mongo e a chave-mestra permanece no servidor.
        </p>
      </Card>

      <SecretManager
        secrets={secrets.data ?? []}
        loading={secrets.isLoading}
        onCreate={(body) => createSecret.mutate(body)}
        onSave={(id, body) => saveSecret.mutate({ id, body })}
        onDelete={(id) => {
          if (window.confirm("Excluir este secret? Essa ação não pode ser desfeita.")) deleteSecret.mutate(id);
        }}
      />
    </div>
  );
}

function SecretManager({
  secrets,
  loading,
  onCreate,
  onSave,
  onDelete,
}: {
  secrets: import("@/lib/api").SecretMetadata[];
  loading: boolean;
  onCreate: (body: { name: string; value: string; description: string }) => void;
  onSave: (id: string, body: { name?: string; value?: string; description?: string }) => void;
  onDelete: (id: string) => void;
}) {
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const [description, setDescription] = useState("");
  return (
    <Card className="mt-4">
      <div className="mb-4 flex items-center gap-2">
        <KeyRound className="h-5 w-5 text-indigo-600" />
        <div>
          <h2 className="font-semibold text-gray-900">Secrets</h2>
          <p className="text-xs text-gray-500">CRUD de valores criptografados para integrações e serviços futuros.</p>
        </div>
      </div>
      <div className="mb-5 grid grid-cols-1 gap-2 rounded-xl bg-gray-50 p-3 md:grid-cols-[1fr_1fr_1fr_auto]">
        <Input placeholder="NOME_DO_SECRET" value={name} onChange={(e) => setName(e.target.value)} />
        <Input type="password" placeholder="Valor" value={value} onChange={(e) => setValue(e.target.value)} />
        <Input placeholder="Descrição (opcional)" value={description} onChange={(e) => setDescription(e.target.value)} />
        <Button
          disabled={!name.trim() || !value}
          onClick={() => {
            onCreate({ name, value, description });
            setName(""); setValue(""); setDescription("");
          }}
        >Criar</Button>
      </div>
      {loading ? <Spinner /> : secrets.length === 0 ? (
        <p className="text-sm text-gray-500">Nenhum secret criado.</p>
      ) : (
        <div className="space-y-3">
          {secrets.map((secret) => <SecretRow key={secret.id} secret={secret} onSave={onSave} onDelete={onDelete} />)}
        </div>
      )}
    </Card>
  );
}

function SecretRow({
  secret,
  onSave,
  onDelete,
}: {
  secret: import("@/lib/api").SecretMetadata;
  onSave: (id: string, body: { name?: string; value?: string; description?: string }) => void;
  onDelete: (id: string) => void;
}) {
  const [name, setName] = useState(secret.name);
  const [value, setValue] = useState("");
  const [description, setDescription] = useState(secret.description);
  return (
    <div className="grid grid-cols-1 gap-2 border-b border-gray-100 pb-3 md:grid-cols-[1fr_1fr_1fr_auto_auto]">
      <Input value={name} onChange={(e) => setName(e.target.value)} />
      <Input type="password" placeholder="Novo valor (opcional)" value={value} onChange={(e) => setValue(e.target.value)} />
      <Input value={description} onChange={(e) => setDescription(e.target.value)} />
      <Button size="sm" onClick={() => { onSave(secret.id, { name, description, ...(value ? { value } : {}) }); setValue(""); }}>
        Salvar
      </Button>
      <Button variant="danger" size="sm" onClick={() => onDelete(secret.id)} aria-label={`Excluir ${secret.name}`}>
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  );
}

function ConfigField({
  name,
  item,
  onSave,
}: {
  name: string;
  item: { secret: boolean; configured: boolean; value: string | null };
  onSave: (value: string) => void;
}) {
  const [value, setValue] = useState("");
  return (
    <div className="border-b border-gray-50 pb-3">
      <div className="mb-1 flex items-center justify-between gap-3">
        <span className="font-medium text-gray-700">{name}</span>
        <span className="text-xs text-gray-400">
          {item.configured ? (item.secret ? "Configurado · oculto" : "Configurado") : "Não configurado"}
        </span>
      </div>
      <div className="flex gap-2">
        <Input
          type={item.secret ? "password" : "text"}
          placeholder={item.secret ? "Digite um novo valor" : item.value ?? "Digite um valor"}
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
        <Button size="sm" disabled={!value.trim()} onClick={() => onSave(value)}>
          Salvar
        </Button>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-gray-50 pb-2">
      <span className="text-gray-500">{label}</span>
      <span className="text-right font-medium text-gray-800">{value}</span>
    </div>
  );
}
