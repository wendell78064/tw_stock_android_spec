from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.schemas import (
    CreateSavedScreenerInput,
    MetaResponse,
    RunScreenerInput,
    SavedScreenerEnvelope,
    SavedScreenerListEnvelope,
    ScreenerFieldMetaSchema,
    ScreenerFieldsEnvelope,
    ScreenerResultEnvelope,
    ScreenerResultSecuritySchema,
    UpdateSavedScreenerInput,
)
from app.core.dependencies import screener_query_service, screener_repository
from app.core.errors import AppError
from app.domain.screener import SCREENER_FIELDS_REGISTRY
from app.repositories.sql_screener import SqlScreenerRepository
from app.services.screener_ast import dict_to_expression, expression_to_dict, validate_expression
from app.services.screener_query import ScreenerQueryService

router = APIRouter(prefix="/v1", tags=["Screeners"])


@router.get(
    "/screener/fields",
    response_model=ScreenerFieldsEnvelope,
    operation_id="getScreenerFields",
)
async def get_screener_fields() -> ScreenerFieldsEnvelope:
    fields = [
        ScreenerFieldMetaSchema(
            field_id=f.field_id,
            label=f.label,
            category=f.category.value,
            value_type=f.value_type.value,
            allowed_operators=[op.value for op in f.allowed_operators],
            unit=f.unit,
            supported_windows=f.supported_windows,
        )
        for f in SCREENER_FIELDS_REGISTRY.values()
    ]
    now = datetime.now(UTC)
    return ScreenerFieldsEnvelope(
        data=fields,
        meta=MetaResponse(
            as_of=now,
            received_at=now,
            data_status="FINAL",
            source="INTERNAL",
        ),
    )


@router.post(
    "/screener/run",
    response_model=ScreenerResultEnvelope,
    operation_id="runScreener",
)
async def run_screener(
    input_data: RunScreenerInput,
    query_service: Annotated[ScreenerQueryService, Depends(screener_query_service)],
) -> ScreenerResultEnvelope:
    ast_expr = dict_to_expression(input_data.expression)
    validate_expression(ast_expr)

    results, total_count, trade_date = await query_service.execute_screener(
        expression=ast_expr,
        target_trade_date=input_data.trade_date,
        sort_field=input_data.sort_field,
        sort_direction=input_data.sort_direction,
        limit=input_data.limit,
        offset=input_data.offset,
    )

    items = [
        ScreenerResultSecuritySchema(
            security_id=r.security_id,
            code=r.code,
            name=r.name,
            market=r.market,
            industry_name=r.industry_name,
            themes=r.themes,
            close=r.close,
            return_pct=r.return_pct,
            matched_conditions=r.matched_conditions,
            extra_metrics=r.extra_metrics,
            data_status=r.data_status,
        )
        for r in results
    ]

    now = datetime.now(UTC)
    return ScreenerResultEnvelope(
        data=items,
        total_count=total_count,
        trade_date=trade_date,
        meta=MetaResponse(
            as_of=now,
            received_at=now,
            data_status="FINAL" if results else "UNAVAILABLE",
            source="INTERNAL",
        ),
    )


@router.get(
    "/screeners",
    response_model=SavedScreenerListEnvelope,
    operation_id="listSavedScreeners",
)
async def list_saved_screeners(
    repository: Annotated[SqlScreenerRepository, Depends(screener_repository)],
) -> SavedScreenerListEnvelope:
    screeners = await repository.list_screeners()
    now = datetime.now(UTC)
    return SavedScreenerListEnvelope(
        data=[
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "expression": expression_to_dict(s.expression),
                "sort_field": s.sort_field,
                "sort_direction": s.sort_direction,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
            }
            for s in screeners
        ],
        meta=MetaResponse(
            as_of=now,
            received_at=now,
            data_status="FINAL",
            source="INTERNAL",
        ),
    )


@router.post(
    "/screeners",
    response_model=SavedScreenerEnvelope,
    status_code=status.HTTP_211_CREATED if False else status.HTTP_201_CREATED,
    operation_id="createSavedScreener",
)
async def create_saved_screener(
    input_data: CreateSavedScreenerInput,
    repository: Annotated[SqlScreenerRepository, Depends(screener_repository)],
) -> SavedScreenerEnvelope:
    ast_expr = dict_to_expression(input_data.expression)
    validate_expression(ast_expr)

    screener = await repository.create_screener(
        name=input_data.name.strip(),
        description=input_data.description.strip() if input_data.description else None,
        expression=ast_expr,
        sort_field=input_data.sort_field,
        sort_direction=input_data.sort_direction,
    )

    now = datetime.now(UTC)
    return SavedScreenerEnvelope(
        data={
            "id": screener.id,
            "name": screener.name,
            "description": screener.description,
            "expression": expression_to_dict(screener.expression),
            "sort_field": screener.sort_field,
            "sort_direction": screener.sort_direction,
            "created_at": screener.created_at,
            "updated_at": screener.updated_at,
        },
        meta=MetaResponse(
            as_of=now,
            received_at=now,
            data_status="FINAL",
            source="INTERNAL",
        ),
    )


@router.get(
    "/screeners/{id}",
    response_model=SavedScreenerEnvelope,
    operation_id="getSavedScreener",
)
async def get_saved_screener(
    id: UUID,
    repository: Annotated[SqlScreenerRepository, Depends(screener_repository)],
) -> SavedScreenerEnvelope:
    screener = await repository.get_screener(id)
    if screener is None:
        raise AppError("SCREENER_NOT_FOUND", f"Saved screener '{id}' not found", 404)

    now = datetime.now(UTC)
    return SavedScreenerEnvelope(
        data={
            "id": screener.id,
            "name": screener.name,
            "description": screener.description,
            "expression": expression_to_dict(screener.expression),
            "sort_field": screener.sort_field,
            "sort_direction": screener.sort_direction,
            "created_at": screener.created_at,
            "updated_at": screener.updated_at,
        },
        meta=MetaResponse(
            as_of=now,
            received_at=now,
            data_status="FINAL",
            source="INTERNAL",
        ),
    )


@router.patch(
    "/screeners/{id}",
    response_model=SavedScreenerEnvelope,
    operation_id="updateSavedScreener",
)
async def update_saved_screener(
    id: UUID,
    input_data: UpdateSavedScreenerInput,
    repository: Annotated[SqlScreenerRepository, Depends(screener_repository)],
) -> SavedScreenerEnvelope:
    ast_expr = None
    if input_data.expression is not None:
        ast_expr = dict_to_expression(input_data.expression)
        validate_expression(ast_expr)

    screener = await repository.update_screener(
        id=id,
        name=input_data.name.strip() if input_data.name is not None else None,
        description=input_data.description.strip() if input_data.description is not None else None,
        expression=ast_expr,
        sort_field=input_data.sort_field,
        sort_direction=input_data.sort_direction,
    )
    if screener is None:
        raise AppError("SCREENER_NOT_FOUND", f"Saved screener '{id}' not found", 404)

    now = datetime.now(UTC)
    return SavedScreenerEnvelope(
        data={
            "id": screener.id,
            "name": screener.name,
            "description": screener.description,
            "expression": expression_to_dict(screener.expression),
            "sort_field": screener.sort_field,
            "sort_direction": screener.sort_direction,
            "created_at": screener.created_at,
            "updated_at": screener.updated_at,
        },
        meta=MetaResponse(
            as_of=now,
            received_at=now,
            data_status="FINAL",
            source="INTERNAL",
        ),
    )


@router.delete(
    "/screeners/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteSavedScreener",
)
async def delete_saved_screener(
    id: UUID,
    repository: Annotated[SqlScreenerRepository, Depends(screener_repository)],
) -> Response:
    deleted = await repository.delete_screener(id)
    if not deleted:
        raise AppError("SCREENER_NOT_FOUND", f"Saved screener '{id}' not found", 404)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/screeners/{id}/run",
    response_model=ScreenerResultEnvelope,
    operation_id="runSavedScreener",
)
async def run_saved_screener(
    id: UUID,
    repository: Annotated[SqlScreenerRepository, Depends(screener_repository)],
    query_service: Annotated[ScreenerQueryService, Depends(screener_query_service)],
    limit: int = 50,
    offset: int = 0,
) -> ScreenerResultEnvelope:
    screener = await repository.get_screener(id)
    if screener is None:
        raise AppError("SCREENER_NOT_FOUND", f"Saved screener '{id}' not found", 404)

    results, total_count, trade_date = await query_service.execute_screener(
        expression=screener.expression,
        sort_field=screener.sort_field,
        sort_direction=screener.sort_direction,
        limit=limit,
        offset=offset,
    )

    items = [
        ScreenerResultSecuritySchema(
            security_id=r.security_id,
            code=r.code,
            name=r.name,
            market=r.market,
            industry_name=r.industry_name,
            themes=r.themes,
            close=r.close,
            return_pct=r.return_pct,
            matched_conditions=r.matched_conditions,
            extra_metrics=r.extra_metrics,
            data_status=r.data_status,
        )
        for r in results
    ]

    now = datetime.now(UTC)
    return ScreenerResultEnvelope(
        data=items,
        total_count=total_count,
        trade_date=trade_date,
        meta=MetaResponse(
            as_of=now,
            received_at=now,
            data_status="FINAL" if results else "UNAVAILABLE",
            source="INTERNAL",
        ),
    )
