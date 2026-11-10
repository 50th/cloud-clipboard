"""管理员 CLI（scripts/set_admin.py）测试。

直接调用 `run_set_admin`，打测试库；不涉及 HTTP。
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.db.models import AdminAuditLog, User
from scripts.set_admin import AdminSetupError, run_set_admin

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://clipboard:clipboard@127.0.0.1:5433/clipboard_test",
)

PASSWORD = "cli-password-123"


async def get_user(session: AsyncSession, username: str) -> User | None:
    return await session.scalar(select(User).where(User.username == username))


class TestSetAdminCreate:
    async def test_创建账号并设为管理员(self, session: AsyncSession, engine) -> None:
        code = await run_set_admin(
            TEST_DATABASE_URL,
            "cli-new-admin",
            create=True,
            email="cli-new-admin@example.com",
            password=PASSWORD,
        )
        assert code == 0

        user = await get_user(session, "cli-new-admin")
        assert user is not None
        assert user.is_admin is True
        assert user.is_active is True
        assert security.verify_password(PASSWORD, user.password_hash)

        actions = (
            await session.scalars(
                select(AdminAuditLog.action).where(AdminAuditLog.target_id == user.id)
            )
        ).all()
        assert set(actions) == {"user.create", "user.promote"}

    async def test_创建时邮箱重复报错(
        self, session: AsyncSession, engine
    ) -> None:
        await run_set_admin(
            TEST_DATABASE_URL,
            "cli-email-a",
            create=True,
            email="shared-cli@example.com",
            password=PASSWORD,
        )
        with pytest.raises(AdminSetupError, match="邮箱已被占用"):
            await run_set_admin(
                TEST_DATABASE_URL,
                "cli-email-b",
                create=True,
                email="shared-cli@example.com",
                password=PASSWORD,
            )

    async def test_密码过短被拒(self, engine) -> None:
        with pytest.raises(AdminSetupError, match="至少"):
            await run_set_admin(
                TEST_DATABASE_URL,
                "cli-short-pw",
                create=True,
                email="cli-short-pw@example.com",
                password="12345",
            )

    async def test_密码超过_72_字节被拒(self, engine) -> None:
        with pytest.raises(AdminSetupError, match="字节"):
            await run_set_admin(
                TEST_DATABASE_URL,
                "cli-long-pw",
                create=True,
                email="cli-long-pw@example.com",
                password="密" * 25,
            )

    async def test_创建与撤销不能同时使用(self, engine) -> None:
        with pytest.raises(AdminSetupError):
            await run_set_admin(
                TEST_DATABASE_URL,
                "cli-both",
                create=True,
                revoke=True,
                email="cli-both@example.com",
                password=PASSWORD,
            )


class TestSetAdminExisting:
    async def test_账号不存在且未指定_create返回_1(self, engine) -> None:
        assert await run_set_admin(TEST_DATABASE_URL, "cli-missing") == 1

    async def test_已存在账号直接授权并写审计(
        self, session: AsyncSession, engine
    ) -> None:
        await run_set_admin(
            TEST_DATABASE_URL,
            "cli-promote",
            create=True,
            email="cli-promote@example.com",
            password=PASSWORD,
        )
        # 先撤销，再重新授权，验证两条路径
        assert await run_set_admin(TEST_DATABASE_URL, "cli-promote", revoke=True) == 0
        user = await get_user(session, "cli-promote")
        assert user is not None
        assert user.is_admin is False

        assert await run_set_admin(TEST_DATABASE_URL, "cli-promote") == 0
        await session.refresh(user)
        assert user.is_admin is True

        actions = (
            await session.scalars(
                select(AdminAuditLog.action)
                .where(AdminAuditLog.target_id == user.id)
                .order_by(AdminAuditLog.created_at)
            )
        ).all()
        assert "user.demote" in actions
        assert actions.count("user.promote") == 2

    async def test_重复授权幂等(self, session: AsyncSession, engine) -> None:
        await run_set_admin(
            TEST_DATABASE_URL,
            "cli-idempotent",
            create=True,
            email="cli-idempotent@example.com",
            password=PASSWORD,
        )
        assert await run_set_admin(TEST_DATABASE_URL, "cli-idempotent") == 0
        user = await get_user(session, "cli-idempotent")
        assert user is not None
        assert user.is_admin is True
