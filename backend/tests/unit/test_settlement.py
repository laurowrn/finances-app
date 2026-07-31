from app.services.settlement import TxInput, UserInput, compute_report


def _users():
    return [
        UserInput(id="A", name="Ana", income=5000.0),
        UserInput(id="B", name="Bruno", income=3000.0),
    ]


def test_proportional_split_basic():
    # Ana ganha 5000, Bruno 3000 -> proporção 0.625 / 0.375
    txs = [
        TxInput("A", 1000.0, True, "c1", "Mercado"),  # Ana pagou compartilhado
        TxInput("B", 200.0, True, "c1", "Mercado"),  # Bruno pagou compartilhado
        TxInput("A", 300.0, False, "c2", "Pessoal"),  # individual da Ana
    ]
    report = compute_report("2025-03", _users(), txs)

    assert report.shared_total == 1200.0
    ana = next(u for u in report.users if u.user_id == "A")
    bruno = next(u for u in report.users if u.user_id == "B")

    assert ana.proportion == 0.625
    assert bruno.proportion == 0.375
    assert ana.fair_share == 750.0  # 0.625 * 1200
    assert bruno.fair_share == 450.0
    assert ana.balance == 250.0  # pagou 1000, devia 750
    assert bruno.balance == -250.0
    assert ana.total_spent == 1300.0  # 1000 shared + 300 individual
    assert bruno.total_spent == 200.0

    # Bruno pagou menos que a cota -> paga a diferença para a Ana
    assert report.settlement.from_user_id == "B"
    assert report.settlement.to_user_id == "A"
    assert report.settlement.amount == 250.0


def test_equal_income_even_split():
    users = [UserInput("A", "Ana", 4000.0), UserInput("B", "Bruno", 4000.0)]
    txs = [TxInput("A", 400.0, True, "c1", "Mercado")]  # só Ana pagou
    report = compute_report("2025-03", users, txs)
    # 50/50 -> cada um deve 200; Bruno paga 200 para Ana
    assert report.settlement.from_user_id == "B"
    assert report.settlement.to_user_id == "A"
    assert report.settlement.amount == 200.0


def test_already_even_no_settlement():
    txs = [
        TxInput("A", 625.0, True, "c1", "Mercado"),  # exatamente a cota da Ana
        TxInput("B", 375.0, True, "c1", "Mercado"),  # exatamente a cota do Bruno
    ]
    report = compute_report("2025-03", _users(), txs)
    assert report.settlement.amount == 0.0
    assert report.settlement.from_user_id is None


def test_individual_only_no_settlement():
    txs = [
        TxInput("A", 100.0, False, "c2", "Pessoal"),
        TxInput("B", 50.0, False, "c2", "Pessoal"),
    ]
    report = compute_report("2025-03", _users(), txs)
    assert report.shared_total == 0.0
    assert report.settlement.amount == 0.0


def test_by_category_breakdown():
    txs = [
        TxInput("A", 100.0, True, "c1", "Mercado"),
        TxInput("B", 50.0, True, "c1", "Mercado"),
        TxInput("A", 30.0, False, "c2", "Pessoal"),
    ]
    report = compute_report("2025-03", _users(), txs)
    by_cat = {c.category_id: c for c in report.by_category}
    assert by_cat["c1"].shared == 150.0
    assert by_cat["c1"].total == 150.0
    assert by_cat["c2"].individual == 30.0
    # ordenado por total desc
    assert report.by_category[0].category_id == "c1"


def test_zero_income_falls_back_to_even():
    users = [UserInput("A", "Ana", 0.0), UserInput("B", "Bruno", 0.0)]
    txs = [TxInput("A", 100.0, True, "c1", "Mercado")]
    report = compute_report("2025-03", users, txs)
    for u in report.users:
        assert u.proportion == 0.5
