from dataclasses import dataclass
from enum import StrEnum


class AnalysisType(StrEnum):
    MARKET_SUMMARY = "MARKET_SUMMARY"
    SECURITY_SUMMARY = "SECURITY_SUMMARY"
    PORTFOLIO_SUMMARY = "PORTFOLIO_SUMMARY"
    INDUSTRY_SUMMARY = "INDUSTRY_SUMMARY"
    COMPARISON_SUMMARY = "COMPARISON_SUMMARY"
    SCREENER_SUMMARY = "SCREENER_SUMMARY"


class StatementType(StrEnum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    CAVEAT = "CAVEAT"


@dataclass(frozen=True)
class GroundingFact:
    category: str
    key: str
    value: str
    data_status: str
    as_of: str | None = None


@dataclass(frozen=True)
class GroundingPackage:
    analysis_type: AnalysisType
    request_id: str
    as_of: str
    timezone: str
    data_status: str
    facts: list[GroundingFact]
    missing_fields: list[str]
    stale_fields: list[str]
    prompt_version: str
    target_identity: str | None = None


@dataclass(frozen=True)
class AnalysisStatement:
    type: StatementType
    text: str
    category: str | None = None


@dataclass(frozen=True)
class StructuredAIAnalysisResult:
    summary: str
    statements: list[AnalysisStatement]
    risks: list[str]
    data_caveats: list[str]
    generated_at: str
    provider: str
    model: str
    prompt_version: str
    grounding_as_of: str
    cache_hit: bool = False
