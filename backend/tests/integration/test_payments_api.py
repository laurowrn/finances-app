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


async def test_monthly_report_ignores_payments(mock_mongo):
    """O acerto do mês reflete só os gastos do período; quem abate pagamento
    é o saldo acumulado."""
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
                "amount_cents": 10000,
            },
            headers=headers,
        )
        assert resp.status_code == 200
        payment = resp.json()
        assert payment["period"] == "2025-03"

        # Gastos: Ana 1000 (cota 750), Bruno 200 (cota 450) -> acerto de 250.
        # O pagamento de 100 NÃO entra aqui.
        resp = await client.get("/reports/2025-03", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["settlement"]["amount_cents"] == 25000
        assert {u["name"]: u["balance_cents"] for u in data["users"]} == {
            "Ana": 25000,
            "Bruno": -25000,
        }

        # ...mas entra no saldo acumulado: 250 - 100 = 150.
        resp = await client.get("/reports/balance", headers=headers)
        assert resp.json()["settlement"]["amount_cents"] == 15000

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
                "amount_cents": 10000,
            },
            headers=headers,
        )
        resp = await client.get("/reports/balance", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["as_of_period"] == "2025-03"
        assert data["settlement"]["from_user_id"] == bruno_id
        assert data["settlement"]["to_user_id"] == ana_id
        assert data["settlement"]["amount_cents"] == 15000


async def test_cumulative_balance_reflects_payment_in_period_without_transactions(mock_mongo):
    """Acerto registrado em um mês sem transações (ex.: pago depois do último import)
    também precisa abater o saldo acumulado."""
    ana_id, bruno_id = await _seed(mock_mongo)
    token = create_access_token(ana_id)
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/payments",
            json={
                "date": "2025-08-10",  # nenhuma transação em 2025-08
                "from_user_id": bruno_id,
                "to_user_id": ana_id,
                "amount_cents": 25000,
            },
            headers=headers,
        )
        assert resp.status_code == 200

        resp = await client.get("/reports/balance", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["as_of_period"] == "2025-08"
        # Saldo bruto era 250 (Bruno devia a Ana); o pagamento de 250 zera o acerto.
        assert data["settlement"]["amount_cents"] == 0
        assert {b["name"]: b["balance_cents"] for b in data["balances"]} == {"Ana": 0, "Bruno": 0}


async def test_payments_require_auth(mock_mongo):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/payments")
    assert resp.status_code == 401
