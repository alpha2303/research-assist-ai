"""
SQLAlchemy database configuration and base setup.

Provides:
- Async engine and session management
- Declarative base for models
- Database dependency for FastAPI endpoints
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

# Declarative base for all models
Base = declarative_base()

# Global engine and session factory (will be initialized in main.py)
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(database_url: str) -> None:
    """
    Initialize the database engine and session factory.
    
    Call this once at application startup.
    
    Args:
        database_url: PostgreSQL connection URL (asyncpg format)
    """
    global _engine, _async_session_factory
    
    _engine = create_async_engine(
        database_url,
        echo=False,  # Set to True to see SQL queries
        future=True,
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True,  # Verify connections before using
    )
    
    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


def get_engine() -> AsyncEngine:
    """Get the database engine"""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the session factory"""
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _async_session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session.
    
    Usage:
        async with get_session() as session:
            result = await session.execute(select(Project))
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.
    
    Usage:
        @app.get("/projects")
        async def get_projects(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Project))
            return result.scalars().all()
    """
    async with get_session() as session:
        yield session


async def close_db() -> None:
    """
    Close database connections.
    
    Call this at application shutdown.
    """
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
