"""认证路由 —— 假数据实现。

第 4 步将替换为真实的密码哈希与 JWT 签发/校验。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.config import settings
from app.crud import user as user_crud
from app.schemas.user import (
    AuthResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["认证"])


def get_current_user() -> UserResponse:
    """认证依赖。

    第 1/2 步：不校验任何凭证，固定返回演示用户，方便 Web 端先跑通闭环。
    第 4 步：改为解析 `Authorization: Bearer <token>`，无效时抛 401。
    """
    return user_crud.get_demo_user()


CurrentUser = Annotated[UserResponse, Depends(get_current_user)]


def _fake_token(user: UserResponse) -> TokenResponse:
    """签发假 JWT（仅用于打通前端流程，不具备任何安全性）。"""
    expires_in = 7 * 24 * 3600
    return TokenResponse(
        access_token=f"fake-jwt-token-for.{user.username}.step1",
        token_type="bearer",
        expires_in=expires_in,
        user=user,
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册（假数据）",
    description="第 1 步不落库、不校验唯一性，固定返回演示用户与假 token。",
)
async def register(payload: UserRegisterRequest) -> AuthResponse:
    user = user_crud.get_demo_user().model_copy(
        update={"username": payload.username, "email": payload.email}
    )
    return AuthResponse(**user.model_dump(), token=_fake_token(user))


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="用户登录（假数据）",
    description="任意用户名密码均返回演示用户与假 token；第 4 步接入真实校验。",
)
async def login(payload: UserLoginRequest) -> AuthResponse:  # noqa: ARG001 - 假数据实现暂不校验
    user = user_crud.get_demo_user()
    return AuthResponse(**user.model_dump(), token=_fake_token(user))


@router.get(
    "/me",
    response_model=UserResponse,
    summary="获取当前用户",
    description="默认返回演示用户；通过 `Authorization` 头传入 token 后应返回该 token 对应用户。",
)
async def me(current_user: CurrentUser) -> UserResponse:
    return current_user
