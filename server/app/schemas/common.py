"""公共枚举与分页模型。

这些枚举属于对外数据契约的一部分，Web 端与鸿蒙端必须保持同名同值。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间（契约要求时间为 ISO 8601 UTC）。"""
    return datetime.now(timezone.utc)


class ContentType(str, Enum):
    """剪贴板内容类型。阶段一仅实现 `text`。"""

    TEXT = "text"
    IMAGE = "image"  # 阶段二
    FILE = "file"  # 阶段三


class SortOrder(str, Enum):
    """排序方向。"""

    DESC = "desc"
    ASC = "asc"


class SortBy(str, Enum):
    """列表排序字段。"""

    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class PageMeta(BaseModel):
    """分页元信息。"""

    page: int = Field(..., ge=1, description="当前页码，从 1 开始")
    size: int = Field(..., ge=1, description="每页条数")
    total: int = Field(..., ge=0, description="符合条件的总条数")
    pages: int = Field(..., ge=0, description="总页数")


class MessageResponse(BaseModel):
    """通用消息响应（删除类接口）。"""

    success: bool = Field(True, description="操作是否成功")
    message: str = Field(..., description="人类可读的结果说明")
