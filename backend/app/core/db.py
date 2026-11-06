from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_url = get_settings().database_url
_engine_kwargs = {"pool_pre_ping": True}
if _url.startswith("sqlite"):
    # SQLite (tests only): no pooling so connections never cross event loops.
    _engine_kwargs = {"poolclass": NullPool}

engine = create_async_engine(_url, **_engine_kwargs)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
