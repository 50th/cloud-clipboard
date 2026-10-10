"""数据库初始化脚本：建表 + 准备演示用户 + 可选种子数据。

用法（在 server 目录下执行）：

    .\\venv\\Scripts\\python.exe -m scripts.init_db              # 建表 + 演示用户 + 种子数据
    .\\venv\\Scripts\\python.exe -m scripts.init_db --no-seed     # 只建表 + 演示用户
    .\\venv\\Scripts\\python.exe -m scripts.init_db --drop        # 先删表再建（⚠️ 会清空数据）
    .\\venv\\Scripts\\python.exe -m scripts.init_db --database postgresql+asyncpg://.../clipboard_test

说明：
- 生产环境的表结构由 **Alembic 迁移**创建（`alembic upgrade head`），本脚本用 `create_all`
  仅面向本地开发与测试库，方便快速铺开。
- 种子数据仅在表为空时写入，重复执行不会产生重复记录。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# 允许 `python -m scripts.init_db` 直接运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.crud import clipboard as clipboard_crud  # noqa: E402
from app.crud import user as user_crud  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import ClipboardItem, User  # noqa: E402  （导入以注册 metadata）
from app.schemas.clipboard import ClipboardItemCreate  # noqa: E402

# 种子数据：与第 1 步的假数据保持一致，便于 Web 端对照
SEED_ITEMS: list[tuple[str, str]] = [
    ("FastAPI 官方教程", "https://fastapi.tiangolo.com/tutorial/"),
    ("后端依赖安装命令", "pip install fastapi uvicorn[standard]"),
    (
        "阶段一范围备忘",
        "云剪贴板阶段一：文字内容的上传、查询、删除 + WebSocket 实时同步 + JWT 认证 + 内容去重。",
    ),
    ("提交规范示例", 'git commit -m "feat: 新增 WebSocket 广播"'),
]


async def run(database_url: str, *, drop: bool, seed: bool) -> int:
    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print(f"[init_db] 目标数据库: {database_url.split('@')[-1]}")

    async with engine.begin() as conn:
        if drop:
            print("[init_db] 删除已有表（--drop）")
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        tables = ", ".join(sorted(Base.metadata.tables))
        print(f"[init_db] 表结构就绪: {tables}")

    async with factory() as session:
        user = await user_crud.ensure_demo_user(session)
        print(f"[init_db] 演示用户: {user.username} ({user.id})")

        existing = await clipboard_crud.count_items(session, user.id)
        if seed and existing == 0:
            for title, content in SEED_ITEMS:
                await clipboard_crud.create_item(
                    session,
                    user.id,
                    ClipboardItemCreate(content=content, title=title),
                    username=user.username,
                )
            total = await clipboard_crud.count_items(session, user.id)
            print(f"[init_db] 写入种子数据: {total} 条")
        else:
            print(f"[init_db] 跳过种子数据（现有 {existing} 条）")

    await engine.dispose()
    print("[init_db] 完成")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化云剪贴板数据库")
    parser.add_argument("--drop", action="store_true", help="先删除所有表（会清空数据）")
    parser.add_argument("--no-seed", action="store_true", help="不写入种子数据")
    parser.add_argument(
        "--database",
        default=settings.DATABASE_URL,
        help="覆盖 DATABASE_URL（例如指向 clipboard_test 库）",
    )
    args = parser.parse_args()

    if args.drop and "test" not in args.database and os.environ.get("ALLOW_DROP_DEV") != "1":
        print(
            "[init_db] 拒绝执行 --drop：目标库名不含 'test'。\n"
            "          确认要清空开发库时，设置环境变量 ALLOW_DROP_DEV=1 再运行。",
            file=sys.stderr,
        )
        return 2

    return asyncio.run(run(args.database, drop=args.drop, seed=not args.no_seed))


if __name__ == "__main__":
    raise SystemExit(main())
