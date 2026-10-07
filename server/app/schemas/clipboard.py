"""剪贴板相关的数据契约 —— **本项目契约的唯一事实来源**。

任何字段变更都必须先改本文件（AGENTS.md 第 4 节）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import (
    ContentType,
    MessageResponse,
    SortBy,
    SortOrder,
)

# 标题长度上限，与 ClipboardItemCreate.title 保持一致
TITLE_MAX_LENGTH = 200


class ClipboardItemCreate(BaseModel):
    """创建剪贴板项请求。"""

    content: str = Field(
        ...,
        min_length=1,
        max_length=100_000,
        description="剪贴板内容（阶段一为纯文本）",
    )
    title: str | None = Field(
        None,
        max_length=TITLE_MAX_LENGTH,
        description=(
            "标题。留空时由服务端自动生成，格式 `<用户名> · <月-日 时:分>`，"
            "时间按 `timezone` 指定的时区展示，例如 `demo · 10-05 21:56`"
        ),
    )
    timezone: str | None = Field(
        None,
        max_length=64,
        description=(
            "自动生成标题时使用的 IANA 时区，例如 `Asia/Shanghai`。"
            "**只影响标题里展示的时间，数据库仍统一存 UTC**。"
            "留空时用服务端 `DEFAULT_TIMEZONE` 配置"
        ),
    )
    content_type: ContentType = Field(
        ContentType.TEXT,
        description="内容类型，阶段一固定 text",
    )
    preview: str | None = Field(
        None,
        max_length=500,
        description="预览文本；不传时由服务端截取正文生成",
    )
    metadata: dict[str, Any] | None = Field(
        None,
        description='附加元信息，例如 {"mime": "text/plain", "size": 1024}',
    )


class ClipboardItemUpdate(BaseModel):
    """更新剪贴板项请求（用于自动保存复用同一条草稿记录）。

    所有字段可选，只更新显式传入的字段。
    """

    content: str | None = Field(None, min_length=1, max_length=100_000)
    title: str | None = Field(None, max_length=TITLE_MAX_LENGTH)
    timezone: str | None = Field(
        None,
        max_length=64,
        description="内容变化且未显式传 `title` 时，重新生成标题所用的 IANA 时区",
    )
    preview: str | None = Field(None, max_length=500)
    metadata: dict[str, Any] | None = Field(None)


class ClipboardItemResponse(BaseModel):
    """剪贴板项对外表示。

    注意：`content_hash` 不对外暴露，仅服务端用于去重。
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="剪贴板项 UUID")
    user_id: str = Field(..., description="所属用户 UUID")
    title: str = Field(..., description="标题，用户未填写时由服务端自动生成")
    content_type: ContentType = Field(..., description="内容类型")
    content: str = Field(..., description="文字内容或文件 URL")
    preview: str | None = Field(None, description="预览文本")
    metadata: dict[str, Any] | None = Field(None, description="附加元信息")
    created_at: datetime = Field(..., description="创建时间（ISO 8601 UTC）")
    updated_at: datetime = Field(..., description="最后更新时间（ISO 8601 UTC）")


class ClipboardItemList(BaseModel):
    """剪贴板列表响应（携带分页元信息）。"""

    items: list[ClipboardItemResponse] = Field(..., description="当前页数据")
    page: int = Field(..., ge=1, description="当前页码，从 1 开始")
    size: int = Field(..., ge=1, description="每页条数")
    total: int = Field(..., ge=0, description="符合条件的总条数")
    pages: int = Field(..., ge=0, description="总页数")

    @classmethod
    def build(
        cls,
        items: list[ClipboardItemResponse],
        *,
        page: int,
        size: int,
        total: int,
    ) -> "ClipboardItemList":
        """按统一公式组装分页响应。"""
        pages = (total + size - 1) // size if total > 0 else 0
        return cls(items=items, page=page, size=size, total=total, pages=pages)


class ClipboardListParams:
    """`GET /clipboard/items` 的查询参数。

    作为依赖使用：`params: Annotated[ClipboardListParams, Depends()]`，
    这样 Swagger UI 会把每个参数展开成独立的输入框。
    """

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1,
        size: Annotated[int, Query(ge=1, le=100, description="每页条数，默认 20，最大 100")] = 20,
        content_type: Annotated[
            ContentType | None, Query(description="按内容类型筛选")
        ] = None,
        search: Annotated[
            str | None,
            Query(max_length=200, description="按标题或内容关键字搜索"),
        ] = None,
        sort_by: Annotated[SortBy, Query(description="排序字段")] = SortBy.CREATED_AT,
        order: Annotated[SortOrder, Query(description="排序方向")] = SortOrder.DESC,
    ) -> None:
        self.page = page
        self.size = size
        self.content_type = content_type
        self.search = search
        self.sort_by = sort_by
        self.order = order


class ClipboardDeleteResponse(MessageResponse):
    """删除单条剪贴板项的响应。"""

    id: str = Field(..., description="被删除的剪贴板项 UUID")
