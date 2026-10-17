"""Relatório de IA: dossiê de entrada, relatório gravado e metas verificáveis.

A decisão de design que sustenta tudo: **uma meta é uma expressão que o servidor
sabe avaliar sozinho**, não uma frase. "Gastar menos no mercado" não é meta;
`category_max(Mercado) <= 200000` é. Assim o "cumpriu ou não" sai dos dados, não
de uma releitura do texto pela IA — que poderia julgar diferente a cada vez.

Todo valor é `int` de centavos (ver `app.services.money`).
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class GoalMetric(StrEnum):
    """O que a meta mede. Toda variante é checável com uma query."""

    CATEGORY_MAX = "category_max"  # gasto na categoria <= target_cents
    TOTAL_MAX = "total_max"  # gasto total do mês <= target_cents
    MERCHANT_MAX = "merchant_max"  # gasto cuja descrição casa `match` <= target_cents
    COUNT_MAX = "count_max"  # nº de lançamentos (categoria e/ou match) <= target_count


class Goal(BaseModel):
    """Meta SMART. Os campos cobrem os cinco pontos:

    - eSpecífica: `title` + `metric` + `category_id`/`match`
    - Mensurável: `target_cents` / `target_count`
    - Atingível: `baseline_*` mostra de onde está saindo
    - Relevante: `rationale`
    - Temporal: o `goals_period` do relatório
    """

    id: str = Field(description="slug estável, ex.: 'mercado-cooper'")
    title: str
    metric: GoalMetric
    category_id: str | None = None
    match: str | None = Field(
        default=None,
        description="Trecho da descrição, comparado já normalizado (sem acento/caixa).",
    )
    target_cents: int | None = Field(default=None, ge=0)
    target_count: int | None = Field(default=None, ge=0)
    baseline_cents: int | None = Field(default=None, ge=0)
    baseline_count: int | None = Field(default=None, ge=0)
    rationale: str


class GoalProgress(BaseModel):
    goal: Goal
    actual_cents: int | None
    actual_count: int | None
    target: int  # o alvo que vale para esta métrica (centavos ou contagem)
    actual: int  # o realizado, na mesma unidade do alvo
    achieved: bool
    delta: int  # realizado - alvo; negativo é bom (ficou abaixo)
    saved_cents: int | None  # baseline - realizado, quando a métrica é em dinheiro


class ReportProgress(BaseModel):
    period: str  # mês avaliado (o alvo das metas)
    goals: list[GoalProgress]
    achieved_count: int
    total_count: int
    total_saved_cents: int  # soma das economias das metas em dinheiro (só as positivas)
    # Quantos lançamentos existem no mês avaliado. Meta de teto é trivialmente
    # cumprida num mês vazio — sem este número, um mês que ainda não começou
    # apareceria como "tudo cumprido, economizamos X".
    transaction_count: int


class AiReportCreate(BaseModel):
    period: str = Field(description='mês analisado, "YYYY-MM"')
    goals_period: str = Field(description='mês alvo das metas, "YYYY-MM"')
    summary_md: str = Field(description="o relatório em markdown")
    goals: list[Goal] = Field(default_factory=list)
    previous_review_md: str | None = Field(
        default=None, description="avaliação das metas do relatório anterior"
    )
    generated_by: str = "claude-code"


class AiReportOut(AiReportCreate):
    id: str
    created_at: datetime


class AiReportSummary(BaseModel):
    """Item de listagem — sem o markdown, que é grande."""

    id: str
    period: str
    goals_period: str
    created_at: datetime
    generated_by: str
    goal_count: int


# ---------- Dossiê de entrada ----------


class CategoryStat(BaseModel):
    category_id: str | None
    category_name: str
    total_cents: int
    count: int
    share_pct: float
    by_user: dict[str, int]  # nome -> centavos
    history_cents: dict[str, int]  # "YYYY-MM" -> centavos, meses anteriores
    average_cents: int  # média dos meses anteriores (0 se não houver)


class MerchantStat(BaseModel):
    key: str
    total_cents: int
    count: int
    avg_ticket_cents: int


class InstallmentStat(BaseModel):
    description: str
    amount_cents: int
    current: int
    total: int
    remaining: int
    remaining_cents: int


class TransactionBrief(BaseModel):
    date: str
    description: str
    amount_cents: int
    category_name: str
    user_name: str


class AnalysisDossier(BaseModel):
    """Tudo que a análise precisa, num request só.

    É deliberadamente pré-agregado: a skill não deve varrer transação por
    transação nem refazer somas — os números vêm prontos e conferidos.
    """

    period: str
    generated_at: datetime
    total_cents: int
    transaction_count: int
    ignored_cents: int
    ignored_count: int
    income_cents: int
    income_by_user: dict[str, int]
    spend_pct_of_income: float
    surplus_cents: int
    by_user: dict[str, int]
    by_category: list[CategoryStat]
    top_merchants: list[MerchantStat]
    recurring: list[TransactionBrief]  # assinaturas, academia, internet
    installments: list[InstallmentStat]
    installment_tail_cents: int
    largest: list[TransactionBrief]
    monthly_totals: dict[str, int]  # série histórica "YYYY-MM" -> centavos
    settlement_from: str | None
    settlement_to: str | None
    settlement_cents: int
    data_warnings: list[str]  # ex.: mês sem renda cadastrada
