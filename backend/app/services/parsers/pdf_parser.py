"""Parser de PDF (extrato/fatura) — melhor esforço.

PDFs não têm layout padronizado; este parser usa heurística de linha e deve ser
tratado como ponto de partida para revisão manual. Casos reais devem ser usados
para calibrar a regex/estratégia (ver nota no plano).
"""

import io
import re
from datetime import date, datetime

from app.services.parsers.base import ParsedTx, ParseError

# Ex.: "12/03/2025  UBER *TRIP           45,90"  ou  "12/03 PADARIA X 12,00"
LINE_RE = re.compile(
    r"^(?P<date>\d{2}/\d{2}(?:/\d{2,4})?)\s+(?P<desc>.+?)\s+"
    r"(?P<amount>-?R?\$?\s?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+\.\d{2})\s*$"
)

DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%d/%m")


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


def _parse_amount(value: str) -> float | None:
    value = value.replace("R$", "").replace("$", "").replace(" ", "").strip()
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    try:
        return float(value)
    except ValueError:
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

    txs: list[ParsedTx] = []
    for line in lines:
        m = LINE_RE.match(line.strip())
        if not m:
            continue
        d = _parse_date(m.group("date"))
        amount = _parse_amount(m.group("amount"))
        desc = m.group("desc").strip()
        if d is None or amount is None or amount == 0 or not desc:
            continue
        # em fatura, valores positivos são gastos; negativos costumam ser estorno/pagamento
        if amount < 0:
            continue
        txs.append(ParsedTx(date=d, description=desc, amount=abs(amount)))
    return txs
