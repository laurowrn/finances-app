from dataclasses import dataclass
from datetime import date


class ParseError(Exception):
    pass


@dataclass
class ParsedTx:
    date: date
    description: str
    amount: float  # sempre positivo = valor do gasto (débito)
