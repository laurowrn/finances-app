"""Todo valor em centavos."""

from app.schemas.ai import Goal, GoalMetric
from app.services.insights import (
    evaluate_goal,
    evaluate_report,
    installment_stats,
    matches,
    merchant_stats,
)


def _tx(amount, desc="Compra", cat="c1"):
    return {"amount_cents": amount, "description": desc, "category_id": cat, "owner_user_id": "u1"}


# ---------- casamento de descrição ----------


def test_matches_ignores_accent_case_and_punctuation():
    assert matches("Cooper Filial Itoupava", "cooper")
    assert matches("Dl*Uberrides", "uberrides")
    assert matches("PIX QRS QTAL MINIME29/07", "qtal")
    assert not matches("Mercado*Mercadolivre", "cooper")


# ---------- parcelas ----------


def test_installment_tail_counts_only_remaining():
    rows = [
        _tx(21000, "Intent Gym - Parcela 5/12"),
        _tx(5845, "Amazon Marketplace Cc - Parcela 5/5"),  # última, não sobra nada
        _tx(10000, "Compra à vista"),
    ]
    stats, tail = installment_stats(rows)
    assert len(stats) == 2
    assert tail == 7 * 21000  # só as 7 restantes da academia
    assert stats[0].remaining == 7
    assert stats[1].remaining == 0


def test_merchant_stats_counts_each_row_once():
    rows = [_tx(10000, "Cooper Filial"), _tx(20000, "Cooper"), _tx(500, "Paygo*Qtal Minimercado")]
    stats = {m.key: m for m in merchant_stats(rows)}
    assert stats["cooper"].total_cents == 30000
    assert stats["cooper"].count == 2
    assert stats["cooper"].avg_ticket_cents == 15000
    assert stats["qtal"].count == 1


# ---------- avaliação de metas ----------


def test_category_max_achieved_and_missed():
    rows = [_tx(50000, cat="mercado"), _tx(30000, cat="mercado"), _tx(90000, cat="lazer")]
    goal = Goal(
        id="mercado",
        title="Mercado até R$ 1.000",
        metric=GoalMetric.CATEGORY_MAX,
        category_id="mercado",
        target_cents=100000,
        baseline_cents=120000,
        rationale="teste",
    )
    p = evaluate_goal(goal, rows)
    assert p.actual_cents == 80000
    assert p.achieved is True
    assert p.delta == -20000  # ficou 200 abaixo do teto
    assert p.saved_cents == 40000  # baseline 1200 -> 800

    apertada = goal.model_copy(update={"target_cents": 70000})
    assert evaluate_goal(apertada, rows).achieved is False


def test_merchant_max_uses_normalized_match():
    rows = [_tx(20000, "Cooper Filial Itoupava"), _tx(10000, "COOPER"), _tx(5000, "Bistek")]
    goal = Goal(
        id="cooper",
        title="Cooper até R$ 250",
        metric=GoalMetric.MERCHANT_MAX,
        match="cooper",
        target_cents=25000,
        baseline_cents=30000,
        rationale="teste",
    )
    p = evaluate_goal(goal, rows)
    assert p.actual_cents == 30000  # só as duas do Cooper
    assert p.achieved is False


def test_count_max_counts_transactions_not_money():
    rows = [_tx(500, "Paygo*Qtal") for _ in range(12)]
    goal = Goal(
        id="qtal-idas",
        title="No máximo 8 idas ao Qtal",
        metric=GoalMetric.COUNT_MAX,
        match="qtal",
        target_count=8,
        baseline_count=20,
        rationale="teste",
    )
    p = evaluate_goal(goal, rows)
    assert p.actual == 12
    assert p.target == 8
    assert p.achieved is False
    assert p.saved_cents is None  # métrica de contagem não tem economia em R$


def test_goal_without_target_is_not_silently_achieved():
    """Meta mal formada não pode passar como cumprida."""
    goal = Goal(id="x", title="?", metric=GoalMetric.CATEGORY_MAX, category_id="c1",
                rationale="sem alvo")
    assert evaluate_goal(goal, [_tx(100)]).achieved is False


def test_goal_with_no_matching_rows_is_achieved():
    """Não gastou nada na categoria: meta de teto cumprida."""
    goal = Goal(id="x", title="?", metric=GoalMetric.CATEGORY_MAX, category_id="inexistente",
                target_cents=1000, baseline_cents=5000, rationale="")
    p = evaluate_goal(goal, [_tx(100, cat="c1")])
    assert p.actual_cents == 0
    assert p.achieved is True
    assert p.saved_cents == 5000


def test_report_progress_sums_only_positive_savings():
    """Estourar uma meta não pode 'descontar' da economia de outra."""
    rows = [_tx(20000, cat="a"), _tx(90000, cat="b")]
    goals = [
        Goal(id="a", title="a", metric=GoalMetric.CATEGORY_MAX, category_id="a",
             target_cents=30000, baseline_cents=50000, rationale=""),  # economizou 300
        Goal(id="b", title="b", metric=GoalMetric.CATEGORY_MAX, category_id="b",
             target_cents=50000, baseline_cents=60000, rationale=""),  # estourou
    ]
    r = evaluate_report("2026-08", goals, rows)
    assert r.achieved_count == 1
    assert r.total_count == 2
    assert r.total_saved_cents == 30000  # só a meta A entra
    assert r.goals[1].achieved is False
    assert r.goals[1].delta == 40000
