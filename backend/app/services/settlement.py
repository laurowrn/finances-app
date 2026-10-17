"""Cálculo do relatório mensal e do acerto proporcional ao salário.

Regras (ver plano):
- Só gastos COMPARTILHADOS entram no acerto.
- Cota justa de cada um = proporção do salário * total compartilhado.
- saldo = quanto a pessoa pagou de compartilhado - cota justa.
- Quem tem saldo negativo paga ao que tem saldo positivo a diferença.
- Gastos INDIVIDUAIS entram só no "quem gastou mais" (total por pessoa), fora do acerto.

O relatório mensal olha APENAS para os gastos do período: pagamentos entre as
pessoas não abatem o acerto do mês. O abatimento acontece no saldo acumulado
(ver `routers/reports.py::cumulative_balance`), que é onde vive o "quanto ainda
falta pagar".

Todo valor aqui é `Cents` (int) — ver `app.services.money`. As cotas saem de
`allocate()`, então a soma das cotas é exatamente o total compartilhado: não
existe centavo órfão, nem quando a proporção é dízima.

As funções aqui são puras (sem Mongo) para facilitar os testes.
"""

from dataclasses import dataclass

from app.schemas.reports import (
    CategoryBreakdown,
    MonthlyReport,
    Settlement,
    UserReport,
)
from app.services.money import Cents, allocate


@dataclass
class TxInput:
    owner_user_id: str
    amount_cents: Cents
    is_shared: bool
    category_id: str | None
    category_name: str


@dataclass
class UserInput:
    id: str
    name: str
    income_cents: Cents


@dataclass
class PaymentInput:
    from_user_id: str
    to_user_id: str
    amount_cents: Cents


@dataclass
class BalanceInput:
    user_id: str
    name: str
    balance_cents: Cents


def compute_report(
    period: str,
    users: list[UserInput],
    transactions: list[TxInput],
) -> MonthlyReport:
    shared_total = sum(t.amount_cents for t in transactions if t.is_shared)

    # A cota justa é rateada de uma vez só, proporcional à renda. `allocate`
    # devolve partes que somam exatamente `shared_total` — arredondar cada cota
    # isoladamente é o que faria sobrar/faltar centavo.
    fair_shares = allocate(shared_total, [u.income_cents for u in users])
    total_income = sum(u.income_cents for u in users)

    user_reports: list[UserReport] = []
    for u, fair_share in zip(users, fair_shares, strict=True):
        shared_paid = sum(
            t.amount_cents for t in transactions if t.is_shared and t.owner_user_id == u.id
        )
        individual_spent = sum(
            t.amount_cents for t in transactions if not t.is_shared and t.owner_user_id == u.id
        )
        proportion = (u.income_cents / total_income) if total_income > 0 else (1 / len(users))
        user_reports.append(
            UserReport(
                user_id=u.id,
                name=u.name,
                income_cents=u.income_cents,
                proportion=round(proportion, 6),
                shared_paid_cents=shared_paid,
                individual_spent_cents=individual_spent,
                total_spent_cents=shared_paid + individual_spent,
                fair_share_cents=fair_share,
                balance_cents=shared_paid - fair_share,
            )
        )

    return MonthlyReport(
        period=period,
        shared_total_cents=shared_total,
        users=user_reports,
        settlement=_compute_settlement(user_reports),
        by_category=_compute_by_category(transactions),
    )


def apply_payments(balances: dict[str, Cents], payments: list[PaymentInput]) -> dict[str, Cents]:
    """Abate os pagamentos de um mapa user_id -> saldo acumulado.

    Quem paga sobe (passa a dever menos), quem recebe desce. Fica fora do
    `compute_report` de propósito: o acerto do mês reflete só os gastos.
    """
    out = dict(balances)
    for p in payments:
        out[p.from_user_id] = out.get(p.from_user_id, 0) + p.amount_cents
        out[p.to_user_id] = out.get(p.to_user_id, 0) - p.amount_cents
    return out


def compute_settlement_from_balances(balances: list[BalanceInput]) -> Settlement:
    """Quem tem saldo negativo (deve) paga ao de saldo positivo (tem a receber)."""
    empty = Settlement(
        from_user_id=None,
        from_user_name=None,
        to_user_id=None,
        to_user_name=None,
        amount_cents=0,
    )
    if not balances:
        return empty

    debtor = min(balances, key=lambda b: b.balance_cents)  # mais negativo -> deve
    creditor = max(balances, key=lambda b: b.balance_cents)  # mais positivo -> recebe
    amount = min(-debtor.balance_cents, creditor.balance_cents)
    if amount <= 0 or debtor.user_id == creditor.user_id:
        return empty

    return Settlement(
        from_user_id=debtor.user_id,
        from_user_name=debtor.name,
        to_user_id=creditor.user_id,
        to_user_name=creditor.name,
        amount_cents=amount,
    )


def _compute_settlement(reports: list[UserReport]) -> Settlement:
    return compute_settlement_from_balances(
        [
            BalanceInput(user_id=r.user_id, name=r.name, balance_cents=r.balance_cents)
            for r in reports
        ]
    )


def _compute_by_category(transactions: list[TxInput]) -> list[CategoryBreakdown]:
    acc: dict[str, CategoryBreakdown] = {}
    for t in transactions:
        key = t.category_id or "__none__"
        if key not in acc:
            acc[key] = CategoryBreakdown(
                category_id=t.category_id,
                category_name=t.category_name,
                shared_cents=0,
                individual_cents=0,
                total_cents=0,
            )
        row = acc[key]
        if t.is_shared:
            row.shared_cents += t.amount_cents
        else:
            row.individual_cents += t.amount_cents
        row.total_cents += t.amount_cents

    result = list(acc.values())
    result.sort(key=lambda r: r.total_cents, reverse=True)
    return result
