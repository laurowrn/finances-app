from datetime import UTC, date, datetime

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.db import get_db
from app.models.enums import ClassifiedBy, Source, Split
from app.repositories.common import doc_out, oid, period_of
from app.services.classifier import classify
from app.services.dedup import dedup_hash, merchant_key


def _build_doc(
    d: date,
    description: str,
    amount: float,
    owner_user_id: str,
    category_id: str | None,
    is_shared: bool,
    source: Source,
    classified_by: ClassifiedBy,
    rule_id: str | None,
    import_batch_id: str | None,
) -> dict:
    date_iso = d.isoformat()
    return {
        "date": date_iso,
        "period": period_of(d),
        "description": description,
        "raw_description": description,
        "amount": round(amount, 2),
        "owner_user_id": owner_user_id,
        "category_id": category_id,
        "is_shared": is_shared,
        "source": source.value,
        "classified_by": classified_by.value,
        "rule_id": rule_id,
        "import_batch_id": import_batch_id,
        "dedup_hash": dedup_hash(date_iso, amount, owner_user_id, description),
        "created_at": datetime.now(UTC),
    }


async def existing_hashes(hashes: list[str]) -> set[str]:
    """Dado um lote de dedup_hash, retorna os que já existem em `transactions`."""
    if not hashes:
        return set()
    docs = (
        await get_db()
        .transactions.find({"dedup_hash": {"$in": hashes}}, {"dedup_hash": 1})
        .to_list(length=len(hashes))
    )
    return {d["dedup_hash"] for d in docs}


async def insert_reviewed(
    rows: list,  # list[ImportCommitRow]
    owner_user_id: str,
    source: Source,
    import_batch_id: str,
) -> dict:
    """Insere linhas já revisadas/classificadas pelo usuário. Recalcula o dedup_hash
    no servidor (não confia no que veio do cliente); o índice único é a rede de
    segurança final contra duplicatas."""
    db = get_db()
    total = matched = unmatched = duplicates = 0

    for r in rows:
        total += 1
        doc = _build_doc(
            r.date,
            r.description,
            r.amount,
            owner_user_id,
            r.category_id,
            r.is_shared,
            source,
            r.classified_by,
            r.rule_id,
            import_batch_id,
        )
        try:
            await db.transactions.insert_one(doc)
            if r.category_id:
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
        "period": period_of(d),
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


async def distinct_periods() -> list[str]:
    """Todos os períodos com pelo menos uma transação, em ordem cronológica."""
    periods = await get_db().transactions.distinct("period")
    return sorted(periods)
