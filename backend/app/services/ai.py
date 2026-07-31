"""Sugestão de regras via Claude (opcional).

Recebe grupos de gastos não classificados (por 'merchant') e a lista de categorias
existentes, e devolve, por grupo, uma categoria sugerida + split (compartilhado/individual).
Só é usado quando ANTHROPIC_API_KEY está setada. É um assistente de *bootstrap*: o
usuário revisa e aceita, virando regras determinísticas.
"""

import json

from app.models.enums import Split
from app.settings import get_settings

SYSTEM = (
    "Você classifica gastos financeiros de um casal em categorias. "
    "Responda SEMPRE apenas com JSON válido, sem markdown."
)


def _build_prompt(groups: list[dict], categories: list[dict]) -> str:
    cats = [{"id": c["id"], "name": c["name"]} for c in categories]
    payload = {
        "categorias_disponiveis": cats,
        "grupos_de_gastos": [
            {
                "merchant_key": g["merchant_key"],
                "exemplos": g["sample_descriptions"][:5],
            }
            for g in groups
        ],
    }
    return (
        "Para cada grupo de gastos abaixo, escolha a MELHOR categoria dentre as disponíveis "
        "(use o id) e diga se o gasto normalmente é 'shared' (compartilhado do casal) ou "
        "'individual'. Se nenhuma categoria servir, use category_id=null.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        'Responda no formato: {"sugestoes": [{"merchant_key": str, "category_id": str|null, '
        '"split": "shared"|"individual"}]}'
    )


async def suggest_rules(groups: list[dict], categories: list[dict]) -> dict[str, dict]:
    """Retorna map merchant_key -> {category_id, split}. Vazio se IA desabilitada/erro."""
    settings = get_settings()
    if not settings.ai_enabled or not groups:
        return {}

    try:
        from anthropic import AsyncAnthropic
    except ImportError:  # pragma: no cover
        return {}

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        resp = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2048,
            system=SYSTEM,
            messages=[{"role": "user", "content": _build_prompt(groups, categories)}],
        )
    except Exception:  # noqa: BLE001 - IA é best-effort; falha não quebra o import
        return {}

    text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
    data = _safe_json(text)
    if not data:
        return {}

    valid_cat_ids = {c["id"] for c in categories}
    out: dict[str, dict] = {}
    for s in data.get("sugestoes", []):
        key = s.get("merchant_key")
        if not key:
            continue
        cat_id = s.get("category_id")
        if cat_id not in valid_cat_ids:
            cat_id = None
        split = s.get("split")
        split = Split.SHARED if split not in (Split.SHARED, Split.INDIVIDUAL) else Split(split)
        out[key] = {"category_id": cat_id, "split": split}
    return out


def _safe_json(text: str) -> dict | None:
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
