from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.core.dependencies import current_user, database_session
from app.repositories.models import UserModel
from app.services.import_export import ExportService

router = APIRouter(prefix="/exports", tags=["Exports"])


@router.get("/portfolio/{portfolio_id}/transactions.csv")
async def export_portfolio_transactions(
    portfolio_id: UUID,
    user: Annotated[UserModel, Depends(current_user)],
    session: Annotated[object, Depends(database_session)],
):
    service = ExportService(session)
    csv_bytes = await service.export_portfolio_transactions_csv(user.id, portfolio_id)
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="portfolio_transactions_{portfolio_id}.csv"'
            )
        },
    )


@router.get("/portfolio/{portfolio_id}/holdings.csv")
async def export_portfolio_holdings(
    portfolio_id: UUID,
    user: Annotated[UserModel, Depends(current_user)],
    session: Annotated[object, Depends(database_session)],
):
    service = ExportService(session)
    csv_bytes = await service.export_portfolio_holdings_csv(user.id, portfolio_id)
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="portfolio_holdings_{portfolio_id}.csv"'
            )
        },
    )


@router.get("/portfolio/{portfolio_id}/summary.csv")
async def export_portfolio_summary(
    portfolio_id: UUID,
    user: Annotated[UserModel, Depends(current_user)],
    session: Annotated[object, Depends(database_session)],
):
    service = ExportService(session)
    csv_bytes = await service.export_portfolio_summary_csv(user.id, portfolio_id)
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="portfolio_summary_{portfolio_id}.csv"'
            )
        },
    )


@router.get("/watchlists.csv")
async def export_watchlists(
    user: Annotated[UserModel, Depends(current_user)],
    session: Annotated[object, Depends(database_session)],
):
    service = ExportService(session)
    csv_bytes = await service.export_watchlists_csv(user.id)
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="watchlists.csv"'},
    )
