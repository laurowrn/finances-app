import io
from decimal import Decimal

from app.services.money import from_decimal
from app.services.parsers.base import ParsedTx, ParseError


def _fix_mojibake(text: str) -> str:
    """Repara texto UTF-8 que foi lido como cp1252: "CrÃ©dito" -> "Crédito".

    Alguns OFX do Nubank declaram `CHARSET:1252` no cabeçalho mas gravam os
    bytes em UTF-8. O ofxparse obedece o cabeçalho e devolve o texto trocado.

    Só mexe quando há sinal claro de troca (Ã/Â/â€) E a reinterpretação
    funciona sem perda — assim um texto legitimamente cp1252 passa intacto.
    """
    if not any(hint in text for hint in ("Ã", "Â", "â€")):
        return text
    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


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
            # ofxparse já entrega Decimal; converter direto preserva o exato.
            amount = from_decimal(Decimal(t.amount))
            if amount >= 0:
                # crédito (salário/estorno) — ignorado; o app rastreia gastos
                continue
            description = _fix_mojibake((t.memo or t.payee or "").strip()) or "Sem descrição"
            txs.append(
                ParsedTx(date=t.date.date(), description=description, amount_cents=abs(amount))
            )
    return txs
