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


async def _seed(client):
    db = client[db_module.get_settings().mongo_db]
    ana_id, bruno_id = ObjectId(), ObjectId()
    await db.users.insert_many(
        [
            {"_id": ana_id, "name": "Ana", "base_salary_cents": 500000},
            {"_id": bruno_id, "name": "Bruno", "base_salary_cents": 300000},
        ]
    )
    cat_id = ObjectId()
    await db.categories.insert_one(
        {"_id": cat_id, "name": "Mercado", "icon": "cart", "is_shared_default": True}
    )
    await db.transactions.insert_many(
        [
            {
                "date": "2025-03-05",
                "period": "2025-03",
                "description": "Mercado",
                "raw_description": "Mercado",
                "amount_cents": 100000,
                "owner_user_id": str(ana_id),
                "category_id": str(cat_id),
                "is_shared": True,
                "source": "manual",
                "classified_by": "manual",
                "rule_id": None,
                "import_batch_id": None,
                "dedup_hash": "h1",
            },
            {
                "date": "2025-03-06",
                "period": "2025-03",
                "description": "Mercado",
                "raw_description": "Mercado",
                "amount_cents": 20000,
                "owner_user_id": str(bruno_id),
                "category_id": str(cat_id),
                "is_shared": True,
                "source": "manual",
                "classified_by": "manual",
                "rule_id": None,
                "import_batch_id": None,
                "dedup_hash": "h2",
            },
        ]
    )
    return str(ana_id), str(bruno_id)


async def test_monthly_report_endpoint(mock_mongo):
    ana_id, bruno_id = await _seed(mock_mongo)
    token = create_access_token(ana_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/reports/2025-03", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["shared_total_cents"] == 120000
    assert data["settlement"]["from_user_id"] == bruno_id
    assert data["settlement"]["to_user_id"] == ana_id
    assert data["settlement"]["amount_cents"] == 25000


async def test_report_requires_auth(mock_mongo):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/reports/2025-03")
    assert resp.status_code == 401


async def test_ignored_transaction_is_excluded_from_report(mock_mongo):
    """Transação marcada como ignorada não entra no relatório nem no acerto."""
    ana_id, bruno_id = await _seed(mock_mongo)
    db = mock_mongo[db_module.get_settings().mongo_db]
    await db.transactions.insert_one(
        {
            "date": "2025-03-07",
            "period": "2025-03",
            "description": "Pagamento de fatura",
            "raw_description": "Pagamento de fatura",
            "amount_cents": 500000,  # R$ 5.000 — distorceria tudo se contasse
            "owner_user_id": str(bruno_id),
            "category_id": None,
            "is_shared": False,
            "is_ignored": True,
            "source": "ofx",
            "classified_by": "rule",
            "rule_id": None,
            "import_batch_id": None,
            "dedup_hash": "h-ignored",
        }
    )
    token = create_access_token(ana_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/reports/2025-03", headers={"Authorization": f"Bearer {token}"})
    data = resp.json()
    # Mesmos números do teste sem a linha ignorada.
    assert data["shared_total_cents"] == 120000
    assert data["settlement"]["amount_cents"] == 25000


async def test_trend_returns_series_ordered_by_period(mock_mongo):
    ana_id, bruno_id = await _seed(mock_mongo)
    db = mock_mongo[db_module.get_settings().mongo_db]
    # Um segundo mês, para a série ter mais de um ponto.
    await db.transactions.insert_one(
        {
            "date": "2025-04-02",
            "period": "2025-04",
            "description": "Mercado",
            "raw_description": "Mercado",
            "amount_cents": 50000,
            "owner_user_id": str(ana_id),
            "category_id": None,
            "is_shared": True,
            "is_ignored": False,
            "source": "manual",
            "classified_by": "manual",
            "rule_id": None,
            "import_batch_id": None,
            "dedup_hash": "h-abr",
        }
    )
    token = create_access_token(ana_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/reports/trend", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()

    assert [p["period"] for p in data["points"]] == ["2025-03", "2025-04"]
    assert data["points"][0]["total_cents"] == 120000
    assert data["points"][1]["total_cents"] == 50000
    assert data["average_total_cents"] == 85000  # (120000 + 50000) / 2
    assert data["categories"][0] == "Mercado"  # a que mais pesa vem primeiro
    assert {u["name"] for u in data["points"][0]["users"]} == {"Ana", "Bruno"}


async def test_trend_respects_months_window(mock_mongo):
    """months=1 devolve só o mês mais recente."""
    ana_id, _ = await _seed(mock_mongo)
    token = create_access_token(ana_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/reports/trend?months=1", headers={"Authorization": f"Bearer {token}"}
        )
    assert [p["period"] for p in resp.json()["points"]] == ["2025-03"]


async def test_trend_excludes_ignored(mock_mongo):
    """A série usa a mesma base do relatório: ignorado não conta."""
    ana_id, bruno_id = await _seed(mock_mongo)
    db = mock_mongo[db_module.get_settings().mongo_db]
    await db.transactions.insert_one(
        {
            "date": "2025-03-08",
            "period": "2025-03",
            "description": "Pagamento de fatura",
            "raw_description": "Pagamento de fatura",
            "amount_cents": 999900,
            "owner_user_id": str(bruno_id),
            "category_id": None,
            "is_shared": False,
            "is_ignored": True,
            "source": "ofx",
            "classified_by": "rule",
            "rule_id": None,
            "import_batch_id": None,
            "dedup_hash": "h-ign-trend",
        }
    )
    token = create_access_token(ana_id)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/reports/trend", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["points"][0]["total_cents"] == 120000
