"""用户数据访问层（当前为内存假数据）。

第 3 步接入数据库、第 4 步接入 JWT 后，本模块将改为真实查询。
"""

from __future__ import annotations

from datetime import datetime

from app.schemas.common import utc_now
from app.schemas.user import UserResponse

DEMO_USER_ID = "3f1a9c62-7d4b-4e18-9f2a-6b0c5d8e1a34"

_DEMO_CREATED_AT = datetime(2026, 9, 27, 10, 0, 0, tzinfo=utc_now().tzinfo)

_DEMO_USER = UserResponse(
    id=DEMO_USER_ID,
    username="demo",
    email="demo@cloud-clipboard.dev",
    nickname="演示用户",
    avatar_url=None,
    created_at=_DEMO_CREATED_AT,
)


def get_demo_user() -> UserResponse:
    """返回演示用户。

    第 1/2 步未接入认证，所有请求都视为该演示用户发起；
    这样剪贴板数据能正确归属到 `user_id`，Web 端可先行跑通闭环。
    """
    return _DEMO_USER.model_copy()


def get_user_by_id(user_id: str) -> UserResponse | None:
    """按 ID 查询用户；非演示用户返回 None。"""
    return _DEMO_USER.model_copy() if user_id == _DEMO_USER.id else None
