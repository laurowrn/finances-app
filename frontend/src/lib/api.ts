import type { Cents } from "@/lib/money";

// Dinheiro vive em money.ts; reexportado aqui porque as telas já importam daqui.
export { centsToInput, formatBRL, parseBRLToCents } from "@/lib/money";
export type { Cents } from "@/lib/money";

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

// "ignored": lançamento fica no histórico mas fora do relatório e do acerto.
export type Split = "shared" | "individual" | "ignored";
export type Source = "ofx" | "csv" | "pdf" | "manual";
export type StatementType = "account" | "credit_card";
export type Institution = "nubank" | "itau" | "other" | "unknown";
export type MatchOp = "contains" | "equals" | "regex";

export interface User {
  id: string;
  name: string;
  base_salary_cents: number;
  is_admin?: boolean;
}

export interface DeployStatus {
  status: "idle" | "queued" | "running" | "success" | "failed" | "unknown";
  commit?: string;
  updated_at?: string;
  message?: string;
}

export interface AdminConfig {
  environment: string;
  ai_enabled: boolean;
  ai_model: string | null;
  cors_origins: string[];
  values: Record<string, { secret: boolean; configured: boolean; value: string | null }>;
  note: string;
}

export interface SecretMetadata {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
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
  amount_cents: Cents;
  owner_user_id: string;
  category_id: string | null;
  is_shared: boolean;
  is_ignored: boolean;
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
  amount_cents: Cents;
  category_id: string | null;
  is_shared: boolean;
  is_ignored: boolean;
  classified_by: string;
  rule_id: string | null;
  is_duplicate: boolean;
}

export interface ImportPreview {
  filename: string;
  source: Source;
  owner_user_id: string;
  rows: ImportPreviewRow[];
  detected_start: string | null;
  detected_end: string | null;
}

export interface ImportBatch {
  id: string;
  filename: string;
  source: Source;
  owner_user_id: string;
  institution: Institution;
  statement_type: StatementType | null;
  statement_start: string | null;
  statement_end: string | null;
  created_at: string;
  counts: Record<string, number>;
}
export interface CoverageIssue { kind: "gap" | "overlap"; start: string; end: string; previous_filename: string; filename: string; }
export interface Coverage { owner_user_id: string; statement_type: StatementType; institution: Institution; batches: ImportBatch[]; gaps: CoverageIssue[]; overlaps: CoverageIssue[]; }

export interface ImportCommitRow {
  date: string;
  description: string;
  amount_cents: Cents;
  category_id: string | null;
  is_shared: boolean;
  is_ignored: boolean;
  classified_by: string;
  rule_id: string | null;
}

export interface UserReport {
  user_id: string;
  name: string;
  income_cents: Cents;
  proportion: number;
  shared_paid_cents: Cents;
  individual_spent_cents: Cents;
  total_spent_cents: Cents;
  fair_share_cents: Cents;
  balance_cents: Cents;
}

export interface CategoryBreakdown {
  category_id: string | null;
  category_name: string;
  shared_cents: Cents;
  individual_cents: Cents;
  total_cents: Cents;
}

export interface Settlement {
  from_user_id: string | null;
  from_user_name: string | null;
  to_user_id: string | null;
  to_user_name: string | null;
  amount_cents: Cents;
}

export interface MonthlyReport {
  period: string;
  shared_total_cents: Cents;
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
  amount_cents: Cents;
  note: string | null;
  created_at: string;
}

export interface UserBalance {
  user_id: string;
  name: string;
  balance_cents: Cents;
}

export interface CumulativeBalance {
  as_of_period: string;
  balances: UserBalance[];
  settlement: Settlement;
}

export interface TrendUserPoint {
  user_id: string;
  name: string;
  total_spent_cents: Cents;
  shared_paid_cents: Cents;
  balance_cents: Cents;
}

export interface TrendCategoryPoint {
  category_id: string | null;
  category_name: string;
  total_cents: Cents;
}

export interface TrendPoint {
  period: string;
  shared_total_cents: Cents;
  individual_total_cents: Cents;
  total_cents: Cents;
  users: TrendUserPoint[];
  by_category: TrendCategoryPoint[];
}

export interface TrendReport {
  points: TrendPoint[];
  categories: string[];
  average_total_cents: Cents;
}

// ---------- Relatório de IA ----------

export type GoalMetric = "category_max" | "total_max" | "merchant_max" | "count_max";

export interface Goal {
  id: string;
  title: string;
  metric: GoalMetric;
  category_id: string | null;
  match: string | null;
  target_cents: Cents | null;
  target_count: number | null;
  baseline_cents: Cents | null;
  baseline_count: number | null;
  rationale: string;
}

export interface GoalProgress {
  goal: Goal;
  actual_cents: Cents | null;
  actual_count: number | null;
  target: number;
  actual: number;
  achieved: boolean;
  delta: number;
  saved_cents: Cents | null;
}

export interface ReportProgress {
  period: string;
  goals: GoalProgress[];
  achieved_count: number;
  total_count: number;
  total_saved_cents: Cents;
  /** Lançamentos no mês avaliado. Zero significa "mês ainda não começou" —
   *  metas de teto ficam trivialmente cumpridas e o número não vale nada. */
  transaction_count: number;
}

export interface AiReport {
  id: string;
  period: string;
  goals_period: string;
  summary_md: string;
  goals: Goal[];
  previous_review_md: string | null;
  generated_by: string;
  created_at: string;
}

export interface AiReportSummary {
  id: string;
  period: string;
  goals_period: string;
  created_at: string;
  generated_by: string;
  goal_count: number;
}

// ---------- Endpoints ----------

export const api = {
  publicUsers: () => request<User[]>("/auth/users"),
  login: (user_id: string, password: string) =>
    request<{ access_token: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ user_id, password }),
    }),

  adminStatus: () => request<DeployStatus>("/admin/status"),
  triggerAdminDeploy: () =>
    request<{ status: string; requested_at: string }>("/admin/deploy", { method: "POST" }),
  adminConfig: () => request<AdminConfig>("/admin/config"),
  updateAdminConfig: (key: string, body: { value?: string; clear?: boolean }) =>
    request<{ key: string; configured: boolean }>(`/admin/config/${key}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  secrets: () => request<SecretMetadata[]>("/admin/secrets"),
  createSecret: (body: { name: string; value: string; description?: string }) =>
    request<SecretMetadata>("/admin/secrets", { method: "POST", body: JSON.stringify(body) }),
  updateSecret: (id: string, body: { name?: string; value?: string; description?: string }) =>
    request<SecretMetadata>(`/admin/secrets/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteSecret: (id: string) => request(`/admin/secrets/${id}`, { method: "DELETE" }),

  users: () => request<User[]>("/users"),
  updateUser: (id: string, body: Partial<User>) =>
    request<User>(`/users/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  incomes: (period: string) =>
    request<{ user_id: string; period: string; amount_cents: number }[]>(
      `/users/incomes/${period}`,
    ),
  upsertIncome: (user_id: string, period: string, amount_cents: Cents) =>
    request(`/users/incomes`, {
      method: "PUT",
      body: JSON.stringify({ user_id, period, amount_cents }),
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
    amount_cents: Cents;
    owner_user_id: string;
    category_id?: string | null;
    is_shared: boolean;
    is_ignored?: boolean;
  }) => request<Transaction>("/transactions", { method: "POST", body: JSON.stringify(body) }),
  updateTransaction: (id: string, body: Partial<Transaction>) =>
    request<Transaction>(`/transactions/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteTransaction: (id: string) => request(`/transactions/${id}`, { method: "DELETE" }),

  previewImport: (file: File, owner_user_id: string, statement_start?: string, statement_end?: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("owner_user_id", owner_user_id);
    if (statement_start) form.append("statement_start", statement_start);
    if (statement_end) form.append("statement_end", statement_end);
    return request<ImportPreview>("/imports/preview", { method: "POST", body: form });
  },
  commitImport: (body: {
    filename: string;
    source: Source;
    owner_user_id: string;
    statement_type: StatementType;
    institution: Institution;
    statement_start?: string;
    statement_end?: string;
    rows: ImportCommitRow[];
  }) => request<ImportSummary>("/imports/commit", { method: "POST", body: JSON.stringify(body) }),
  importCoverage: (owner_user_id: string, statement_type: StatementType, institution: Institution) =>
    request<Coverage>(`/imports/coverage?owner_user_id=${encodeURIComponent(owner_user_id)}&statement_type=${statement_type}&institution=${institution}`),

  report: (period: string) => request<MonthlyReport>(`/reports/${period}`),
  cumulativeBalance: () => request<CumulativeBalance>("/reports/balance"),
  trend: (months: number) => request<TrendReport>(`/reports/trend?months=${months}`),

  payments: (period?: string) =>
    request<Payment[]>(`/payments${period ? `?period=${period}` : ""}`),
  createPayment: (body: {
    date: string;
    from_user_id: string;
    to_user_id: string;
    amount_cents: Cents;
    note?: string;
  }) => request<Payment>("/payments", { method: "POST", body: JSON.stringify(body) }),
  deletePayment: (id: string) => request(`/payments/${id}`, { method: "DELETE" }),

  aiReports: () => request<AiReportSummary[]>("/ai/reports"),
  aiReport: (period: string) => request<AiReport>(`/ai/reports/${period}`),
  aiReportProgress: (period: string, against?: string) =>
    request<ReportProgress>(
      `/ai/reports/${period}/progress${against ? `?against=${encodeURIComponent(against)}` : ""}`,
    ),
};

function toPeriod(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function currentPeriod(): string {
  return toPeriod(new Date());
}

/** Mês fechado — é sobre ele que o acerto das contas acontece. */
export function previousPeriod(): string {
  const now = new Date();
  return toPeriod(new Date(now.getFullYear(), now.getMonth() - 1, 1));
}
