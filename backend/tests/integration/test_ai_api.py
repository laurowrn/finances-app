"""Fluxo completo do relatório de IA: dossiê -> gravar -> conferir metas."""

import pytest
from bson import ObjectId
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

import app.db as db_module
from app.auth import create_access_token
from app.main import app


@pytest.fixture
def mock_mongo(monkeypatch):
    client = AsyncMongoMockClient()
    monkeypatch.setattr(db_module, "_client", client)
    return client


def _tx(period, date, amount, owner, cat, desc, ignored=False):
    return {
        "date": date,
        "period": period,
        "description": desc,
        "raw_description": desc,
        "amount_cents": amount,
        "owner_user_id": owner,
        "category_id": cat,
        "is_shared": True,
        "is_ignored": ignored,
        "source": "ofx",
        "classified_by": "rule",
        "rule_id": None,
        "import_batch_id": None,
        "dedup_hash": f"h-{period}-{date}-{amount}-{desc}",
    }


async def _seed(client):
    db = client[db_module.get_settings().mongo_db]
    ana, bruno = ObjectId(), ObjectId()
    await db.users.insert_many([
        {"_id": ana, "name": "Ana", "base_salary_cents": 500000},
        {"_id": bruno, "name": "Bruno", "base_salary_cents": 300000},
    ])
    mercado, lazer = ObjectId(), ObjectId()
    await db.categories.insert_many([
        {"_id": mercado, "name": "Mercado", "icon": "cart", "is_shared_default": True},
        {"_id": lazer, "name": "Lazer", "icon": "party", "is_shared_default": True},
    ])
    a, b, m, laz = str(ana), str(bruno), str(mercado), str(lazer)
    await db.transactions.insert_many([
        _tx("2026-07", "2026-07-05", 120000, a, m, "Cooper Filial"),
        _tx("2026-07", "2026-07-12", 80000, a, m, "Cooper"),
        _tx("2026-07", "2026-07-20", 60000, b, laz, "Cinema - Parcela 2/4"),
        _tx("2026-07", "2026-07-25", 500000, a, None, "Pagamento de fatura", ignored=True),
        # mês anterior, para o histórico
        _tx("2026-06", "2026-06-10", 150000, a, m, "Cooper"),
    ])
    return a, b, m, laz


@pytest.fixture
async def auth(mock_mongo):
    ids = await _seed(mock_mongo)
    token = create_access_token(ids[0])
    return {"Authorization": f"Bearer {token}"}, ids


async def test_analysis_dossier_aggregates_the_month(auth):
    headers, (a, b, m, laz) = auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/ai/analysis/2026-07", headers=headers)
    assert resp.status_code == 200
    d = resp.json()

    # ignorado não entra no total, mas é reportado à parte
    assert d["total_cents"] == 260000
    assert d["transaction_count"] == 3
    assert d["ignored_cents"] == 500000
    assert d["ignored_count"] == 1

    assert d["income_cents"] == 800000
    assert d["spend_pct_of_income"] == 32.5
    assert d["surplus_cents"] == 540000
    assert d["by_user"] == {"Ana": 200000, "Bruno": 60000}

    mercado = next(c for c in d["by_category"] if c["category_name"] == "Mercado")
    assert mercado["total_cents"] == 200000
    assert mercado["count"] == 2
    assert mercado["history_cents"]["2026-06"] == 150000

    assert d["installment_tail_cents"] == 2 * 60000  # parcela 2/4 -> faltam 2
    assert d["monthly_totals"]["2026-07"] == 260000
    assert d["monthly_totals"]["2026-06"] == 150000

    cooper = next(mm for mm in d["top_merchants"] if mm["key"] == "cooper")
    assert cooper["total_cents"] == 200000


async def test_create_report_then_check_goals_against_next_month(auth, mock_mongo):
    headers, (a, b, m, laz) = auth
    db = mock_mongo[db_module.get_settings().mongo_db]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/ai/reports", headers=headers, json={
            "period": "2026-07",
            "goals_period": "2026-08",
            "summary_md": "# Julho\nGastamos demais no mercado.",
            "goals": [
                {"id": "mercado", "title": "Mercado até R$ 1.500",
                 "metric": "category_max", "category_id": m,
                 "target_cents": 150000, "baseline_cents": 200000,
                 "rationale": "cortar 25%"},
                {"id": "idas-cooper", "title": "No máximo 1 ida ao Cooper",
                 "metric": "count_max", "match": "cooper",
                 "target_count": 1, "baseline_count": 2,
                 "rationale": "concentrar a compra"},
            ],
        })
        assert resp.status_code == 200
        assert resp.json()["period"] == "2026-07"

        # ainda não há agosto: metas de teto ficam cumpridas com zero gasto
        resp = await c.get("/ai/reports/2026-07/progress", headers=headers)
        assert resp.json()["achieved_count"] == 2

        # agosto acontece: estoura a de dinheiro, cumpre a de contagem
        await db.transactions.insert_one(
            _tx("2026-08", "2026-08-03", 180000, a, m, "Cooper Filial")
        )
        resp = await c.get("/ai/reports/2026-07/progress", headers=headers)
        prog = resp.json()

    assert prog["period"] == "2026-08"
    assert prog["achieved_count"] == 1
    by_id = {g["goal"]["id"]: g for g in prog["goals"]}
    assert by_id["mercado"]["achieved"] is False
    assert by_id["mercado"]["actual_cents"] == 180000
    assert by_id["mercado"]["delta"] == 30000  # 300 acima do teto
    assert by_id["idas-cooper"]["achieved"] is True
    assert by_id["idas-cooper"]["actual"] == 1
    # meta estourada não gera "economia"
    assert prog["total_saved_cents"] == 20000  # baseline 2000 - real 1800


async def test_report_upsert_replaces_same_period(auth):
    headers, _ = auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        base = {"period": "2026-07", "goals_period": "2026-08", "goals": []}
        await c.post("/ai/reports", headers=headers, json={**base, "summary_md": "v1"})
        await c.post("/ai/reports", headers=headers, json={**base, "summary_md": "v2"})
        listed = (await c.get("/ai/reports", headers=headers)).json()
        current = (await c.get("/ai/reports/2026-07", headers=headers)).json()
    assert len(listed) == 1
    assert current["summary_md"] == "v2"


async def test_duplicate_goal_ids_are_rejected(auth):
    headers, (a, b, m, laz) = auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/ai/reports", headers=headers, json={
            "period": "2026-07", "goals_period": "2026-08", "summary_md": "x",
            "goals": [
                {"id": "dup", "title": "a", "metric": "total_max",
                 "target_cents": 1, "rationale": ""},
                {"id": "dup", "title": "b", "metric": "total_max",
                 "target_cents": 2, "rationale": ""},
            ],
        })
    assert resp.status_code == 400


async def test_missing_report_returns_404(auth):
    headers, _ = auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get("/ai/reports/1999-01", headers=headers)).status_code == 404
        assert (await c.get("/ai/reports/1999-01/progress", headers=headers)).status_code == 404


async def test_ai_endpoints_require_auth(mock_mongo):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get("/ai/analysis/2026-07")).status_code == 401
        assert (await c.get("/ai/reports")).status_code == 401
