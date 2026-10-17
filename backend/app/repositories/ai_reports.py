"""Relatórios de IA. Um relatório por período analisado — gravar de novo
substitui o anterior, para não acumular versões do mesmo mês."""

from datetime import UTC, datetime

from app.db import get_db
from app.repositories.common import doc_out


async def upsert_report(data: dict) -> dict:
    doc = {**data, "created_at": datetime.now(UTC)}
    await get_db().ai_reports.replace_one({"period": data["period"]}, doc, upsert=True)
    return doc_out(await get_db().ai_reports.find_one({"period": data["period"]}))


async def get_report(period: str) -> dict | None:
    return doc_out(await get_db().ai_reports.find_one({"period": period}))


async def list_reports() -> list[dict]:
    docs = await get_db().ai_reports.find().sort("period", -1).to_list(length=200)
    return [doc_out(d) for d in docs]


async def latest_report() -> dict | None:
    docs = await get_db().ai_reports.find().sort("period", -1).to_list(length=1)
    return doc_out(docs[0]) if docs else None


async def delete_report(period: str) -> int:
    result = await get_db().ai_reports.delete_one({"period": period})
    return result.deleted_count
