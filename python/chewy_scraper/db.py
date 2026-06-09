from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from chewy_scraper.config import DatabaseConfig

_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_db(config: DatabaseConfig) -> None:
    global _sessionmaker
    engine = create_async_engine(config.url, pool_size=config.pool_size, echo=False)
    _sessionmaker = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if _sessionmaker is None:
        raise RuntimeError("Database not initialised — call init_db() first")
    async with _sessionmaker() as session:
        async with session.begin():
            yield session
