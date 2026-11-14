"""管理员操作审计。

两类写入方式：

- `build_audit_entry`：只构造并 `session.add`，由**高危操作**与业务修改在同一个
  `session.commit()` 中提交；审计失败会让整个操作回滚。
- `record_admin_action`：用于低危操作（如管理员登录），自行 commit；
  失败只记异常，不阻断业务，应用日志仍是兜底。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.admin_audit_log import AdminAuditLog
from app.db.models.user import User

logger = logging.getLogger(__name__)

ACTION_ADMIN_LOGIN = "admin.login"
ACTION_USER_UPDATE = "user.update"
ACTION_USER_ENABLE = "user.enable"
ACTION_USER_DISABLE = "user.disable"
ACTION_USER_PROMOTE = "user.promote"
ACTION_USER_DEMOTE = "user.demote"
ACTION_USER_RESET_PASSWORD = "user.reset_password"
ACTION_USER_DELETE = "user.delete"
ACTION_USER_CLIPBOARDS_CLEAR = "user.clipboards.clear"
ACTION_CLIPBOARD_DELETE = "clipboard.delete"
ACTION_INVITE_CREATE = "invite.create"
ACTION_INVITE_REVOKE = "invite.revoke"
ACTION_SHARE_QUOTA_UPDATE = "settings.share_quota.update"
ACTION_USER_SHARE_LIMIT_UPDATE = "user.share_limit.update"


def build_audit_entry(
    session: AsyncSession,
    admin: User,
    action: str,
    *,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    detail: dict[str, Any] | None = None,
) -> AdminAuditLog:
    """构造一条审计记录并加入当前事务，**不 commit**。

    调用方必须在同一事务里提交业务修改与审计，保证两者原子性。
    """
    entry = AdminAuditLog(
        admin_id=admin.id,
        admin_username=admin.username,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )
    session.add(entry)
    return entry


async def record_admin_action(
    session: AsyncSession,
    admin: User,
    action: str,
    *,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """低危操作审计：自行 commit；失败只记异常，不影响调用方。"""
    try:
        build_audit_entry(
            session,
            admin,
            action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
        await session.commit()
    except Exception:  # noqa: BLE001 - 审计失败不能反向破坏低危操作
        await session.rollback()
        logger.exception(
            "审计写入失败: action=%s admin=%s target=%s",
            action,
            admin.username,
            target_id,
        )
