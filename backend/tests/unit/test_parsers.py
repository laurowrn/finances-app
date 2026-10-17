from datetime import date
from pathlib import Path

from app.services.parsers import parse_csv, parse_ofx
from app.services.parsers.ofx_parser import _fix_mojibake

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_parse_ofx_skips_credits():
    txs = parse_ofx((FIXTURES / "sample.ofx").read_bytes())
    # 2 débitos; o crédito (salário) é ignorado
    assert len(txs) == 2
    amounts = sorted(t.amount_cents for t in txs)
    assert amounts == [4590, 12000]
    assert all(t.amount_cents > 0 for t in txs)
    uber = next(t for t in txs if "UBER" in t.description)
    assert uber.date == date(2025, 3, 5)


def test_parse_csv_card_invoice_all_positive():
    txs = parse_csv((FIXTURES / "nubank_cartao.csv").read_bytes())
    assert len(txs) == 3  # todas as compras (positivas)
    assert {t.amount_cents for t in txs} == {4590, 12000, 3990}


def test_parse_csv_account_statement_ptbr():
    txs = parse_csv((FIXTURES / "extrato_conta.csv").read_bytes())
    # extrato: pega os débitos (negativos), ignora o salário positivo
    assert len(txs) == 2
    amounts = sorted(t.amount_cents for t in txs)
    assert amounts == [4590, 112050]  # decimal PT-BR "1.120,50"
    assert txs[0].date == date(2025, 3, 5) or txs[1].date == date(2025, 3, 5)


def test_fix_mojibake_repairs_utf8_read_as_cp1252():
    """Nubank declara CHARSET:1252 mas grava UTF-8 em alguns arquivos."""
    assert _fix_mojibake("Pix no CrÃ©dito - CARREFOUR") == "Pix no Crédito - CARREFOUR"
    assert _fix_mojibake("SÃ£o Paulo") == "São Paulo"


def test_fix_mojibake_leaves_correct_text_alone():
    assert _fix_mojibake("Pix no Crédito") == "Pix no Crédito"
    assert _fix_mojibake("Cooper Filial Itoupava") == "Cooper Filial Itoupava"
    assert _fix_mojibake("") == ""


# ---------- PDF: extrato de conta vs. fatura de cartão ----------


def _pdf_lines(text: str):
    """Roda só a lógica de linha do parser de PDF, sem precisar gerar um PDF."""
    import app.services.parsers.pdf_parser as mod

    class _FakePage:
        def extract_text(self):
            return text

    class _FakePdf:
        pages = [_FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _FakePlumber:
        @staticmethod
        def open(_):
            return _FakePdf()

    import sys

    sys.modules["pdfplumber"] = _FakePlumber
    try:
        return mod.parse_pdf(b"")
    finally:
        del sys.modules["pdfplumber"]


ITAU_EXTRATO = """\
data lançamentos valor (R$) saldo (R$)
03/08/2026 PAGTO SALARIO 3.127,22
03/08/2026 PIX QRS CREMER S.A.01/08 -41,05
01/08/2026 SALDO DO DIA 3.094,23
29/07/2026 PIX QRS QTAL MINIME29/07 -4,74
29/07/2026 SALDO DO DIA 8,06
27/07/2026 PIX TRANSF Lauro W27/07 -250,00
27/07/2026 SALDO DO DIA 26,16
"""


def test_pdf_account_statement_takes_negatives_as_expenses():
    """Extrato de conta: gasto é negativo. Antes o parser fixava
    'positivo = gasto' e importava salário e saldo em vez das despesas."""
    txs = _pdf_lines(ITAU_EXTRATO)
    descs = [t.description for t in txs]

    assert all("SALDO" not in d.upper() for d in descs), "saldo do dia não é lançamento"
    assert all("SALARIO" not in d.upper() for d in descs), "salário é receita, não gasto"
    assert sorted(t.amount_cents for t in txs) == [474, 4105, 25000]
    assert all(t.amount_cents > 0 for t in txs)


FATURA_CARTAO = """\
12/03/2026 UBER *TRIP 45,90
13/03/2026 PADARIA X 12,00
14/03/2026 MERCADO Y 120,00
15/03/2026 ESTORNO COMPRA -30,00
"""


def test_pdf_card_invoice_still_takes_positives_as_expenses():
    """Fatura de cartão: compra é positiva, estorno é negativo."""
    txs = _pdf_lines(FATURA_CARTAO)
    assert sorted(t.amount_cents for t in txs) == [1200, 4590, 12000]
    assert all("ESTORNO" not in t.description.upper() for t in txs)


def test_pdf_drops_balance_lines_even_when_spaced():
    txs = _pdf_lines("01/07/2026 S A L D O ANTERIOR 1.000,00\n02/07/2026 COMPRA 10,00\n")
    assert [t.description for t in txs] == ["COMPRA"]
