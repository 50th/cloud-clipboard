"""后台管理相关的数据契约。

字段变更属于契约变更：必须同步 `docs/api.md`、Web 端类型与迁移。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ContentType, SortOrder
from app.schemas.user import (
    MIN_PASSWORD_LENGTH,
    validate_password_bytes,
    validate_password_strength,
)


class AdminUserStatus(str, Enum):
    """用户列表的状态筛选。"""

    ALL = "all"
    ACTIVE = "active"
    DISABLED = "disabled"


class AdminUserRole(str, Enum):
    """用户列表的角色筛选。"""

    ALL = "all"
    ADMIN = "admin"
    USER = "user"


class AdminInviteCodeStatus(str, Enum):
    """邀请码状态筛选。"""

    ALL = "all"
    ACTIVE = "active"
    EXHAUSTED = "exhausted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class AdminUserSortBy(str, Enum):
    """用户列表排序字段。"""

    CREATED_AT = "created_at"
    LAST_LOGIN_AT = "last_login_at"
    ITEM_COUNT = "item_count"


class AdminClipboardSortBy(str, Enum):
    """剪贴板列表排序字段。"""

    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class AdminUserResponse(BaseModel):
    """管理端用户表示（含统计字段）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="用户 UUID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    nickname: str | None = Field(None, description="昵称")
    is_admin: bool = Field(..., description="是否管理员")
    is_active: bool = Field(..., description="账号是否启用")
    created_at: datetime = Field(..., description="注册时间（ISO 8601 UTC）")
    last_login_at: datetime | None = Field(None, description="最后登录时间")
    item_count: int = Field(0, ge=0, description="剪贴板条数")
    last_item_at: datetime | None = Field(None, description="最后一条剪贴板更新时间")


class AdminUserList(BaseModel):
    """用户分页列表。"""

    items: list[AdminUserResponse] = Field(..., description="当前页数据")
    page: int = Field(..., ge=1)
    size: int = Field(..., ge=1)
    total: int = Field(..., ge=0)
    pages: int = Field(..., ge=0)

    @classmethod
    def build(
        cls, items: list[AdminUserResponse], *, page: int, size: int, total: int
    ) -> "AdminUserList":
        pages = (total + size - 1) // size if total > 0 else 0
        return cls(items=items, page=page, size=size, total=total, pages=pages)


class AdminUserUpdate(BaseModel):
    """修改用户资料/状态/角色；所有字段可选，只更新显式传入的字段。"""

    nickname: str | None = Field(None, max_length=64)
    email: str | None = Field(None, min_length=3, max_length=254)
    is_active: bool | None = Field(None, description="false = 禁用账号")
    is_admin: bool | None = Field(None, description="false = 取消管理员")


class AdminPasswordResetRequest(BaseModel):
    """重置密码请求。"""

    password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH,
        description=(
            "新密码，至少 8 个字符，必须同时包含字母和数字，不能包含目标用户名，"
            "且不超过 72 字节（bcrypt 上限）"
        ),
    )

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        return validate_password_strength(validate_password_bytes(value))


class AdminClipboardItemResponse(BaseModel):
    """管理端剪贴板项（含所属用户名）。**不包含 `content_hash`**。"""

    id: str
    user_id: str
    username: str
    title: str
    content_type: ContentType
    content: str
    preview: str | None
    metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class AdminClipboardItemList(BaseModel):
    """剪贴板分页列表。"""

    items: list[AdminClipboardItemResponse] = Field(..., description="当前页数据")
    page: int = Field(..., ge=1)
    size: int = Field(..., ge=1)
    total: int = Field(..., ge=0)
    pages: int = Field(..., ge=0)

    @classmethod
    def build(
        cls,
        items: list[AdminClipboardItemResponse],
        *,
        page: int,
        size: int,
        total: int,
    ) -> "AdminClipboardItemList":
        pages = (total + size - 1) // size if total > 0 else 0
        return cls(items=items, page=page, size=size, total=total, pages=pages)


class AdminStatsResponse(BaseModel):
    """后台概览统计。"""

    user_count: int = Field(..., ge=0)
    active_user_count: int = Field(..., ge=0)
    admin_count: int = Field(..., ge=0)
    item_count: int = Field(..., ge=0)
    total_bytes: int = Field(..., ge=0)
    new_users_7d: int = Field(..., ge=0)
    new_items_7d: int = Field(..., ge=0)
    invite_code_count: int = Field(..., ge=0, description="邀请码总数")
    active_invite_count: int = Field(..., ge=0, description="当前可用的邀请码数")
    invite_used_count: int = Field(..., ge=0, description="邀请码累计使用次数")


class AdminInviteCodeCreate(BaseModel):
    """创建邀请码请求。"""

    label: str | None = Field(None, max_length=64, description="备注，便于辨认")
    max_uses: int = Field(
        ...,
        ge=1,
        le=1000,
        description="最大使用次数（必填），用尽后邀请码失效",
    )
    expires_days: int = Field(
        7,
        ge=0,
        le=3650,
        description="有效期天数，0 表示不过期",
    )


class AdminInviteCodeResponse(BaseModel):
    """邀请码表示。**明文只在创建时返回一次**，列表只展示 `code_hint`。"""

    id: str
    code_hint: str = Field(..., description="明文前 8 位，仅用于辨认")
    label: str | None
    max_uses: int | None = Field(None, description="最大使用次数；历史数据可能为不限次数")
    used_count: int
    status: str = Field(..., description="active / exhausted / expired / revoked")
    expires_at: datetime | None
    revoked_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime


class AdminInviteCodeCreated(AdminInviteCodeResponse):
    """创建成功的响应：额外返回一次性明文。"""

    code: str = Field(..., description="邀请码明文，仅本次返回")


class AdminInviteCodeList(BaseModel):
    """邀请码分页列表。"""

    items: list[AdminInviteCodeResponse] = Field(..., description="当前页数据")
    page: int = Field(..., ge=1)
    size: int = Field(..., ge=1)
    total: int = Field(..., ge=0)
    pages: int = Field(..., ge=0)

    @classmethod
    def build(
        cls,
        items: list[AdminInviteCodeResponse],
        *,
        page: int,
        size: int,
        total: int,
    ) -> "AdminInviteCodeList":
        pages = (total + size - 1) // size if total > 0 else 0
        return cls(items=items, page=page, size=size, total=total, pages=pages)


class AdminInviteCodeListParams:
    """`GET /admin/invite-codes` 查询参数。"""

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1,
        size: Annotated[int, Query(ge=1, le=100, description="每页条数，最大 100")] = 20,
        status: Annotated[
            AdminInviteCodeStatus, Query(description="按状态筛选")
        ] = AdminInviteCodeStatus.ALL,
    ) -> None:
        self.page = page
        self.size = size
        self.status = status


class AdminInviteCodeUsage(BaseModel):
    """邀请码使用详情：通过该码注册的用户。"""

    user_id: str
    username: str
    email: str
    registered_at: datetime


class AdminInviteCodeUsageList(BaseModel):
    """邀请码使用详情分页列表。"""

    items: list[AdminInviteCodeUsage] = Field(..., description="当前页数据")
    page: int = Field(..., ge=1)
    size: int = Field(..., ge=1)
    total: int = Field(..., ge=0)
    pages: int = Field(..., ge=0)

    @classmethod
    def build(
        cls,
        items: list[AdminInviteCodeUsage],
        *,
        page: int,
        size: int,
        total: int,
    ) -> "AdminInviteCodeUsageList":
        pages = (total + size - 1) // size if total > 0 else 0
        return cls(items=items, page=page, size=size, total=total, pages=pages)


class AdminInviteCodeUsageListParams:
    """`GET /admin/invite-codes/{id}/usages` 查询参数。"""

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1,
        size: Annotated[int, Query(ge=1, le=100, description="每页条数，最大 100")] = 20,
    ) -> None:
        self.page = page
        self.size = size


class AdminAuditLogResponse(BaseModel):
    """一条管理员审计记录。"""

    id: str
    admin_id: str | None
    admin_username: str
    action: str
    target_type: str | None
    target_id: str | None
    detail: dict[str, Any] | None
    created_at: datetime


class AdminAuditLogList(BaseModel):
    """审计记录分页列表。"""

    items: list[AdminAuditLogResponse] = Field(..., description="当前页数据")
    page: int = Field(..., ge=1)
    size: int = Field(..., ge=1)
    total: int = Field(..., ge=0)
    pages: int = Field(..., ge=0)

    @classmethod
    def build(
        cls,
        items: list[AdminAuditLogResponse],
        *,
        page: int,
        size: int,
        total: int,
    ) -> "AdminAuditLogList":
        pages = (total + size - 1) // size if total > 0 else 0
        return cls(items=items, page=page, size=size, total=total, pages=pages)


class AdminUserListParams:
    """`GET /admin/users` 查询参数。"""

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1,
        size: Annotated[int, Query(ge=1, le=100, description="每页条数，最大 100")] = 20,
        search: Annotated[
            str | None, Query(max_length=100, description="匹配用户名或邮箱")
        ] = None,
        status: Annotated[AdminUserStatus, Query(description="账号状态筛选")] = (
            AdminUserStatus.ALL
        ),
        role: Annotated[AdminUserRole, Query(description="角色筛选")] = (
            AdminUserRole.ALL
        ),
        sort_by: Annotated[AdminUserSortBy, Query(description="排序字段")] = (
            AdminUserSortBy.CREATED_AT
        ),
        order: Annotated[SortOrder, Query(description="排序方向")] = SortOrder.DESC,
    ) -> None:
        self.page = page
        self.size = size
        self.search = search
        self.status = status
        self.role = role
        self.sort_by = sort_by
        self.order = order


class AdminClipboardListParams:
    """`GET /admin/clipboards` 查询参数。"""

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1,
        size: Annotated[int, Query(ge=1, le=100, description="每页条数，最大 100")] = 20,
        user_id: Annotated[
            uuid.UUID | None, Query(description="按用户 UUID 精确筛选")
        ] = None,
        username: Annotated[
            str | None, Query(max_length=32, description="按用户名模糊筛选")
        ] = None,
        search: Annotated[
            str | None, Query(max_length=100, description="匹配标题或内容")
        ] = None,
        content_type: Annotated[
            ContentType | None, Query(description="按内容类型筛选")
        ] = None,
        sort_by: Annotated[AdminClipboardSortBy, Query(description="排序字段")] = (
            AdminClipboardSortBy.CREATED_AT
        ),
        order: Annotated[SortOrder, Query(description="排序方向")] = SortOrder.DESC,
    ) -> None:
        self.page = page
        self.size = size
        self.user_id = user_id
        self.username = username
        self.search = search
        self.content_type = content_type
        self.sort_by = sort_by
        self.order = order


class AdminAuditLogListParams:
    """`GET /admin/audit-logs` 查询参数。"""

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1,
        size: Annotated[int, Query(ge=1, le=100, description="每页条数，最大 100")] = 20,
        admin_username: Annotated[
            str | None, Query(max_length=32, description="按管理员用户名模糊筛选")
        ] = None,
        action: Annotated[
            str | None, Query(max_length=32, description="按动作精确筛选")
        ] = None,
        target_id: Annotated[
            uuid.UUID | None, Query(description="按目标对象 UUID 筛选")
        ] = None,
        start: Annotated[
            datetime | None, Query(description="起始时间（ISO 8601）")
        ] = None,
        end: Annotated[
            datetime | None, Query(description="结束时间（ISO 8601）")
        ] = None,
    ) -> None:
        self.page = page
        self.size = size
        self.admin_username = admin_username
        self.action = action
        self.target_id = target_id
        self.start = start
        self.end = end
