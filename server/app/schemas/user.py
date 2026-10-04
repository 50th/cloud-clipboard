"""用户相关的数据契约。

⚠️ 字段变更属于契约变更，必须同步 `docs/api.yaml`、Web 端类型与鸿蒙模型。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserRegisterRequest(BaseModel):
    """注册请求。"""

    username: str = Field(..., min_length=3, max_length=32, description="用户名，3-32 字符")
    email: str = Field(..., min_length=3, max_length=254, description="邮箱")
    password: str = Field(
        ...,
        min_length=6,
        max_length=72,
        description="密码，6-72 字符（bcrypt 上限 72 字节）",
    )


class UserLoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    """用户公开信息。**绝不包含密码哈希**。"""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="用户 UUID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    nickname: str | None = Field(None, description="昵称")
    avatar_url: str | None = Field(None, description="头像地址")
    created_at: datetime = Field(..., description="注册时间（ISO 8601 UTC）")


class TokenResponse(BaseModel):
    """登录/注册成功后返回的令牌。"""

    access_token: str = Field(..., description="JWT 访问令牌")
    token_type: str = Field("bearer", description="令牌类型，固定 bearer")
    expires_in: int = Field(..., description="有效期（秒）")
    user: UserResponse = Field(..., description="当前登录用户")


class AuthResponse(UserResponse):
    """注册/登录响应：用户信息 + 令牌（供前端一次拿到完整上下文）。"""

    token: TokenResponse = Field(..., description="令牌信息，便于前端一次取用")
