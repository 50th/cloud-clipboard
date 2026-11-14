"""分享数据访问层（异步）。

路由层只调用本模块，不直接写 SQL（见 AGENTS.md 的「开发规范」）。
哈希/校验、密码、状态判定等纯逻辑也集中在这里，便于单测。
"""

from __future__ import annotations

import ipaddress
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.crud import share_setting as share_setting_crud
from app.db.models.clipboard import ClipboardItem
from app.db.models.share import ClipboardShare
from app.db.models.share_access_log import ShareAccessLog
from app.db.models.user import User
from app.schemas.share import (
    SHARE_PER_ITEM_LIMIT,
    ClipboardShareCreate,
    ShareAccessResult,
    ShareExpiresIn,
    ShareMode,
    ShareStatus,
)
from app.schemas.common import utc_now

logger = logging.getLogger(__name__)

# 有效期 → timedelta
EXPIRES_DELTAS: dict[ShareExpiresIn, timedelta] = {
    ShareExpiresIn.HOUR_1: timedelta(hours=1),
    ShareExpiresIn.DAY_1: timedelta(days=1),
    ShareExpiresIn.DAY_7: timedelta(days=7),
    ShareExpiresIn.DAY_30: timedelta(days=30),
}

USER_AGENT_MAX_LENGTH = 512
OWNER_UA_PREVIEW_LENGTH = 200


class ShareLimitExceeded(RuntimeError):
    """该用户的有效分享数已达上限。"""

    def __init__(self, limit: int) -> None:
        super().__init__(limit)
        self.limit = limit


class ItemShareLimitExceeded(RuntimeError):
    """同一条剪贴板的有效分享数已达上限。"""

    def __init__(self, limit: int) -> None:
        super().__init__(limit)
        self.limit = limit


@dataclass
class AdminShareRow:
    """全局分享列表：分享 + 分享者用户名。"""

    share: ClipboardShare
    owner_username: str


@dataclass
class AdminShareAccessLogRow:
    """管理端访问记录：日志 + 分享标题 + 分享者。"""

    log: ShareAccessLog
    share_title: str
    owner_id: uuid.UUID
    owner_username: str


def build_share_url(token: str) -> str:
    """拼接公开链接；**不使用请求的 Host 头**，避免 Host 头注入。"""
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/s/{token}"


def _ensure_utc(value: datetime) -> datetime:
    """ISO 8601 未带时区时按 UTC 处理，避免与 timestamptz 比较时出错。"""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def share_status(share: ClipboardShare, now: datetime | None = None) -> ShareStatus:
    """分享状态判定：撤销 → 过期 → 次数用尽 → 有效（顺序不可调换）。"""
    moment = now or utc_now()
    if share.revoked_at is not None:
        return ShareStatus.REVOKED
    if share.expires_at is not None and _ensure_utc(share.expires_at) <= moment:
        return ShareStatus.EXPIRED
    if share.max_views is not None and share.view_count >= share.max_views:
        return ShareStatus.EXHAUSTED
    return ShareStatus.ACTIVE


def remaining_views(share: ClipboardShare) -> int | None:
    """剩余查看次数；`max_views` 为空时返回 None（不限）。"""
    if share.max_views is None:
        return None
    return max(0, share.max_views - share.view_count)


def _status_conditions(status: ShareStatus, now: datetime) -> list[Any]:
    """把状态翻译成 SQL 条件，筛选顺序与 `share_status` 保持一致。"""
    not_revoked = ClipboardShare.revoked_at.is_(None)
    not_expired = or_(
        ClipboardShare.expires_at.is_(None), ClipboardShare.expires_at > now
    )

    if status is ShareStatus.REVOKED:
        return [ClipboardShare.revoked_at.is_not(None)]
    if status is ShareStatus.EXPIRED:
        return [
            not_revoked,
            ClipboardShare.expires_at.is_not(None),
            ClipboardShare.expires_at <= now,
        ]
    if status is ShareStatus.EXHAUSTED:
        return [
            not_revoked,
            not_expired,
            ClipboardShare.max_views.is_not(None),
            ClipboardShare.view_count >= ClipboardShare.max_views,
        ]
    return [
        not_revoked,
        not_expired,
        or_(
            ClipboardShare.max_views.is_(None),
            ClipboardShare.view_count < ClipboardShare.max_views,
        ),
    ]


async def count_active_shares(session: AsyncSession, user_id: uuid.UUID) -> int:
    """统计该用户当前有效的分享数（口径同 5.1）。"""
    total = await session.scalar(
        select(func.count())
        .select_from(ClipboardShare)
        .where(
            ClipboardShare.user_id == user_id,
            *_status_conditions(ShareStatus.ACTIVE, utc_now()),
        )
    )
    return int(total or 0)


async def count_shares(session: AsyncSession, *, active_only: bool = False) -> int:
    """全站分享计数；`active_only=True` 时只统计当前有效分享。"""
    statement = select(func.count()).select_from(ClipboardShare)
    if active_only:
        statement = statement.where(
            *_status_conditions(ShareStatus.ACTIVE, utc_now())
        )
    return int(await session.scalar(statement) or 0)


async def count_active_shares_for_item(
    session: AsyncSession, user_id: uuid.UUID, item_id: uuid.UUID
) -> int:
    """统计某条剪贴板当前有效的分享数（单条限额用）。"""
    total = await session.scalar(
        select(func.count())
        .select_from(ClipboardShare)
        .where(
            ClipboardShare.user_id == user_id,
            ClipboardShare.item_id == item_id,
            *_status_conditions(ShareStatus.ACTIVE, utc_now()),
        )
    )
    return int(total or 0)


async def create_share(
    session: AsyncSession,
    user_id: uuid.UUID,
    item: ClipboardItem,
    payload: ClipboardShareCreate,
) -> ClipboardShare:
    """创建分享。

    在同一事务内锁定用户行、读取限额并统计有效分享数；
    达到上限抛 `ShareLimitExceeded`，由路由转成 409。
    """
    # 锁定用户行：并发创建时串行化配额检查，避免同时越过上限。
    # 同时读取该用户的单独限额（NULL = 跟随全局）。
    locked = await session.execute(
        select(User.share_limit).where(User.id == user_id).with_for_update()
    )
    locked_row = locked.first()
    override_limit = locked_row[0] if locked_row is not None else None
    limit = (
        override_limit
        if override_limit is not None
        else await share_setting_crud.get_share_settings(session)
    )
    if await count_active_shares(session, user_id) >= limit:
        raise ShareLimitExceeded(limit)

    # 单条记录也设上限：避免同一条内容反复创建链接，挤占全局额度。
    if (
        await count_active_shares_for_item(session, user_id, item.id)
        >= SHARE_PER_ITEM_LIMIT
    ):
        raise ItemShareLimitExceeded(SHARE_PER_ITEM_LIMIT)

    now = utc_now()
    snapshot = payload.mode is ShareMode.SNAPSHOT
    share = ClipboardShare(
        id=uuid.uuid4(),
        user_id=user_id,
        item_id=item.id,
        mode=payload.mode.value,
        token=secrets.token_urlsafe(32),
        title=item.title,
        content=item.content if snapshot else None,
        content_type=item.content_type,
        password_hash=hash_password(payload.password) if payload.password else None,
        expires_at=now + EXPIRES_DELTAS[payload.expires_in],
        max_views=payload.max_views,
        view_count=0,
        created_at=now,
    )
    session.add(share)
    await session.commit()
    await session.refresh(share)
    return share


async def list_shares(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    page: int,
    size: int,
    status: ShareStatus | None,
    item_id: uuid.UUID | None,
    search: str | None = None,
) -> tuple[list[ClipboardShare], int]:
    """分页查询我的分享，按创建时间倒序。

    搜索同时匹配分享标题与正文：快照读分享行副本，跟随模式回退到原记录正文。
    """
    conditions: list[Any] = [ClipboardShare.user_id == user_id]
    if item_id is not None:
        conditions.append(ClipboardShare.item_id == item_id)
    if status is not None:
        conditions.extend(_status_conditions(status, utc_now()))
    if search and search.strip():
        pattern = _like_pattern(search.strip())
        conditions.append(
            or_(
                ClipboardShare.title.ilike(pattern, escape="\\"),
                func.coalesce(
                    ClipboardShare.content, ClipboardItem.content
                ).ilike(pattern, escape="\\"),
            )
        )

    # item 与 share 是一对一（item_id 外键），join 不影响计数；
    # 跟随模式的 content 为 NULL，靠 ClipboardItem.content 兜底。
    join_item = ClipboardShare.item_id == ClipboardItem.id
    total = await session.scalar(
        select(func.count())
        .select_from(ClipboardShare)
        .join(ClipboardItem, join_item)
        .where(*conditions)
    )
    rows = await session.scalars(
        select(ClipboardShare)
        .join(ClipboardItem, join_item)
        .where(*conditions)
        .order_by(ClipboardShare.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return list(rows), int(total or 0)


async def get_share(
    session: AsyncSession, user_id: uuid.UUID, share_id: uuid.UUID
) -> ClipboardShare | None:
    """按 ID 取本人分享；不存在或不属于本人返回 None。"""
    share = await session.get(ClipboardShare, share_id)
    if share is None or share.user_id != user_id:
        return None
    return share


async def get_by_token(session: AsyncSession, token: str) -> ClipboardShare | None:
    """公开访问：按 token 取分享。"""
    return await session.scalar(
        select(ClipboardShare).where(ClipboardShare.token == token)
    )


async def revoke_share(
    session: AsyncSession, user_id: uuid.UUID, share_id: uuid.UUID
) -> bool:
    """撤销分享；已撤销再撤销视为成功（幂等）。"""
    share = await get_share(session, user_id, share_id)
    if share is None:
        return False
    if share.revoked_at is not None:
        return True
    share.revoked_at = utc_now()
    await session.commit()
    return True


def normalize_ip(value: str | None) -> str | None:
    """校验 IP 字面量；非法或缺失时返回 None（入库为 NULL）。"""
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def truncate_user_agent(value: str | None, limit: int = USER_AGENT_MAX_LENGTH) -> str | None:
    """User-Agent 截断；空值返回 None。"""
    if not value:
        return None
    return value[:limit]


def mask_ip(value: object | None) -> str | None:
    """所有者的脱敏 IP：IPv4 最后一段、IPv6 后 64 位替换为 `*`。

    `INET` 列读出来可能是 `ipaddress.IPv4Address`，统一先转成文本。
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv4Address):
        parts = text.split(".")
        return ".".join(parts[:3] + ["*"])
    groups = address.exploded.split(":")
    return ":".join(groups[:4] + ["*"])


async def resolve_content(
    session: AsyncSession, share: ClipboardShare
) -> tuple[str, str, str] | None:
    """取正文：快照读分享行副本，跟随读取原记录最新内容。"""
    if share.mode == ShareMode.LIVE.value:
        item = await session.get(ClipboardItem, share.item_id)
        if item is None:
            return None
        return item.title, item.content, item.content_type
    if share.content is None:
        return None
    return share.title, share.content, share.content_type


async def consume_view(
    session: AsyncSession,
    share: ClipboardShare,
    *,
    ip: str | None,
    user_agent: str | None,
) -> tuple[int, int | None] | None:
    """原子递增查看次数，并在同一事务写入成功访问记录。

    条件不满足（已撤销 / 过期 / 次数用尽）返回 None，由路由转成 410。
    """
    now = utc_now()
    result = await session.execute(
        update(ClipboardShare)
        .where(
            ClipboardShare.id == share.id,
            ClipboardShare.revoked_at.is_(None),
            or_(ClipboardShare.expires_at.is_(None), ClipboardShare.expires_at > now),
            or_(
                ClipboardShare.max_views.is_(None),
                ClipboardShare.view_count < ClipboardShare.max_views,
            ),
        )
        .values(view_count=ClipboardShare.view_count + 1, last_viewed_at=now)
        .returning(ClipboardShare.view_count, ClipboardShare.max_views)
    )
    row = result.first()
    if row is None:
        # 条件更新未命中：并发下已被撤销 / 过期 / 用尽。不提交也不回滚，
        # 由路由按当前状态写入失败记录（回滚会让调用方对象过期并触发懒加载）。
        return None

    session.add(
        ShareAccessLog(
            share_id=share.id,
            accessed_at=now,
            result=ShareAccessResult.SUCCESS.value,
            ip=ip,
            user_agent=truncate_user_agent(user_agent),
        )
    )
    await session.commit()
    return int(row[0]), row[1]


async def record_access_log(
    session: AsyncSession,
    share: ClipboardShare,
    *,
    result: ShareAccessResult,
    ip: str | None,
    user_agent: str | None,
) -> None:
    """失败尝试记录：独立事务提交，失败只写应用日志，不影响原响应。"""
    try:
        session.add(
            ShareAccessLog(
                share_id=share.id,
                accessed_at=utc_now(),
                result=result.value,
                ip=ip,
                user_agent=truncate_user_agent(user_agent),
            )
        )
        await session.commit()
    except Exception:  # noqa: BLE001 - 记录失败不能改变 403 / 410 响应
        await session.rollback()
        logger.exception("分享访问记录写入失败: share=%s result=%s", share.id, result.value)


async def list_access_logs(
    session: AsyncSession,
    share_id: uuid.UUID,
    *,
    page: int,
    size: int,
    include_failures: bool = False,
) -> tuple[list[ShareAccessLog], int]:
    """按分享查询访问记录，`accessed_at DESC`；默认只看成功记录。"""
    conditions: list[Any] = [ShareAccessLog.share_id == share_id]
    if not include_failures:
        conditions.append(ShareAccessLog.result == ShareAccessResult.SUCCESS.value)

    total = await session.scalar(
        select(func.count()).select_from(ShareAccessLog).where(*conditions)
    )
    rows = await session.scalars(
        select(ShareAccessLog)
        .where(*conditions)
        .order_by(ShareAccessLog.accessed_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return list(rows), int(total or 0)


def _like_pattern(value: str) -> str:
    """转义 LIKE 通配符，避免用户输入的 `%` / `_` 变成意外模式。"""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def list_all_shares(
    session: AsyncSession,
    *,
    page: int,
    size: int,
    status: ShareStatus | None,
    username: str | None,
) -> tuple[list[AdminShareRow], int]:
    """管理员：跨用户分页查询分享，按创建时间倒序。"""
    conditions: list[Any] = []
    if status is not None:
        conditions.extend(_status_conditions(status, utc_now()))
    if username and username.strip():
        conditions.append(
            User.username.ilike(_like_pattern(username.strip()), escape="\\")
        )

    join_user = ClipboardShare.user_id == User.id
    total = await session.scalar(
        select(func.count())
        .select_from(ClipboardShare)
        .join(User, join_user)
        .where(*conditions)
    )
    rows = await session.execute(
        select(ClipboardShare, User.username)
        .join(User, join_user)
        .where(*conditions)
        .order_by(ClipboardShare.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return (
        [
            AdminShareRow(share=row[0], owner_username=row[1])
            for row in rows.all()
        ],
        int(total or 0),
    )


async def list_all_access_logs(
    session: AsyncSession,
    *,
    page: int,
    size: int,
    result: str,
    share_id: uuid.UUID | None,
    username: str | None,
    start: datetime | None,
    end: datetime | None,
) -> tuple[list[AdminShareAccessLogRow], int]:
    """管理员：跨分享查询成功与失败记录。"""
    conditions: list[Any] = []
    if result == "success":
        conditions.append(ShareAccessLog.result == ShareAccessResult.SUCCESS.value)
    elif result == "failure":
        conditions.append(ShareAccessLog.result != ShareAccessResult.SUCCESS.value)
    if share_id is not None:
        conditions.append(ShareAccessLog.share_id == share_id)
    if username and username.strip():
        conditions.append(
            User.username.ilike(_like_pattern(username.strip()), escape="\\")
        )
    if start is not None:
        conditions.append(ShareAccessLog.accessed_at >= _ensure_utc(start))
    if end is not None:
        conditions.append(ShareAccessLog.accessed_at < _ensure_utc(end))

    base = (
        select(
            ShareAccessLog,
            ClipboardShare.title,
            ClipboardShare.user_id,
            User.username,
        )
        .join(ClipboardShare, ShareAccessLog.share_id == ClipboardShare.id)
        .join(User, ClipboardShare.user_id == User.id)
        .where(*conditions)
    )
    total = await session.scalar(
        select(func.count())
        .select_from(ShareAccessLog)
        .join(ClipboardShare, ShareAccessLog.share_id == ClipboardShare.id)
        .join(User, ClipboardShare.user_id == User.id)
        .where(*conditions)
    )
    rows = await session.execute(
        base.order_by(ShareAccessLog.accessed_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return (
        [
            AdminShareAccessLogRow(
                log=row[0],
                share_title=row[1],
                owner_id=row[2],
                owner_username=row[3],
            )
            for row in rows.all()
        ],
        int(total or 0),
    )
