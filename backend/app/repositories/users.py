from app.db import get_db
from app.repositories.common import doc_out, oid


async def list_users() -> list[dict]:
    docs = await get_db().users.find().to_list(length=100)
    return [doc_out(d) for d in docs]


async def get_user(user_id: str) -> dict | None:
    return doc_out(await get_db().users.find_one({"_id": oid(user_id)}))


async def update_user(user_id: str, changes: dict) -> dict | None:
    changes = {k: v for k, v in changes.items() if v is not None}
    if changes:
        await get_db().users.update_one({"_id": oid(user_id)}, {"$set": changes})
    return await get_user(user_id)


# ---------- incomes (salário por mês) ----------


async def upsert_income(user_id: str, period: str, amount_cents: int) -> None:
    await get_db().incomes.update_one(
        {"user_id": user_id, "period": period},
        {"$set": {"amount_cents": amount_cents}},
        upsert=True,
    )


async def get_income(user_id: str, period: str) -> int | None:
    doc = await get_db().incomes.find_one({"user_id": user_id, "period": period})
    return doc["amount_cents"] if doc else None


async def list_incomes(period: str) -> list[dict]:
    docs = await get_db().incomes.find({"period": period}).to_list(length=100)
    return [
        {"user_id": d["user_id"], "period": d["period"], "amount_cents": d["amount_cents"]}
        for d in docs
    ]
