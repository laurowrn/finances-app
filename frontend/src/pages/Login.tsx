import { useQuery } from "@tanstack/react-query";
import { PiggyBank } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { Button, Card, Input, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function Login() {
  const { login } = useAuth();
  const { data: users } = useQuery({ queryKey: ["public-users"], queryFn: api.publicUsers });
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (users && users.length && !userId) setUserId(users[0].id);
  }, [users, userId]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(userId, password);
    } catch {
      setError("Usuário ou senha incorretos.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <Card className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <PiggyBank className="h-10 w-10 text-indigo-600" />
          <h1 className="text-xl font-semibold text-gray-900">Finanças do Casal</h1>
          <p className="text-sm text-gray-500">Entre para acompanhar os gastos</p>
        </div>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Quem é você?</label>
            <Select value={userId} onChange={(e) => setUserId(e.target.value)}>
              {(users ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Senha</label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Senha compartilhada"
              autoFocus
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button type="submit" disabled={busy || !userId}>
            {busy ? "Entrando..." : "Entrar"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
