from datetime import UTC, date, datetime, timedelta

from app.db import get_db
from app.repositories.common import doc_out


async def create_batch(
    filename: str,
    source: str,
    owner_user_id: str,
    statement_type: str = "account",
    institution: str = "unknown",
    statement_start: date | None = None,
    statement_end: date | None = None,
) -> str:
    doc = {
        "filename": filename,
        "source": source,
        "owner_user_id": owner_user_id,
        "created_at": datetime.now(UTC),
        "counts": {},
        "statement_type": statement_type,
        "institution": institution,
        "statement_start": statement_start.isoformat() if statement_start else None,
        "statement_end": statement_end.isoformat() if statement_end else None,
    }
    result = await get_db().import_batches.insert_one(doc)
    return str(result.inserted_id)


async def set_counts(batch_id: str, counts: dict) -> None:
    from app.repositories.common import oid

    await get_db().import_batches.update_one({"_id": oid(batch_id)}, {"$set": {"counts": counts}})


async def list_batches() -> list[dict]:
    docs = await get_db().import_batches.find().sort("created_at", -1).to_list(length=200)
    return [doc_out(d) for d in docs]


async def coverage(owner_user_id: str, statement_type: str, institution: str = "unknown") -> dict:
    docs = await get_db().import_batches.find(
        {
            "owner_user_id": owner_user_id,
            "statement_type": statement_type,
            "institution": institution,
            "statement_start": {"$ne": None},
            "statement_end": {"$ne": None},
        }
    ).sort("statement_start", 1).to_list(length=500)
    batches = [doc_out(d) for d in docs]
    gaps, overlaps = [], []
    if not batches:
        return {"owner_user_id": owner_user_id, "statement_type": statement_type,
                "institution": institution,
                "batches": [], "gaps": [], "overlaps": []}
    active = batches[0]
    active_end = date.fromisoformat(active["statement_end"])
    for current in batches[1:]:
        cur_start = date.fromisoformat(current["statement_start"])
        cur_end = date.fromisoformat(current["statement_end"])
        if cur_start > active_end + timedelta(days=1):
            gaps.append({
                "kind": "gap", "start": active_end + timedelta(days=1),
                "end": cur_start - timedelta(days=1),
                "previous_filename": active["filename"],
                "filename": current["filename"],
            })
        elif cur_start <= active_end:
            overlaps.append({
                "kind": "overlap", "start": cur_start,
                "end": min(active_end, cur_end),
                "previous_filename": active["filename"],
                "filename": current["filename"],
            })
        if cur_end > active_end:
            active, active_end = current, cur_end
    return {"owner_user_id": owner_user_id, "statement_type": statement_type,
            "institution": institution,
            "batches": batches, "gaps": gaps, "overlaps": overlaps}
