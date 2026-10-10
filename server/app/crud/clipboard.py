"""剪贴板数据访问层（异步）。

路由层只调用本模块，不直接写 SQL（见 AGENTS.md 的「开发规范」）。
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.clipboard import ClipboardItem
from app.schemas.clipboard import ClipboardItemCreate, ClipboardItemUpdate
from app.schemas.common import ContentType, SortBy, SortOrder, utc_now

PREVIEW_LIMIT = 80


def content_hash(content: str) -> str:
    """内容去重用的哈希。**不对外暴露**（见 AGENTS.md 的「数据契约」）。"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def make_preview(content: str, limit: int = PREVIEW_LIMIT) -> str:
    """生成预览文本：压缩空白字符后按长度截断。"""
    collapsed = " ".join(content.split())
    return collapsed if len(collapsed) <= limit else f"{collapsed[:limit]}..."


def resolve_timezone(name: str | None) -> ZoneInfo:
    """把 IANA 时区名解析为 ZoneInfo；非法或缺失时回退到配置的默认时区。

    注意：数据库统一存 UTC，时区**只影响自动标题里展示的时间**。
    """
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # noqa: PLC0415
    from zoneinfo import available_timezones

    candidate = (name or "").strip()
    if candidate and candidate in available_timezones():
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError, KeyError):
            pass
    return ZoneInfo(settings.DEFAULT_TIMEZONE)


def generate_default_title(
    username: str,
    moment: datetime,
    tz: ZoneInfo | None = None,
) -> str:
    """用户未填标题时的自动标题，按指定时区展示：`demo · 10-05 21:56`。

    `moment` 是带时区的 UTC 时间；未指定 `tz` 时使用 `DEFAULT_TIMEZONE`。
    """
    zone = tz or resolve_timezone(None)
    return f"{username} · {moment.astimezone(zone).strftime('%m-%d %H:%M')}"


async def list_items(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    page: int = 1,
    size: int = 20,
    content_type: ContentType | None = None,
    search: str | None = None,
    sort_by: SortBy = SortBy.CREATED_AT,
    order: SortOrder = SortOrder.DESC,
) -> tuple[list[ClipboardItem], int]:
    """分页查询，返回 (当前页数据, 总条数)。

    搜索同时匹配 `title` 与 `content`（见 AGENTS.md 的「数据契约」）。
    """
    conditions = [ClipboardItem.user_id == user_id]
    if content_type is not None:
        conditions.append(ClipboardItem.content_type == content_type.value)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(ClipboardItem.title.ilike(pattern), ClipboardItem.content.ilike(pattern))
        )

    total = await session.scalar(
        select(func.count()).select_from(ClipboardItem).where(*conditions)
    )

    sort_column = (
        ClipboardItem.updated_at
        if sort_by is SortBy.UPDATED_AT
        else ClipboardItem.created_at
    )
    ordered = sort_column.desc() if order is SortOrder.DESC else sort_column.asc()

    rows = await session.scalars(
        select(ClipboardItem)
        .where(*conditions)
        .order_by(ordered)
        .offset((page - 1) * size)
        .limit(size)
    )
    return list(rows), int(total or 0)


async def get_item(
    session: AsyncSession, user_id: uuid.UUID, item_id: str | uuid.UUID
) -> ClipboardItem | None:
    """按 ID 查询单条；不存在或不属于该用户时返回 None。"""
    try:
        key = item_id if isinstance(item_id, uuid.UUID) else uuid.UUID(str(item_id))
    except (ValueError, AttributeError, TypeError):
        return None
    item = await session.get(ClipboardItem, key)
    if item is None or item.user_id != user_id:
        return None
    return item


async def get_by_content_hash(
    session: AsyncSession, user_id: uuid.UUID, digest: str
) -> ClipboardItem | None:
    """按内容哈希查询（去重用）。"""
    result = await session.execute(
        select(ClipboardItem).where(
            ClipboardItem.user_id == user_id,
            ClipboardItem.content_hash == digest,
        )
    )
    return result.scalar_one_or_none()


async def create_item(
    session: AsyncSession,
    user_id: uuid.UUID,
    payload: ClipboardItemCreate,
    *,
    username: str = "demo",
) -> tuple[ClipboardItem, bool]:
    """创建剪贴板项。

    `username` 用于在用户未填标题时生成自动标题。

    返回 (item, created)：
    - `created=True`：新建记录 → 第 5 步广播 `clipboard.created`
    - `created=False`：命中内容去重，仅刷新时间戳 → 第 6 步广播 `clipboard.updated`
    """
    digest = content_hash(payload.content)
    existing = await get_by_content_hash(session, user_id, digest)

    if existing is not None:
        existing.updated_at = utc_now()
        # 去重时仅当用户显式填写了标题才覆盖
        if payload.title:
            existing.title = payload.title
        if payload.preview is not None:
            existing.preview = payload.preview
        if payload.metadata is not None:
            existing.meta = payload.metadata
        await session.commit()
        await session.refresh(existing)
        return existing, False

    now = utc_now()
    item = ClipboardItem(
        id=uuid.uuid4(),
        user_id=user_id,
        title=(payload.title or "").strip()
        or generate_default_title(username, now, resolve_timezone(payload.timezone)),
        content_type=payload.content_type.value,
        content=payload.content,
        preview=payload.preview or make_preview(payload.content),
        meta=payload.metadata
        or {"mime": "text/plain", "size": len(payload.content.encode("utf-8"))},
        content_hash=digest,
        created_at=now,
        updated_at=now,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item, True


async def update_item(
    session: AsyncSession,
    user_id: uuid.UUID,
    item_id: str | uuid.UUID,
    payload: ClipboardItemUpdate,
    *,
    username: str = "demo",
) -> ClipboardItem | None:
    """更新已有剪贴板项（只更新显式传入的字段）。

    用途：**自动保存时复用同一条草稿记录**，避免打字过程中的每个中间态都新建一行。

    返回更新后的对象；不存在或不属于该用户时返回 None。
    """
    item = await get_item(session, user_id, item_id)
    if item is None:
        return None

    now = utc_now()

    if payload.content is not None and payload.content != item.content:
        item.content = payload.content
        item.content_hash = content_hash(payload.content)
        item.preview = payload.preview or make_preview(payload.content)
        # 内容变了但用户没给标题 → 标题跟随内容重新生成（时间取更新时刻）
        if not (payload.title or "").strip():
            item.title = generate_default_title(
                username, now, resolve_timezone(payload.timezone)
            )

    if (payload.title or "").strip():
        item.title = payload.title.strip()  # type: ignore[assignment]
    if payload.preview is not None:
        item.preview = payload.preview
    if payload.metadata is not None:
        item.meta = payload.metadata

    item.updated_at = now
    await session.commit()
    await session.refresh(item)
    return item


async def delete_item(
    session: AsyncSession, user_id: uuid.UUID, item_id: str | uuid.UUID
) -> bool:
    """删除单条；不存在或不属于该用户时返回 False。"""
    item = await get_item(session, user_id, item_id)
    if item is None:
        return False
    await session.delete(item)
    await session.commit()
    return True


async def clear_items(session: AsyncSession, user_id: uuid.UUID) -> int:
    """清空该用户全部剪贴板项，返回删除条数。"""
    result = await session.execute(
        delete(ClipboardItem).where(ClipboardItem.user_id == user_id)
    )
    await session.commit()
    return int(result.rowcount or 0)


async def count_items(session: AsyncSession, user_id: uuid.UUID | None = None) -> int:
    """统计条数。"""
    statement = select(func.count()).select_from(ClipboardItem)
    if user_id is not None:
        statement = statement.where(ClipboardItem.user_id == user_id)
    return int(await session.scalar(statement) or 0)
