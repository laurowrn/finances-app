from datetime import UTC, date, datetime

from app.db import get_db
from app.repositories.common import doc_out, oid, period_of


async def create_payment(data: dict) -> dict:
    d: date = data["date"]
    doc = {
        "date": d.isoformat(),
        "period": period_of(d),
        "from_user_id": data["from_user_id"],
        "to_user_id": data["to_user_id"],
        "amount": round(data["amount"], 2),
        "note": data.get("note"),
        "created_at": datetime.now(UTC),
    }
    result = await get_db().payments.insert_one(doc)
    return doc_out(await get_db().payments.find_one({"_id": result.inserted_id}))


async def list_payments(period: str | None = None) -> list[dict]:
    query = {"period": period} if period else {}
    docs = await get_db().payments.find(query).sort("date", -1).to_list(length=5000)
    return [doc_out(d) for d in docs]


async def delete_payment(payment_id: str) -> None:
    await get_db().payments.delete_one({"_id": oid(payment_id)})
