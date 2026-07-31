from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.settings import get_settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongo_uri)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[get_settings().mongo_db]


async def ensure_indexes() -> None:
    """Cria índices idempotentes. Chamado no startup."""
    db = get_db()
    # Evita reimportar a mesma transação de extratos sobrepostos.
    await db.transactions.create_index("dedup_hash", unique=True)
    await db.transactions.create_index("period")
    await db.transactions.create_index("owner_user_id")
    await db.transactions.create_index("category_id")
    await db.rules.create_index("priority")
    await db.incomes.create_index([("user_id", 1), ("period", 1)], unique=True)
    await db.payments.create_index("period")


def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
