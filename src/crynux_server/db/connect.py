from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from anyio import fail_after
from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession,
                                    async_sessionmaker, create_async_engine)

from crynux_server.config import get_config

from .models import Base

__all__ = ["session_scope", "init", "close", "Base", "get_session"]

_local = threading.local()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if (not hasattr(_local, "session")) or (not hasattr(_local, "engine")):
        raise ValueError("db has not been initialized")
    session: async_sessionmaker[AsyncSession] = _local.session
    async with session() as sess:
        try:
            yield sess
        except:
            with fail_after(5, shield=True):
                await sess.rollback()
            raise


session_scope = asynccontextmanager(get_session)


async def init(db: str | None = None):
    if db is None:        
        db = get_config().db

    if hasattr(_local, "session") or hasattr(_local, "engine"):
        raise ValueError("db has been initialized")

    engine = create_async_engine(
        db,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False},
        # echo=True,
    )
    session = async_sessionmaker(engine, autoflush=False, expire_on_commit=False)

    paths = db.split("://", maxsplit=1)
    if len(paths) == 2 and len(paths[1]) > 0:
        path = paths[1].split(r"/", maxsplit=1)[1]

        if not os.path.exists(path):
            dirname = os.path.dirname(path)
            if len(dirname) > 0:
                os.makedirs(dirname, exist_ok=True)

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
    else:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    _local.engine = engine
    _local.session = session


async def close():
    if (not hasattr(_local, "session")) or (not hasattr(_local, "engine")):
        raise ValueError("db has not been initialized")

    engine: AsyncEngine = _local.engine
    await engine.dispose()

    delattr(_local, "engine")
    delattr(_local, "session")
