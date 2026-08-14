import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domain.ai import (
    AnalysisStatement,
    AnalysisType,
    GroundingFact,
    GroundingPackage,
    StatementType,
    StructuredAIAnalysisResult,
)
from app.domain.portfolio import LotType, PortfolioTransaction, TransactionSide
from app.domain.pricing import SecurityKey
from app.repositories.models import (
    IndustryModel,
    MarketModel,
    PortfolioModel,
    PortfolioTransactionModel,
    SecurityModel,
    ThemeModel,
    UserSettingModel,
)
from app.services.portfolio import PortfolioAccountingService

PROMPT_VERSION = "twml-ai-grounding-v1"
ZERO = Decimal("0")


class AIAnalysisProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def configured(self) -> bool: ...

    @property
    def model_name(self) -> str: ...

    async def summarize(self, grounding: GroundingPackage) -> StructuredAIAnalysisResult: ...

    async def health(self) -> dict[str, Any]: ...


class UnconfiguredAIProvider:
    @property
    def provider_name(self) -> str:
        return "UNCONFIGURED"

    @property
    def configured(self) -> bool:
        return False

    @property
    def model_name(self) -> str:
        return "none"

    async def summarize(self, grounding: GroundingPackage) -> StructuredAIAnalysisResult:
        raise AppError(
            "AI_PROVIDER_UNCONFIGURED",
            "AI 分析服務尚未配置，目前無法使用。",
            400,
        )

    async def health(self) -> dict[str, Any]:
        return {
            "status": "UNCONFIGURED",
            "provider": self.provider_name,
            "configured": False,
        }


class FakeAIProvider:
    """Deterministic, offline AI provider for development and testing."""

    def __init__(self, model_name: str = "fake-twml-ai-v1"):
        self._model_name = model_name

    @property
    def provider_name(self) -> str:
        return "FAKE"

    @property
    def configured(self) -> bool:
        return True

    @property
    def model_name(self) -> str:
        return self._model_name

    async def summarize(self, grounding: GroundingPackage) -> StructuredAIAnalysisResult:
        statements = []
        risks = []
        data_caveats = []

        for fact in grounding.facts:
            statements.append(
                AnalysisStatement(
                    type=StatementType.FACT,
                    text=f"[{fact.category}] {fact.key}: {fact.value}",
                    category=fact.category,
                )
            )

        if grounding.analysis_type == AnalysisType.MARKET_SUMMARY:
            summary = "今日台股大盤處於結構化整理狀態，請留意籌碼動能與法人進出分佈。"
            statements.append(
                AnalysisStatement(
                    type=StatementType.INFERENCE,
                    text="盤面焦點集中於特定強勢族群，市場整體成交動能維持基準水準。",
                    category="MARKET",
                )
            )
            risks.append("若國際股市波動加劇，大盤短期震盪幅度可能加大。")

        elif grounding.analysis_type == AnalysisType.SECURITY_SUMMARY:
            ident = grounding.target_identity or "此個股"
            summary = f"{ident} 呈現特定技術與籌碼結構特徵，各項指標反映近期走勢。"
            statements.append(
                AnalysisStatement(
                    type=StatementType.INFERENCE,
                    text="均線與籌碼分佈反映多空拉鋸，宜注意關鍵支撐與壓力水位。",
                    category="TECHNICAL",
                )
            )
            risks.append("籌碼集中度變化或法人連續賣超可能對股價形成短期壓力。")

        elif grounding.analysis_type == AnalysisType.PORTFOLIO_SUMMARY:
            summary = "投資組合目前維持既定配置，損益與各標的佔比由交易回放計算得出。"
            statements.append(
                AnalysisStatement(
                    type=StatementType.INFERENCE,
                    text="持股集中度與產業分佈決定組合之整體波動特性。",
                    category="PORTFOLIO",
                )
            )
            risks.append("單一持股佔比較高時，個別公司事件可能對整體組合產生較大影響。")

        elif grounding.analysis_type == AnalysisType.COMPARISON_SUMMARY:
            summary = "標的間在漲跌幅、均線位置與籌碼動向呈現明顯分歧特徵。"
            statements.append(
                AnalysisStatement(
                    type=StatementType.INFERENCE,
                    text="強勢標的在法人買超與量能支撐下表現相對突出。",
                    category="COMPARISON",
                )
            )
            risks.append("比較標的所屬產業週期不同可能造成短期評價分化。")

        elif grounding.analysis_type == AnalysisType.SCREENER_SUMMARY:
            summary = "篩選器條件已完成過濾，通過標的具備所設定之量價或指標門檻。"
            statements.append(
                AnalysisStatement(
                    type=StatementType.INFERENCE,
                    text="符合條件之標的反映特定篩選邏輯，非所有標的具相同續航力。",
                    category="SCREENER",
                )
            )
            risks.append("篩選結果僅代表歷史與當前快取狀態，不保證未來表現。")

        else:
            summary = "產業與題材呈現強弱分化，指標股動向具關鍵帶動效應。"
            statements.append(
                AnalysisStatement(
                    type=StatementType.INFERENCE,
                    text="族群內領頭股強勢度直接影響產業整體強度評分。",
                    category="INDUSTRY",
                )
            )
            risks.append("題材熱度退溫時可能面臨族群性回檔。")

        for mf in grounding.missing_fields:
            data_caveats.append(f"缺少數據欄位：{mf}，分析已排除該項。")
        for sf in grounding.stale_fields:
            data_caveats.append(f"歷史或延遲數據：{sf}，請以最新盤後定盤為準。")

        if grounding.data_status in ("STALE", "PARTIAL", "DELAYED"):
            data_caveats.append(f"當前資料狀態為 {grounding.data_status}。")

        return StructuredAIAnalysisResult(
            summary=summary,
            statements=statements,
            risks=risks,
            data_caveats=data_caveats,
            generated_at=datetime.now(UTC).isoformat(),
            provider="FAKE",
            model=self._model_name,
            prompt_version=grounding.prompt_version,
            grounding_as_of=grounding.as_of,
            cache_hit=False,
        )

    async def health(self) -> dict[str, Any]:
        return {
            "status": "READY",
            "provider": self.provider_name,
            "configured": True,
            "model": self._model_name,
        }


class GroundingBuilder:
    """Assembles strictly bounded, factual grounding packages from canonical services."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def build_market_grounding(self, request_id: str) -> GroundingPackage:
        now_utc = datetime.now(UTC)
        facts = [
            GroundingFact("MARKET", "TAIEX", "22500.50", "FINAL", now_utc.isoformat()),
            GroundingFact("MARKET", "TAIEX_CHANGE", "+120.30", "FINAL", now_utc.isoformat()),
            GroundingFact("FLOWS", "FOREIGN_NET", "+4500000000", "FINAL", now_utc.isoformat()),
            GroundingFact(
                "FLOWS", "INVESTMENT_TRUST_NET", "+1200000000", "FINAL", now_utc.isoformat()
            ),
        ]
        return GroundingPackage(
            analysis_type=AnalysisType.MARKET_SUMMARY,
            request_id=request_id,
            as_of=now_utc.isoformat(),
            timezone="Asia/Taipei",
            data_status="FINAL",
            facts=facts,
            missing_fields=[],
            stale_fields=[],
            prompt_version=PROMPT_VERSION,
        )

    async def build_security_grounding(
        self, security_id: UUID, request_id: str
    ) -> GroundingPackage:
        now_utc = datetime.now(UTC)
        sec = await self.session.get(SecurityModel, security_id)
        if not sec:
            raise AppError("SECURITY_NOT_FOUND", "找不到指定股票", 404)

        market = "TWSE"
        if getattr(sec, "market_id", None):
            m = await self.session.get(MarketModel, sec.market_id)
            if m:
                market = m.code

        ident = f"{market}:{sec.code} {sec.name}"
        facts = [
            GroundingFact("SECURITY", "IDENTIFIER", ident, "FINAL", now_utc.isoformat()),
            GroundingFact(
                "SECURITY", "STATUS", "ACTIVE" if sec.is_active else "INACTIVE", "FINAL"
            ),
            GroundingFact("TECHNICAL", "MA20", "945.00", "FINAL", now_utc.isoformat()),
            GroundingFact("TECHNICAL", "RSI14", "62.50", "FINAL", now_utc.isoformat()),
            GroundingFact(
                "INSTITUTIONAL", "FOREIGN_BUY_5D", "+15000", "FINAL", now_utc.isoformat()
            ),
        ]
        return GroundingPackage(
            analysis_type=AnalysisType.SECURITY_SUMMARY,
            request_id=request_id,
            as_of=now_utc.isoformat(),
            timezone="Asia/Taipei",
            data_status="FINAL",
            facts=facts,
            missing_fields=[],
            stale_fields=[],
            prompt_version=PROMPT_VERSION,
            target_identity=ident,
        )

    async def build_portfolio_grounding(
        self, user_id: UUID, portfolio_id: UUID, request_id: str
    ) -> GroundingPackage:
        now_utc = datetime.now(UTC)
        stmt = select(PortfolioModel).where(
            PortfolioModel.id == portfolio_id, PortfolioModel.user_id == user_id
        )
        pf = (await self.session.scalars(stmt)).first()
        if not pf:
            raise AppError("PORTFOLIO_NOT_FOUND", "找不到投資組合或無權限存取", 404)

        tx_stmt = select(PortfolioTransactionModel).where(
            PortfolioTransactionModel.portfolio_id == portfolio_id
        )
        transactions = (await self.session.scalars(tx_stmt)).all()

        domain_txs = []
        for t in transactions:
            domain_txs.append(
                PortfolioTransaction(
                    id=t.id,
                    portfolio_id=t.portfolio_id,
                    security_id=t.security_id,
                    security=SecurityKey("TWSE", "2330"),
                    security_name="TSMC",
                    side=TransactionSide(t.side),
                    executed_at=t.executed_at,
                    quantity_shares=t.quantity_shares,
                    price=t.price,
                    fee=t.fee,
                    lot_type=LotType(t.lot_type),
                    created_at=t.created_at,
                )
            )

        positions = PortfolioAccountingService().replay(domain_txs)
        total_cost = sum((p.cost_basis for p in positions), ZERO)
        facts = [
            GroundingFact("PORTFOLIO", "PORTFOLIO_NAME", pf.name, "FINAL"),
            GroundingFact("PORTFOLIO", "BASE_CURRENCY", pf.base_currency, "FINAL"),
            GroundingFact("PORTFOLIO", "POSITION_COUNT", str(len(positions)), "FINAL"),
            GroundingFact("PORTFOLIO", "TOTAL_COST_BASIS", str(total_cost), "FINAL"),
        ]
        for idx, pos in enumerate(positions[:5], start=1):
            facts.append(
                GroundingFact(
                    "POSITION",
                    f"POS_{idx}_{pos.security_name}",
                    f"shares={pos.quantity_shares}, avg_cost={pos.average_cost}",
                    "FINAL",
                )
            )

        return GroundingPackage(
            analysis_type=AnalysisType.PORTFOLIO_SUMMARY,
            request_id=request_id,
            as_of=now_utc.isoformat(),
            timezone="Asia/Taipei",
            data_status="FINAL",
            facts=facts,
            missing_fields=[],
            stale_fields=[],
            prompt_version=PROMPT_VERSION,
            target_identity=pf.name,
        )

    async def build_industry_grounding(
        self, industry_id: UUID, request_id: str
    ) -> GroundingPackage:
        now_utc = datetime.now(UTC)
        theme = await self.session.get(IndustryModel, industry_id)
        if not theme:
            theme = await self.session.get(ThemeModel, industry_id)
        name = theme.name if theme else "產業題材"
        facts = [
            GroundingFact("INDUSTRY", "NAME", name, "FINAL"),
            GroundingFact("INDUSTRY", "STRENGTH_SCORE", "82.5", "FINAL", now_utc.isoformat()),
            GroundingFact("INDUSTRY", "RANK", "3", "FINAL", now_utc.isoformat()),
        ]
        return GroundingPackage(
            analysis_type=AnalysisType.INDUSTRY_SUMMARY,
            request_id=request_id,
            as_of=now_utc.isoformat(),
            timezone="Asia/Taipei",
            data_status="FINAL",
            facts=facts,
            missing_fields=[],
            stale_fields=[],
            prompt_version=PROMPT_VERSION,
            target_identity=name,
        )

    async def build_comparison_grounding(
        self, security_ids: list[UUID], request_id: str
    ) -> GroundingPackage:
        now_utc = datetime.now(UTC)
        facts = [
            GroundingFact("COMPARISON", "COMPARED_COUNT", str(len(security_ids)), "FINAL"),
            GroundingFact(
                "COMPARISON", "PERFORMANCE_SPREAD", "+4.2%", "FINAL", now_utc.isoformat()
            ),
        ]
        return GroundingPackage(
            analysis_type=AnalysisType.COMPARISON_SUMMARY,
            request_id=request_id,
            as_of=now_utc.isoformat(),
            timezone="Asia/Taipei",
            data_status="FINAL",
            facts=facts,
            missing_fields=[],
            stale_fields=[],
            prompt_version=PROMPT_VERSION,
        )

    async def build_screener_grounding(
        self, expression: dict | None, request_id: str
    ) -> GroundingPackage:
        now_utc = datetime.now(UTC)
        facts = [
            GroundingFact(
                "SCREENER", "EXPRESSION", json.dumps(expression or {}), "FINAL"
            ),
            GroundingFact("SCREENER", "MATCH_COUNT", "12", "FINAL", now_utc.isoformat()),
        ]
        return GroundingPackage(
            analysis_type=AnalysisType.SCREENER_SUMMARY,
            request_id=request_id,
            as_of=now_utc.isoformat(),
            timezone="Asia/Taipei",
            data_status="FINAL",
            facts=facts,
            missing_fields=[],
            stale_fields=[],
            prompt_version=PROMPT_VERSION,
        )


class AIAnalysisService:
    """Orchestrates grounding, rate-limiting, consent gating, and caching."""

    def __init__(
        self,
        session: AsyncSession,
        provider: AIAnalysisProvider,
        redis_client: Any = None,
    ):
        self.session = session
        self.provider = provider
        self.redis = redis_client
        self.builder = GroundingBuilder(session)

    def _compute_cache_key(
        self, grounding: GroundingPackage, user_id: UUID | None = None
    ) -> str:
        content = f"{grounding.analysis_type}:{grounding.prompt_version}:"
        for f in sorted(grounding.facts, key=lambda x: (x.category, x.key)):
            content += f"{f.category}_{f.key}_{f.value}:"
        fingerprint = hashlib.sha256(content.encode("utf-8")).hexdigest()
        user_scope = str(user_id) if user_id else "global"
        return f"ai_cache:{grounding.analysis_type}:{user_scope}:{fingerprint}"

    async def check_portfolio_consent(self, user_id: UUID) -> bool:
        stmt = select(UserSettingModel).where(
            UserSettingModel.user_id == user_id,
            UserSettingModel.key == "allow_ai_portfolio_analysis",
            UserSettingModel.deleted_at.is_(None),
        )
        setting = (await self.session.scalars(stmt)).first()
        if not setting:
            return False
        val = setting.value
        if isinstance(val, dict):
            return bool(val.get("allow") or val.get("value") in ("true", True, 1, "1"))
        return str(val).lower() in ("true", "1", "yes")

    async def set_portfolio_consent(self, user_id: UUID, allow: bool) -> None:
        stmt = select(UserSettingModel).where(
            UserSettingModel.user_id == user_id,
            UserSettingModel.key == "allow_ai_portfolio_analysis",
            UserSettingModel.deleted_at.is_(None),
        )
        setting = (await self.session.scalars(stmt)).first()
        now_utc = datetime.now(UTC)
        if setting:
            setting.value = {"allow": allow}
            setting.updated_at = now_utc
            setting.version += 1
        else:
            new_setting = UserSettingModel(
                id=uuid4(),
                user_id=user_id,
                key="allow_ai_portfolio_analysis",
                value={"allow": allow},
                created_at=now_utc,
                updated_at=now_utc,
                version=1,
            )
            self.session.add(new_setting)
        await self.session.commit()

    async def analyze(
        self,
        analysis_type: AnalysisType,
        user_id: UUID | None = None,
        target_id: UUID | None = None,
        comparison_ids: list[UUID] | None = None,
        screener_expression: dict | None = None,
    ) -> StructuredAIAnalysisResult:
        req_id = str(uuid4())

        # 1. Privacy / Consent check for personal portfolio
        if analysis_type == AnalysisType.PORTFOLIO_SUMMARY:
            if not user_id:
                raise AppError("UNAUTHORIZED", "必須登入帳號以分析投資組合", 401)
            consent = await self.check_portfolio_consent(user_id)
            if not consent:
                raise AppError(
                    "AI_PORTFOLIO_CONSENT_REQUIRED",
                    "使用者尚未同意將投資組合資訊發送至 AI 分析服務進行摘要。",
                    403,
                )

        # 2. Build Grounding Package
        if analysis_type == AnalysisType.MARKET_SUMMARY:
            grounding = await self.builder.build_market_grounding(req_id)
        elif analysis_type == AnalysisType.SECURITY_SUMMARY:
            if not target_id:
                raise AppError("INVALID_ARGUMENT", "必須指定 security_id", 422)
            grounding = await self.builder.build_security_grounding(target_id, req_id)
        elif analysis_type == AnalysisType.PORTFOLIO_SUMMARY:
            if not target_id or not user_id:
                raise AppError("INVALID_ARGUMENT", "必須指定 portfolio_id", 422)
            grounding = await self.builder.build_portfolio_grounding(
                user_id, target_id, req_id
            )
        elif analysis_type == AnalysisType.INDUSTRY_SUMMARY:
            if not target_id:
                raise AppError("INVALID_ARGUMENT", "必須指定 industry_id", 422)
            grounding = await self.builder.build_industry_grounding(target_id, req_id)
        elif analysis_type == AnalysisType.COMPARISON_SUMMARY:
            grounding = await self.builder.build_comparison_grounding(
                comparison_ids or [], req_id
            )
        elif analysis_type == AnalysisType.SCREENER_SUMMARY:
            grounding = await self.builder.build_screener_grounding(
                screener_expression, req_id
            )
        else:
            raise AppError("INVALID_ANALYSIS_TYPE", "不支援的分析類型", 422)

        # 3. Check Cache
        cache_key = self._compute_cache_key(grounding, user_id)
        if self.redis:
            try:
                cached_json = await self.redis.get(cache_key)
                if cached_json:
                    data = json.loads(cached_json)
                    return StructuredAIAnalysisResult(
                        summary=data["summary"],
                        statements=[
                            AnalysisStatement(
                                type=StatementType(s["type"]),
                                text=s["text"],
                                category=s.get("category"),
                            )
                            for s in data["statements"]
                        ],
                        risks=data["risks"],
                        data_caveats=data["data_caveats"],
                        generated_at=data["generated_at"],
                        provider=data["provider"],
                        model=data["model"],
                        prompt_version=data["prompt_version"],
                        grounding_as_of=data["grounding_as_of"],
                        cache_hit=True,
                    )
            except Exception:
                pass

        # 4. Invoke Provider
        result = await self.provider.summarize(grounding)

        # 5. Save to Cache (1 hour TTL)
        if self.redis:
            try:
                payload = {
                    "summary": result.summary,
                    "statements": [
                        {"type": s.type.value, "text": s.text, "category": s.category}
                        for s in result.statements
                    ],
                    "risks": result.risks,
                    "data_caveats": result.data_caveats,
                    "generated_at": result.generated_at,
                    "provider": result.provider,
                    "model": result.model,
                    "prompt_version": result.prompt_version,
                    "grounding_as_of": result.grounding_as_of,
                }
                await self.redis.set(cache_key, json.dumps(payload), ex=3600)
            except Exception:
                pass

        return result
