from pydantic import BaseModel


class UserReport(BaseModel):
    user_id: str
    name: str
    income: float
    proportion: float  # fração 0..1 do salário total
    shared_paid: float  # quanto pagou de gastos compartilhados
    individual_spent: float  # gastos individuais (fora do acerto)
    total_spent: float  # shared_paid + individual_spent
    fair_share: float  # cota justa proporcional dos compartilhados
    balance: float  # shared_paid - fair_share (positivo = pagou a mais)


class CategoryBreakdown(BaseModel):
    category_id: str | None
    category_name: str
    shared: float
    individual: float
    total: float


class Settlement(BaseModel):
    from_user_id: str | None
    from_user_name: str | None
    to_user_id: str | None
    to_user_name: str | None
    amount: float


class MonthlyReport(BaseModel):
    period: str
    shared_total: float
    users: list[UserReport]
    settlement: Settlement
    by_category: list[CategoryBreakdown]


class UserBalance(BaseModel):
    user_id: str
    name: str
    balance: float  # saldo acumulado até o último período com transações


class CumulativeBalance(BaseModel):
    as_of_period: str
    balances: list[UserBalance]
    settlement: Settlement
