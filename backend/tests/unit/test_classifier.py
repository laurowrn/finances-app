from app.models.enums import MatchOp, Split
from app.services.classifier import Rule, classify, split_flags


def _rule(id, value, cat, op=MatchOp.CONTAINS, split=Split.SHARED, priority=100, enabled=True):
    return Rule(id, "description", op, value, cat, split, priority, enabled)


def test_contains_match_ignores_accents_and_case():
    rules = [_rule("r1", "supermercado", "mercado")]
    m = classify("SUPÉRMERCADO XPTO 123", rules)
    assert m is not None and m.category_id == "mercado"
    assert m.split == Split.SHARED


def test_priority_wins():
    rules = [
        _rule("low", "uber", "transporte", priority=200),
        _rule("high", "uber eats", "delivery", priority=10, split=Split.INDIVIDUAL),
    ]
    m = classify("UBER EATS pedido", rules)
    assert m.category_id == "delivery"
    assert m.rule_id == "high"


def test_no_match_returns_none():
    rules = [_rule("r1", "netflix", "assinatura")]
    assert classify("padaria do joao", rules) is None


def test_disabled_rule_ignored():
    rules = [_rule("r1", "netflix", "assinatura", enabled=False)]
    assert classify("NETFLIX.COM", rules) is None


def test_regex_op():
    rules = [_rule("r1", r"posto\s+\w+", "transporte", op=MatchOp.REGEX)]
    assert classify("POSTO SHELL centro", rules).category_id == "transporte"


def test_equals_op():
    rules = [_rule("r1", "spotify", "assinatura", op=MatchOp.EQUALS)]
    assert classify("Spotify", rules) is not None
    assert classify("Spotify BR premium", rules) is None


def test_split_flags_maps_each_split():
    assert split_flags(Split.SHARED) == (True, False)
    assert split_flags(Split.INDIVIDUAL) == (False, False)
    # Ignorado não é compartilhado nem individual — sai da conta inteira.
    assert split_flags(Split.IGNORED) == (False, True)


def test_rule_can_mark_as_ignored():
    """Extrato da conta e fatura do cartão se sobrepõem: o pagamento da fatura
    precisa poder ser marcado como ignorado por regra."""
    rules = [
        Rule(
            id="r1",
            field="description",
            op=MatchOp.CONTAINS,
            value="pagamento de fatura",
            category_id="c-ignorado",
            split_default=Split.IGNORED,
            priority=10,
        )
    ]
    match = classify("Pagamento de fatura", rules)
    assert match is not None
    assert match.split == Split.IGNORED
    assert split_flags(match.split) == (False, True)
