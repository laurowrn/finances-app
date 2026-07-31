from app.models.enums import Source
from app.services.parsers.base import ParsedTx, ParseError
from app.services.parsers.csv_parser import parse_csv
from app.services.parsers.ofx_parser import parse_ofx
from app.services.parsers.pdf_parser import parse_pdf


def parse_file(filename: str, content: bytes, source: Source | None = None) -> list[ParsedTx]:
    """Dispatch por extensão/source. Retorna gastos (débitos) como valores positivos."""
    src = source or _infer_source(filename)
    if src == Source.OFX:
        return parse_ofx(content)
    if src == Source.CSV:
        return parse_csv(content)
    if src == Source.PDF:
        return parse_pdf(content)
    raise ParseError(f"Tipo de arquivo não suportado: {filename}")


def _infer_source(filename: str) -> Source:
    name = filename.lower()
    if name.endswith(".ofx"):
        return Source.OFX
    if name.endswith(".csv"):
        return Source.CSV
    if name.endswith(".pdf"):
        return Source.PDF
    raise ParseError(f"Não foi possível inferir o tipo do arquivo: {filename}")


__all__ = ["ParsedTx", "ParseError", "parse_file", "parse_ofx", "parse_csv", "parse_pdf"]
