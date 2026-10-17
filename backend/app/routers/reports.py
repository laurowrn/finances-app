from fastapi import APIRouter, Depends, Query

from app.auth import current_user_id
from app.repositories import categories as cat_repo
from app.repositories import payments as pay_repo
from app.repositories import transactions as tx_repo
from app.repositories import users as users_repo
from app.schemas.reports import (
    CumulativeBalance,
    MonthlyReport,
    TrendCategoryPoint,
    TrendPoint,
    TrendReport,
    TrendUserPoint,
    UserBalance,
)
from app.services.settlement import (
    BalanceInput,
    PaymentInput,
    TxInput,
    UserInput,
    apply_payments,
    compute_report,
    compute_settlement_from_balances,
)

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(current_user_id)])


async def _user_inputs(period: str) -> list[UserInput]:
    users = await users_repo.list_users()
    incomes = {i["user_id"]: i["amount_cents"] for i in await users_repo.list_incomes(period)}
    return [
        UserInput(
            id=u["id"],
            name=u["name"],
            income_cents=incomes.get(u["id"], u.get("base_salary_cents", 0)),
        )
        for u in users
    ]


async def _tx_inputs(period: str) -> list[TxInput]:
    categories = {c["id"]: c["name"] for c in await cat_repo.list_categories()}
    return [
        TxInput(
            owner_user_id=t["owner_user_id"],
            amount_cents=t["amount_cents"],
            is_shared=t["is_shared"],
            category_id=t.get("category_id"),
            category_name=categories.get(t.get("category_id"), "Sem categoria"),
        )
        for t in await tx_repo.transactions_for_report(period)
    ]


async def _payment_inputs(period: str | None = None) -> list[PaymentInput]:
    """Sem período, devolve os pagamentos de todos os tempos."""
    return [
        PaymentInput(
            from_user_id=p["from_user_id"],
            to_user_id=p["to_user_id"],
            amount_cents=p["amount_cents"],
        )
        for p in await pay_repo.list_payments(period)
    ]


@router.get("/balance", response_model=CumulativeBalance)
async def cumulative_balance():
    """Saldo devedor acumulado: o desbalanceamento de gastos de todos os meses,
    abatido de todos os pagamentos já registrados.

    É aqui — e não no relatório mensal — que os pagamentos entram. Por isso o
    abatimento é global: um pagamento pode cair num mês sem nenhuma transação
    (ex.: acerto feito depois do último import) e ainda assim precisa contar."""
    users = await users_repo.list_users()
    tx_periods = await tx_repo.distinct_periods()

    running = {u["id"]: 0 for u in users}
    for period in tx_periods:
        report = compute_report(period, await _user_inputs(period), await _tx_inputs(period))
        for ur in report.users:
            running[ur.user_id] = running.get(ur.user_id, 0) + ur.balance_cents

    running = apply_payments(running, await _payment_inputs())

    periods = sorted(set(tx_periods) | set(await pay_repo.distinct_periods()))
    balances = [
        UserBalance(user_id=u["id"], name=u["name"], balance_cents=running[u["id"]])
        for u in users
    ]
    settlement = compute_settlement_from_balances(
        [
            BalanceInput(user_id=b.user_id, name=b.name, balance_cents=b.balance_cents)
            for b in balances
        ]
    )
    return CumulativeBalance(
        as_of_period=periods[-1] if periods else "",
        balances=balances,
        settlement=settlement,
    )


@router.get("/trend", response_model=TrendReport)
async def trend(months: int = Query(default=12, ge=1, le=60)):
    """Série dos últimos N meses COM transações, para ver a variação dos gastos.

    Pula meses sem lançamento em vez de preenchê-los com zero: um mês vazio
    quase sempre significa "extrato ainda não importado", e um zero no gráfico
    leria como "não gastamos nada".
    """
    periods = (await tx_repo.distinct_periods())[-months:]

    points: list[TrendPoint] = []
    category_totals: dict[str, int] = {}
    for period in periods:
        report = compute_report(period, await _user_inputs(period), await _tx_inputs(period))
        individual_total = sum(u.individual_spent_cents for u in report.users)
        for row in report.by_category:
            category_totals[row.category_name] = (
                category_totals.get(row.category_name, 0) + row.total_cents
            )
        points.append(
            TrendPoint(
                period=period,
                shared_total_cents=report.shared_total_cents,
                individual_total_cents=individual_total,
                total_cents=report.shared_total_cents + individual_total,
                users=[
                    TrendUserPoint(
                        user_id=u.user_id,
                        name=u.name,
                        total_spent_cents=u.total_spent_cents,
                        shared_paid_cents=u.shared_paid_cents,
                        balance_cents=u.balance_cents,
                    )
                    for u in report.users
                ],
                by_category=[
                    TrendCategoryPoint(
                        category_id=row.category_id,
                        category_name=row.category_name,
                        total_cents=row.total_cents,
                    )
                    for row in report.by_category
                ],
            )
        )

    # Média é estatística, não rateio: divisão inteira basta, não precisa
    # conservar centavo como em `allocate`.
    total = sum(p.total_cents for p in points)
    return TrendReport(
        points=points,
        categories=sorted(category_totals, key=lambda name: -category_totals[name]),
        average_total_cents=(total // len(points)) if points else 0,
    )


@router.get("/{period}", response_model=MonthlyReport)
async def monthly_report(period: str):
    """Acerto do mês pelos gastos do período. Pagamentos não entram aqui —
    eles abatem o saldo acumulado em /reports/balance."""
    return compute_report(period, await _user_inputs(period), await _tx_inputs(period))
