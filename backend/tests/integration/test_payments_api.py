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
            {"_id": ana_id, "name": "Ana", "base_salary": 5000.0},
            {"_id": bruno_id, "name": "Bruno", "base_salary": 3000.0},
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
                "amount": 1000.0,
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
                "amount": 200.0,
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


async def test_create_payment_reduces_monthly_report(mock_mongo):
    ana_id, bruno_id = await _seed(mock_mongo)
    token = create_access_token(ana_id)
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/payments",
            json={
                "date": "2025-03-10",
                "from_user_id": bruno_id,
                "to_user_id": ana_id,
                "amount": 100.0,
            },
            headers=headers,
        )
        assert resp.status_code == 200
        payment = resp.json()
        assert payment["period"] == "2025-03"

        resp = await client.get("/reports/2025-03", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["settlement"]["amount"] == 150.0

        resp = await client.get("/payments?period=2025-03", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = await client.delete(f"/payments/{payment['id']}", headers=headers)
        assert resp.status_code == 204


async def test_cumulative_balance_reflects_payment(mock_mongo):
    ana_id, bruno_id = await _seed(mock_mongo)
    token = create_access_token(ana_id)
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/payments",
            json={
                "date": "2025-03-10",
                "from_user_id": bruno_id,
                "to_user_id": ana_id,
                "amount": 100.0,
            },
            headers=headers,
        )
        resp = await client.get("/reports/balance", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["as_of_period"] == "2025-03"
        assert data["settlement"]["from_user_id"] == bruno_id
        assert data["settlement"]["to_user_id"] == ana_id
        assert data["settlement"]["amount"] == 150.0


async def test_payments_require_auth(mock_mongo):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/payments")
    assert resp.status_code == 401
