import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Sparkles, Target, XCircle } from "lucide-react";
import { useState } from "react";

import { Markdown } from "@/components/Markdown";
import { Badge, Card, EmptyState, PageHeader, Spinner } from "@/components/ui";
import {
  api,
  currentPeriod,
  formatBRL,
  previousPeriod,
  type GoalProgress,
  type ReportProgress,
} from "@/lib/api";
import { shortPeriod } from "@/lib/chartPalette";
import { PeriodPicker } from "@/components/PeriodPicker";

function shiftPeriod(period: string, delta: number): string {
  const [year, month] = period.split("-").map(Number);
  const shifted = new Date(year, month - 1 + delta, 1);
  return `${shifted.getFullYear()}-${String(shifted.getMonth() + 1).padStart(2, "0")}`;
}

export function AiReportPage() {
  const { data: list, isLoading } = useQuery({
    queryKey: ["ai-reports"],
    queryFn: api.aiReports,
  });
  const [selected, setSelected] = useState<string | null>(null);
  const period =
    selected ??
    list?.find((r) => r.period === previousPeriod())?.period ??
    list?.[0]?.period ??
    previousPeriod();
  const previousReportPeriod = shiftPeriod(period, -1);

  const { data: report, isError: reportNotFound } = useQuery({
    queryKey: ["ai-report", period],
    queryFn: () => api.aiReport(period as string),
    enabled: !!period,
  });
  const { data: progress } = useQuery({
    queryKey: ["ai-progress", period],
    queryFn: () => api.aiReportProgress(period as string),
    enabled: !!period,
  });
  const { data: previousReport } = useQuery({
    queryKey: ["ai-report", previousReportPeriod],
    queryFn: () => api.aiReport(previousReportPeriod),
    enabled: !!period,
    retry: false,
  });
  const { data: previousProgress } = useQuery({
    queryKey: ["ai-progress", previousReportPeriod, period],
    queryFn: () => api.aiReportProgress(previousReportPeriod, period),
    enabled: !!previousReport,
    retry: false,
  });

  return (
    <div>
      <PageHeader
        title="Relatório IA"
        subtitle="Análise dos gastos, resultado das metas e próximo plano mensal"
        action={<PeriodPicker period={period} onChange={setSelected} />}
      />

      {isLoading && <Spinner />}
      {list && list.length === 0 && !report && !reportNotFound && <NoReports />}
      {reportNotFound && <NoReportForPeriod period={period} />}
      {report && (
        <div className="flex flex-col gap-6">
          {previousProgress && previousProgress.total_count > 0 && (
            <GoalsPanel
              title={`Como foram as metas de ${shortPeriod(period)}`}
              subtitle="Metas definidas no relatório do mês anterior"
              progress={previousProgress}
              review={report.previous_review_md}
            />
          )}

          <Card>
            <h2 className="mb-3 text-sm font-semibold text-gray-700">
              Análise de {shortPeriod(report.period)}
            </h2>
            <Markdown source={report.summary_md} />
          </Card>

          {progress && progress.total_count > 0 && (
            <GoalsPanel
              title={`Metas para ${shortPeriod(report.goals_period)}`}
              subtitle="O que acompanhar no novo mês"
              progress={progress}
            />
          )}

          <p className="text-center text-xs text-gray-400">
            Gerado por {report.generated_by} em{" "}
            {new Date(report.created_at).toLocaleString("pt-BR")}
          </p>
        </div>
      )}
    </div>
  );
}

function NoReports() {
  return (
    <EmptyState>
      <div className="flex flex-col items-center gap-2">
        <Sparkles className="h-8 w-8 text-gray-300" />
        <p>Nenhum relatório gerado ainda.</p>
        <p className="text-xs text-gray-400">
          Peça ao Claude Code:{" "}
          <code className="rounded bg-gray-100 px-1.5 py-0.5">/relatorio-financeiro</code>
        </p>
      </div>
    </EmptyState>
  );
}

function NoReportForPeriod({ period }: { period: string }) {
  return (
    <EmptyState>
      <div className="flex flex-col items-center gap-2">
        <Sparkles className="h-8 w-8 text-gray-300" />
        <p>Nenhum relatório encontrado para {shortPeriod(period)}.</p>
        <p className="text-xs text-gray-400">
          Use as setas para navegar para outro mês ou gere o relatório desse período.
        </p>
      </div>
    </EmptyState>
  );
}

function GoalsPanel({
  title,
  subtitle,
  progress,
  review,
}: {
  title: string;
  subtitle: string;
  progress: ReportProgress;
  review?: string | null;
}) {
  const pct = Math.round((100 * progress.achieved_count) / progress.total_count);
  // Duas checagens diferentes, e as duas importam:
  // - `started`: mês sem nenhum lançamento cumpre qualquer teto trivialmente.
  // - `closed`: no meio do mês o "economizou X" é só o baseline ainda não
  //   gasto. Economia só é economia depois que o mês fecha.
  const started = progress.transaction_count > 0;
  const closed = progress.period < currentPeriod();
  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Target className="h-5 w-5 text-indigo-600" />
          <h2 className="text-sm font-semibold text-gray-700">
            {title}
          </h2>
        </div>
        <div className="flex items-center gap-3 text-sm">
          {!started ? (
            <Badge tone="gray">mês ainda sem lançamentos</Badge>
          ) : (
            <>
              <span className="text-gray-500">
                {progress.achieved_count} de {progress.total_count}{" "}
                {closed ? "cumpridas" : "no rumo"} ({pct}%)
              </span>
              {closed ? (
                progress.total_saved_cents > 0 && (
                  <Badge tone="green">economia {formatBRL(progress.total_saved_cents)}</Badge>
                )
              ) : (
                <Badge tone="amber">mês em andamento</Badge>
              )}
            </>
          )}
        </div>
      </div>
      <p className="-mt-2 mb-4 text-xs text-gray-400">{subtitle}</p>

      <div className="flex flex-col gap-3">
        {progress.goals.map((g) => (
          <GoalRow key={g.goal.id} p={g} started={started} />
        ))}
      </div>
      {review && (
        <div className="mt-4 border-t border-gray-100 pt-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">
            Análise das metas
          </p>
          <Markdown source={review} />
        </div>
      )}
    </Card>
  );
}

function GoalRow({ p, started }: { p: GoalProgress; started: boolean }) {
  const isMoney = p.goal.metric !== "count_max";
  const fmt = (v: number) => (isMoney ? formatBRL(v) : `${v}×`);
  // Barra até 100% do teto; estourar preenche tudo e fica vermelha.
  const filled = p.target > 0 ? Math.min(100, Math.round((100 * p.actual) / p.target)) : 100;
  const ok = started && p.achieved;
  const failing = started && !p.achieved;
  const Icon = failing ? XCircle : CheckCircle2;

  return (
    <div className="rounded-lg border border-gray-100 p-3">
      <div className="mb-1.5 flex items-start justify-between gap-3">
        <div className="flex items-start gap-2">
          <Icon
            className={`mt-0.5 h-4 w-4 shrink-0 ${
              ok ? "text-emerald-600" : failing ? "text-red-500" : "text-gray-300"
            }`}
          />
          <div>
            <div className="text-sm font-medium text-gray-900">{p.goal.title}</div>
            <div className="text-xs text-gray-500">{p.goal.rationale}</div>
          </div>
        </div>
        <div className="whitespace-nowrap text-right text-sm">
          <span className={failing ? "font-medium text-red-600" : "font-medium text-gray-900"}>
            {fmt(p.actual)}
          </span>
          <span className="text-gray-400"> / {fmt(p.target)}</span>
        </div>
      </div>

      <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-100">
        <div
          className={`h-full rounded-full ${failing ? "bg-red-500" : "bg-emerald-500"}`}
          style={{ width: `${started ? filled : 0}%` }}
        />
      </div>

      <div className="mt-1.5 flex justify-between text-xs text-gray-400">
        <span>
          {p.goal.baseline_cents != null && isMoney
            ? `partiu de ${formatBRL(p.goal.baseline_cents)}`
            : p.goal.baseline_count != null
              ? `partiu de ${p.goal.baseline_count}×`
              : ""}
        </span>
        <span className={failing ? "text-red-500" : "text-emerald-600"}>
          {p.delta <= 0 ? `${fmt(-p.delta)} de folga` : `${fmt(p.delta)} acima`}
        </span>
      </div>
    </div>
  );
}
