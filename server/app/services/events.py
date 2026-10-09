"""对外事件的序列化与广播载荷。

**唯一目的**：让 REST 响应与 WebSocket 推送共用同一份 `ClipboardItem` 序列化，
避免两处各写一份导致字段漂移（字段清单的权威定义见 `app/schemas/clipboard.py`）。

协议细节（事件名、载荷形状）见 `docs/ws-protocol.md`。
"""

from __future__ import annotations

import uuid
from typing import Any

from app.db.models.clipboard import ClipboardItem
from app.schemas.clipboard import ClipboardItemResponse

# 事件名。改动即协议变更，必须同步 docs/ws-protocol.md、Web 端与鸿蒙端。
EVENT_CREATED = "clipboard.created"
EVENT_UPDATED = "clipboard.updated"
EVENT_DELETED = "clipboard.deleted"
EVENT_CLEARED = "clipboard.cleared"
EVENT_PONG = "pong"


def item_payload(item: ClipboardItem) -> dict[str, Any]:
    """把 ORM 对象转成可推送的 JSON 字典。`content_hash` 不外露。"""
    return to_item_response(item).model_dump(mode="json")


def to_item_response(item: ClipboardItem) -> ClipboardItemResponse:
    """把 ORM 对象转换为对外响应模型。

    REST 路由与 WebSocket 推送都走这里，保证两边字段完全一致。
    """
    return ClipboardItemResponse(
        id=str(item.id),
        user_id=str(item.user_id),
        title=item.title,
        content_type=item.content_type,
        content=item.content,
        preview=item.preview,
        metadata=item.meta,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def deleted_payload(item_id: str | uuid.UUID) -> dict[str, Any]:
    """删除事件的载荷：只有 id。"""
    return {"id": str(item_id)}
