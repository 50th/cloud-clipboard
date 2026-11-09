"""后台管理员 CLI。

用法（在 server 目录下执行）：

    python -m scripts.set_admin --username alice
    python -m scripts.set_admin --username alice --revoke

说明：
- 只按用户名查找既有账号，不创建用户；用户不存在时返回非 0 退出码
- 变更会写入 `admin_audit_logs`（admin_username=`cli`），便于事后追溯
- 生产环境通过容器执行：
  docker compose -f deploy/docker-compose.prod.yml run --rm api \
    python -m scripts.set_admin --username alice
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# 允许 `python -m scripts.set_admin` 直接运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings  # noqa: E402
from app.db.models import AdminAuditLog, User  # noqa: E402


async def run_set_admin(database_url: str, username: str, *, revoke: bool) -> int:
    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            user = await session.scalar(select(User).where(User.username == username))
            if user is None:
                print(f"[admin] 用户不存在: {username}")
                return 1

            desired = not revoke
            if user.is_admin == desired:
                print(
                    f"[admin] 无需变更: {username} 当前 is_admin={user.is_admin}"
                )
                return 0

            user.is_admin = desired
            action = "user.demote" if revoke else "user.promote"
            session.add(
                AdminAuditLog(
                    admin_id=None,
                    admin_username="cli",
                    action=action,
                    target_type="user",
                    target_id=user.id,
                    detail={"source": "scripts.set_admin"},
                )
            )
            await session.commit()
            print(
                f"[admin] {'已撤销' if revoke else '已设置'}管理员: "
                f"{username} (id={user.id})"
            )
            return 0
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="设置 / 撤销后台管理员")
    parser.add_argument("--username", required=True, help="目标用户名")
    parser.add_argument("--revoke", action="store_true", help="撤销管理员权限")
    parser.add_argument(
        "--database-url",
        default=None,
        help="覆盖 DATABASE_URL（默认取 server/.env）",
    )
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            run_set_admin(
                args.database_url or settings.DATABASE_URL,
                args.username.strip(),
                revoke=args.revoke,
            )
        )
    )


if __name__ == "__main__":
    main()
