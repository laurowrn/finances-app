import io

from app.services.parsers.base import ParsedTx, ParseError


def parse_ofx(content: bytes) -> list[ParsedTx]:
    """Parseia OFX (extrato ou fatura). Considera apenas débitos (gastos)."""
    try:
        from ofxparse import OfxParser
    except ImportError as exc:  # pragma: no cover
        raise ParseError("Biblioteca ofxparse não instalada") from exc

    try:
        ofx = OfxParser.parse(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001 - ofxparse levanta erros variados
        raise ParseError(f"OFX inválido: {exc}") from exc

    txs: list[ParsedTx] = []
    for account in ofx.accounts:
        statement = account.statement
        for t in statement.transactions:
            amount = float(t.amount)
            if amount >= 0:
                # crédito (salário/estorno) — ignorado; o app rastreia gastos
                continue
            description = (t.memo or t.payee or "").strip() or "Sem descrição"
            txs.append(ParsedTx(date=t.date.date(), description=description, amount=abs(amount)))
    return txs
