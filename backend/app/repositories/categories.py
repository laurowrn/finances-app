from app.db import get_db
from app.repositories.common import doc_out, oid


async def list_categories() -> list[dict]:
    docs = await get_db().categories.find().sort("name", 1).to_list(length=500)
    return [doc_out(d) for d in docs]


async def get_category(category_id: str) -> dict | None:
    return doc_out(await get_db().categories.find_one({"_id": oid(category_id)}))


async def create_category(data: dict) -> dict:
    result = await get_db().categories.insert_one(data)
    return doc_out(await get_db().categories.find_one({"_id": result.inserted_id}))


async def update_category(category_id: str, changes: dict) -> dict | None:
    changes = {k: v for k, v in changes.items() if v is not None}
    if changes:
        await get_db().categories.update_one({"_id": oid(category_id)}, {"$set": changes})
    return await get_category(category_id)


async def delete_category(category_id: str) -> None:
    await get_db().categories.delete_one({"_id": oid(category_id)})
