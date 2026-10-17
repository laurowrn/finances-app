"""Todo valor monetário é `int` de centavos — ver `app.services.money`.

O sufixo `_cents` no nome do campo é proposital: deixa explícito na API que o
número não é reais, e torna impossível somar por engano um valor em reais.
"""

from pydantic import BaseModel


class UserReport(BaseModel):
    user_id: str
    name: str
    income_cents: int
    proportion: float  # fração 0..1 do salário total — razão, não dinheiro
    shared_paid_cents: int  # quanto pagou de gastos compartilhados
    individual_spent_cents: int  # gastos individuais (fora do acerto)
    total_spent_cents: int  # shared_paid + individual_spent
    fair_share_cents: int  # cota justa proporcional dos compartilhados
    balance_cents: int  # shared_paid - fair_share (positivo = pagou a mais); sem pagamentos


class CategoryBreakdown(BaseModel):
    category_id: str | None
    category_name: str
    shared_cents: int
    individual_cents: int
    total_cents: int


class Settlement(BaseModel):
    from_user_id: str | None
    from_user_name: str | None
    to_user_id: str | None
    to_user_name: str | None
    amount_cents: int


class MonthlyReport(BaseModel):
    period: str
    shared_total_cents: int
    users: list[UserReport]
    settlement: Settlement
    by_category: list[CategoryBreakdown]


class UserBalance(BaseModel):
    user_id: str
    name: str
    balance_cents: int  # gastos de todos os meses, já abatidos os pagamentos


class CumulativeBalance(BaseModel):
    as_of_period: str
    balances: list[UserBalance]
    settlement: Settlement


# ---------- Evolução mês a mês ----------


class TrendUserPoint(BaseModel):
    user_id: str
    name: str
    total_spent_cents: int  # compartilhado + individual
    shared_paid_cents: int
    balance_cents: int


class TrendCategoryPoint(BaseModel):
    category_id: str | None
    category_name: str
    total_cents: int


class TrendPoint(BaseModel):
    period: str
    shared_total_cents: int
    individual_total_cents: int
    total_cents: int
    users: list[TrendUserPoint]
    by_category: list[TrendCategoryPoint]


class TrendReport(BaseModel):
    """Série mensal para acompanhar a variação dos gastos."""

    points: list[TrendPoint]  # ordem cronológica
    categories: list[str]  # nomes de categoria, das que mais pesam para as que menos
    average_total_cents: int  # média mensal do gasto total no intervalo
