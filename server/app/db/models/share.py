"""ORM 模型：剪贴板分享。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ClipboardShare(Base):
    """单条剪贴板的受控只读分享。

    `content` 只在 `snapshot` 模式写入；`live` 模式为 NULL，
    公开访问时按 `item_id` 读取原记录最新内容。

    刻意不建 relationship：公开访问用显式查询取原记录，
    避免异步懒加载触发 `MissingGreenlet`。
    """

    __tablename__ = "clipboard_shares"
    __table_args__ = (
        UniqueConstraint("token"),
        Index("ix_clipboard_shares_user_created", "user_id", "created_at"),
        Index("ix_clipboard_shares_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("clipboard_items.id", ondelete="CASCADE"),
        index=True,
    )
    mode: Mapped[str] = mapped_column(
        String(16), default="snapshot", server_default="snapshot", nullable=False
    )
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(
        String(16), default="text", server_default="text", nullable=False
    )
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    max_views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    view_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    last_viewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<ClipboardShare {self.title!r} ({self.id})>"
