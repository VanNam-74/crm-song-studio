"""Create all tables (development only - use Alembic migrations in production).

    python -m scripts.init_db
"""
import asyncio

from app.core.db import engine
from app.models import Base


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Tables created.")


if __name__ == "__main__":
    asyncio.run(main())
