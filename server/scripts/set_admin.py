"""后台管理员 CLI。

用法（在 server 目录下执行）：

    # 账号已存在：只授权
    python -m scripts.set_admin --username alice

    # 账号不存在：创建并授权（交互输入密码）
    python -m scripts.set_admin --username admin --email admin@example.com --create

    # 非交互：密码从 stdin 读取（至少 8 个字符，需含字母和数字，不能包含用户名）
    printf 'AdminPass2026' | python -m scripts.set_admin --username admin \
        --email admin@example.com --create --password-stdin

    python -m scripts.set_admin --username alice --revoke

说明：
- 密码不接受命令行参数，避免出现在 shell 历史与进程列表
- 变更写入 `admin_audit_logs`（admin_username=`cli`），便于事后追溯
- 生产环境通过容器执行：
  docker compose -f deploy/docker-compose.prod.yml run --rm -it api \
    python -m scripts.set_admin --username admin --email admin@example.com --create
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
import uuid

# 允许 `python -m scripts.set_admin` 直接运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core import security  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db.models import AdminAuditLog, User  # noqa: E402
from app.schemas.user import (  # noqa: E402
    validate_password_against_username,
    validate_password_bytes,
    validate_password_strength,
)


class AdminSetupError(RuntimeError):
    """脚本参数或数据校验失败（由入口转成非 0 退出码）。"""


def _audit(user: User, action: str) -> AdminAuditLog:
    return AdminAuditLog(
        admin_id=None,
        admin_username="cli",
        action=action,
        target_type="user",
        target_id=user.id,
        detail={"source": "scripts.set_admin"},
    )


async def run_set_admin(
    database_url: str,
    username: str,
    *,
    revoke: bool = False,
    create: bool = False,
    email: str | None = None,
    password: str | None = None,
) -> int:
    """设置 / 撤销管理员。`--create` 时账号不存在则创建。"""
    if create and revoke:
        raise AdminSetupError("--create 与 --revoke 不能同时使用")
    if create and not revoke:
        if password is None:
            raise AdminSetupError("创建账号需要密码")
        try:
            validate_password_bytes(password)
            validate_password_strength(password)
            validate_password_against_username(password, username)
        except ValueError as exc:
            raise AdminSetupError(str(exc)) from exc

    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            user = await session.scalar(select(User).where(User.username == username))

            if user is None:
                if not create:
                    print(f"[admin] 用户不存在: {username}（如需创建请加 --create --email）")
                    return 1
                if not email:
                    raise AdminSetupError("--create 需要同时提供 --email")
                conflict = await session.scalar(
                    select(User.id).where(User.email == email)
                )
                if conflict is not None:
                    raise AdminSetupError(f"邮箱已被占用: {email}")

                user = User(
                    id=uuid.uuid4(),
                    username=username,
                    email=email,
                    password_hash=security.hash_password(password or ""),
                    is_admin=True,
                    is_active=True,
                    token_version=0,
                )
                session.add(user)
                await session.flush()
                session.add(_audit(user, "user.create"))
                session.add(_audit(user, "user.promote"))
                await session.commit()
                print(f"[admin] 已创建管理员: {username} (id={user.id})")
                return 0

            desired = not revoke
            if user.is_admin == desired:
                print(f"[admin] 无需变更: {username} 当前 is_admin={user.is_admin}")
                return 0

            user.is_admin = desired
            session.add(_audit(user, "user.demote" if revoke else "user.promote"))
            await session.commit()
            print(
                f"[admin] {'已撤销' if revoke else '已设置'}管理员: "
                f"{username} (id={user.id})"
            )
            return 0
    finally:
        await engine.dispose()


def read_password_from_stdin() -> str:
    """从 stdin 读一行密码；去掉行尾换行，保留其余字符。"""
    line = sys.stdin.readline()
    if not line:
        raise AdminSetupError("stdin 为空，未读到密码")
    return line.rstrip("\r\n")


def prompt_password() -> str:
    """交互式输入两遍密码。"""
    if not sys.stdin.isatty():
        raise AdminSetupError(
            "当前不是交互终端；请改用 --password-stdin 从标准输入传入密码"
        )
    first = getpass.getpass("密码: ")
    second = getpass.getpass("确认密码: ")
    if first != second:
        raise AdminSetupError("两次输入的密码不一致")
    return first


def main() -> None:
    parser = argparse.ArgumentParser(description="设置 / 撤销后台管理员")
    parser.add_argument("--username", required=True, help="目标用户名")
    parser.add_argument("--email", default=None, help="创建账号时的邮箱（必填）")
    parser.add_argument(
        "--create",
        action="store_true",
        help="用户不存在时创建账号并设为管理员",
    )
    parser.add_argument("--revoke", action="store_true", help="撤销管理员权限")
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="从 stdin 读取创建账号的密码（非交互场景）",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="覆盖 DATABASE_URL（默认取 server/.env）",
    )
    args = parser.parse_args()

    password: str | None = None
    try:
        if args.create and not args.revoke:
            password = (
                read_password_from_stdin()
                if args.password_stdin
                else prompt_password()
            )
        raise SystemExit(
            asyncio.run(
                run_set_admin(
                    args.database_url or settings.DATABASE_URL,
                    args.username.strip(),
                    revoke=args.revoke,
                    create=args.create,
                    email=(args.email or "").strip() or None,
                    password=password,
                )
            )
        )
    except AdminSetupError as exc:
        print(f"[admin] {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
