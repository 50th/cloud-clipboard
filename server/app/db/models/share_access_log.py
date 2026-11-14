"""ORM 模型：分享访问记录。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ShareAccessLog(Base):
    """一次成功的查看或失败尝试。

    **不记录** token、正文、密码、Referer；失败记录仅管理员可见。
    """

    __tablename__ = "clipboard_share_access_logs"
    __table_args__ = (
        Index("ix_share_access_logs_share_accessed", "share_id", "accessed_at"),
        Index("ix_share_access_logs_result_accessed", "result", "accessed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=_uuid
    )
    share_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("clipboard_shares.id", ondelete="CASCADE"),
        index=True,
    )
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    # 原始 IP 仅用于安全排查；用户端返回脱敏值，只有管理端返回原始值。
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<ShareAccessLog {self.result} share={self.share_id}>"
