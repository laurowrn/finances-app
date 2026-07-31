from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import ClassifiedBy, MatchOp, Source, Split, SuggestionStatus

# ---------- Users / Incomes ----------


class UserUpdate(BaseModel):
    name: str | None = None
    base_salary: float | None = None


class IncomeUpsert(BaseModel):
    user_id: str
    period: str  # "YYYY-MM"
    amount: float


class IncomeOut(BaseModel):
    user_id: str
    period: str
    amount: float


# ---------- Categories ----------


class CategoryCreate(BaseModel):
    name: str
    icon: str = "tag"
    is_shared_default: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    is_shared_default: bool | None = None


class CategoryOut(BaseModel):
    id: str
    name: str
    icon: str
    is_shared_default: bool


# ---------- Rules ----------


class Matcher(BaseModel):
    field: str = "description"
    op: MatchOp = MatchOp.CONTAINS
    value: str


class RuleCreate(BaseModel):
    matcher: Matcher
    category_id: str
    split_default: Split = Split.SHARED
    priority: int = 100
    enabled: bool = True


class RuleUpdate(BaseModel):
    matcher: Matcher | None = None
    category_id: str | None = None
    split_default: Split | None = None
    priority: int | None = None
    enabled: bool | None = None


class RuleOut(BaseModel):
    id: str
    matcher: Matcher
    category_id: str
    split_default: Split
    priority: int
    enabled: bool


# ---------- Transactions ----------


class TransactionCreate(BaseModel):
    """Lançamento manual."""

    date: date
    description: str
    amount: float = Field(gt=0)
    owner_user_id: str
    category_id: str | None = None
    is_shared: bool = True


class TransactionUpdate(BaseModel):
    description: str | None = None
    amount: float | None = None
    owner_user_id: str | None = None
    category_id: str | None = None
    is_shared: bool | None = None


class TransactionOut(BaseModel):
    id: str
    date: date
    period: str
    description: str
    raw_description: str
    amount: float
    owner_user_id: str
    category_id: str | None
    is_shared: bool
    source: Source
    classified_by: ClassifiedBy
    rule_id: str | None = None
    import_batch_id: str | None = None


# ---------- Rule suggestions ----------


class RuleSuggestionOut(BaseModel):
    id: str
    merchant_key: str
    sample_descriptions: list[str]
    suggested_category_id: str | None
    suggested_category_name: str | None
    suggested_split: Split
    count: int
    status: SuggestionStatus


class AcceptSuggestionRequest(BaseModel):
    category_id: str
    split_default: Split = Split.SHARED
    priority: int = 100


# ---------- Payments ----------


class PaymentCreate(BaseModel):
    date: date
    from_user_id: str
    to_user_id: str
    amount: float = Field(gt=0)
    note: str | None = None


class PaymentOut(BaseModel):
    id: str
    date: date
    period: str
    from_user_id: str
    to_user_id: str
    amount: float
    note: str | None = None
    created_at: datetime


# ---------- Imports ----------


class ImportPreviewRow(BaseModel):
    date: date
    description: str
    amount: float
    category_id: str | None
    is_shared: bool
    classified_by: ClassifiedBy
    rule_id: str | None = None
    is_duplicate: bool


class ImportPreview(BaseModel):
    filename: str
    source: Source
    owner_user_id: str
    rows: list[ImportPreviewRow]


class ImportCommitRow(BaseModel):
    date: date
    description: str
    amount: float = Field(gt=0)
    category_id: str | None = None
    is_shared: bool = True
    classified_by: ClassifiedBy = ClassifiedBy.MANUAL
    rule_id: str | None = None


class ImportCommitRequest(BaseModel):
    filename: str
    source: Source
    owner_user_id: str
    rows: list[ImportCommitRow]


class ImportSummary(BaseModel):
    import_batch_id: str
    filename: str
    source: Source
    owner_user_id: str
    total: int
    matched: int
    unmatched: int
    duplicates: int
    created_at: datetime
