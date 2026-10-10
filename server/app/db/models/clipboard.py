"""ORM 模型：剪贴板项。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ClipboardItem(Base):
    """剪贴板项。

    去重靠 `(user_id, content_hash)` 唯一约束：同一用户提交相同内容时
    命中的是同一条记录，只刷新 `updated_at`（见 AGENTS.md 的「数据契约」）。

    `content_hash` 不对外暴露，仅服务端用于去重。
    """

    __tablename__ = "clipboard_items"
    __table_args__ = (
        UniqueConstraint("user_id", "content_hash"),
        # 列表查询按用户 + 时间倒序，建复合索引
        Index("ix_clipboard_items_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=_uuid
    )
    # index=True 让「按用户筛选」走索引
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_type: Mapped[str] = mapped_column(String(16), default="text", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    preview: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 属性名用 meta：`metadata` 是 SQLAlchemy Declarative 的保留名
    meta: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="items")

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<ClipboardItem {self.title!r} ({self.id})>"
