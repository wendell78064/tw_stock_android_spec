from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.core.dependencies import current_user, database_session
from app.repositories.models import UserModel
from app.services.import_export import ReportService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/portfolio/{portfolio_id}.pdf")
async def generate_portfolio_report(
    portfolio_id: UUID,
    user: Annotated[UserModel, Depends(current_user)],
    session: Annotated[object, Depends(database_session)],
):
    service = ReportService(session)
    pdf_bytes = await service.generate_portfolio_pdf_report(user.id, portfolio_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="portfolio_report_{portfolio_id}.pdf"'
            )
        },
    )
