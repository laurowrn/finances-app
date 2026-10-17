"""Agregações para o relatório de IA e avaliação objetiva das metas.

Funções puras: recebem transações já carregadas e devolvem números. O router
cuida do Mongo. Assim dá para testar o cálculo sem banco.
"""

import re
from collections import Counter, defaultdict

from app.schemas.ai import (
    CategoryStat,
    Goal,
    GoalMetric,
    GoalProgress,
    InstallmentStat,
    MerchantStat,
    ReportProgress,
    TransactionBrief,
)
from app.services.dedup import normalize_description
from app.services.money import Cents

# "Parcela 3/12", "PARCELA 3/12", "3/12" no fim da descrição
INSTALLMENT_RE = re.compile(r"parcela\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)

# Categorias cujo gasto é recorrente por natureza — o que a análise olha
# primeiro quando procura corte fácil.
RECURRING_CATEGORIES = ("Assinaturas", "Academia", "Internet")

# Comerciantes reconhecidos para medir concentração. Chave = trecho normalizado.
MERCHANT_KEYS = (
    "cooper",
    "qtal",
    "uberrides",
    "mercadolivre",
    "amazon",
    "ifd",
    "posto",
    "farmaci",
    "raia",
    "neumarkt",
    "havan",
    "officina",
    "bistek",
    "carrefour",
    "giassi",
)


def matches(description: str, needle: str) -> bool:
    """Casamento de descrição usado por metas e por merchant: normalizado dos
    dois lados, igual ao rule engine — sem acento, sem caixa, sem pontuação."""
    return normalize_description(needle) in normalize_description(description)


def category_stats(
    rows: list[dict],
    category_name: dict[str | None, str],
    user_name: dict[str, str],
    history: dict[str, dict[str | None, int]],
) -> list[CategoryStat]:
    """`history` é {periodo: {category_id: centavos}} dos meses ANTERIORES."""
    total = sum(r["amount_cents"] for r in rows) or 1
    agg: dict[str | None, dict] = defaultdict(
        lambda: {"total": 0, "count": 0, "by_user": Counter()}
    )
    for r in rows:
        cid = r.get("category_id")
        a = agg[cid]
        a["total"] += r["amount_cents"]
        a["count"] += 1
        a["by_user"][user_name.get(r["owner_user_id"], "?")] += r["amount_cents"]

    out: list[CategoryStat] = []
    for cid, a in agg.items():
        hist = {p: per.get(cid, 0) for p, per in history.items()}
        out.append(
            CategoryStat(
                category_id=cid,
                category_name=category_name.get(cid, "Sem categoria"),
                total_cents=a["total"],
                count=a["count"],
                share_pct=round(100 * a["total"] / total, 1),
                by_user=dict(a["by_user"]),
                history_cents=hist,
                average_cents=(sum(hist.values()) // len(hist)) if hist else 0,
            )
        )
    out.sort(key=lambda c: -c.total_cents)
    return out


def merchant_stats(rows: list[dict], limit: int = 10) -> list[MerchantStat]:
    agg: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        norm = normalize_description(r.get("description", ""))
        for key in MERCHANT_KEYS:
            if key in norm:
                agg[key][0] += r["amount_cents"]
                agg[key][1] += 1
                break  # um lançamento conta para um merchant só
    stats = [
        MerchantStat(key=k, total_cents=v, count=n, avg_ticket_cents=v // n)
        for k, (v, n) in agg.items()
        if n
    ]
    stats.sort(key=lambda m: -m.total_cents)
    return stats[:limit]


def installment_stats(rows: list[dict]) -> tuple[list[InstallmentStat], Cents]:
    """Parcelas em aberto e quanto elas já comprometem dos meses seguintes."""
    out: list[InstallmentStat] = []
    tail = 0
    for r in rows:
        m = INSTALLMENT_RE.search(r.get("description", ""))
        if not m:
            continue
        current, total = int(m.group(1)), int(m.group(2))
        remaining = max(total - current, 0)
        remaining_cents = remaining * r["amount_cents"]
        tail += remaining_cents
        out.append(
            InstallmentStat(
                description=r.get("description", ""),
                amount_cents=r["amount_cents"],
                current=current,
                total=total,
                remaining=remaining,
                remaining_cents=remaining_cents,
            )
        )
    out.sort(key=lambda i: -i.remaining_cents)
    return out, tail


def to_brief(
    rows: list[dict], category_name: dict[str | None, str], user_name: dict[str, str]
) -> list[TransactionBrief]:
    return [
        TransactionBrief(
            date=r["date"],
            description=r.get("description", ""),
            amount_cents=r["amount_cents"],
            category_name=category_name.get(r.get("category_id"), "Sem categoria"),
            user_name=user_name.get(r["owner_user_id"], "?"),
        )
        for r in rows
    ]


# ---------- avaliação de metas ----------


def _selected(rows: list[dict], goal: Goal) -> list[dict]:
    sel = rows
    if goal.category_id is not None:
        sel = [r for r in sel if r.get("category_id") == goal.category_id]
    if goal.match:
        sel = [r for r in sel if matches(r.get("description", ""), goal.match)]
    return sel


def evaluate_goal(goal: Goal, rows: list[dict]) -> GoalProgress:
    """Avalia uma meta contra os lançamentos do mês alvo.

    Toda métrica é do tipo "no máximo": `achieved` é `realizado <= alvo`. Uma
    meta sem alvo definido não pode ser avaliada — tratamos como alvo 0, o que
    a marca como não cumprida em vez de fingir sucesso.
    """
    sel = _selected(rows, goal)
    actual_cents = sum(r["amount_cents"] for r in sel)
    actual_count = len(sel)

    if goal.metric is GoalMetric.COUNT_MAX:
        target = goal.target_count or 0
        actual = actual_count
        saved = None
    else:
        target = goal.target_cents or 0
        actual = actual_cents
        saved = (goal.baseline_cents - actual_cents) if goal.baseline_cents is not None else None

    return GoalProgress(
        goal=goal,
        actual_cents=actual_cents,
        actual_count=actual_count,
        target=target,
        actual=actual,
        achieved=actual <= target,
        delta=actual - target,
        saved_cents=saved,
    )


def evaluate_report(period: str, goals: list[Goal], rows: list[dict]) -> ReportProgress:
    progress = [evaluate_goal(g, rows) for g in goals]
    return ReportProgress(
        period=period,
        goals=progress,
        transaction_count=len(rows),
        achieved_count=sum(1 for p in progress if p.achieved),
        total_count=len(progress),
        # Só economia positiva soma: estourar uma meta não "desconta" da outra,
        # senão o número vira uma média disfarçada e esconde o estouro.
        total_saved_cents=sum(
            p.saved_cents for p in progress if p.saved_cents and p.saved_cents > 0
        ),
    )
