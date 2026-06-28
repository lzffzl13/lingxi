"""Database connection management tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db import database


class FakeConnection:
    """Async connection stub for init_db table creation."""

    def __init__(self):
        self.run_sync = AsyncMock()


class FakeBeginContext:
    """Async context manager stub returned by engine.begin()."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeEngine:
    """Async engine stub with disposable lifecycle."""

    def __init__(self):
        self.conn = FakeConnection()
        self.dispose = AsyncMock()

    def begin(self):
        return FakeBeginContext(self.conn)


@pytest.fixture(autouse=True)
def reset_database_state():
    database.engine = None
    database.async_session_factory = None
    yield
    database.engine = None
    database.async_session_factory = None


@pytest.mark.asyncio
async def test_init_db_uses_configured_pool_settings():
    fake_engine = FakeEngine()
    fake_session_factory = MagicMock(name="session_factory")

    with (
        patch.object(database.settings, "DATABASE_URL", "mysql://user:pass@localhost/db"),
        patch.object(database.settings, "DB_POOL_SIZE", 11),
        patch.object(database.settings, "DB_MAX_OVERFLOW", 7),
        patch.object(database.settings, "DB_POOL_TIMEOUT", 19),
        patch.object(database.settings, "DB_POOL_RECYCLE", 321),
        patch.object(database.settings, "APP_ENV", "production"),
        patch("app.db.database.create_async_engine", return_value=fake_engine) as create_engine,
        patch("app.db.database.async_sessionmaker", return_value=fake_session_factory) as sessionmaker_cls,
    ):
        await database.init_db()

    create_engine.assert_called_once_with(
        "mysql+aiomysql://user:pass@localhost/db",
        echo=False,
        pool_size=11,
        max_overflow=7,
        pool_pre_ping=True,
        pool_timeout=19,
        pool_recycle=321,
    )
    sessionmaker_cls.assert_called_once()
    fake_engine.conn.run_sync.assert_awaited_once()
    assert database.engine is fake_engine
    assert database.async_session_factory is fake_session_factory


@pytest.mark.asyncio
async def test_init_db_is_idempotent_once_initialized():
    database.engine = MagicMock()
    database.async_session_factory = MagicMock()

    with patch("app.db.database.create_async_engine") as create_engine:
        await database.init_db()

    create_engine.assert_not_called()


@pytest.mark.asyncio
async def test_close_db_disposes_engine_and_resets_state():
    fake_engine = FakeEngine()
    database.engine = fake_engine
    database.async_session_factory = MagicMock()

    await database.close_db()

    fake_engine.dispose.assert_awaited_once()
    assert database.engine is None
    assert database.async_session_factory is None
