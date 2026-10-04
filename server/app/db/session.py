"""数据库会话与引擎管理。

约定：
- 应用运行时统一走**异步引擎**（asyncpg）
- Alembic 迁移走同步引擎（见 `alembic/env.py`），避免 async 迁移样板
- `get_db()` 是 FastAPI 依赖，每个请求一个会话，异常自动回滚
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """返回进程内唯一的异步引擎（懒创建）。"""
    global _engine
    if _engine is None:
        if not settings.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL 未配置。请参考 server/.env.example 设置，"
                "例如 postgresql+asyncpg://clipboard:clipboard@127.0.0.1:5433/clipboard"
            )
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DB_ECHO,
            pool_pre_ping=True,  # 连接被数据库重启掐断时自动剔除坏连接
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """返回进程内唯一的 session 工厂（懒创建）。"""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,  # 提交后仍可读取对象属性，便于直接构造响应
            autoflush=False,
        )
    return _session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：提供一个请求级会话。"""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """关闭连接池（应用退出时调用）。"""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def ping() -> dict[str, Any]:
    """连通性探测：返回数据库版本与当前库名。"""
    engine = get_engine()
    async with engine.connect() as conn:
        version = await conn.scalar(text("select version()"))
        database = await conn.scalar(text("select current_database()"))
    return {"database": database, "version": str(version).split(" on ")[0]}
