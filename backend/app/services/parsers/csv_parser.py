import csv
import io
from datetime import date, datetime

from app.services.parsers.base import ParsedTx, ParseError

DATE_HEADERS = {"data", "date", "data da compra", "data de compra"}
DESC_HEADERS = {
    "descricao",
    "descrição",
    "description",
    "title",
    "titulo",
    "título",
    "historico",
    "histórico",
    "estabelecimento",
    "lancamento",
    "lançamento",
}
AMOUNT_HEADERS = {"valor", "amount", "value", "quantia"}

DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y", "%m/%d/%Y")


def _decode(content: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _sniff_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except csv.Error:
        # heurística: ; é comum em CSV PT-BR
        return ";" if sample.count(";") > sample.count(",") else ","


def _parse_date(value: str) -> date | None:
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(value: str) -> float | None:
    value = (value or "").strip().replace("R$", "").replace(" ", "")
    if not value:
        return None
    # formato PT-BR "1.234,56" -> "1234.56"; formato US "1,234.56" -> "1234.56"
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def _pick(headers: list[str], candidates: set[str]) -> str | None:
    norm = {h: h.strip().lower() for h in headers}
    for h, low in norm.items():
        if low in candidates:
            return h
    for h, low in norm.items():
        if any(c in low for c in candidates):
            return h
    return None


def parse_csv(content: bytes) -> list[ParsedTx]:
    text = _decode(content)
    if not text.strip():
        raise ParseError("CSV vazio")
    delimiter = _sniff_delimiter(text[:2048])
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ParseError("CSV sem cabeçalho reconhecível")

    headers = list(reader.fieldnames)
    date_col = _pick(headers, DATE_HEADERS)
    desc_col = _pick(headers, DESC_HEADERS)
    amount_col = _pick(headers, AMOUNT_HEADERS)
    if not (date_col and desc_col and amount_col):
        raise ParseError(f"Não achei colunas de data/descrição/valor no CSV. Cabeçalhos: {headers}")

    rows: list[tuple[date, str, float]] = []
    for raw in reader:
        d = _parse_date(raw.get(date_col, ""))
        amount = _parse_amount(raw.get(amount_col, ""))
        desc = (raw.get(desc_col) or "").strip() or "Sem descrição"
        if d is None or amount is None or amount == 0:
            continue
        rows.append((d, desc, amount))

    if not rows:
        return []

    # Heurística de sinal: extrato de conta tem mais débitos (negativos);
    # fatura de cartão vem com compras positivas. Escolhe o lado majoritário como "gasto".
    positives = [r for r in rows if r[2] > 0]
    negatives = [r for r in rows if r[2] < 0]
    if len(positives) > len(negatives):
        expenses = positives  # fatura de cartão
    else:
        expenses = negatives  # extrato de conta

    return [ParsedTx(date=d, description=desc, amount=abs(amt)) for (d, desc, amt) in expenses]
