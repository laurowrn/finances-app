from enum import StrEnum


class Split(StrEnum):
    """Como um gasto entra na conta do casal.

    IGNORED existe porque o extrato da conta e a fatura do cartão se sobrepõem:
    "Pagamento de fatura" no extrato é a mesma despesa que as compras da fatura.
    Lançamento ignorado fica gravado (some do relatório, não do histórico).
    """

    SHARED = "shared"
    INDIVIDUAL = "individual"
    IGNORED = "ignored"


class Source(StrEnum):
    OFX = "ofx"
    CSV = "csv"
    PDF = "pdf"
    MANUAL = "manual"


class StatementType(StrEnum):
    ACCOUNT = "account"
    CREDIT_CARD = "credit_card"


class ClassifiedBy(StrEnum):
    RULE = "rule"
    AI = "ai"
    MANUAL = "manual"
    NONE = "none"


class MatchOp(StrEnum):
    CONTAINS = "contains"
    EQUALS = "equals"
    REGEX = "regex"


class SuggestionStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
