"""Parser de PDF (extrato/fatura) — melhor esforço.

PDFs não têm layout padronizado; este parser usa heurística de linha e deve ser
tratado como ponto de partida para revisão manual. Casos reais devem ser usados
para calibrar a regex/estratégia (ver nota no plano).
"""

import io
import re
from datetime import date, datetime

from app.services.money import parse_brl
from app.services.parsers.base import ParsedTx, ParseError

# Ex.: "12/03/2025  UBER *TRIP           45,90"  ou  "12/03 PADARIA X 12,00"
LINE_RE = re.compile(
    r"^(?P<date>\d{2}/\d{2}(?:/\d{2,4})?)\s+(?P<desc>.+?)\s+"
    r"(?P<amount>-?R?\$?\s?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+\.\d{2})\s*$"
)

DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%d/%m")

# O Itaú (e outros) intercalam o saldo do dia no meio dos lançamentos, com a
# mesma cara de uma linha de transação. Sem filtrar, o saldo vira "gasto" —
# num extrato real isso somou R$ 8.843 de lixo. O \s* entre as letras cobre
# bancos que imprimem "S A L D O".
NON_TRANSACTION_RE = re.compile(
    r"^\s*(s\s*a\s*l\s*d\s*o\b|total\b|subtotal\b|limite\b)", re.IGNORECASE
)


def _parse_date(value: str) -> date | None:
    for fmt in DATE_FORMATS:
        try:
            d = datetime.strptime(value, fmt).date()
            if fmt == "%d/%m":
                # sem ano no extrato: assume ano corrente (ajustável na revisão)
                d = d.replace(year=datetime.now().year)
            return d
        except ValueError:
            continue
    return None


def parse_pdf(content: bytes) -> list[ParsedTx]:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover
        raise ParseError("Biblioteca pdfplumber não instalada") from exc

    try:
        lines: list[str] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines.extend(text.splitlines())
    except Exception as exc:  # noqa: BLE001
        raise ParseError(f"Falha ao ler PDF: {exc}") from exc

    rows: list[tuple[date, str, int]] = []
    for line in lines:
        m = LINE_RE.match(line.strip())
        if not m:
            continue
        d = _parse_date(m.group("date"))
        amount = parse_brl(m.group("amount"))
        desc = m.group("desc").strip()
        if d is None or amount is None or amount == 0 or not desc:
            continue
        if NON_TRANSACTION_RE.match(desc):
            continue
        rows.append((d, desc, amount))

    if not rows:
        return []

    # Mesma heurística de sinal do parser de CSV: extrato de conta lança gasto
    # como negativo (e salário/estorno como positivo); fatura de cartão lança
    # compra como positivo. O lado majoritário é o gasto.
    #
    # Antes isto era fixo em "positivo = gasto", o que num extrato de conta
    # invertia tudo: descartava as 23 despesas reais e importava o salário.
    positives = [r for r in rows if r[2] > 0]
    negatives = [r for r in rows if r[2] < 0]
    expenses = positives if len(positives) > len(negatives) else negatives

    return [ParsedTx(date=d, description=desc, amount_cents=abs(a)) for d, desc, a in expenses]
