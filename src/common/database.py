"""SQLAlchemy async database configuration with naming conventions.

Provides async engine, session factory, and dependency injection for FastAPI.
Follows SQLAlchemy 2.0 async patterns and PostgreSQL naming conventions.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from src.common.config import common_settings

# =============================================================================
# Naming Conventions (PostgreSQL standard)
# =============================================================================

POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}

# =============================================================================
# Metadata and Base
# =============================================================================

metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)
Base = declarative_base(metadata=metadata)

# =============================================================================
# Engine and Session Factory
# =============================================================================

engine = create_async_engine(
    common_settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=common_settings.DEBUG,
)

SessionFactory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

# =============================================================================
# Dependency for FastAPI
# =============================================================================


async def get_db() -> AsyncSession:
    """Yield an async database session for dependency injection.

    Usage:
        @router.get("/items")
        async def get_items(db: DbDep):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with SessionFactory() as session:
        yield session


# Type alias for Annotated dependency injection (modern FastAPI pattern)
DbDep = Annotated[AsyncSession, Depends(get_db)]

__all__ = [
    "Base",
    "engine",
    "SessionFactory",
    "get_db",
    "DbDep",
    "metadata",
    "POSTGRES_INDEXES_NAMING_CONVENTION",
]
