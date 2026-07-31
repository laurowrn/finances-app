"""Cálculo do relatório mensal e do acerto proporcional ao salário.

Regras (ver plano):
- Só gastos COMPARTILHADOS entram no acerto.
- Cota justa de cada um = proporção do salário * total compartilhado.
- saldo = quanto a pessoa pagou de compartilhado - cota justa.
- Quem tem saldo negativo paga ao que tem saldo positivo a diferença.
- Gastos INDIVIDUAIS entram só no "quem gastou mais" (total por pessoa), fora do acerto.

As funções aqui são puras (sem Mongo) para facilitar os testes.
"""

from dataclasses import dataclass

from app.schemas.reports import (
    CategoryBreakdown,
    MonthlyReport,
    Settlement,
    UserReport,
)


@dataclass
class TxInput:
    owner_user_id: str
    amount: float
    is_shared: bool
    category_id: str | None
    category_name: str


@dataclass
class UserInput:
    id: str
    name: str
    income: float


def _round(value: float) -> float:
    return round(value + 1e-9, 2)


def compute_report(
    period: str,
    users: list[UserInput],
    transactions: list[TxInput],
) -> MonthlyReport:
    shared_total = _round(sum(t.amount for t in transactions if t.is_shared))
    total_income = sum(u.income for u in users)

    user_reports: list[UserReport] = []
    for u in users:
        shared_paid = _round(
            sum(t.amount for t in transactions if t.is_shared and t.owner_user_id == u.id)
        )
        individual_spent = _round(
            sum(t.amount for t in transactions if not t.is_shared and t.owner_user_id == u.id)
        )
        proportion = (u.income / total_income) if total_income > 0 else (1 / len(users))
        fair_share = _round(proportion * shared_total)
        balance = _round(shared_paid - fair_share)
        user_reports.append(
            UserReport(
                user_id=u.id,
                name=u.name,
                income=_round(u.income),
                proportion=round(proportion, 6),
                shared_paid=shared_paid,
                individual_spent=individual_spent,
                total_spent=_round(shared_paid + individual_spent),
                fair_share=fair_share,
                balance=balance,
            )
        )

    settlement = _compute_settlement(user_reports)
    by_category = _compute_by_category(transactions)

    return MonthlyReport(
        period=period,
        shared_total=shared_total,
        users=user_reports,
        settlement=settlement,
        by_category=by_category,
    )


def _compute_settlement(reports: list[UserReport]) -> Settlement:
    """Quem tem saldo negativo (pagou menos que a cota) paga ao de saldo positivo."""
    empty = Settlement(
        from_user_id=None,
        from_user_name=None,
        to_user_id=None,
        to_user_name=None,
        amount=0.0,
    )
    if not reports:
        return empty

    debtor = min(reports, key=lambda r: r.balance)  # mais negativo -> deve
    creditor = max(reports, key=lambda r: r.balance)  # mais positivo -> recebe
    amount = _round(min(-debtor.balance, creditor.balance))
    if amount <= 0.005 or debtor.user_id == creditor.user_id:
        return empty

    return Settlement(
        from_user_id=debtor.user_id,
        from_user_name=debtor.name,
        to_user_id=creditor.user_id,
        to_user_name=creditor.name,
        amount=amount,
    )


def _compute_by_category(transactions: list[TxInput]) -> list[CategoryBreakdown]:
    acc: dict[str, CategoryBreakdown] = {}
    for t in transactions:
        key = t.category_id or "__none__"
        if key not in acc:
            acc[key] = CategoryBreakdown(
                category_id=t.category_id,
                category_name=t.category_name,
                shared=0.0,
                individual=0.0,
                total=0.0,
            )
        row = acc[key]
        if t.is_shared:
            row.shared += t.amount
        else:
            row.individual += t.amount
        row.total += t.amount

    result = list(acc.values())
    for row in result:
        row.shared = _round(row.shared)
        row.individual = _round(row.individual)
        row.total = _round(row.total)
    result.sort(key=lambda r: r.total, reverse=True)
    return result
