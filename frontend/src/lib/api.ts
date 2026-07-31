const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const TOKEN_KEY = "gf_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");

  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (resp.status === 401) {
    setToken(null);
    if (!path.startsWith("/auth")) window.location.href = "/login";
  }
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const data = await resp.json();
      detail = data.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, typeof detail === "string" ? detail : "Erro");
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

// ---------- Types ----------

export type Split = "shared" | "individual";
export type Source = "ofx" | "csv" | "pdf" | "manual";
export type MatchOp = "contains" | "equals" | "regex";

export interface User {
  id: string;
  name: string;
  base_salary: number;
}

export interface Category {
  id: string;
  name: string;
  icon: string;
  is_shared_default: boolean;
}

export interface Matcher {
  field: string;
  op: MatchOp;
  value: string;
}

export interface Rule {
  id: string;
  matcher: Matcher;
  category_id: string;
  split_default: Split;
  priority: number;
  enabled: boolean;
}

export interface Transaction {
  id: string;
  date: string;
  period: string;
  description: string;
  raw_description: string;
  amount: number;
  owner_user_id: string;
  category_id: string | null;
  is_shared: boolean;
  source: Source;
  classified_by: string;
  rule_id: string | null;
  import_batch_id: string | null;
}

export interface RuleSuggestion {
  id: string;
  merchant_key: string;
  sample_descriptions: string[];
  suggested_category_id: string | null;
  suggested_category_name: string | null;
  suggested_split: Split;
  count: number;
  status: string;
}

export interface ImportSummary {
  import_batch_id: string;
  filename: string;
  source: Source;
  owner_user_id: string;
  total: number;
  matched: number;
  unmatched: number;
  duplicates: number;
  created_at: string;
}

export interface ImportPreviewRow {
  date: string;
  description: string;
  amount: number;
  category_id: string | null;
  is_shared: boolean;
  classified_by: string;
  rule_id: string | null;
  is_duplicate: boolean;
}

export interface ImportPreview {
  filename: string;
  source: Source;
  owner_user_id: string;
  rows: ImportPreviewRow[];
}

export interface ImportCommitRow {
  date: string;
  description: string;
  amount: number;
  category_id: string | null;
  is_shared: boolean;
  classified_by: string;
  rule_id: string | null;
}

export interface UserReport {
  user_id: string;
  name: string;
  income: number;
  proportion: number;
  shared_paid: number;
  individual_spent: number;
  total_spent: number;
  fair_share: number;
  balance: number;
}

export interface CategoryBreakdown {
  category_id: string | null;
  category_name: string;
  shared: number;
  individual: number;
  total: number;
}

export interface Settlement {
  from_user_id: string | null;
  from_user_name: string | null;
  to_user_id: string | null;
  to_user_name: string | null;
  amount: number;
}

export interface MonthlyReport {
  period: string;
  shared_total: number;
  users: UserReport[];
  settlement: Settlement;
  by_category: CategoryBreakdown[];
}

export interface Payment {
  id: string;
  date: string;
  period: string;
  from_user_id: string;
  to_user_id: string;
  amount: number;
  note: string | null;
  created_at: string;
}

export interface UserBalance {
  user_id: string;
  name: string;
  balance: number;
}

export interface CumulativeBalance {
  as_of_period: string;
  balances: UserBalance[];
  settlement: Settlement;
}

// ---------- Endpoints ----------

export const api = {
  publicUsers: () => request<User[]>("/auth/users"),
  login: (user_id: string, password: string) =>
    request<{ access_token: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ user_id, password }),
    }),

  users: () => request<User[]>("/users"),
  updateUser: (id: string, body: Partial<User>) =>
    request<User>(`/users/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  incomes: (period: string) =>
    request<{ user_id: string; period: string; amount: number }[]>(`/users/incomes/${period}`),
  upsertIncome: (user_id: string, period: string, amount: number) =>
    request(`/users/incomes`, {
      method: "PUT",
      body: JSON.stringify({ user_id, period, amount }),
    }),

  categories: () => request<Category[]>("/categories"),
  createCategory: (body: Omit<Category, "id">) =>
    request<Category>("/categories", { method: "POST", body: JSON.stringify(body) }),
  updateCategory: (id: string, body: Partial<Category>) =>
    request<Category>(`/categories/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteCategory: (id: string) => request(`/categories/${id}`, { method: "DELETE" }),

  rules: () => request<Rule[]>("/rules"),
  createRule: (body: Omit<Rule, "id">) =>
    request<Rule>("/rules", { method: "POST", body: JSON.stringify(body) }),
  updateRule: (id: string, body: Partial<Rule>) =>
    request<Rule>(`/rules/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteRule: (id: string) => request(`/rules/${id}`, { method: "DELETE" }),
  reclassify: () => request<{ reclassified: number }>("/rules/reclassify", { method: "POST" }),
  suggestions: () => request<RuleSuggestion[]>("/rules/suggestions"),
  suggest: () =>
    request<{ ai_enabled: boolean; created: number; message?: string }>("/rules/suggest", {
      method: "POST",
    }),
  acceptSuggestion: (id: string, category_id: string, split_default: Split, priority = 100) =>
    request<Rule>(`/rules/suggestions/${id}/accept`, {
      method: "POST",
      body: JSON.stringify({ category_id, split_default, priority }),
    }),
  rejectSuggestion: (id: string) =>
    request(`/rules/suggestions/${id}/reject`, { method: "POST" }),

  transactions: (params: {
    period?: string;
    owner_user_id?: string;
    category_id?: string;
    only_unclassified?: boolean;
  }) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") q.set(k, String(v));
    });
    return request<Transaction[]>(`/transactions?${q.toString()}`);
  },
  createTransaction: (body: {
    date: string;
    description: string;
    amount: number;
    owner_user_id: string;
    category_id?: string | null;
    is_shared: boolean;
  }) => request<Transaction>("/transactions", { method: "POST", body: JSON.stringify(body) }),
  updateTransaction: (id: string, body: Partial<Transaction>) =>
    request<Transaction>(`/transactions/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteTransaction: (id: string) => request(`/transactions/${id}`, { method: "DELETE" }),

  previewImport: (file: File, owner_user_id: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("owner_user_id", owner_user_id);
    return request<ImportPreview>("/imports/preview", { method: "POST", body: form });
  },
  commitImport: (body: {
    filename: string;
    source: Source;
    owner_user_id: string;
    rows: ImportCommitRow[];
  }) => request<ImportSummary>("/imports/commit", { method: "POST", body: JSON.stringify(body) }),

  report: (period: string) => request<MonthlyReport>(`/reports/${period}`),
  cumulativeBalance: () => request<CumulativeBalance>("/reports/balance"),

  payments: (period?: string) =>
    request<Payment[]>(`/payments${period ? `?period=${period}` : ""}`),
  createPayment: (body: {
    date: string;
    from_user_id: string;
    to_user_id: string;
    amount: number;
    note?: string;
  }) => request<Payment>("/payments", { method: "POST", body: JSON.stringify(body) }),
  deletePayment: (id: string) => request(`/payments/${id}`, { method: "DELETE" }),
};

export function formatBRL(value: number): string {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value);
}

export function currentPeriod(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}
