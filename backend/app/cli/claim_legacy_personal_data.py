import argparse
import asyncio
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.settings import get_settings
from app.repositories.models import UserModel, WatchlistItemModel, WatchlistModel


async def claim(user_id: UUID) -> tuple[int, int]:
    engine = create_async_engine(get_settings().database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        if await session.scalar(select(UserModel.id).where(UserModel.id == user_id)) is None:
            raise ValueError("target user does not exist")
        groups = await session.execute(
            update(WatchlistModel).where(WatchlistModel.user_id.is_(None)).values(user_id=user_id)
        )
        items = await session.execute(
            update(WatchlistItemModel)
            .where(
                WatchlistItemModel.user_id.is_(None),
                WatchlistItemModel.watchlist_id.in_(
                    select(WatchlistModel.id).where(WatchlistModel.user_id == user_id)
                ),
            )
            .values(user_id=user_id)
        )
        await session.commit()
    await engine.dispose()
    return groups.rowcount, items.rowcount


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Explicitly claim unowned legacy watchlists for one existing account"
    )
    parser.add_argument("--user", required=True, type=UUID)
    args = parser.parse_args()
    groups, items = asyncio.run(claim(args.user))
    print(f"claimed watchlists={groups} items={items}")


if __name__ == "__main__":
    main()
