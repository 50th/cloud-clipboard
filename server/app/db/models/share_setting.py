"""ORM 模型：分享全局设置（单行表，id 固定为 1）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, SmallInteger, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

DEFAULT_USER_SHARE_LIMIT = 50


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ShareSetting(Base):
    """全局分享限额；行缺失时读取代码回退默认 50。"""

    __tablename__ = "share_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    user_share_limit: Mapped[int] = mapped_column(
        Integer, default=DEFAULT_USER_SHARE_LIMIT, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
