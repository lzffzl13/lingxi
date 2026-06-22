"""Database connection management with SQLAlchemy async."""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings
from app.utils.logger import logger

# Async engine
engine = None
async_session_factory = None


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Initialize database connection and create tables."""
    global engine, async_session_factory

    database_url = settings.DATABASE_URL
    if not database_url:
        logger.warning("DATABASE_URL not set, database features disabled")
        return

    try:
        # Convert mysql:// to mysql+aiomysql://
        if database_url.startswith("mysql://"):
            database_url = database_url.replace("mysql://", "mysql+aiomysql://", 1)

        engine = create_async_engine(
            database_url,
            echo=settings.APP_ENV == "development",
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
        )

        async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}. Running without database.")
        engine = None
        async_session_factory = None


async def close_db() -> None:
    """Close database connection."""
    global engine
    if engine:
        await engine.dispose()
        logger.info("Database connection closed")


async def get_db() -> AsyncSession:
    """Get database session."""
    if not async_session_factory:
        raise RuntimeError("Database not initialized")

    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
