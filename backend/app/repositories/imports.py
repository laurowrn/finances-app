from datetime import UTC, datetime

from app.db import get_db
from app.repositories.common import doc_out


async def create_batch(filename: str, source: str, owner_user_id: str) -> str:
    doc = {
        "filename": filename,
        "source": source,
        "owner_user_id": owner_user_id,
        "created_at": datetime.now(UTC),
        "counts": {},
    }
    result = await get_db().import_batches.insert_one(doc)
    return str(result.inserted_id)


async def set_counts(batch_id: str, counts: dict) -> None:
    from app.repositories.common import oid

    await get_db().import_batches.update_one({"_id": oid(batch_id)}, {"$set": {"counts": counts}})


async def list_batches() -> list[dict]:
    docs = await get_db().import_batches.find().sort("created_at", -1).to_list(length=200)
    return [doc_out(d) for d in docs]
