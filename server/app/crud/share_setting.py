"""分享全局设置的数据访问层。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import audit as audit_crud
from app.db.models.share_setting import DEFAULT_USER_SHARE_LIMIT, ShareSetting
from app.db.models.user import User
from app.schemas.common import utc_now


@dataclass
class ShareSettingsState:
    """分享限额 + 最近更新信息（管理端展示用）。"""

    user_share_limit: int
    updated_at: datetime | None
    updated_by: uuid.UUID | None
    updated_by_username: str | None


async def get_share_settings(session: AsyncSession) -> int:
    """读取每用户有效分享上限；行缺失时回退默认 50。"""
    row = await session.get(ShareSetting, 1)
    return row.user_share_limit if row is not None else DEFAULT_USER_SHARE_LIMIT


async def get_share_settings_state(session: AsyncSession) -> ShareSettingsState:
    """读取限额与最近更新人；行缺失时返回默认值。"""
    row = await session.get(ShareSetting, 1)
    if row is None:
        return ShareSettingsState(
            user_share_limit=DEFAULT_USER_SHARE_LIMIT,
            updated_at=None,
            updated_by=None,
            updated_by_username=None,
        )
    username: str | None = None
    if row.updated_by is not None:
        user = await session.get(User, row.updated_by)
        username = user.username if user is not None else None
    return ShareSettingsState(
        user_share_limit=row.user_share_limit,
        updated_at=row.updated_at,
        updated_by=row.updated_by,
        updated_by_username=username,
    )


async def update_share_settings(
    session: AsyncSession,
    user_share_limit: int,
    admin: User,
) -> ShareSetting:
    """更新限额；更新与审计同事务提交，审计失败整体回滚。"""
    row = await session.get(ShareSetting, 1)
    old_limit = row.user_share_limit if row is not None else DEFAULT_USER_SHARE_LIMIT

    if row is None:
        row = ShareSetting(id=1, user_share_limit=user_share_limit)
        session.add(row)
    else:
        row.user_share_limit = user_share_limit
    row.updated_at = utc_now()
    row.updated_by = admin.id

    audit_crud.build_audit_entry(
        session,
        admin,
        audit_crud.ACTION_SHARE_QUOTA_UPDATE,
        target_type="settings",
        detail={"old": old_limit, "new": user_share_limit},
    )
    await session.commit()
    await session.refresh(row)
    return row
