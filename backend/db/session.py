import os
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://temporal:temporal@localhost:5432/loan_disbursement",
)

engine = create_async_engine(DATABASE_URL)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    # ponytail: create_all() for dev bring-up; swap for real Alembic
    # migrations before this touches a shared/prod database.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session_scope():
    async with SessionLocal() as session:
        async with session.begin():
            yield session
