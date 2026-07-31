from app.models.enums import MatchOp, Split
from app.services.classifier import Rule, classify


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
