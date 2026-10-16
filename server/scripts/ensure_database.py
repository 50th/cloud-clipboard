"""确保某个数据库存在（不存在则创建）。

用途：给测试准备独立数据库。`run_web_tests.ps1` 在启动隔离后端前会调用它。

为什么需要：后端 pytest 每个用例都会 `drop_all` 重建表。如果 Web 端测试
与它**共用同一个测试库**，两者同时跑就会互相删表（实测踩过：并行跑时
Web 测试因表被删而失败）。各自一个库后互不干扰。

用法（在 server 目录下，或用 venv 的 python 调用）：
    python -m scripts.ensure_database --database-url postgresql+asyncpg://clipboard:clipboard@127.0.0.1:5433/clipboard_web_test

默认值取自 `E2E_DATABASE_URL` 环境变量，其次用本机默认。

⚠️ 库名**必须含 `test`**：Web 端测试以库名判定"这是可丢弃的测试库"，
不含 `test` 的库不允许跑破坏性用例。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys

import asyncpg

DEFAULT_URL = "postgresql+asyncpg://clipboard:clipboard@127.0.0.1:5433/clipboard_web_test"

# 数据库名会拼进 SQL（CREATE DATABASE 不支持参数化），必须先严格校验
_SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def to_asyncpg_dsn(url: str) -> str:
    """把 SQLAlchemy 的 `postgresql+asyncpg://` 转成 asyncpg 能吃的 DSN。"""
    return url.replace("postgresql+asyncpg://", "postgresql://")


def split_database(url: str) -> tuple[str, str]:
    """拆成 (不含库名的基础串, 库名)。"""
    base, _, name = url.rpartition("/")
    if not base or not name:
        raise SystemExit(f"无法从连接串解析出库名: {url!r}")
    return base, name


async def ensure_database(url: str) -> bool:
    """确保目标数据库存在。返回 True 表示本次新建了它。"""
    base, db_name = split_database(url)
    if not _SAFE_NAME.match(db_name):
        raise SystemExit(f"数据库名不合法（只允许字母、数字、下划线）: {db_name!r}")

    # 连到维护库 postgres 上执行建库
    admin = to_asyncpg_dsn(f"{base}/postgres")
    conn = await asyncpg.connect(admin)
    try:
        exists = await conn.fetchval("select 1 from pg_database where datname = $1", db_name)
        if exists:
            print(f"[ensure_db] {db_name} 已存在，跳过创建")
            return False
        await conn.execute(f'CREATE DATABASE "{db_name}"')
        print(f"[ensure_db] 已创建数据库 {db_name}")
        return True
    finally:
        await conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="确保测试数据库存在")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("E2E_DATABASE_URL", DEFAULT_URL),
        help="目标数据库连接串（SQLAlchemy 风格亦可）",
    )
    args = parser.parse_args()

    try:
        asyncio.run(ensure_database(args.database_url))
    except asyncpg.PostgresError as exc:
        print(f"[ensure_db] 失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
