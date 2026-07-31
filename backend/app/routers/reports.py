from fastapi import APIRouter, Depends

from app.auth import current_user_id
from app.repositories import categories as cat_repo
from app.repositories import payments as pay_repo
from app.repositories import transactions as tx_repo
from app.repositories import users as users_repo
from app.schemas.reports import CumulativeBalance, MonthlyReport, UserBalance
from app.services.settlement import (
    BalanceInput,
    PaymentInput,
    TxInput,
    UserInput,
    compute_report,
    compute_settlement_from_balances,
)

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(current_user_id)])


async def _user_inputs(period: str) -> list[UserInput]:
    users = await users_repo.list_users()
    incomes = {i["user_id"]: i["amount"] for i in await users_repo.list_incomes(period)}
    return [
        UserInput(
            id=u["id"],
            name=u["name"],
            income=incomes.get(u["id"], u.get("base_salary", 0.0)),
        )
        for u in users
    ]


async def _tx_inputs(period: str) -> list[TxInput]:
    categories = {c["id"]: c["name"] for c in await cat_repo.list_categories()}
    return [
        TxInput(
            owner_user_id=t["owner_user_id"],
            amount=t["amount"],
            is_shared=t["is_shared"],
            category_id=t.get("category_id"),
            category_name=categories.get(t.get("category_id"), "Sem categoria"),
        )
        for t in await tx_repo.transactions_for_report(period)
    ]


async def _payment_inputs(period: str) -> list[PaymentInput]:
    return [
        PaymentInput(
            from_user_id=p["from_user_id"],
            to_user_id=p["to_user_id"],
            amount=p["amount"],
        )
        for p in await pay_repo.list_payments(period)
    ]


@router.get("/balance", response_model=CumulativeBalance)
async def cumulative_balance():
    """Saldo devedor acumulado entre os usuários, somando o desbalanceamento
    (já líquido de pagamentos) de todos os períodos com transações."""
    users = await users_repo.list_users()
    periods = await tx_repo.distinct_periods()

    running = {u["id"]: 0.0 for u in users}
    for period in periods:
        report = compute_report(
            period,
            await _user_inputs(period),
            await _tx_inputs(period),
            await _payment_inputs(period),
        )
        for ur in report.users:
            running[ur.user_id] = running.get(ur.user_id, 0.0) + ur.balance

    balances = [
        UserBalance(user_id=u["id"], name=u["name"], balance=round(running[u["id"]] + 1e-9, 2))
        for u in users
    ]
    settlement = compute_settlement_from_balances(
        [BalanceInput(user_id=b.user_id, name=b.name, balance=b.balance) for b in balances]
    )
    return CumulativeBalance(
        as_of_period=periods[-1] if periods else "",
        balances=balances,
        settlement=settlement,
    )


@router.get("/{period}", response_model=MonthlyReport)
async def monthly_report(period: str):
    return compute_report(
        period,
        await _user_inputs(period),
        await _tx_inputs(period),
        await _payment_inputs(period),
    )
