"""用户数据访问层（异步）。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.user import User


async def get_by_id(session: AsyncSession, user_id: str | uuid.UUID) -> User | None:
    """按主键查询用户。"""
    try:
        key = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
    except (ValueError, AttributeError, TypeError):
        return None
    return await session.get(User, key)


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    """按用户名查询用户。"""
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    """按邮箱查询用户。"""
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    username: str,
    email: str,
    password_hash: str | None = None,
    nickname: str | None = None,
    user_id: uuid.UUID | None = None,
) -> User:
    """创建用户并提交。"""
    user = User(
        id=user_id or uuid.uuid4(),
        username=username,
        email=email,
        password_hash=password_hash,
        nickname=nickname,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def ensure_demo_user(session: AsyncSession) -> User:
    """确保演示用户存在（按配置的用户名与固定 id）。

    第 1/2 步未接入认证，所有请求都视为演示用户发起；
    第 4 步接入真实登录后，本函数仅用于开发/测试数据准备。
    """
    user = await get_by_id(session, settings.DEMO_USER_ID)
    if user is not None:
        return user

    return await create(
        session,
        user_id=uuid.UUID(settings.DEMO_USER_ID),
        username=settings.DEMO_USERNAME,
        email=settings.DEMO_EMAIL,
        nickname="演示用户",
    )
