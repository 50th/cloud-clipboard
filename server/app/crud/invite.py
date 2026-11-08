"""邀请码数据访问层。

- 生成：随机明文 + SHA-256 哈希入库，明文只返回一次
- 校验：`consume_code` 用一条带条件的 UPDATE 原子扣减次数，避免并发超发
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.invite_code import InviteCode

# 去掉容易看错的 0/O/1/I
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 12


def normalize_code(value: str) -> str:
    """去空白并统一大写，避免用户输入大小写不一致导致校验失败。"""
    return value.strip().upper()


def hash_code(value: str) -> str:
    """对规范化后的邀请码做 SHA-256。"""
    return hashlib.sha256(normalize_code(value).encode("utf-8")).hexdigest()


def generate_code() -> str:
    """生成一个新的随机邀请码明文。"""
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


async def create_code(
    session: AsyncSession,
    *,
    label: str | None = None,
    max_uses: int | None = 1,
    expires_at: datetime | None = None,
) -> tuple[str, InviteCode]:
    """创建邀请码，返回 `(明文, 记录)`。明文不会持久化。"""
    plaintext = generate_code()
    row = InviteCode(
        code_hash=hash_code(plaintext),
        code_hint=plaintext[:8],
        label=label,
        max_uses=max_uses,
        expires_at=expires_at,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return plaintext, row


async def consume_code(session: AsyncSession, code: str) -> InviteCode | None:
    """原子校验并占用一次使用机会。

    条件更新保证并发下不会超出 `max_uses`；返回 `None` 表示邀请码
    不存在、已过期、已撤销或已用尽。调用方应在同一事务内创建用户，
    若创建失败由请求级回滚把 `used_count` 一并还原。
    """
    if not normalize_code(code):
        return None
    stmt = (
        update(InviteCode)
        .where(
            InviteCode.code_hash == hash_code(code),
            InviteCode.revoked_at.is_(None),
            or_(InviteCode.expires_at.is_(None), InviteCode.expires_at > func.now()),
            or_(
                InviteCode.max_uses.is_(None),
                InviteCode.used_count < InviteCode.max_uses,
            ),
        )
        .values(
            used_count=InviteCode.used_count + 1,
            last_used_at=func.now(),
        )
        .returning(InviteCode)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_codes(session: AsyncSession) -> list[InviteCode]:
    """按创建时间倒序列出邀请码。"""
    result = await session.execute(
        select(InviteCode).order_by(InviteCode.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_code(
    session: AsyncSession, *, code_id: uuid.UUID | None = None, hint: str | None = None
) -> InviteCode | None:
    """按 id 或明文前缀撤销；返回被撤销的记录，未找到则返回 None。"""
    if code_id is not None:
        result = await session.execute(select(InviteCode).where(InviteCode.id == code_id))
    elif hint:
        result = await session.execute(
            select(InviteCode).where(InviteCode.code_hint == hint.strip().upper())
        )
    else:
        return None
    row = result.scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return row
    row.revoked_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(row)
    return row
