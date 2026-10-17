"""Migração única: valores em `float` de reais -> `int` de centavos.

Converte os documentos já gravados para o money pattern (ver
`app.services.money`). Idempotente: documentos já migrados são ignorados, então
rodar duas vezes não faz mal.

    python -m app.migrate_to_cents            # só mostra o que faria
    python -m app.migrate_to_cents --apply    # grava

Campos migrados:
    transactions.amount     -> amount_cents      (+ dedup_hash recalculado)
    payments.amount         -> amount_cents
    incomes.amount          -> amount_cents
    users.base_salary       -> base_salary_cents

O `dedup_hash` precisa ser recalculado porque passou a usar centavos na chave;
sem isso, um reimport do mesmo extrato não reconheceria as duplicatas antigas.
"""

import argparse
import asyncio
from collections import Counter

from app.db import close_client, get_db
from app.services.dedup import dedup_hash
from app.services.money import format_brl, from_float


async def _migrate_simple(collection: str, old_field: str, new_field: str, apply: bool) -> dict:
    """Converte um campo float de reais para um campo int de centavos."""
    db = get_db()
    cursor = db[collection].find({old_field: {"$exists": True}})
    stats = Counter()
    async for doc in cursor:
        stats["encontrados"] += 1
        if new_field in doc:
            stats["já migrados"] += 1
            continue
        cents = from_float(doc[old_field])
        stats["a converter"] += 1
        stats["soma_centavos"] += cents
        if apply:
            await db[collection].update_one(
                {"_id": doc["_id"]},
                {"$set": {new_field: cents}, "$unset": {old_field: ""}},
            )
    return stats


async def _migrate_transactions(apply: bool) -> dict:
    """Transações: converte o valor E recalcula o dedup_hash (que usa o valor)."""
    db = get_db()
    stats = Counter()
    seen_hashes: dict[str, object] = {}
    collisions = []

    async for doc in db.transactions.find({}):
        stats["encontrados"] += 1
        if "amount_cents" in doc:
            stats["já migrados"] += 1
            continue

        cents = from_float(doc["amount"])
        new_hash = dedup_hash(
            doc["date"], cents, doc["owner_user_id"], doc.get("description", "")
        )
        # O índice único em dedup_hash rejeitaria a segunda gravação; detectar
        # aqui dá uma mensagem útil em vez de um DuplicateKeyError no meio.
        if new_hash in seen_hashes:
            collisions.append((doc["_id"], seen_hashes[new_hash], doc["date"], cents))
            stats["colisões"] += 1
            continue
        seen_hashes[new_hash] = doc["_id"]

        stats["a converter"] += 1
        stats["soma_centavos"] += cents
        if apply:
            await db.transactions.update_one(
                {"_id": doc["_id"]},
                {"$set": {"amount_cents": cents, "dedup_hash": new_hash}, "$unset": {"amount": ""}},
            )

    if collisions:
        print(f"\n  ATENÇÃO: {len(collisions)} transação(ões) viraram duplicata exata após a")
        print("  conversão (mesma data, valor, dono e descrição). Não foram migradas:")
        for _id, other, date, cents in collisions[:10]:
            print(f"    {_id} colide com {other} — {date} {format_brl(cents)}")
    return stats


async def main(apply: bool) -> None:
    print("=== Migração float(reais) -> int(centavos) ===")
    print(f"modo: {'APLICANDO' if apply else 'simulação (use --apply para gravar)'}\n")

    targets = [
        ("transactions", None),
        ("payments", ("amount", "amount_cents")),
        ("incomes", ("amount", "amount_cents")),
        ("users", ("base_salary", "base_salary_cents")),
    ]

    for collection, fields in targets:
        if collection == "transactions":
            stats = await _migrate_transactions(apply)
        else:
            stats = await _migrate_simple(collection, fields[0], fields[1], apply)
        total = stats.pop("soma_centavos", 0)
        detail = ", ".join(f"{k}={v}" for k, v in stats.items()) or "nada"
        print(f"{collection:<14} {detail}")
        if total:
            print(f"{'':<14} soma convertida: {format_brl(total)}")

    if not apply:
        print("\nNada foi gravado. Rode com --apply para efetivar.")
    close_client()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="grava as mudanças no Mongo")
    asyncio.run(main(parser.parse_args().apply))
