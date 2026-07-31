from enum import StrEnum


class Split(StrEnum):
    SHARED = "shared"
    INDIVIDUAL = "individual"


class Source(StrEnum):
    OFX = "ofx"
    CSV = "csv"
    PDF = "pdf"
    MANUAL = "manual"


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
