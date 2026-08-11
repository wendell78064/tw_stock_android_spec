from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.domain.market_data import DataStatus
from app.domain.security import MarketCode, SecurityType


class TaxonomyType(StrEnum):
    OFFICIAL = "OFFICIAL"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True)
class IndustryInfo:
    id: UUID
    code: str
    name: str
    classification_source: str
    member_count: int = 0


@dataclass(frozen=True)
class ThemeInfo:
    id: UUID
    code: str
    name: str
    description: str | None
    classification_type: str
    member_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class MemberSecurity:
    security_id: UUID
    code: str
    name: str
    market: MarketCode
    security_type: SecurityType
    is_active: bool
    close: Decimal | None
    change: Decimal | None
    change_percent: Decimal | None
    as_of: datetime | None
    data_status: DataStatus


class IndustryRepository(Protocol):
    async def list_industries(self) -> list[IndustryInfo]: ...
    async def get_industry(self, industry_id: UUID) -> IndustryInfo | None: ...
    async def list_industry_securities(
        self, industry_id: UUID
    ) -> tuple[IndustryInfo, list[MemberSecurity], datetime, DataStatus]: ...
    async def list_themes(self) -> list[ThemeInfo]: ...
    async def get_theme(self, theme_id: UUID) -> ThemeInfo | None: ...
    async def list_theme_securities(
        self, theme_id: UUID
    ) -> tuple[ThemeInfo, list[MemberSecurity], datetime, DataStatus]: ...
    async def create_theme(
        self, code: str, name: str, description: str | None, classification_type: str
    ) -> ThemeInfo: ...
    async def update_theme(
        self, theme_id: UUID, name: str | None, description: str | None
    ) -> ThemeInfo | None: ...
    async def delete_theme(self, theme_id: UUID) -> bool: ...
    async def add_theme_security(self, theme_id: UUID, security_id: UUID) -> bool: ...
    async def remove_theme_security(self, theme_id: UUID, security_id: UUID) -> bool: ...
