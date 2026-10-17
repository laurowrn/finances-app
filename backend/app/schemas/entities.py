"""Todo valor monetário é `int` de centavos — ver `app.services.money`."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import ClassifiedBy, MatchOp, Source, Split, StatementType, SuggestionStatus

# ---------- Users / Incomes ----------


class UserUpdate(BaseModel):
    name: str | None = None
    base_salary_cents: int | None = Field(default=None, ge=0)


class IncomeUpsert(BaseModel):
    user_id: str
    period: str  # "YYYY-MM"
    amount_cents: int = Field(ge=0)


class IncomeOut(BaseModel):
    user_id: str
    period: str
    amount_cents: int


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
    amount_cents: int = Field(gt=0)
    owner_user_id: str
    category_id: str | None = None
    is_shared: bool = True
    is_ignored: bool = False


class TransactionUpdate(BaseModel):
    description: str | None = None
    amount_cents: int | None = Field(default=None, gt=0)
    owner_user_id: str | None = None
    category_id: str | None = None
    is_shared: bool | None = None
    is_ignored: bool | None = None


class TransactionOut(BaseModel):
    id: str
    date: date
    period: str
    description: str
    raw_description: str
    amount_cents: int
    owner_user_id: str
    category_id: str | None
    is_shared: bool
    is_ignored: bool = False
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
    amount_cents: int = Field(gt=0)
    note: str | None = None


class PaymentOut(BaseModel):
    id: str
    date: date
    period: str
    from_user_id: str
    to_user_id: str
    amount_cents: int
    note: str | None = None
    created_at: datetime


# ---------- Imports ----------


class ImportPreviewRow(BaseModel):
    date: date
    description: str
    amount_cents: int
    category_id: str | None
    is_shared: bool
    is_ignored: bool = False
    classified_by: ClassifiedBy
    rule_id: str | None = None
    is_duplicate: bool


class ImportPreview(BaseModel):
    filename: str
    source: Source
    owner_user_id: str
    rows: list[ImportPreviewRow]
    detected_start: date | None = None
    detected_end: date | None = None


class ImportBatchOut(BaseModel):
    id: str
    filename: str
    source: Source
    owner_user_id: str
    institution: str = "unknown"
    statement_type: StatementType | None = None
    statement_start: date | None = None
    statement_end: date | None = None
    created_at: datetime
    counts: dict = {}


class CoverageIssue(BaseModel):
    kind: str
    start: date
    end: date
    previous_filename: str
    filename: str


class CoverageOut(BaseModel):
    owner_user_id: str
    statement_type: StatementType
    institution: str
    batches: list[ImportBatchOut]
    gaps: list[CoverageIssue]
    overlaps: list[CoverageIssue]


class ImportCommitRow(BaseModel):
    date: date
    description: str
    amount_cents: int = Field(gt=0)
    category_id: str | None = None
    is_shared: bool = True
    is_ignored: bool = False
    classified_by: ClassifiedBy = ClassifiedBy.MANUAL
    rule_id: str | None = None


class ImportCommitRequest(BaseModel):
    filename: str
    source: Source
    owner_user_id: str
    rows: list[ImportCommitRow]
    statement_type: StatementType = StatementType.ACCOUNT
    institution: str = "unknown"
    statement_start: date | None = None
    statement_end: date | None = None


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
