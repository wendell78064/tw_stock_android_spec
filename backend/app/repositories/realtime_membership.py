from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.realtime_strength import RealtimeTaxonomyType
from app.repositories.models import (
    IndustryModel,
    MarketModel,
    SecurityIndustryModel,
    SecurityModel,
    SecurityThemeModel,
    ThemeModel,
)


@dataclass(frozen=True)
class RealtimeMember:
    security_id: str
    market: str
    code: str
    name: str

    @property
    def key(self) -> str:
        return f"{self.market.upper()}:{self.code.upper()}"


@dataclass
class RealtimeMembershipSnapshot:
    members: dict[str, RealtimeMember] = field(default_factory=dict)
    taxonomies: dict[tuple[RealtimeTaxonomyType, str], tuple[str, str, set[str]]] = field(
        default_factory=dict
    )
    by_security: dict[str, set[tuple[RealtimeTaxonomyType, str]]] = field(default_factory=dict)


async def load_realtime_memberships(session: AsyncSession) -> RealtimeMembershipSnapshot:
    snapshot = RealtimeMembershipSnapshot()
    securities = (
        await session.execute(
            select(SecurityModel, MarketModel.code)
            .join(MarketModel, MarketModel.id == SecurityModel.market_id)
            .where(SecurityModel.is_active.is_(True))
        )
    ).all()
    id_to_key = {}
    for security, market in securities:
        member = RealtimeMember(str(security.id), market, security.code, security.name)
        snapshot.members[member.key] = member
        id_to_key[security.id] = member.key

    industries = (
        await session.execute(
            select(SecurityIndustryModel, IndustryModel).join(
                IndustryModel, IndustryModel.id == SecurityIndustryModel.industry_id
            )
        )
    ).all()
    themes = (
        await session.execute(
            select(SecurityThemeModel, ThemeModel).join(
                ThemeModel, ThemeModel.id == SecurityThemeModel.theme_id
            )
        )
    ).all()
    for mapping, taxonomy, taxonomy_type in (
        *((mapping, taxonomy, RealtimeTaxonomyType.INDUSTRY) for mapping, taxonomy in industries),
        *((mapping, taxonomy, RealtimeTaxonomyType.THEME) for mapping, taxonomy in themes),
    ):
        key = id_to_key.get(mapping.security_id)
        if key is None:
            continue
        taxonomy_key = (taxonomy_type, str(taxonomy.id))
        code, name, members = snapshot.taxonomies.setdefault(
            taxonomy_key, (taxonomy.code, taxonomy.name, set())
        )
        members.add(key)
        snapshot.by_security.setdefault(key, set()).add(taxonomy_key)
    return snapshot
