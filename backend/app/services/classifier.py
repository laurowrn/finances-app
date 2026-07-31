"""Rule engine determinístico (sem IA).

Percorre as regras por prioridade (menor = maior prioridade) e a primeira que casar
define categoria + split. Pura para facilitar teste; o router carrega as regras do Mongo.
"""

import re
from dataclasses import dataclass

from app.models.enums import MatchOp, Split
from app.services.dedup import normalize_description


@dataclass
class Rule:
    id: str
    field: str
    op: MatchOp
    value: str
    category_id: str
    split_default: Split
    priority: int
    enabled: bool = True


@dataclass
class Match:
    category_id: str
    split: Split
    rule_id: str


def _matches(rule: Rule, description: str) -> bool:
    if not rule.enabled:
        return False
    haystack = normalize_description(description)
    needle = normalize_description(rule.value)
    if rule.op == MatchOp.CONTAINS:
        return needle in haystack
    if rule.op == MatchOp.EQUALS:
        return needle == haystack
    if rule.op == MatchOp.REGEX:
        try:
            # regex casa contra a descrição original (case-insensitive), não a normalizada
            return re.search(rule.value, description, re.IGNORECASE) is not None
        except re.error:
            return False
    return False


def classify(description: str, rules: list[Rule]) -> Match | None:
    """Retorna o primeiro match segundo a ordem de prioridade, ou None."""
    for rule in sorted(rules, key=lambda r: r.priority):
        if _matches(rule, description):
            return Match(
                category_id=rule.category_id,
                split=rule.split_default,
                rule_id=rule.id,
            )
    return None
