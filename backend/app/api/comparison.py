from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.schemas import (
    ComparisonEnvelope,
    ComparisonResultSchema,
    ComparisonSecuritySummarySchema,
    MetaResponse,
    NormalizedPointSchema,
    ObjectiveSignalSchema,
    RunComparisonInput,
)
from app.core.dependencies import comparison_service
from app.domain.comparison import ComparisonWindow
from app.services.comparison import ComparisonService

router = APIRouter(prefix="/v1", tags=["Comparisons"])


@router.post(
    "/comparisons/run",
    response_model=ComparisonEnvelope,
    operation_id="runComparison",
)
async def run_comparison(
    input_data: RunComparisonInput,
    service: Annotated[ComparisonService, Depends(comparison_service)],
) -> ComparisonEnvelope:
    targets = [{"code": t.code, "market": t.market.value} for t in input_data.targets]
    win = ComparisonWindow(input_data.window)

    res = await service.compare_securities(
        targets=targets,
        window=win,
        target_trade_date=input_data.trade_date,
    )

    sec_schemas = [
        ComparisonSecuritySummarySchema(
            security_id=s.security_id,
            code=s.code,
            name=s.name,
            market=s.market,
            latest_close=(
                str(s.latest_close) if s.latest_close is not None else None
            ),
            return_1d=str(s.return_1d) if s.return_1d is not None else None,
            return_5d=str(s.return_5d) if s.return_5d is not None else None,
            return_10d=(
                str(s.return_10d) if s.return_10d is not None else None
            ),
            return_20d=(
                str(s.return_20d) if s.return_20d is not None else None
            ),
            return_60d=(
                str(s.return_60d) if s.return_60d is not None else None
            ),
            return_selected_window=(
                str(s.return_selected_window)
                if s.return_selected_window is not None
                else None
            ),
            ma5=str(s.ma5) if s.ma5 is not None else None,
            ma20=str(s.ma20) if s.ma20 is not None else None,
            ma60=str(s.ma60) if s.ma60 is not None else None,
            close_vs_ma20=(
                str(s.close_vs_ma20) if s.close_vs_ma20 is not None else None
            ),
            close_vs_ma60=(
                str(s.close_vs_ma60) if s.close_vs_ma60 is not None else None
            ),
            rsi14=str(s.rsi14) if s.rsi14 is not None else None,
            macd_state=s.macd_state,
            kd_state=s.kd_state,
            foreign_1d_net=(
                str(s.foreign_1d_net) if s.foreign_1d_net is not None else None
            ),
            foreign_5d_net=(
                str(s.foreign_5d_net) if s.foreign_5d_net is not None else None
            ),
            trust_1d_net=(
                str(s.trust_1d_net) if s.trust_1d_net is not None else None
            ),
            trust_5d_net=(
                str(s.trust_5d_net) if s.trust_5d_net is not None else None
            ),
            dealer_1d_net=(
                str(s.dealer_1d_net) if s.dealer_1d_net is not None else None
            ),
            dealer_5d_net=(
                str(s.dealer_5d_net) if s.dealer_5d_net is not None else None
            ),
            margin_balance_change=(
                str(s.margin_balance_change)
                if s.margin_balance_change is not None
                else None
            ),
            short_balance_change=(
                str(s.short_balance_change)
                if s.short_balance_change is not None
                else None
            ),
            lending_balance_change=(
                str(s.lending_balance_change)
                if s.lending_balance_change is not None
                else None
            ),
            industry_name=s.industry_name,
            themes=s.themes,
            industry_strength_score=(
                str(s.industry_strength_score)
                if s.industry_strength_score is not None
                else None
            ),
            industry_strength_rank=s.industry_strength_rank,
            selected_set_return_rank=s.selected_set_return_rank,
            selected_set_rsi_rank=s.selected_set_rsi_rank,
            selected_set_foreign_rank=s.selected_set_foreign_rank,
            data_status=s.data_status,
        )
        for s in res.securities
    ]

    series_schemas = [
        NormalizedPointSchema(
            trade_date=p.trade_date,
            values={k: str(v) if v is not None else None for k, v in p.values.items()},
        )
        for p in res.normalized_series
    ]

    signal_schemas = [
        ObjectiveSignalSchema(
            signal_type=sig.signal_type.value,
            subject_code=sig.subject_code,
            comparator_code=sig.comparator_code,
            headline=sig.headline,
            details=sig.details,
            metrics=sig.metrics,
        )
        for sig in res.objective_signals
    ]

    now = datetime.now(UTC)
    return ComparisonEnvelope(
        data=ComparisonResultSchema(
            window=res.window.value,
            requested_start=res.requested_start,
            effective_start=res.effective_start,
            effective_end=res.effective_end,
            securities=sec_schemas,
            normalized_series=series_schemas,
            objective_signals=signal_schemas,
            coverage=str(res.coverage),
        ),
        meta=MetaResponse(
            as_of=now,
            received_at=now,
            data_status=res.data_status,
            source="INTERNAL",
        ),
    )
