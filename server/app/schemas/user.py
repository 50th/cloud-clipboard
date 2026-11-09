"""用户相关的数据契约。

⚠️ 字段变更属于契约变更，必须同步 `docs/api.md`、Web 端类型与鸿蒙模型。
"""

from __future__ import annotations

import unicodedata
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# bcrypt 只处理密码的前 72 **字节**（5.x 起超出直接抛错，不再静默截断）。
MAX_PASSWORD_BYTES = 72


def _check_no_log_control_chars(value: str) -> str:
    """拒绝换行等控制字符。

    这些字符会直接破坏日志行的结构（用户名被原样写进审计日志），
    即“日志注入”：一条输入可以伪造出多行日志。
    """
    if "\u2028" in value or "\u2029" in value:
        raise ValueError("用户名不能包含换行或其他控制字符")
    if any(unicodedata.category(ch) == "Cc" for ch in value):
        raise ValueError("用户名不能包含换行或其他控制字符")
    return value


def validate_password_bytes(value: str) -> str:
    """按 UTF-8 字节数校验密码长度。

    ⚠️ 不能只靠 `max_length`：Pydantic 的 `max_length` 数的是**字符数**，
    而 bcrypt 限制的是**字节数**。一个 24 字符的中文密码就是 72 字节，
    30 个汉字则是 90 字节——只校验字符数会让这类密码通过校验后在哈希阶段抛错。
    """
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"密码不能超过 {MAX_PASSWORD_BYTES} 字节（bcrypt 上限）")
    return value


class UserRegisterRequest(BaseModel):
    """注册请求。"""

    username: str = Field(..., min_length=3, max_length=32, description="用户名，3-32 字符")
    email: str = Field(..., min_length=3, max_length=254, description="邮箱")
    password: str = Field(
        ...,
        min_length=6,
        description="密码，至少 6 字符，且不超过 72 字节（bcrypt 上限）",
    )
    invite_code: str | None = Field(
        None,
        max_length=64,
        description=(
            "邀请码。服务端设置 `REGISTRATION_INVITE_CODE` 时必填且必须匹配，"
            "否则返回 403；未设置时可为空"
        ),
    )

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        """用户名会写进日志，必须拒绝换行等控制字符。"""
        return _check_no_log_control_chars(value)

    @field_validator("password")
    @classmethod
    def _validate_password_bytes(cls, value: str) -> str:
        """按 UTF-8 字节数校验密码长度（见 `validate_password_bytes` 的说明）。"""
        return validate_password_bytes(value)


class UserLoginRequest(BaseModel):
    """登录请求。"""

    # 上限按邮箱长度（254）：登录框允许用邮箱代替用户名；
    # 同时避免超长输入把失败审计日志撑爆。
    username: str = Field(
        ..., min_length=1, max_length=254, description="用户名或邮箱"
    )
    password: str = Field(..., description="密码")

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        """用户名会写进失败审计日志，必须拒绝换行等控制字符。"""
        return _check_no_log_control_chars(value)


class UserResponse(BaseModel):
    """用户公开信息。**绝不包含密码哈希**。"""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="用户 UUID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    nickname: str | None = Field(None, description="昵称")
    avatar_url: str | None = Field(None, description="头像地址")
    is_admin: bool = Field(False, description="是否管理员（仅用于展示，权限仍由服务端校验）")
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
