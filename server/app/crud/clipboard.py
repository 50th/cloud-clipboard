"""剪贴板数据访问层（当前为内存假数据）。

路线层只调用本模块，不直接操作存储 —— 第 3 步换成数据库实现时路由无需改动。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

from app.crud.store import make_preview, seed_demo_items
from app.schemas.clipboard import (
    TITLE_MAX_LENGTH,
    ClipboardItemCreate,
    ClipboardItemResponse,
)
from app.schemas.common import ContentType, SortBy, SortOrder, utc_now

# 进程内存存储：{item_id: item}
_STORE: Final[dict[str, ClipboardItemResponse]] = seed_demo_items()

# 去重索引：{user_id: {content_hash: item_id}}
_INDEX: Final[dict[str, dict[str, str]]] = {}


def _content_hash(content: str) -> str:
    """内容去重用的哈希。**不对外暴露**（AGENT.md 第 4 节）。"""
    import hashlib

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def generate_default_title(username: str, moment: datetime) -> str:
    """用户未填标题时的自动标题：`demo · 10-02 14:30`。"""
    return f"{username} · {moment.strftime('%m-%d %H:%M')}"


def to_response(item: ClipboardItemResponse) -> ClipboardItemResponse:
    """把存储对象转换为对外响应模型。"""
    return item.model_copy()


def list_items(
    user_id: str,
    *,
    page: int = 1,
    size: int = 20,
    content_type: ContentType | None = None,
    search: str | None = None,
    sort_by: SortBy = SortBy.CREATED_AT,
    order: SortOrder = SortOrder.DESC,
) -> tuple[list[ClipboardItemResponse], int]:
    """分页查询剪贴板项，返回 (当前页数据, 总条数)。"""
    rows = [item for item in _STORE.values() if item.user_id == user_id]

    if content_type is not None:
        rows = [item for item in rows if item.content_type == content_type]

    # 搜索同时匹配标题与正文
    if search:
        keyword = search.strip().lower()
        rows = [
            item
            for item in rows
            if keyword in item.title.lower() or keyword in item.content.lower()
        ]

    field = sort_by.value
    rows.sort(key=lambda item: getattr(item, field), reverse=order is SortOrder.DESC)

    total = len(rows)
    start = (page - 1) * size
    return rows[start : start + size], total


def get_item(user_id: str, item_id: str) -> ClipboardItemResponse | None:
    """按 ID 查询单条；不存在或不属于该用户时返回 None。"""
    item = _STORE.get(item_id)
    if item is None or item.user_id != user_id:
        return None
    return item


def create_item(
    user_id: str,
    payload: ClipboardItemCreate,
    *,
    username: str = "demo",
) -> tuple[ClipboardItemResponse, bool]:
    """创建剪贴板项。

    `username` 用于在用户未填标题时生成自动标题。

    返回 (item, created)：
    - `created=True`：新建记录 → 第 5 步应广播 `clipboard.created`
    - `created=False`：命中内容去重，仅更新时间戳 → 第 6 步应广播 `clipboard.updated`
    """
    digest = _content_hash(payload.content)
    user_index = _INDEX.setdefault(user_id, {})

    if digest in user_index:
        item = _STORE[user_index[digest]]
        item.updated_at = utc_now()
        # 去重时仅当用户显式填写了标题才覆盖
        if payload.title:
            item.title = payload.title
        if payload.preview is not None:
            item.preview = payload.preview
        if payload.metadata is not None:
            item.metadata = payload.metadata
        return item, False

    now = utc_now()
    item_id = _new_id()
    item = ClipboardItemResponse(
        id=item_id,
        user_id=user_id,
        title=(payload.title or "").strip() or generate_default_title(username, now),
        content_type=payload.content_type,
        content=payload.content,
        preview=payload.preview or make_preview(payload.content),
        metadata=payload.metadata
        or {"mime": "text/plain", "size": len(payload.content.encode("utf-8"))},
        created_at=now,
        updated_at=now,
    )
    _STORE[item_id] = item
    user_index[digest] = item_id
    return item, True


def delete_item(user_id: str, item_id: str) -> bool:
    """删除单条；不存在时返回 False。"""
    item = get_item(user_id, item_id)
    if item is None:
        return False
    del _STORE[item_id]
    user_index = _INDEX.get(user_id, {})
    user_index.pop(_content_hash(item.content), None)
    return True


def clear_items(user_id: str) -> int:
    """清空该用户全部剪贴板项，返回删除条数。"""
    ids = [item.id for item in _STORE.values() if item.user_id == user_id]
    for item_id in ids:
        del _STORE[item_id]
    _INDEX.pop(user_id, None)
    return len(ids)


def count_items(user_id: str | None = None) -> int:
    """统计条数（调试/测试用）。"""
    if user_id is None:
        return len(_STORE)
    return sum(1 for item in _STORE.values() if item.user_id == user_id)


def reset_store() -> None:
    """重置为初始种子数据（测试用）。"""
    _STORE.clear()
    _STORE.update(seed_demo_items())
    _INDEX.clear()


def _new_id() -> str:
    """生成 UUID4 字符串。"""
    import uuid

    return str(uuid.uuid4())


def raw_store() -> dict[str, Any]:
    """只读调试视图。"""
    return {"items": len(_STORE), "indexed_users": len(_INDEX), "title_max": TITLE_MAX_LENGTH}
