from datetime import date
from pathlib import Path

from app.services.parsers import parse_csv, parse_ofx

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_parse_ofx_skips_credits():
    txs = parse_ofx((FIXTURES / "sample.ofx").read_bytes())
    # 2 débitos; o crédito (salário) é ignorado
    assert len(txs) == 2
    amounts = sorted(t.amount for t in txs)
    assert amounts == [45.90, 120.00]
    assert all(t.amount > 0 for t in txs)
    uber = next(t for t in txs if "UBER" in t.description)
    assert uber.date == date(2025, 3, 5)


def test_parse_csv_card_invoice_all_positive():
    txs = parse_csv((FIXTURES / "nubank_cartao.csv").read_bytes())
    assert len(txs) == 3  # todas as compras (positivas)
    assert {t.amount for t in txs} == {45.90, 120.00, 39.90}


def test_parse_csv_account_statement_ptbr():
    txs = parse_csv((FIXTURES / "extrato_conta.csv").read_bytes())
    # extrato: pega os débitos (negativos), ignora o salário positivo
    assert len(txs) == 2
    amounts = sorted(t.amount for t in txs)
    assert amounts == [45.90, 1120.50]  # decimal PT-BR "1.120,50"
    assert txs[0].date == date(2025, 3, 5) or txs[1].date == date(2025, 3, 5)
