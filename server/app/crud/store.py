"""内存假数据存储（仅第 1 步使用）。

第 3 步接入 PostgreSQL 后，本模块连同 `seed_demo_items()` 一并删除。
"""

from __future__ import annotations

from app.crud.user import DEMO_USER_ID
from app.schemas.clipboard import ClipboardItemResponse
from app.schemas.common import ContentType, utc_now


def make_preview(content: str, limit: int = 80) -> str:
    """生成预览文本：压缩空白字符后按长度截断。"""
    collapsed = " ".join(content.split())
    return collapsed if len(collapsed) <= limit else f"{collapsed[:limit]}..."


def _item(
    item_id: str,
    title: str,
    content: str,
    minutes_ago: int,
    *,
    updated_minutes_ago: int | None = None,
) -> ClipboardItemResponse:
    """构造一条种子数据。"""
    from datetime import timedelta

    now = utc_now()
    created_at = now - timedelta(minutes=minutes_ago)
    updated_at = now - timedelta(
        minutes=minutes_ago if updated_minutes_ago is None else updated_minutes_ago
    )
    return ClipboardItemResponse(
        id=item_id,
        user_id=DEMO_USER_ID,
        title=title,
        content_type=ContentType.TEXT,
        content=content,
        preview=make_preview(content),
        metadata={"mime": "text/plain", "size": len(content.encode("utf-8"))},
        created_at=created_at,
        updated_at=updated_at,
    )


def seed_demo_items() -> dict[str, ClipboardItemResponse]:
    """返回初始假数据：{id: item}。"""
    items = [
        _item(
            "9c8b7a65-4321-4f0e-8d3c-1a2b3c4d5e6f",
            "FastAPI 官方教程",
            "https://fastapi.tiangolo.com/tutorial/",
            12,
        ),
        _item(
            "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
            "后端依赖安装命令",
            "pip install fastapi uvicorn[standard]",
            35,
        ),
        _item(
            "7f6e5d4c-3b2a-4190-8f7e-6d5c4b3a2910",
            "MVP 范围备忘",
            "云剪贴板 MVP 范围：文字内容的上传、查询、删除 + WebSocket 实时同步 + JWT 认证 + 内容去重。",
            58,
        ),
        _item(
            "2b3c4d5e-6f70-4182-9a3b-4c5d6e7f8091",
            "提交规范示例",
            "git commit -m \"feat: 新增 WebSocket 广播\"",
            90,
            updated_minutes_ago=3,
        ),
    ]
    return {item.id: item for item in items}
