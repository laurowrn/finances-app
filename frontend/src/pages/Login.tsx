import { useQuery } from "@tanstack/react-query";
import { PiggyBank } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Button, Card, Input, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function Login() {
  const { login, loginWithOidc } = useAuth();
  const { data: users } = useQuery({ queryKey: ["public-users"], queryFn: api.publicUsers });
  const { data: oidc } = useQuery({ queryKey: ["oidc-config"], queryFn: api.oidcConfig });
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const processedOidcCode = useRef<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");
    const savedState = sessionStorage.getItem("oidc_state");
    const verifier = sessionStorage.getItem("oidc_verifier");
    if (!code || !state || state !== savedState || !verifier || !oidc?.redirect_uri) return;
    if (processedOidcCode.current === code) return;
    processedOidcCode.current = code;
    setBusy(true);
    loginWithOidc({ code, code_verifier: verifier, redirect_uri: oidc?.redirect_uri ?? "" })
      .then(() => {
        sessionStorage.removeItem("oidc_state");
        sessionStorage.removeItem("oidc_verifier");
        window.history.replaceState({}, document.title, window.location.pathname);
      })
      .catch(() => setError("Não foi possível concluir o login com Google."))
      .finally(() => setBusy(false));
  }, [loginWithOidc, oidc]);

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

  async function loginGoogle() {
    if (!oidc?.enabled) return;
    const state = randomString();
    const verifier = randomString(64);
    const challenge = await sha256Base64Url(verifier);
    sessionStorage.setItem("oidc_state", state);
    sessionStorage.setItem("oidc_verifier", verifier);
    const query = new URLSearchParams({
      client_id: oidc.client_id,
      redirect_uri: oidc.redirect_uri,
      response_type: "code",
      scope: "openid profile email",
      state,
      code_challenge: challenge,
      code_challenge_method: "S256",
      kc_idp_hint: "google",
    });
    window.location.assign(`${oidc.authorization_endpoint}?${query}`);
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
          {oidc?.enabled && (
            <Button type="button" variant="secondary" onClick={loginGoogle} disabled={busy}>
              Entrar com Google
            </Button>
          )}
        </form>
      </Card>
    </div>
  );
}

function randomString(length = 32) {
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function sha256Base64Url(value: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  const bytes = new Uint8Array(digest);
  let binary = "";
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
