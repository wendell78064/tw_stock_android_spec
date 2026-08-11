from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import industry_repository, security_repository
from app.domain.industry import IndustryInfo, MemberSecurity, ThemeInfo
from app.domain.market_data import DataStatus
from app.domain.security import MarketCode, Security, SecurityStatus, SecurityType, ThemeRef
from app.main import app
from app.repositories.models import DailyPriceModel
from tests.fakes import InMemorySecurityRepository


class InMemoryIndustryRepository:
    def __init__(self):
        self.industries: dict[UUID, IndustryInfo] = {}
        self.themes: dict[UUID, ThemeInfo] = {}
        self.security_industries: dict[UUID, list[UUID]] = {}
        self.security_themes: dict[UUID, list[UUID]] = {}
        self.securities: dict[UUID, Security] = {}
        self.prices: dict[UUID, list[DailyPriceModel]] = {}

    async def list_industries(self) -> list[IndustryInfo]:
        result = []
        for ind in self.industries.values():
            count = sum(
                1 for sec_id, ind_ids in self.security_industries.items() if ind.id in ind_ids
            )
            result.append(replace(ind, member_count=count))
        return sorted(result, key=lambda x: x.name)

    async def get_industry(self, industry_id: UUID) -> IndustryInfo | None:
        ind = self.industries.get(industry_id)
        if ind is None:
            return None
        count = sum(
            1 for sec_id, ind_ids in self.security_industries.items() if industry_id in ind_ids
        )
        return replace(ind, member_count=count)

    async def list_industry_securities(
        self, industry_id: UUID
    ) -> tuple[IndustryInfo, list[MemberSecurity], datetime, DataStatus]:
        ind = await self.get_industry(industry_id)
        if ind is None:
            raise LookupError("Industry not found")
        member_sec_ids = [
            sec_id for sec_id, ind_ids in self.security_industries.items() if industry_id in ind_ids
        ]
        members, as_of, status = self._enrich_members(member_sec_ids)
        return ind, members, as_of, status

    async def list_themes(self) -> list[ThemeInfo]:
        result = []
        for theme in self.themes.values():
            count = sum(
                1 for sec_id, theme_ids in self.security_themes.items() if theme.id in theme_ids
            )
            result.append(replace(theme, member_count=count))
        return sorted(result, key=lambda x: x.name)

    async def get_theme(self, theme_id: UUID) -> ThemeInfo | None:
        theme = self.themes.get(theme_id)
        if theme is None:
            return None
        count = sum(
            1 for sec_id, theme_ids in self.security_themes.items() if theme_id in theme_ids
        )
        return replace(theme, member_count=count)

    async def list_theme_securities(
        self, theme_id: UUID
    ) -> tuple[ThemeInfo, list[MemberSecurity], datetime, DataStatus]:
        theme = await self.get_theme(theme_id)
        if theme is None:
            raise LookupError("Theme not found")
        member_sec_ids = [
            sec_id for sec_id, theme_ids in self.security_themes.items() if theme_id in theme_ids
        ]
        members, as_of, status = self._enrich_members(member_sec_ids)
        return theme, members, as_of, status

    async def create_theme(
        self, code: str, name: str, description: str | None, classification_type: str
    ) -> ThemeInfo:
        if any(t.code == code for t in self.themes.values()):
            raise ValueError(f"Theme code {code} already exists")
        now = datetime.now(UTC)
        t_id = uuid4()
        theme = ThemeInfo(
            id=t_id,
            code=code,
            name=name,
            description=description,
            classification_type=classification_type,
            member_count=0,
            created_at=now,
            updated_at=now,
        )
        self.themes[t_id] = theme
        return theme

    async def update_theme(
        self, theme_id: UUID, name: str | None, description: str | None
    ) -> ThemeInfo | None:
        theme = self.themes.get(theme_id)
        if theme is None:
            return None
        updated = replace(
            theme,
            name=name if name is not None else theme.name,
            description=description if description is not None else theme.description,
            updated_at=datetime.now(UTC),
        )
        self.themes[theme_id] = updated
        return await self.get_theme(theme_id)

    async def delete_theme(self, theme_id: UUID) -> bool:
        if theme_id not in self.themes:
            return False
        del self.themes[theme_id]
        for sec_id in list(self.security_themes.keys()):
            self.security_themes[sec_id] = [
                t for t in self.security_themes[sec_id] if t != theme_id
            ]
        return True

    async def add_theme_security(self, theme_id: UUID, security_id: UUID) -> bool:
        if theme_id not in self.themes or security_id not in self.securities:
            return False
        if security_id not in self.security_themes:
            self.security_themes[security_id] = []
        if theme_id not in self.security_themes[security_id]:
            self.security_themes[security_id].append(theme_id)
        return True

    async def remove_theme_security(self, theme_id: UUID, security_id: UUID) -> bool:
        if (
            security_id not in self.security_themes
            or theme_id not in self.security_themes[security_id]
        ):
            return False
        self.security_themes[security_id].remove(theme_id)
        return True

    def _enrich_members(
        self, security_ids: list[UUID]
    ) -> tuple[list[MemberSecurity], datetime, DataStatus]:
        now = datetime.now(UTC)
        if not security_ids:
            return [], now, DataStatus.UNAVAILABLE
        members = []
        all_as_of = []
        statuses = set()
        for sec_id in security_ids:
            sec = self.securities[sec_id]
            plist = self.prices.get(sec_id, [])
            plist_sorted = sorted(plist, key=lambda x: x.trade_date, reverse=True)
            c_val = chg_val = chg_pct_val = s_as_of = None
            s_stat = sec.data_status
            if plist_sorted:
                latest = plist_sorted[0]
                c_val = Decimal(str(latest.close)) if latest.close is not None else None
                s_as_of = latest.as_of
                s_stat = latest.data_status
                all_as_of.append(latest.as_of)
                statuses.add(latest.data_status)
                if len(plist_sorted) >= 2 and c_val is not None:
                    prev = plist_sorted[1]
                    prev_c = Decimal(str(prev.close)) if prev.close is not None else None
                    if prev_c is not None and prev_c != Decimal("0"):
                        chg_val = c_val - prev_c
                        chg_pct_val = ((chg_val / prev_c) * Decimal("100")).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        )
            else:
                all_as_of.append(sec.as_of)
                statuses.add(sec.data_status)

            members.append(
                MemberSecurity(
                    security_id=sec.id,
                    code=sec.code,
                    name=sec.name,
                    market=sec.market,
                    security_type=sec.security_type,
                    is_active=sec.is_active,
                    close=c_val,
                    change=chg_val,
                    change_percent=chg_pct_val,
                    as_of=s_as_of or sec.as_of,
                    data_status=s_stat,
                )
            )
        max_as_of = max(all_as_of) if all_as_of else now
        agg_status = (
            statuses.pop()
            if len(statuses) == 1
            else (DataStatus.PARTIAL if len(statuses) > 1 else DataStatus.UNAVAILABLE)
        )
        return members, max_as_of, agg_status


@pytest.mark.asyncio
async def test_industry_and_theme_repository_flow() -> None:
    repo = InMemoryIndustryRepository()
    now = datetime.now(UTC)

    # Official industries
    ind_semi = IndustryInfo(
        id=uuid4(), code="24", name="半導體", classification_source="TWSE", member_count=0
    )
    ind_elec = IndustryInfo(
        id=uuid4(), code="25", name="電腦及週邊設備", classification_source="TWSE", member_count=0
    )
    repo.industries[ind_semi.id] = ind_semi
    repo.industries[ind_elec.id] = ind_elec

    # Securities
    sec1 = Security(
        id=uuid4(),
        market=MarketCode.TWSE,
        code="2330",
        name="台積電",
        security_type=SecurityType.COMMON_STOCK,
        status=SecurityStatus.ACTIVE,
        is_active=True,
        listing_date=date(1994, 9, 5),
        primary_industry="半導體",
        source_code="TWSE",
        as_of=now,
        received_at=now,
        data_status=DataStatus.FINAL,
    )
    sec2 = Security(
        id=uuid4(),
        market=MarketCode.TWSE,
        code="2382",
        name="廣達",
        security_type=SecurityType.COMMON_STOCK,
        status=SecurityStatus.ACTIVE,
        is_active=True,
        listing_date=date(1999, 1, 8),
        primary_industry="電腦及週邊設備",
        source_code="TWSE",
        as_of=now,
        received_at=now,
        data_status=DataStatus.FINAL,
    )
    repo.securities[sec1.id] = sec1
    repo.securities[sec2.id] = sec2

    repo.security_industries[sec1.id] = [ind_semi.id]
    repo.security_industries[sec2.id] = [ind_elec.id]

    # Prices for bulk enrichment
    repo.prices[sec1.id] = [
        DailyPriceModel(
            security_id=sec1.id,
            trade_date=date(2026, 8, 10),
            close=Decimal("1000.0"),
            as_of=now,
            data_status=DataStatus.FINAL,
        ),
        DailyPriceModel(
            security_id=sec1.id,
            trade_date=date(2026, 8, 9),
            close=Decimal("980.0"),
            as_of=now,
            data_status=DataStatus.FINAL,
        ),
    ]

    # List industries
    industries = await repo.list_industries()
    assert len(industries) == 2
    semi = next(i for i in industries if i.name == "半導體")
    assert semi.member_count == 1

    # Industry members
    ind_info, members, as_of, status = await repo.list_industry_securities(ind_semi.id)
    assert ind_info.name == "半導體"
    assert len(members) == 1
    assert members[0].code == "2330"
    assert members[0].close == Decimal("1000.0")
    assert members[0].change == Decimal("20.0")
    assert members[0].change_percent == Decimal("2.04")

    # Create Themes
    theme1 = await repo.create_theme(
        code="AI_SERVER",
        name="AI 伺服器",
        description="AI Server Supply Chain",
        classification_type="CUSTOM",
    )
    theme2 = await repo.create_theme(
        code="CPO",
        name="CPO 矽光子",
        description="Co-packaged optics",
        classification_type="CUSTOM",
    )

    # Multi-Theme security
    await repo.add_theme_security(theme1.id, sec1.id)
    await repo.add_theme_security(theme2.id, sec1.id)
    await repo.add_theme_security(theme1.id, sec2.id)

    # Duplicate mapping check
    await repo.add_theme_security(theme1.id, sec1.id)

    themes = await repo.list_themes()
    ai_t = next(t for t in themes if t.code == "AI_SERVER")
    cpo_t = next(t for t in themes if t.code == "CPO")
    assert ai_t.member_count == 2
    assert cpo_t.member_count == 1


@pytest.mark.asyncio
async def test_industry_and_theme_api_endpoints() -> None:
    ind_repo = InMemoryIndustryRepository()
    sec_repo = InMemorySecurityRepository()

    now = datetime.now(UTC)
    ind = IndustryInfo(
        id=uuid4(), code="24", name="半導體", classification_source="TWSE", member_count=1
    )
    ind_repo.industries[ind.id] = ind

    theme = ThemeInfo(
        id=uuid4(),
        code="DRAM",
        name="DRAM 記憶體",
        description="DRAM theme",
        classification_type="CUSTOM",
        member_count=1,
        created_at=now,
        updated_at=now,
    )
    ind_repo.themes[theme.id] = theme

    sec = Security(
        id=uuid4(),
        market=MarketCode.TWSE,
        code="2408",
        name="南亞科",
        security_type=SecurityType.COMMON_STOCK,
        status=SecurityStatus.ACTIVE,
        is_active=True,
        listing_date=date(2000, 1, 1),
        primary_industry="半導體",
        source_code="TWSE",
        as_of=now,
        received_at=now,
        data_status=DataStatus.FINAL,
        themes=[ThemeRef(id=theme.id, code=theme.code, name=theme.name)],
    )
    ind_repo.securities[sec.id] = sec
    ind_repo.security_industries[sec.id] = [ind.id]
    ind_repo.security_themes[sec.id] = [theme.id]
    sec_repo.items[(MarketCode.TWSE, "2408")] = sec

    app.dependency_overrides[industry_repository] = lambda: ind_repo
    app.dependency_overrides[security_repository] = lambda: sec_repo

    try:
        with TestClient(app) as test_client:
            # GET /v1/industries
            res = test_client.get("/v1/industries")
            assert res.status_code == 200
            assert len(res.json()["data"]) == 1

            # GET /v1/industries/{id}
            res_ind = test_client.get(f"/v1/industries/{ind.id}")
            assert res_ind.status_code == 200
            assert res_ind.json()["data"]["name"] == "半導體"

            # GET /v1/industries/{id}/securities
            res_ind_sec = test_client.get(f"/v1/industries/{ind.id}/securities")
            assert res_ind_sec.status_code == 200
            assert len(res_ind_sec.json()["data"]) == 1

            # GET /v1/themes
            res_t = test_client.get("/v1/themes")
            assert res_t.status_code == 200
            assert len(res_t.json()["data"]) == 1

            # GET /v1/themes/{id}
            res_t_detail = test_client.get(f"/v1/themes/{theme.id}")
            assert res_t_detail.status_code == 200
            assert res_t_detail.json()["data"]["name"] == "DRAM 記憶體"

            # GET /v1/themes/{id}/securities
            res_t_sec = test_client.get(f"/v1/themes/{theme.id}/securities")
            assert res_t_sec.status_code == 200

            # Admin CRUD without key -> 401
            res_unauth = test_client.post(
                "/v1/themes", json={"code": "HBM", "name": "HBM 高頻寬記憶體"}
            )
            assert res_unauth.status_code == 401

            # Admin CRUD with valid key -> 201
            admin_headers = {"X-Admin-Key": "admin-secret-key"}
            res_create = test_client.post(
                "/v1/themes",
                headers=admin_headers,
                json={
                    "code": "HBM",
                    "name": "HBM 高頻寬記憶體",
                    "description": "High Bandwidth Memory",
                },
            )
            assert res_create.status_code == 201
            hbm_id = res_create.json()["data"]["id"]

            # Admin update theme
            res_update = test_client.put(
                f"/v1/themes/{hbm_id}",
                headers=admin_headers,
                json={"name": "HBM3e 高頻寬記憶體"},
            )
            assert res_update.status_code == 200
            assert res_update.json()["data"]["name"] == "HBM3e 高頻寬記憶體"

            # Admin add security to theme
            res_add_sec = test_client.post(
                f"/v1/themes/{hbm_id}/securities",
                headers=admin_headers,
                json={"security_id": str(sec.id)},
            )
            assert res_add_sec.status_code == 200

            # Security Detail returns Industry & Themes
            res_sec_detail = test_client.get("/v1/securities/2408", params={"market": "TWSE"})
            assert res_sec_detail.status_code == 200
            sec_data = res_sec_detail.json()["data"]
            assert sec_data["primary_industry"] == "半導體"
            assert len(sec_data["themes"]) >= 1

            # Admin remove security from theme
            res_rem = test_client.delete(
                f"/v1/themes/{hbm_id}/securities/{sec.id}", headers=admin_headers
            )
            assert res_rem.status_code == 204

            # Admin delete theme
            res_del = test_client.delete(f"/v1/themes/{hbm_id}", headers=admin_headers)
            assert res_del.status_code == 204
    finally:
        app.dependency_overrides.clear()
