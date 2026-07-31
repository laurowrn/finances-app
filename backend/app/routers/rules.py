from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user_id
from app.models.enums import MatchOp, SuggestionStatus
from app.repositories import categories as cat_repo
from app.repositories import rules as repo
from app.repositories import suggestions as sugg_repo
from app.repositories import transactions as tx_repo
from app.schemas.entities import (
    AcceptSuggestionRequest,
    RuleCreate,
    RuleOut,
    RuleSuggestionOut,
    RuleUpdate,
)
from app.services.ai import suggest_rules
from app.settings import get_settings

router = APIRouter(prefix="/rules", tags=["rules"], dependencies=[Depends(current_user_id)])


def _rule_out(d: dict) -> RuleOut:
    return RuleOut(
        id=d["id"],
        matcher=d["matcher"],
        category_id=d["category_id"],
        split_default=d["split_default"],
        priority=d["priority"],
        enabled=d["enabled"],
    )


@router.get("", response_model=list[RuleOut])
async def list_rules():
    return [_rule_out(r) for r in await repo.list_rules()]


@router.post("", response_model=RuleOut, status_code=201)
async def create_rule(body: RuleCreate):
    created = await repo.create_rule(body.model_dump())
    # aplica a nova regra às transações ainda não classificadas
    await tx_repo.reclassify(await repo.load_engine_rules(), only_unclassified=True)
    return _rule_out(created)


@router.patch("/{rule_id}", response_model=RuleOut)
async def update_rule(rule_id: str, body: RuleUpdate):
    r = await repo.update_rule(rule_id, body.model_dump(exclude_none=True))
    if r is None:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    return _rule_out(r)


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: str):
    await repo.delete_rule(rule_id)


@router.post("/reclassify")
async def reclassify(only_unclassified: bool = True):
    count = await tx_repo.reclassify(await repo.load_engine_rules(), only_unclassified)
    return {"reclassified": count}


# ---------- sugestões via IA ----------


@router.get("/suggestions", response_model=list[RuleSuggestionOut])
async def list_suggestions():
    return [RuleSuggestionOut(**s) for s in await sugg_repo.list_pending()]


@router.post("/suggest")
async def suggest():
    """Gera sugestões de regras (IA) a partir dos gastos não classificados."""
    settings = get_settings()
    groups = await tx_repo.unmatched_groups()
    if not groups:
        await sugg_repo.replace_pending([])
        return {"ai_enabled": settings.ai_enabled, "created": 0, "message": "Nada a classificar"}

    categories = await cat_repo.list_categories()
    cat_by_id = {c["id"]: c for c in categories}
    ai_map = await suggest_rules(groups, categories)

    docs = []
    for g in groups:
        s = ai_map.get(g["merchant_key"], {})
        cat_id = s.get("category_id")
        docs.append(
            {
                "merchant_key": g["merchant_key"],
                "sample_descriptions": g["sample_descriptions"],
                "count": g["count"],
                "suggested_category_id": cat_id,
                "suggested_category_name": cat_by_id.get(cat_id, {}).get("name")
                if cat_id
                else None,
                "suggested_split": s.get("split", "shared"),
                "status": SuggestionStatus.PENDING.value,
            }
        )
    await sugg_repo.replace_pending(docs)
    return {"ai_enabled": settings.ai_enabled, "created": len(docs)}


@router.post("/suggestions/{suggestion_id}/accept", response_model=RuleOut)
async def accept_suggestion(suggestion_id: str, body: AcceptSuggestionRequest):
    """Aceita uma sugestão: cria a regra (match 'contains' no merchant_key) e reclassifica."""
    s = await sugg_repo.get_suggestion(suggestion_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada")

    rule_data = {
        "matcher": {
            "field": "description",
            "op": MatchOp.CONTAINS.value,
            "value": s["merchant_key"],
        },
        "category_id": body.category_id,
        "split_default": body.split_default.value,
        "priority": body.priority,
        "enabled": True,
    }
    created = await repo.create_rule(rule_data)
    await sugg_repo.set_status(suggestion_id, SuggestionStatus.ACCEPTED)
    await tx_repo.reclassify(await repo.load_engine_rules(), only_unclassified=True)
    return _rule_out(created)


@router.post("/suggestions/{suggestion_id}/reject", status_code=204)
async def reject_suggestion(suggestion_id: str):
    await sugg_repo.set_status(suggestion_id, SuggestionStatus.REJECTED)
