"""Todo valor aqui é int de centavos: R$ 1.000,00 -> 100000."""

from app.services.settlement import (
    BalanceInput,
    PaymentInput,
    TxInput,
    UserInput,
    apply_payments,
    compute_report,
    compute_settlement_from_balances,
)


def _users():
    return [
        UserInput(id="A", name="Ana", income_cents=500000),
        UserInput(id="B", name="Bruno", income_cents=300000),
    ]


def test_proportional_split_basic():
    # Ana ganha 5000, Bruno 3000 -> proporção 0.625 / 0.375
    txs = [
        TxInput("A", 100000, True, "c1", "Mercado"),  # Ana pagou compartilhado
        TxInput("B", 20000, True, "c1", "Mercado"),  # Bruno pagou compartilhado
        TxInput("A", 30000, False, "c2", "Pessoal"),  # individual da Ana
    ]
    report = compute_report("2025-03", _users(), txs)

    assert report.shared_total_cents == 120000
    ana = next(u for u in report.users if u.user_id == "A")
    bruno = next(u for u in report.users if u.user_id == "B")

    assert ana.proportion == 0.625
    assert bruno.proportion == 0.375
    assert ana.fair_share_cents == 75000  # 0.625 * 1200
    assert bruno.fair_share_cents == 45000
    assert ana.balance_cents == 25000  # pagou 1000, devia 750
    assert bruno.balance_cents == -25000
    assert ana.total_spent_cents == 130000  # 1000 shared + 300 individual
    assert bruno.total_spent_cents == 20000

    # Bruno pagou menos que a cota -> paga a diferença para a Ana
    assert report.settlement.from_user_id == "B"
    assert report.settlement.to_user_id == "A"
    assert report.settlement.amount_cents == 25000


def test_equal_income_even_split():
    users = [UserInput("A", "Ana", 400000), UserInput("B", "Bruno", 400000)]
    txs = [TxInput("A", 40000, True, "c1", "Mercado")]  # só Ana pagou
    report = compute_report("2025-03", users, txs)
    # 50/50 -> cada um deve 200; Bruno paga 200 para Ana
    assert report.settlement.from_user_id == "B"
    assert report.settlement.to_user_id == "A"
    assert report.settlement.amount_cents == 20000


def test_already_even_no_settlement():
    txs = [
        TxInput("A", 62500, True, "c1", "Mercado"),  # exatamente a cota da Ana
        TxInput("B", 37500, True, "c1", "Mercado"),  # exatamente a cota do Bruno
    ]
    report = compute_report("2025-03", _users(), txs)
    assert report.settlement.amount_cents == 0
    assert report.settlement.from_user_id is None


def test_individual_only_no_settlement():
    txs = [
        TxInput("A", 10000, False, "c2", "Pessoal"),
        TxInput("B", 5000, False, "c2", "Pessoal"),
    ]
    report = compute_report("2025-03", _users(), txs)
    assert report.shared_total_cents == 0
    assert report.settlement.amount_cents == 0


def test_by_category_breakdown():
    txs = [
        TxInput("A", 10000, True, "c1", "Mercado"),
        TxInput("B", 5000, True, "c1", "Mercado"),
        TxInput("A", 3000, False, "c2", "Pessoal"),
    ]
    report = compute_report("2025-03", _users(), txs)
    by_cat = {c.category_id: c for c in report.by_category}
    assert by_cat["c1"].shared_cents == 15000
    assert by_cat["c1"].total_cents == 15000
    assert by_cat["c2"].individual_cents == 3000
    # ordenado por total desc
    assert report.by_category[0].category_id == "c1"


def test_payment_reduces_accumulated_balance():
    balances = {"A": 25000, "B": -25000}
    payments = [PaymentInput(from_user_id="B", to_user_id="A", amount_cents=10000)]
    out = apply_payments(balances, payments)
    assert out == {"A": 15000, "B": -15000}  # Bruno devia 250, pagou 100


def test_payments_can_fully_settle_accumulated_balance():
    out = apply_payments(
        {"A": 20000, "B": -20000},
        [PaymentInput(from_user_id="B", to_user_id="A", amount_cents=20000)],
    )
    assert out == {"A": 0, "B": 0}
    assert (
        compute_settlement_from_balances(
            [BalanceInput("A", "Ana", out["A"]), BalanceInput("B", "Bruno", out["B"])]
        ).amount_cents
        == 0
    )


def test_monthly_report_ignores_payments():
    """O acerto do mês é só dos gastos: pagar não muda o relatório do período."""
    txs = [
        TxInput("A", 100000, True, "c1", "Mercado"),
        TxInput("B", 20000, True, "c1", "Mercado"),
    ]
    report = compute_report("2025-03", _users(), txs)
    assert report.settlement.amount_cents == 25000

    # Mesmo com o acerto quitado, o relatório do mês continua mostrando 250.
    settled = apply_payments(
        {u.user_id: u.balance_cents for u in report.users},
        [PaymentInput(from_user_id="B", to_user_id="A", amount_cents=25000)],
    )
    assert settled == {"A": 0, "B": 0}
    assert compute_report("2025-03", _users(), txs).settlement.amount_cents == 25000


def test_zero_income_falls_back_to_even():
    users = [UserInput("A", "Ana", 0), UserInput("B", "Bruno", 0)]
    txs = [TxInput("A", 10000, True, "c1", "Mercado")]
    report = compute_report("2025-03", users, txs)
    for u in report.users:
        assert u.proportion == 0.5
    assert sum(u.fair_share_cents for u in report.users) == 10000


# ---------- conservação de centavos (o ponto do money pattern) ----------


def test_fair_shares_always_sum_to_shared_total():
    """Rateio com proporção que é dízima: as cotas ainda somam o total exato."""
    users = [
        UserInput("A", "Ana", 333333),
        UserInput("B", "Bruno", 333333),
        UserInput("C", "Caio", 333334),
    ]
    txs = [TxInput("A", 10001, True, "c1", "Mercado")]  # R$ 100,01 entre 3
    report = compute_report("2025-03", users, txs)

    assert sum(u.fair_share_cents for u in report.users) == 10001
    assert report.shared_total_cents == 10001


def test_balances_always_sum_to_zero():
    """Se as cotas somam o total, os saldos somam zero: ninguém perde centavo."""
    users = [
        UserInput("A", "Ana", 512345),
        UserInput("B", "Bruno", 287655),
        UserInput("C", "Caio", 100001),
    ]
    txs = [
        TxInput("A", 33333, True, "c1", "Mercado"),
        TxInput("B", 11111, True, "c1", "Mercado"),
        TxInput("C", 7, True, "c2", "Padaria"),
        TxInput("A", 99999, False, "c3", "Pessoal"),  # individual não conta
    ]
    report = compute_report("2025-03", users, txs)
    assert sum(u.balance_cents for u in report.users) == 0


def test_settlement_of_one_cent_is_not_swallowed():
    """Antes, o acerto abaixo de meio centavo virava zero por um epsilon."""
    settlement = compute_settlement_from_balances(
        [BalanceInput("A", "Ana", 1), BalanceInput("B", "Bruno", -1)]
    )
    assert settlement.amount_cents == 1
    assert settlement.from_user_id == "B"
