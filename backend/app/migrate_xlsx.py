"""Migração única da planilha antiga (Gastos Mensais.xlsx) para o Mongo.

Lê salários, categorias, transações (todas marcadas como compartilhadas — na
planilha só existiam gastos já compartilhados, sem regra de classificação) e
pagamentos reais (uma linha de pagamento com valor NEGATIVO é um hack da
planilha antiga para carregar saldo não pago pro mês seguinte — não é um
pagamento real, e é sempre ignorada; o saldo acumulado do app novo resolve
isso estruturalmente).

Uso:
    python -m app.migrate_xlsx "Gastos Mensais.xlsx" --dry-run   # só relatório, não grava nada
    python -m app.migrate_xlsx "Gastos Mensais.xlsx"             # grava de verdade

Idempotente: pode rodar mais de uma vez sem duplicar transações (índice único
de dedup_hash) nem categorias (upsert por nome). Pagamentos não têm índice
único formal, mas o script confere duplicata exata (período/de/para/valor)
antes de inserir.
"""

import argparse
import asyncio
from datetime import UTC, date, datetime

from openpyxl import load_workbook

from app.db import close_client, ensure_indexes, get_db
from app.models.enums import ClassifiedBy, Source
from app.repositories import users as users_repo
from app.repositories.common import period_of
from app.services.dedup import dedup_hash
from app.settings import get_settings

SHEET_PERIODS: dict[str, tuple[int, int]] = {
    "Agosto": (2024, 8),
    "Setembro": (2024, 9),
    "Outubro": (2024, 10),
    "Novembro": (2024, 11),
    "Dezembro": (2024, 12),
    "Janeiro": (2025, 1),
    "Fevereiro": (2025, 2),
    "Março": (2025, 3),
    "Abril": (2025, 4),
    "Maio": (2025, 5),
    "Junho": (2025, 6),
    "Julho": (2025, 7),
    "Agosto2025": (2025, 8),
    "Setembro2025": (2025, 9),
    "Outubro2025": (2025, 10),
    "Novembro2025": (2025, 11),
    "Dezembro2025": (2025, 12),
    "Janeiro2026": (2026, 1),
    "Fevereiro2026": (2026, 2),
    "Março2026": (2026, 3),
    "Abril2026": (2026, 4),
    "Maio2026": (2026, 5),
    "Junho2026": (2026, 6),
}

# Categorias da planilha sem equivalente no app hoje — preserva granularidade
# total (nenhuma é mesclada em outra existente).
NEW_CATEGORIES = [
    ("Qtal", "tag", True),
    ("Farmácia", "pill", True),
    ("Internet", "wifi", True),
    ("Luz", "zap", True),
    ("Gasolina", "fuel", True),
    ("Ensino", "graduation-cap", True),
    ("Academia", "dumbbell", True),
]
FALLBACK_CATEGORY = "Outros"


def _parse_amount(raw: object) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, int | float):
        return float(raw)
    text = str(raw).strip().replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


async def _resolve_users() -> dict[str, str]:
    settings = get_settings()
    users = await users_repo.list_users()
    by_name = {u["name"]: u["id"] for u in users}
    expected = (settings.user_a_name, settings.user_b_name)
    missing = [n for n in expected if n not in by_name]
    if missing:
        raise SystemExit(
            f"Usuário(s) não encontrado(s): {missing}. Rode o seed antes (python -m app.seed)."
        )
    return by_name


async def _ensure_categories(dry_run: bool, warnings: list[str]) -> dict[str, str]:
    db = get_db()
    existing = {c["name"]: str(c["_id"]) async for c in db.categories.find()}
    to_create = [(n, i, s) for n, i, s in NEW_CATEGORIES if n not in existing]
    if to_create:
        names = [n for n, _, _ in to_create]
        if dry_run:
            warnings.append(f"[dry-run] categorias que seriam criadas: {names}")
            for n, _, _ in to_create:
                existing[n] = f"<dry-run:{n}>"
        else:
            for name, icon, shared_default in to_create:
                await db.categories.update_one(
                    {"name": name},
                    {
                        "$setOnInsert": {
                            "name": name,
                            "icon": icon,
                            "is_shared_default": shared_default,
                        }
                    },
                    upsert=True,
                )
            existing = {c["name"]: str(c["_id"]) async for c in db.categories.find()}
            print(f"Categorias criadas: {names}")
    if FALLBACK_CATEGORY not in existing:
        raise SystemExit(f"Categoria {FALLBACK_CATEGORY!r} não existe. Rode o seed antes.")
    return existing


async def _migrate_sheet(
    sheet_name: str,
    year: int,
    month: int,
    ws,
    user_ids: dict[str, str],
    category_ids: dict[str, str],
    dry_run: bool,
    stats: dict[str, int],
    warnings: list[str],
    last_salaries: dict[str, float],
) -> None:
    db = get_db()
    period = f"{year:04d}-{month:02d}"
    tx_date = date(year, month, 1)
    names = list(user_ids.keys())

    # --- salários ---
    for cell, expected_name in (("A2", names[0]), ("A3", names[1])):
        label = ws[cell].value
        if label != expected_name:
            warnings.append(
                f"{sheet_name}: rótulo {cell}={label!r}, esperava {expected_name!r} "
                "— salário dessa linha pulado"
            )

    for row, name in ((2, names[0]), (3, names[1])):
        salary = _parse_amount(ws.cell(row=row, column=2).value)
        if salary is None:
            warnings.append(f"{sheet_name}: salário de {name} (B{row}) vazio/inválido — pulado")
            continue
        last_salaries[name] = salary
        stats["incomes_upserted"] += 1
        if not dry_run:
            await users_repo.upsert_income(user_ids[name], period, salary)

    # --- transações ---
    for row in range(2, ws.max_row + 1):
        buyer = ws.cell(row=row, column=4).value
        category_raw = ws.cell(row=row, column=5).value
        item = ws.cell(row=row, column=6).value
        amount_raw = ws.cell(row=row, column=7).value
        if buyer is None and category_raw is None and amount_raw is None:
            continue

        owner_user_id = user_ids.get(buyer) if isinstance(buyer, str) else None
        if owner_user_id is None:
            warnings.append(f"{sheet_name} D{row}: comprador {buyer!r} desconhecido — linha pulada")
            stats["tx_skipped"] += 1
            continue

        amount = _parse_amount(amount_raw)
        if amount is None or amount <= 0:
            warnings.append(
                f"{sheet_name} G{row}: valor {amount_raw!r} ausente/inválido — linha pulada"
            )
            stats["tx_skipped"] += 1
            continue

        category_name = category_raw.strip() if isinstance(category_raw, str) else None
        category_id = category_ids.get(category_name) if category_name else None
        if category_id is None:
            if category_name:
                warnings.append(
                    f"{sheet_name} E{row}: categoria {category_name!r} sem mapeamento "
                    f"— usando {FALLBACK_CATEGORY!r}"
                )
            category_id = category_ids[FALLBACK_CATEGORY]

        description = (
            item.strip()
            if isinstance(item, str) and item.strip()
            else (category_name or FALLBACK_CATEGORY)
        )
        date_iso = tx_date.isoformat()
        doc = {
            "date": date_iso,
            "period": period_of(tx_date),
            "description": description,
            "raw_description": description,
            "amount": round(amount, 2),
            "owner_user_id": owner_user_id,
            "category_id": category_id,
            "is_shared": True,
            "source": Source.MANUAL.value,
            "classified_by": ClassifiedBy.MANUAL.value,
            "rule_id": None,
            "import_batch_id": None,
            "dedup_hash": dedup_hash(date_iso, amount, owner_user_id, description),
            "created_at": datetime.now(UTC),
        }
        if dry_run:
            stats["tx_inserted"] += 1
            continue
        try:
            await db.transactions.insert_one(doc)
            stats["tx_inserted"] += 1
        except Exception as exc:  # DuplicateKeyError (import indireto evita acoplar pymongo aqui)
            if "duplicate key" in str(exc).lower():
                stats["tx_duplicate"] += 1
            else:
                raise

    # --- pagamentos ---
    for row in (18, 19):
        name = ws.cell(row=row, column=9).value
        amount_raw = ws.cell(row=row, column=10).value
        if name is None and amount_raw is None:
            continue
        amount = _parse_amount(amount_raw)
        if amount is None:
            warnings.append(
                f"{sheet_name} J{row}: valor de pagamento inválido ({amount_raw!r}) — pulado"
            )
            continue
        if amount < 0:
            # hack de carregar saldo não pago pro mês seguinte — não é pagamento real.
            stats["pay_skipped_negative"] += 1
            continue
        if amount == 0:
            continue
        if not isinstance(name, str) or name not in user_ids:
            warnings.append(
                f"{sheet_name} I{row}: pagamento de {amount} sem pagador reconhecível "
                f"({name!r}) — pulado, revise manualmente"
            )
            stats["pay_skipped_no_name"] += 1
            continue

        from_user_id = user_ids[name]
        to_user_id = next(uid for n, uid in user_ids.items() if n != name)
        note = f"Migrado da planilha ({sheet_name})"

        if not dry_run:
            existing = await db.payments.find_one(
                {
                    "period": period,
                    "from_user_id": from_user_id,
                    "to_user_id": to_user_id,
                    "amount": round(amount, 2),
                }
            )
            if existing:
                stats["pay_duplicate"] += 1
                continue
            await db.payments.insert_one(
                {
                    "date": tx_date.isoformat(),
                    "period": period,
                    "from_user_id": from_user_id,
                    "to_user_id": to_user_id,
                    "amount": round(amount, 2),
                    "note": note,
                    "created_at": datetime.now(UTC),
                }
            )
        stats["pay_inserted"] += 1


async def migrate(path: str, dry_run: bool) -> None:
    await ensure_indexes()
    wb = load_workbook(path, data_only=True)

    user_ids = await _resolve_users()
    warnings: list[str] = []
    category_ids = await _ensure_categories(dry_run, warnings)

    stats = {
        "tx_inserted": 0,
        "tx_duplicate": 0,
        "tx_skipped": 0,
        "pay_inserted": 0,
        "pay_skipped_negative": 0,
        "pay_skipped_no_name": 0,
        "pay_duplicate": 0,
        "incomes_upserted": 0,
    }
    last_salaries: dict[str, float] = {}

    for sheet_name, (year, month) in SHEET_PERIODS.items():
        if sheet_name not in wb.sheetnames:
            warnings.append(f"Aba {sheet_name!r} não encontrada no arquivo — pulada")
            continue
        await _migrate_sheet(
            sheet_name,
            year,
            month,
            wb[sheet_name],
            user_ids,
            category_ids,
            dry_run,
            stats,
            warnings,
            last_salaries,
        )

    if not dry_run and last_salaries:
        for name, salary in last_salaries.items():
            await users_repo.update_user(user_ids[name], {"base_salary": salary})

    print()
    print("=== Resumo da migração" + (" (DRY-RUN — nada foi gravado)" if dry_run else "") + " ===")
    print(f"Transações inseridas: {stats['tx_inserted']}")
    print(f"Transações já existentes (dedup): {stats['tx_duplicate']}")
    print(f"Transações puladas (dado inválido): {stats['tx_skipped']}")
    print(f"Pagamentos inseridos: {stats['pay_inserted']}")
    print(f"Pagamentos ignorados (carry-over negativo): {stats['pay_skipped_negative']}")
    print(f"Pagamentos ignorados (sem nome do pagador): {stats['pay_skipped_no_name']}")
    print(f"Pagamentos já existentes (duplicata exata): {stats['pay_duplicate']}")
    print(f"Incomes upsertados: {stats['incomes_upserted']}")
    if last_salaries:
        print(f"Novo base_salary (último mês encontrado): {last_salaries}")
    if warnings:
        print(f"\n{len(warnings)} aviso(s):")
        for w in warnings:
            print(f"  - {w}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default="Gastos Mensais.xlsx")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    async def _run() -> None:
        try:
            await migrate(args.path, args.dry_run)
        finally:
            close_client()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
