"""Seed idempotente: cria os 2 usuários (casal) e categorias padrão.

Uso:  python -m app.seed
"""

import asyncio

from app.db import close_client, ensure_indexes, get_db
from app.settings import get_settings

DEFAULT_CATEGORIES = [
    ("Mercado", "shopping-cart", True),
    ("Aluguel", "home", True),
    ("Contas (luz/água/net)", "receipt", True),
    ("Restaurante/Delivery", "utensils", True),
    ("Transporte", "car", True),
    ("Lazer", "party-popper", True),
    ("Saúde", "heart-pulse", True),
    ("Assinaturas", "repeat", True),
    ("Cuidados pessoais", "user", False),
    ("Outros", "tag", True),
]


async def seed() -> None:
    settings = get_settings()
    db = get_db()
    await ensure_indexes()

    # Usuários (upsert por nome)
    for name, salary in (
        (settings.user_a_name, settings.user_a_salary),
        (settings.user_b_name, settings.user_b_salary),
    ):
        await db.users.update_one(
            {"name": name},
            {"$setOnInsert": {"name": name, "base_salary": salary}},
            upsert=True,
        )

    # Categorias padrão (upsert por nome)
    for name, icon, shared_default in DEFAULT_CATEGORIES:
        await db.categories.update_one(
            {"name": name},
            {"$setOnInsert": {"name": name, "icon": icon, "is_shared_default": shared_default}},
            upsert=True,
        )

    users = await db.users.find().to_list(length=10)
    cats = await db.categories.count_documents({})
    print(f"Seed OK. Usuários: {[u['name'] for u in users]}. Categorias: {cats}.")
    print(f"Senha de login (todos): {settings.login_password!r}")


async def seed_if_empty() -> None:
    """Roda o seed apenas se ainda não houver usuários (chamado no startup)."""
    if await get_db().users.count_documents({}) == 0:
        await seed()


if __name__ == "__main__":

    async def _main() -> None:
        await seed()
        close_client()

    asyncio.run(_main())
