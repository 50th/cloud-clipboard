"""后台管理数据访问层。

所有跨用户查询与高危写操作都在这里完成；路由层只做参数校验与响应组装。
高危写操作（删除用户、重置密码、角色/状态变更、清空剪贴板）把业务修改与审计
放进同一个事务，审计失败会整体回滚。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.crud import audit as audit_crud
from app.crud import invite as invite_crud
from app.db.models.admin_audit_log import AdminAuditLog
from app.db.models.clipboard import ClipboardItem
from app.db.models.invite_code import InviteCode
from app.db.models.user import User
from app.schemas.admin import (
    AdminClipboardSortBy,
    AdminInviteCodeStatus,
    AdminUserRole,
    AdminUserSortBy,
    AdminUserStatus,
    AdminUserUpdate,
)
from app.schemas.common import ContentType, SortOrder, utc_now


@dataclass
class UserWithStats:
    """用户 + 剪贴板统计。"""

    user: User
    item_count: int
    last_item_at: datetime | None


@dataclass
class ClipboardWithUsername:
    """剪贴板项 + 所属用户名。"""

    item: ClipboardItem
    username: str


class EmailConflictError(RuntimeError):
    """修改后的邮箱已被其他用户占用。"""


def _like_pattern(value: str) -> str:
    """转义 LIKE 通配符，避免用户输入的 `%` / `_` 变成意外模式。"""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _ordered(column: Any, order: SortOrder) -> Any:
    """统一排序方向；DESC 时把 NULL 放最后，避免未登录用户占满首页。"""
    return column.desc().nullslast() if order is SortOrder.DESC else column.asc()


def _item_count_subquery() -> Any:
    return (
        select(func.count(ClipboardItem.id))
        .where(ClipboardItem.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )


def _last_item_at_subquery() -> Any:
    return (
        select(func.max(ClipboardItem.updated_at))
        .where(ClipboardItem.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )


async def list_users(
    session: AsyncSession,
    *,
    page: int,
    size: int,
    search: str | None,
    status: AdminUserStatus,
    role: AdminUserRole,
    sort_by: AdminUserSortBy,
    order: SortOrder,
) -> tuple[list[UserWithStats], int]:
    """分页查询用户，附带剪贴板条数与最后更新时间。"""
    item_count = _item_count_subquery()
    last_item_at = _last_item_at_subquery()

    conditions: list[Any] = []
    if search and search.strip():
        pattern = _like_pattern(search.strip())
        conditions.append(
            or_(
                User.username.ilike(pattern, escape="\\"),
                User.email.ilike(pattern, escape="\\"),
            )
        )
    if status is AdminUserStatus.ACTIVE:
        conditions.append(User.is_active.is_(True))
    elif status is AdminUserStatus.DISABLED:
        conditions.append(User.is_active.is_(False))
    if role is AdminUserRole.ADMIN:
        conditions.append(User.is_admin.is_(True))
    elif role is AdminUserRole.USER:
        conditions.append(User.is_admin.is_(False))

    total = await session.scalar(
        select(func.count()).select_from(User).where(*conditions)
    )

    if sort_by is AdminUserSortBy.ITEM_COUNT:
        sort_column = item_count
    elif sort_by is AdminUserSortBy.LAST_LOGIN_AT:
        sort_column = User.last_login_at
    else:
        sort_column = User.created_at

    rows = await session.execute(
        select(User, item_count.label("item_count"), last_item_at.label("last_item_at"))
        .where(*conditions)
        .order_by(_ordered(sort_column, order))
        .offset((page - 1) * size)
        .limit(size)
    )
    return (
        [
            UserWithStats(
                user=row[0],
                item_count=int(row[1] or 0),
                last_item_at=row[2],
            )
            for row in rows.all()
        ],
        int(total or 0),
    )


async def get_user_with_stats(
    session: AsyncSession, user_id: uuid.UUID
) -> UserWithStats | None:
    """按 id 查询用户与统计。"""
    user = await session.get(User, user_id)
    if user is None:
        return None
    item_count = await session.scalar(
        select(func.count(ClipboardItem.id)).where(ClipboardItem.user_id == user.id)
    )
    last_item_at = await session.scalar(
        select(func.max(ClipboardItem.updated_at)).where(
            ClipboardItem.user_id == user.id
        )
    )
    return UserWithStats(
        user=user,
        item_count=int(item_count or 0),
        last_item_at=last_item_at,
    )


async def update_user(
    session: AsyncSession,
    admin: User,
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
) -> UserWithStats | None:
    """修改用户资料/状态/角色，并把审计与修改放在同一事务。"""
    user = await session.get(User, user_id)
    if user is None:
        return None

    changed_fields: list[str] = []

    if payload.email is not None and payload.email != user.email:
        conflict = await session.scalar(
            select(User.id).where(
                User.email == payload.email,
                User.id != user.id,
            )
        )
        if conflict is not None:
            raise EmailConflictError(f"邮箱已被占用: {payload.email}")
        user.email = payload.email
        changed_fields.append("email")

    if payload.nickname is not None and payload.nickname != user.nickname:
        user.nickname = payload.nickname
        changed_fields.append("nickname")

    if payload.is_active is not None and payload.is_active != user.is_active:
        user.is_active = payload.is_active
        action = (
            audit_crud.ACTION_USER_ENABLE
            if payload.is_active
            else audit_crud.ACTION_USER_DISABLE
        )
        if not payload.is_active:
            # 禁用同时使旧令牌失效；重新启用后旧令牌也不会复活
            user.token_version += 1
        audit_crud.build_audit_entry(
            session,
            admin,
            action,
            target_type="user",
            target_id=user.id,
        )

    if payload.is_admin is not None and payload.is_admin != user.is_admin:
        user.is_admin = payload.is_admin
        action = (
            audit_crud.ACTION_USER_PROMOTE
            if payload.is_admin
            else audit_crud.ACTION_USER_DEMOTE
        )
        audit_crud.build_audit_entry(
            session,
            admin,
            action,
            target_type="user",
            target_id=user.id,
        )

    if changed_fields:
        audit_crud.build_audit_entry(
            session,
            admin,
            audit_crud.ACTION_USER_UPDATE,
            target_type="user",
            target_id=user.id,
            detail={"fields": changed_fields},
        )

    await session.commit()
    return await get_user_with_stats(session, user_id)


async def reset_password(
    session: AsyncSession,
    admin: User,
    user_id: uuid.UUID,
    password: str,
) -> UserWithStats | None:
    """重置密码并使该用户全部旧令牌失效。"""
    user = await session.get(User, user_id)
    if user is None:
        return None
    user.password_hash = security.hash_password(password)
    user.token_version += 1
    audit_crud.build_audit_entry(
        session,
        admin,
        audit_crud.ACTION_USER_RESET_PASSWORD,
        target_type="user",
        target_id=user.id,
    )
    await session.commit()
    return await get_user_with_stats(session, user_id)


async def delete_user(
    session: AsyncSession,
    admin: User,
    user_id: uuid.UUID,
) -> int | None:
    """物理删除用户及其剪贴板，返回被删除的剪贴板条数。"""
    user = await session.get(User, user_id)
    if user is None:
        return None
    item_count = int(
        await session.scalar(
            select(func.count(ClipboardItem.id)).where(
                ClipboardItem.user_id == user.id
            )
        )
        or 0
    )
    audit_crud.build_audit_entry(
        session,
        admin,
        audit_crud.ACTION_USER_DELETE,
        target_type="user",
        target_id=user.id,
        detail={"deleted_items": item_count},
    )
    await session.delete(user)
    await session.commit()
    return item_count


async def clear_user_clipboards(
    session: AsyncSession,
    admin: User,
    user_id: uuid.UUID,
) -> int | None:
    """清空某用户全部剪贴板，返回删除条数。"""
    user = await session.get(User, user_id)
    if user is None:
        return None
    result = await session.execute(
        delete(ClipboardItem).where(ClipboardItem.user_id == user.id)
    )
    deleted = int(result.rowcount or 0)
    audit_crud.build_audit_entry(
        session,
        admin,
        audit_crud.ACTION_USER_CLIPBOARDS_CLEAR,
        target_type="user",
        target_id=user.id,
        detail={"deleted_items": deleted},
    )
    await session.commit()
    return deleted


async def list_clipboards(
    session: AsyncSession,
    *,
    page: int,
    size: int,
    user_id: uuid.UUID | None,
    username: str | None,
    search: str | None,
    content_type: ContentType | None,
    sort_by: AdminClipboardSortBy,
    order: SortOrder,
) -> tuple[list[ClipboardWithUsername], int]:
    """跨用户分页查询剪贴板。"""
    conditions: list[Any] = []
    if user_id is not None:
        conditions.append(ClipboardItem.user_id == user_id)
    if username and username.strip():
        conditions.append(
            User.username.ilike(_like_pattern(username.strip()), escape="\\")
        )
    if search and search.strip():
        pattern = _like_pattern(search.strip())
        conditions.append(
            or_(
                ClipboardItem.title.ilike(pattern, escape="\\"),
                ClipboardItem.content.ilike(pattern, escape="\\"),
            )
        )
    if content_type is not None:
        conditions.append(ClipboardItem.content_type == content_type.value)

    total = await session.scalar(
        select(func.count())
        .select_from(ClipboardItem)
        .join(User, ClipboardItem.user_id == User.id)
        .where(*conditions)
    )

    sort_column = (
        ClipboardItem.updated_at
        if sort_by is AdminClipboardSortBy.UPDATED_AT
        else ClipboardItem.created_at
    )
    rows = await session.execute(
        select(ClipboardItem, User.username)
        .join(User, ClipboardItem.user_id == User.id)
        .where(*conditions)
        .order_by(_ordered(sort_column, order))
        .offset((page - 1) * size)
        .limit(size)
    )
    return (
        [
            ClipboardWithUsername(item=row[0], username=row[1])
            for row in rows.all()
        ],
        int(total or 0),
    )


async def get_clipboard(
    session: AsyncSession, item_id: uuid.UUID
) -> ClipboardWithUsername | None:
    """按 id 查询任意用户的剪贴板项。"""
    row = (
        await session.execute(
            select(ClipboardItem, User.username)
            .join(User, ClipboardItem.user_id == User.id)
            .where(ClipboardItem.id == item_id)
        )
    ).first()
    if row is None:
        return None
    return ClipboardWithUsername(item=row[0], username=row[1])


async def delete_clipboard(
    session: AsyncSession,
    admin: User,
    item_id: uuid.UUID,
) -> uuid.UUID | None:
    """删除任意用户的单条剪贴板，返回所属用户 id。"""
    item = await session.get(ClipboardItem, item_id)
    if item is None:
        return None
    owner_id = item.user_id
    audit_crud.build_audit_entry(
        session,
        admin,
        audit_crud.ACTION_CLIPBOARD_DELETE,
        target_type="clipboard",
        target_id=item.id,
    )
    await session.delete(item)
    await session.commit()
    return owner_id


async def get_stats(session: AsyncSession) -> dict[str, Any]:
    """后台概览统计。"""
    seven_days_ago = utc_now() - timedelta(days=7)

    user_count = int(await session.scalar(select(func.count()).select_from(User)) or 0)
    active_user_count = int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.is_active.is_(True))
        )
        or 0
    )
    admin_count = int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.is_admin.is_(True))
        )
        or 0
    )
    item_count = int(
        await session.scalar(select(func.count()).select_from(ClipboardItem)) or 0
    )
    total_bytes = int(
        await session.scalar(
            select(
                func.coalesce(
                    func.sum(func.octet_length(ClipboardItem.content)), 0
                )
            )
        )
        or 0
    )
    new_users_7d = int(
        await session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.created_at >= seven_days_ago)
        )
        or 0
    )
    new_items_7d = int(
        await session.scalar(
            select(func.count())
            .select_from(ClipboardItem)
            .where(ClipboardItem.created_at >= seven_days_ago)
        )
        or 0
    )

    return {
        "user_count": user_count,
        "active_user_count": active_user_count,
        "admin_count": admin_count,
        "item_count": item_count,
        "total_bytes": total_bytes,
        "new_users_7d": new_users_7d,
        "new_items_7d": new_items_7d,
    }


async def list_audit_logs(
    session: AsyncSession,
    *,
    page: int,
    size: int,
    admin_username: str | None,
    action: str | None,
    target_id: uuid.UUID | None,
    start: datetime | None,
    end: datetime | None,
) -> tuple[list[AdminAuditLog], int]:
    """分页查询审计记录。"""
    conditions: list[Any] = []
    if admin_username and admin_username.strip():
        conditions.append(
            AdminAuditLog.admin_username.ilike(
                _like_pattern(admin_username.strip()), escape="\\"
            )
        )
    if action:
        conditions.append(AdminAuditLog.action == action)
    if target_id is not None:
        conditions.append(AdminAuditLog.target_id == target_id)
    if start is not None:
        conditions.append(
            AdminAuditLog.created_at >= _ensure_utc(start)
        )
    if end is not None:
        conditions.append(
            AdminAuditLog.created_at <= _ensure_utc(end)
        )

    total = await session.scalar(
        select(func.count()).select_from(AdminAuditLog).where(*conditions)
    )
    rows = await session.scalars(
        select(AdminAuditLog)
        .where(*conditions)
        .order_by(AdminAuditLog.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return list(rows), int(total or 0)


def _ensure_utc(value: datetime) -> datetime:
    """ISO 8601 未带时区时按 UTC 处理，避免与 timestamptz 比较时出错。"""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def invite_code_status(row: InviteCode, now: datetime | None = None) -> str:
    """邀请码展示状态；撤销优先于过期，过期优先于用尽。"""
    moment = now or utc_now()
    if row.revoked_at is not None:
        return "revoked"
    if row.expires_at is not None and _ensure_utc(row.expires_at) <= moment:
        return "expired"
    if row.max_uses is not None and row.used_count >= row.max_uses:
        return "exhausted"
    return "active"


def _invite_status_conditions(status: AdminInviteCodeStatus) -> list[Any]:
    """把状态筛选翻译为 SQL 条件，与 `invite_code_status` 保持一致。"""
    now = utc_now()
    not_revoked = InviteCode.revoked_at.is_(None)
    not_expired = or_(InviteCode.expires_at.is_(None), InviteCode.expires_at > now)

    if status is AdminInviteCodeStatus.REVOKED:
        return [InviteCode.revoked_at.is_not(None)]
    if status is AdminInviteCodeStatus.EXPIRED:
        return [
            not_revoked,
            InviteCode.expires_at.is_not(None),
            InviteCode.expires_at <= now,
        ]
    if status is AdminInviteCodeStatus.EXHAUSTED:
        return [
            not_revoked,
            not_expired,
            InviteCode.max_uses.is_not(None),
            InviteCode.used_count >= InviteCode.max_uses,
        ]
    if status is AdminInviteCodeStatus.ACTIVE:
        return [
            not_revoked,
            not_expired,
            or_(
                InviteCode.max_uses.is_(None),
                InviteCode.used_count < InviteCode.max_uses,
            ),
        ]
    return []


async def list_invite_codes(
    session: AsyncSession,
    *,
    page: int,
    size: int,
    status: AdminInviteCodeStatus,
) -> tuple[list[InviteCode], int]:
    """分页查询邀请码。"""
    conditions = _invite_status_conditions(status)
    total = await session.scalar(
        select(func.count()).select_from(InviteCode).where(*conditions)
    )
    rows = await session.scalars(
        select(InviteCode)
        .where(*conditions)
        .order_by(InviteCode.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return list(rows), int(total or 0)


async def create_invite_code(
    session: AsyncSession,
    admin: User,
    *,
    label: str | None,
    max_uses: int,
    expires_days: int,
) -> tuple[str, InviteCode]:
    """创建邀请码，返回 `(明文, 记录)`；明文不落库，审计与创建同事务。"""
    plaintext = invite_crud.generate_code()
    expires_at = (
        utc_now() + timedelta(days=expires_days) if expires_days > 0 else None
    )
    row = InviteCode(
        code_hash=invite_crud.hash_code(plaintext),
        code_hint=plaintext[:8],
        label=label,
        max_uses=max_uses,
        expires_at=expires_at,
    )
    session.add(row)
    # flush 后才能拿到默认生成的 id，供审计的 target_id 使用
    await session.flush()
    audit_crud.build_audit_entry(
        session,
        admin,
        audit_crud.ACTION_INVITE_CREATE,
        target_type="invite",
        target_id=row.id,
        detail={"max_uses": max_uses, "expires_days": expires_days},
    )
    await session.commit()
    await session.refresh(row)
    return plaintext, row


async def revoke_invite_code(
    session: AsyncSession,
    admin: User,
    code_id: uuid.UUID,
) -> InviteCode | None:
    """撤销邀请码；已撤销的直接返回原记录。"""
    row = await session.get(InviteCode, code_id)
    if row is None:
        return None
    if row.revoked_at is not None:
        return row
    row.revoked_at = utc_now()
    audit_crud.build_audit_entry(
        session,
        admin,
        audit_crud.ACTION_INVITE_REVOKE,
        target_type="invite",
        target_id=row.id,
    )
    await session.commit()
    await session.refresh(row)
    return row
