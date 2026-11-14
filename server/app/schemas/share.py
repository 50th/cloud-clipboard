"""剪贴板分享的数据契约 —— **本项目分享契约的唯一事实来源**。

字段变更必须先改本文件，再同步 `docs/api.md` 与 Web 端类型。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ContentType


class ShareMode(str, Enum):
    """分享内容模式。"""

    SNAPSHOT = "snapshot"
    LIVE = "live"


class ShareExpiresIn(str, Enum):
    """分享有效期选项；P0 不支持永久。"""

    HOUR_1 = "1h"
    DAY_1 = "1d"
    DAY_7 = "7d"
    DAY_30 = "30d"


class ShareStatus(str, Enum):
    """分享展示状态。判定顺序：撤销 → 过期 → 次数用尽 → 有效。"""

    ACTIVE = "active"
    EXPIRED = "expired"
    EXHAUSTED = "exhausted"
    REVOKED = "revoked"


class ShareAccessResult(str, Enum):
    """访问记录结果。失败结果仅管理员可见。"""

    SUCCESS = "success"
    PASSWORD_FAILED = "password_failed"
    EXPIRED = "expired"
    REVOKED = "revoked"
    EXHAUSTED = "exhausted"
    OWNER_DISABLED = "owner_disabled"


# 密码字符数范围；字节上限由 bcrypt 决定，单独在 validator 里检查。
SHARE_PASSWORD_MIN_LENGTH = 4
SHARE_PASSWORD_MAX_LENGTH = 24
SHARE_PASSWORD_MAX_BYTES = 72

SHARE_MAX_VIEWS_MIN = 1
SHARE_MAX_VIEWS_MAX = 10_000

# 同一条剪贴板最多同时存在多少个有效分享（超出返回 409）。
SHARE_PER_ITEM_LIMIT = 5


class ClipboardShareCreate(BaseModel):
    """创建分享请求。"""

    mode: ShareMode = Field(ShareMode.SNAPSHOT, description="snapshot 快照 / live 跟随最新")
    expires_in: ShareExpiresIn = Field(
        ShareExpiresIn.DAY_7, description="有效期：1h / 1d / 7d / 30d，默认 7d"
    )
    password: str | None = Field(
        None,
        min_length=SHARE_PASSWORD_MIN_LENGTH,
        max_length=SHARE_PASSWORD_MAX_LENGTH,
        description="访问密码，可空；4–24 字符，UTF-8 不超过 72 字节",
    )
    max_views: int | None = Field(
        None,
        ge=SHARE_MAX_VIEWS_MIN,
        le=SHARE_MAX_VIEWS_MAX,
        description="最大查看次数，可空（不限）",
    )

    @field_validator("password")
    @classmethod
    def _validate_password_bytes(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if len(value.encode("utf-8")) > SHARE_PASSWORD_MAX_BYTES:
            raise ValueError(
                f"密码不能超过 {SHARE_PASSWORD_MAX_BYTES} 字节（bcrypt 上限）"
            )
        return value


class ClipboardShareResponse(BaseModel):
    """登录态下的分享表示（含 token 与完整链接）。"""

    id: str = Field(..., description="分享 UUID")
    item_id: str = Field(..., description="原剪贴板项 UUID")
    mode: ShareMode = Field(..., description="内容模式")
    status: ShareStatus = Field(..., description="当前状态")
    title: str = Field(..., description="创建时的标题")
    token: str = Field(..., description="分享 token")
    url: str = Field(..., description="完整公开链接")
    password_protected: bool = Field(..., description="是否设置访问密码")
    expires_at: datetime | None = Field(None, description="到期时间（ISO 8601 UTC）")
    max_views: int | None = Field(None, description="最大查看次数；空表示不限")
    view_count: int = Field(..., description="已成功查看次数")
    remaining_views: int | None = Field(
        None, description="剩余查看次数；空表示不限"
    )
    created_at: datetime = Field(..., description="创建时间（ISO 8601 UTC）")
    last_viewed_at: datetime | None = Field(
        None, description="最后一次成功查看时间"
    )


class ClipboardShareList(BaseModel):
    """我的分享分页列表。"""

    items: list[ClipboardShareResponse] = Field(..., description="当前页数据")
    page: int = Field(..., ge=1, description="当前页码，从 1 开始")
    size: int = Field(..., ge=1, description="每页条数")
    total: int = Field(..., ge=0, description="符合条件的总条数")
    pages: int = Field(..., ge=0, description="总页数")

    @classmethod
    def build(
        cls,
        items: list[ClipboardShareResponse],
        *,
        page: int,
        size: int,
        total: int,
    ) -> "ClipboardShareList":
        pages = (total + size - 1) // size if total > 0 else 0
        return cls(items=items, page=page, size=size, total=total, pages=pages)


class ClipboardShareListParams:
    """`GET /clipboard/shares` 查询参数。"""

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1,
        size: Annotated[
            int, Query(ge=1, le=100, description="每页条数，默认 10，最大 100")
        ] = 10,
        status: Annotated[
            ShareStatus | None, Query(description="按状态筛选")
        ] = None,
        item_id: Annotated[
            uuid.UUID | None, Query(description="按原剪贴板项 UUID 筛选")
        ] = None,
        search: Annotated[
            str | None,
            Query(max_length=200, description="按分享标题或内容关键字搜索"),
        ] = None,
    ) -> None:
        self.page = page
        self.size = size
        self.status = status
        self.item_id = item_id
        self.search = search


class PublicShareMeta(BaseModel):
    """公开分享元信息；不返回正文、不计数。"""

    title: str | None = Field(
        None, description="有密码时为 null，避免未解锁泄露标题"
    )
    mode: ShareMode = Field(..., description="内容模式")
    content_type: ContentType = Field(..., description="内容类型")
    password_required: bool = Field(..., description="是否需要访问密码")
    expires_at: datetime | None = Field(None, description="到期时间")
    remaining_views: int | None = Field(
        None, description="剩余查看次数；空表示不限"
    )


class PublicShareAccessRequest(BaseModel):
    """公开查看正文请求；无密码分享可传空对象。"""

    password: str | None = Field(None, description="访问密码")


class PublicShareContent(BaseModel):
    """公开查看正文响应。"""

    title: str = Field(..., description="标题")
    content: str = Field(..., description="文字正文")
    content_type: ContentType = Field(..., description="内容类型")
    created_at: datetime = Field(..., description="原记录创建时间（ISO 8601 UTC）")
    expires_at: datetime | None = Field(None, description="分享到期时间")
    remaining_views: int | None = Field(
        None, description="本次查看后的剩余次数；空表示不限"
    )


class ShareAccessLogResponse(BaseModel):
    """所有者可见的访问记录（只含成功记录，IP 已脱敏）。"""

    id: str
    accessed_at: datetime
    result: ShareAccessResult
    ip_masked: str | None = Field(None, description="脱敏 IP")
    user_agent: str | None = Field(None, description="User-Agent，最多 200 字符")


class ShareAccessLogList(BaseModel):
    """访问记录分页列表。"""

    items: list[ShareAccessLogResponse] = Field(..., description="当前页数据")
    page: int = Field(..., ge=1)
    size: int = Field(..., ge=1)
    total: int = Field(..., ge=0)
    pages: int = Field(..., ge=0)

    @classmethod
    def build(
        cls,
        items: list[ShareAccessLogResponse],
        *,
        page: int,
        size: int,
        total: int,
    ) -> "ShareAccessLogList":
        pages = (total + size - 1) // size if total > 0 else 0
        return cls(items=items, page=page, size=size, total=total, pages=pages)


class ShareAccessLogListParams:
    """`GET /clipboard/shares/{id}/access-logs` 查询参数。"""

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1,
        size: Annotated[
            int, Query(ge=1, le=100, description="每页条数，默认 10，最大 100")
        ] = 10,
    ) -> None:
        self.page = page
        self.size = size


class ShareSettingsResponse(BaseModel):
    """管理端分享限额设置。"""

    user_share_limit: int = Field(..., ge=1, le=10_000, description="每用户有效分享上限")
    updated_at: datetime | None = Field(None, description="最近更新时间")
    updated_by: str | None = Field(None, description="最近更新人 UUID")
    updated_by_username: str | None = Field(None, description="最近更新人用户名")


class ShareSettingsUpdate(BaseModel):
    """更新分享限额请求。"""

    user_share_limit: int = Field(
        ...,
        ge=1,
        le=10_000,
        description="每用户有效分享上限，范围 1–10000",
    )
