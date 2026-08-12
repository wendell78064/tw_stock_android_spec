from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.screener import SavedScreener, ScreenerExpression
from app.repositories.models import SavedScreenerModel
from app.services.screener_ast import dict_to_expression, expression_to_dict


class SqlScreenerRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_screeners(self) -> list[SavedScreener]:
        stmt = select(SavedScreenerModel).order_by(SavedScreenerModel.updated_at.desc())
        res = await self.session.execute(stmt)
        return [self._to_domain(m) for m in res.scalars().all()]

    async def get_screener(self, id: UUID) -> SavedScreener | None:
        stmt = select(SavedScreenerModel).where(SavedScreenerModel.id == id)
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def create_screener(
        self,
        name: str,
        expression: ScreenerExpression,
        description: str | None = None,
        sort_field: str = "code",
        sort_direction: str = "ASC",
    ) -> SavedScreener:
        now = datetime.now(UTC)
        model = SavedScreenerModel(
            name=name,
            description=description,
            expression=expression_to_dict(expression),
            sort_field=sort_field,
            sort_direction=sort_direction,
            created_at=now,
            updated_at=now,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_domain(model)

    async def update_screener(
        self,
        id: UUID,
        name: str | None = None,
        description: str | None = None,
        expression: ScreenerExpression | None = None,
        sort_field: str | None = None,
        sort_direction: str | None = None,
    ) -> SavedScreener | None:
        stmt = select(SavedScreenerModel).where(SavedScreenerModel.id == id)
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        if model is None:
            return None

        if name is not None:
            model.name = name
        if description is not None:
            model.description = description
        if expression is not None:
            model.expression = expression_to_dict(expression)
        if sort_field is not None:
            model.sort_field = sort_field
        if sort_direction is not None:
            model.sort_direction = sort_direction

        model.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_domain(model)

    async def delete_screener(self, id: UUID) -> bool:
        stmt = delete(SavedScreenerModel).where(SavedScreenerModel.id == id)
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.rowcount > 0

    def _to_domain(self, model: SavedScreenerModel) -> SavedScreener:
        expr = dict_to_expression(model.expression)
        return SavedScreener(
            id=model.id,
            name=model.name,
            description=model.description,
            expression=expr,
            sort_field=model.sort_field,
            sort_direction=model.sort_direction,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
