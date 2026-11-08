"""ORM 模型：注册邀请码。

只保存邀请码的哈希，明文仅在生成时输出一次。这样即使数据库泄露，
也无法直接拿到可用的邀请码。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class InviteCode(Base):
    """一条邀请码。`max_uses=None` 表示不限次数，`expires_at=None` 表示不过期。"""

    __tablename__ = "invite_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=_uuid
    )
    # 对规范化后的明文做 SHA-256；唯一索引避免重复码
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # 明文前 8 位，仅用于 CLI 列表/撤销时辨认，不可用于注册
    code_hint: Mapped[str] = mapped_column(String(8))
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
