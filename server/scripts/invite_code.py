"""邀请码管理 CLI。

用法（在 server 目录下执行）：

    python -m scripts.invite_code create --days 7 --max-uses 1 --label "alice"
    python -m scripts.invite_code list
    python -m scripts.invite_code revoke --hint ABCD1234
    python -m scripts.invite_code revoke --id <uuid>

说明：
- 邀请码明文只在 `create` 时输出一次，数据库中只保存 SHA-256 哈希
- `--days 0` 表示不过期；`--max-uses 0` 表示不限次数
- 生产环境通过容器执行：
  docker compose -f deploy/docker-compose.prod.yml run --rm api \
    python -m scripts.invite_code create --days 7 --max-uses 1
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

# 允许 `python -m scripts.invite_code` 直接运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.crud import invite as invite_crud  # noqa: E402
from app.db.models import InviteCode  # noqa: E402,F401  （导入以注册 metadata）


async def run_create(
    database_url: str, *, days: int, max_uses: int, label: str | None
) -> int:
    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=days) if days > 0 else None
    )
    try:
        async with factory() as session:
            plaintext, row = await invite_crud.create_code(
                session,
                label=label,
                max_uses=None if max_uses <= 0 else max_uses,
                expires_at=expires_at,
            )
            print(f"[invite] 已创建（明文仅显示一次）: {plaintext}")
            print(
                f"[invite] id={row.id} hint={row.code_hint} "
                f"expires={row.expires_at or 'never'} "
                f"max_uses={row.max_uses if row.max_uses is not None else 'unlimited'}"
            )
    finally:
        await engine.dispose()
    return 0


async def run_list(database_url: str) -> int:
    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            rows = await invite_crud.list_codes(session)
            if not rows:
                print("[invite] 暂无邀请码")
                return 0
            now = datetime.now(timezone.utc)
            for row in rows:
                if row.revoked_at is not None:
                    status = "revoked"
                elif row.expires_at is not None and row.expires_at <= now:
                    status = "expired"
                elif row.max_uses is not None and row.used_count >= row.max_uses:
                    status = "exhausted"
                else:
                    status = "active"
                max_uses = "∞" if row.max_uses is None else str(row.max_uses)
                print(
                    f"[invite] {row.id} hint={row.code_hint} label={row.label or '-'} "
                    f"status={status} used={row.used_count}/{max_uses} "
                    f"expires={row.expires_at or 'never'}"
                )
    finally:
        await engine.dispose()
    return 0


async def run_revoke(
    database_url: str, *, code_id: str | None, hint: str | None
) -> int:
    parsed_id: uuid.UUID | None = None
    if code_id:
        try:
            parsed_id = uuid.UUID(code_id)
        except ValueError:
            print(f"[invite] 无效的 UUID: {code_id}", file=sys.stderr)
            return 2
    if parsed_id is None and not hint:
        print("[invite] 需要 --id 或 --hint", file=sys.stderr)
        return 2

    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            row = await invite_crud.revoke_code(
                session, code_id=parsed_id, hint=hint
            )
            if row is None:
                print("[invite] 未找到匹配的邀请码", file=sys.stderr)
                return 1
            print(f"[invite] 已撤销 id={row.id} hint={row.code_hint}")
    finally:
        await engine.dispose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="管理注册邀请码")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="生成邀请码")
    p_create.add_argument("--days", type=int, default=7, help="有效期天数；0=不过期")
    p_create.add_argument("--max-uses", type=int, default=1, help="最大使用次数；0=不限")
    p_create.add_argument("--label", default=None, help="备注，例如邀请对象")
    p_create.add_argument("--database", default=settings.DATABASE_URL)

    p_list = sub.add_parser("list", help="列出邀请码")
    p_list.add_argument("--database", default=settings.DATABASE_URL)

    p_revoke = sub.add_parser("revoke", help="撤销邀请码")
    p_revoke.add_argument("--id", default=None, help="邀请码记录的 UUID")
    p_revoke.add_argument("--hint", default=None, help="邀请码明文前 8 位")
    p_revoke.add_argument("--database", default=settings.DATABASE_URL)

    args = parser.parse_args()

    if args.command == "create":
        return asyncio.run(
            run_create(
                args.database,
                days=args.days,
                max_uses=args.max_uses,
                label=args.label,
            )
        )
    if args.command == "list":
        return asyncio.run(run_list(args.database))
    return asyncio.run(
        run_revoke(args.database, code_id=args.id, hint=args.hint)
    )


if __name__ == "__main__":
    raise SystemExit(main())
