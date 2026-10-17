"""Relatório de IA: dossiê de entrada, gravação do relatório e conferência das metas.

O modelo de execução aqui é diferente do resto do app. Não há chamada a LLM no
servidor — quem analisa é um agente externo (Claude Code, via a skill
`relatorio-financeiro`), que lê `/ai/analysis/{period}`, escreve o relatório e
o devolve em `POST /ai/reports`. O backend é a fonte dos números e o juiz das
metas; o agente é o autor do texto.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import current_user_id
from app.repositories import ai_reports as report_repo
from app.repositories import categories as cat_repo
from app.repositories import transactions as tx_repo
from app.repositories import users as users_repo
from app.schemas.ai import (
    AiReportCreate,
    AiReportOut,
    AiReportSummary,
    AnalysisDossier,
    ReportProgress,
)
from app.services import insights
from app.services.settlement import TxInput, UserInput, compute_report

router = APIRouter(prefix="/ai", tags=["ai"], dependencies=[Depends(current_user_id)])

HISTORY_MONTHS = 5


def _shift(period: str, delta: int) -> str:
    y, m = (int(x) for x in period.split("-"))
    total = y * 12 + (m - 1) + delta
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


@router.get("/analysis/{period}", response_model=AnalysisDossier)
async def analysis(period: str):
    """Dossiê pré-agregado do mês. É a única leitura que a skill precisa fazer
    para escrever o relatório — os números já vêm somados e conferidos."""
    users = await users_repo.list_users()
    user_name = {u["id"]: u["name"] for u in users}
    categories = await cat_repo.list_categories()
    category_name: dict[str | None, str] = {c["id"]: c["name"] for c in categories}
    category_name[None] = "Sem categoria"

    rows = await tx_repo.transactions_for_report(period)
    all_rows = await tx_repo.transactions_in_period(period)
    ignored = [r for r in all_rows if r.get("is_ignored")]

    total = sum(r["amount_cents"] for r in rows)

    incomes = {i["user_id"]: i["amount_cents"] for i in await users_repo.list_incomes(period)}
    income_by_user = {
        u["name"]: incomes.get(u["id"], u.get("base_salary_cents", 0)) for u in users
    }
    income_total = sum(income_by_user.values())

    warnings: list[str] = []
    if not incomes:
        warnings.append(
            f"Nenhuma renda cadastrada para {period}; usando o salário base de cada um."
        )
    if not rows:
        warnings.append(f"Nenhum lançamento em {period}.")

    history_periods = [_shift(period, -i) for i in range(HISTORY_MONTHS, 0, -1)]
    history: dict[str, dict[str | None, int]] = {}
    monthly_totals: dict[str, int] = {}
    for p in history_periods:
        prev = await tx_repo.transactions_for_report(p)
        per: dict[str | None, int] = {}
        for r in prev:
            per[r.get("category_id")] = per.get(r.get("category_id"), 0) + r["amount_cents"]
        history[p] = per
        monthly_totals[p] = sum(r["amount_cents"] for r in prev)
    monthly_totals[period] = total

    by_user: dict[str, int] = {}
    for r in rows:
        name = user_name.get(r["owner_user_id"], "?")
        by_user[name] = by_user.get(name, 0) + r["amount_cents"]

    recurring_ids = {
        c["id"] for c in categories if c["name"] in insights.RECURRING_CATEGORIES
    }
    recurring_rows = sorted(
        (r for r in rows if r.get("category_id") in recurring_ids),
        key=lambda r: -r["amount_cents"],
    )
    installments, tail = insights.installment_stats(rows)
    largest = sorted(rows, key=lambda r: -r["amount_cents"])[:15]

    report = compute_report(
        period,
        [
            UserInput(
                id=u["id"],
                name=u["name"],
                income_cents=incomes.get(u["id"], u.get("base_salary_cents", 0)),
            )
            for u in users
        ],
        [
            TxInput(
                owner_user_id=r["owner_user_id"],
                amount_cents=r["amount_cents"],
                is_shared=r["is_shared"],
                category_id=r.get("category_id"),
                category_name=category_name.get(r.get("category_id"), "Sem categoria"),
            )
            for r in rows
        ],
    )

    return AnalysisDossier(
        period=period,
        generated_at=datetime.now(UTC),
        total_cents=total,
        transaction_count=len(rows),
        ignored_cents=sum(r["amount_cents"] for r in ignored),
        ignored_count=len(ignored),
        income_cents=income_total,
        income_by_user=income_by_user,
        spend_pct_of_income=round(100 * total / income_total, 1) if income_total else 0.0,
        surplus_cents=income_total - total,
        by_user=by_user,
        by_category=insights.category_stats(rows, category_name, user_name, history),
        top_merchants=insights.merchant_stats(rows),
        recurring=insights.to_brief(recurring_rows, category_name, user_name),
        installments=installments,
        installment_tail_cents=tail,
        largest=insights.to_brief(largest, category_name, user_name),
        monthly_totals=monthly_totals,
        settlement_from=report.settlement.from_user_name,
        settlement_to=report.settlement.to_user_name,
        settlement_cents=report.settlement.amount_cents,
        data_warnings=warnings,
    )


@router.get("/reports", response_model=list[AiReportSummary])
async def list_reports():
    return [
        AiReportSummary(
            id=r["id"],
            period=r["period"],
            goals_period=r["goals_period"],
            created_at=r["created_at"],
            generated_by=r.get("generated_by", "?"),
            goal_count=len(r.get("goals", [])),
        )
        for r in await report_repo.list_reports()
    ]


@router.get("/reports/latest", response_model=AiReportOut)
async def get_latest():
    doc = await report_repo.latest_report()
    if doc is None:
        raise HTTPException(status_code=404, detail="Nenhum relatório gerado ainda")
    return AiReportOut(**doc)


@router.post("/reports", response_model=AiReportOut)
async def create_report(body: AiReportCreate):
    """Grava o relatório. Regravar o mesmo `period` substitui o anterior."""
    if len({g.id for g in body.goals}) != len(body.goals):
        raise HTTPException(status_code=400, detail="ids de meta duplicados")
    return AiReportOut(**await report_repo.upsert_report(body.model_dump()))


@router.get("/reports/{period}", response_model=AiReportOut)
async def get_report(period: str):
    doc = await report_repo.get_report(period)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Sem relatório para {period}")
    return AiReportOut(**doc)


@router.delete("/reports/{period}", status_code=204)
async def delete_report(period: str):
    if not await report_repo.delete_report(period):
        raise HTTPException(status_code=404, detail=f"Sem relatório para {period}")


@router.get("/reports/{period}/progress", response_model=ReportProgress)
async def report_progress(period: str, against: str | None = Query(default=None)):
    """Confere as metas do relatório de `period` contra os lançamentos reais.

    Por padrão avalia contra o `goals_period` do próprio relatório (o mês
    seguinte). `against` permite conferir contra outro mês — útil para
    acompanhar o mês corrente antes de ele fechar.
    """
    doc = await report_repo.get_report(period)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Sem relatório para {period}")

    target = against or doc["goals_period"]
    rows = await tx_repo.transactions_for_report(target)
    goals = [g if hasattr(g, "metric") else _as_goal(g) for g in doc.get("goals", [])]
    return insights.evaluate_report(target, goals, rows)


def _as_goal(raw: dict):
    from app.schemas.ai import Goal

    return Goal(**raw)
