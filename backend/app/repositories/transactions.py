from datetime import UTC, date, datetime

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.db import get_db
from app.models.enums import ClassifiedBy, Source, Split
from app.repositories.common import doc_out, oid
from app.services.classifier import Match, classify
from app.services.dedup import dedup_hash, merchant_key


def _period_of(d: date) -> str:
    return d.strftime("%Y-%m")


async def insert_parsed(
    parsed: list,  # list[ParsedTx]
    owner_user_id: str,
    source: Source,
    import_batch_id: str,
    engine_rules: list,
) -> dict:
    """Insere transações parseadas, aplicando dedup e o rule engine. Retorna contagens."""
    db = get_db()
    total = matched = unmatched = duplicates = 0

    for p in parsed:
        total += 1
        date_iso = p.date.isoformat()
        h = dedup_hash(date_iso, p.amount, owner_user_id, p.description)
        match: Match | None = classify(p.description, engine_rules)

        doc = {
            "date": date_iso,
            "period": _period_of(p.date),
            "description": p.description,
            "raw_description": p.description,
            "amount": round(p.amount, 2),
            "owner_user_id": owner_user_id,
            "category_id": match.category_id if match else None,
            "is_shared": (match.split == Split.SHARED) if match else True,
            "source": source.value,
            "classified_by": ClassifiedBy.RULE.value if match else ClassifiedBy.NONE.value,
            "rule_id": match.rule_id if match else None,
            "import_batch_id": import_batch_id,
            "dedup_hash": h,
            "created_at": datetime.now(UTC),
        }
        try:
            await db.transactions.insert_one(doc)
            if match:
                matched += 1
            else:
                unmatched += 1
        except DuplicateKeyError:
            duplicates += 1

    return {
        "total": total,
        "matched": matched,
        "unmatched": unmatched,
        "duplicates": duplicates,
    }


async def create_manual(data: dict) -> dict:
    d: date = data["date"]
    doc = {
        "date": d.isoformat(),
        "period": _period_of(d),
        "description": data["description"],
        "raw_description": data["description"],
        "amount": round(data["amount"], 2),
        "owner_user_id": data["owner_user_id"],
        "category_id": data.get("category_id"),
        "is_shared": data.get("is_shared", True),
        "source": Source.MANUAL.value,
        "classified_by": ClassifiedBy.MANUAL.value,
        "rule_id": None,
        "import_batch_id": None,
        "dedup_hash": dedup_hash(
            d.isoformat(), data["amount"], data["owner_user_id"], data["description"]
        ),
        "created_at": datetime.now(UTC),
    }
    result = await get_db().transactions.insert_one(doc)
    return doc_out(await get_db().transactions.find_one({"_id": result.inserted_id}))


async def list_transactions(
    period: str | None = None,
    owner_user_id: str | None = None,
    category_id: str | None = None,
    only_unclassified: bool = False,
) -> list[dict]:
    query: dict = {}
    if period:
        query["period"] = period
    if owner_user_id:
        query["owner_user_id"] = owner_user_id
    if category_id:
        query["category_id"] = category_id
    if only_unclassified:
        query["category_id"] = None
    docs = await get_db().transactions.find(query).sort("date", -1).to_list(length=5000)
    return [doc_out(d) for d in docs]


async def update_transaction(tx_id: str, changes: dict) -> dict | None:
    changes = {k: v for k, v in changes.items() if v is not None}
    if "category_id" in changes or "is_shared" in changes:
        # edição manual sobrescreve a classificação por regra
        changes["classified_by"] = ClassifiedBy.MANUAL.value
    if changes:
        doc = await get_db().transactions.find_one_and_update(
            {"_id": oid(tx_id)}, {"$set": changes}, return_document=ReturnDocument.AFTER
        )
        return doc_out(doc)
    return doc_out(await get_db().transactions.find_one({"_id": oid(tx_id)}))


async def delete_transaction(tx_id: str) -> None:
    await get_db().transactions.delete_one({"_id": oid(tx_id)})


async def reclassify(engine_rules: list, only_unclassified: bool = True) -> int:
    """Reaplica o rule engine. Por padrão só nas não classificadas (não mexe em manuais).
    Retorna quantas foram classificadas."""
    query: dict = {}
    if only_unclassified:
        query = {
            "$or": [
                {"category_id": None},
                {"classified_by": ClassifiedBy.NONE.value},
            ],
            "classified_by": {"$ne": ClassifiedBy.MANUAL.value},
        }
    docs = await get_db().transactions.find(query).to_list(length=10000)
    count = 0
    for d in docs:
        match = classify(d.get("description", ""), engine_rules)
        if not match:
            continue
        await get_db().transactions.update_one(
            {"_id": d["_id"]},
            {
                "$set": {
                    "category_id": match.category_id,
                    "is_shared": match.split == Split.SHARED,
                    "classified_by": ClassifiedBy.RULE.value,
                    "rule_id": match.rule_id,
                }
            },
        )
        count += 1
    return count


async def unmatched_groups() -> list[dict]:
    """Agrupa transações não classificadas por merchant_key."""
    docs = await get_db().transactions.find({"category_id": None}).to_list(length=10000)
    groups: dict[str, dict] = {}
    for d in docs:
        key = merchant_key(d.get("description", ""))
        g = groups.setdefault(key, {"merchant_key": key, "sample_descriptions": [], "count": 0})
        g["count"] += 1
        if d["description"] not in g["sample_descriptions"] and len(g["sample_descriptions"]) < 5:
            g["sample_descriptions"].append(d["description"])
    return sorted(groups.values(), key=lambda g: g["count"], reverse=True)


async def transactions_for_report(period: str) -> list[dict]:
    docs = await get_db().transactions.find({"period": period}).to_list(length=10000)
    return [doc_out(d) for d in docs]
