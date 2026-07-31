from app.db import get_db
from app.models.enums import SuggestionStatus
from app.repositories.common import doc_out, oid


async def replace_pending(suggestions: list[dict]) -> None:
    """Substitui as sugestões pendentes por um novo conjunto."""
    db = get_db()
    await db.rule_suggestions.delete_many({"status": SuggestionStatus.PENDING.value})
    if suggestions:
        await db.rule_suggestions.insert_many(suggestions)


async def list_pending() -> list[dict]:
    docs = (
        await get_db()
        .rule_suggestions.find({"status": SuggestionStatus.PENDING.value})
        .sort("count", -1)
        .to_list(length=1000)
    )
    return [doc_out(d) for d in docs]


async def get_suggestion(suggestion_id: str) -> dict | None:
    return doc_out(await get_db().rule_suggestions.find_one({"_id": oid(suggestion_id)}))


async def set_status(suggestion_id: str, status: SuggestionStatus) -> None:
    await get_db().rule_suggestions.update_one(
        {"_id": oid(suggestion_id)}, {"$set": {"status": status.value}}
    )
