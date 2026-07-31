from app.db import get_db
from app.models.enums import MatchOp, Split
from app.repositories.common import doc_out, oid
from app.services.classifier import Rule


async def list_rules() -> list[dict]:
    docs = await get_db().rules.find().sort("priority", 1).to_list(length=1000)
    return [doc_out(d) for d in docs]


async def get_rule(rule_id: str) -> dict | None:
    return doc_out(await get_db().rules.find_one({"_id": oid(rule_id)}))


async def create_rule(data: dict) -> dict:
    result = await get_db().rules.insert_one(data)
    return doc_out(await get_db().rules.find_one({"_id": result.inserted_id}))


async def update_rule(rule_id: str, changes: dict) -> dict | None:
    changes = {k: v for k, v in changes.items() if v is not None}
    if changes:
        await get_db().rules.update_one({"_id": oid(rule_id)}, {"$set": changes})
    return await get_rule(rule_id)


async def delete_rule(rule_id: str) -> None:
    await get_db().rules.delete_one({"_id": oid(rule_id)})


async def load_engine_rules() -> list[Rule]:
    """Carrega as regras habilitadas no formato do rule engine."""
    rules: list[Rule] = []
    for d in await list_rules():
        if not d.get("enabled", True):
            continue
        matcher = d.get("matcher", {})
        rules.append(
            Rule(
                id=d["id"],
                field=matcher.get("field", "description"),
                op=MatchOp(matcher.get("op", "contains")),
                value=matcher.get("value", ""),
                category_id=d["category_id"],
                split_default=Split(d.get("split_default", "shared")),
                priority=d.get("priority", 100),
                enabled=d.get("enabled", True),
            )
        )
    return rules
