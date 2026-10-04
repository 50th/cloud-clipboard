"""Alembic 迁移环境（异步引擎）。

与默认模板的差异：
1. 连接串从 `app.core.config.settings.DATABASE_URL` 读取，**不写在 alembic.ini 里**（避免提交密码）
2. `target_metadata` 指向项目 Base，并显式导入模型包，保证 autogenerate 能发现所有表
3. 支持 `-x db_url=...` 覆盖目标库（用于对测试库单独跑迁移）

常用命令（在 server 目录下执行）：

    .\\venv\\Scripts\\python.exe -m alembic revision --autogenerate -m "描述"
    .\\venv\\Scripts\\python.exe -m alembic upgrade head
    .\\venv\\Scripts\\python.exe -m alembic downgrade -1
    .\\venv\\Scripts\\python.exe -m alembic current
    .\\venv\\Scripts\\python.exe -m alembic history
    # 对测试库跑迁移：
    .\\venv\\Scripts\\python.exe -m alembic -x db_url=postgresql+asyncpg://clipboard:clipboard@127.0.0.1:5433/clipboard_test upgrade head
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.db.base import Base

# 导入模型包，把表注册进 Base.metadata（autogenerate 依赖它）
from app.db.models import ClipboardItem, User  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """优先用 -x db_url=... 覆盖，否则用应用配置。"""
    override = context.get_x_argument(as_dictionary=True).get("db_url")
    return override or settings.DATABASE_URL


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连数据库。"""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """异步模式：创建临时异步引擎并执行迁移。"""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """在线模式入口。"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
