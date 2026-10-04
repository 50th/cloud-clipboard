"""认证路由。

第 1/2 步：不校验凭证，固定返回配置里的演示用户（便于 Web 端先跑通闭环）。
第 4 步：替换为真实的密码哈希校验与 JWT 签发。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud import user as user_crud
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.user import (
    AuthResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["认证"])


def to_user_response(user: User) -> UserResponse:
    """把 ORM 用户对象转换为对外响应模型。"""
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
    )


async def get_current_user(session: Annotated[AsyncSession, Depends(get_db)]) -> User:
    """认证依赖。

    当前返回配置里的演示用户；第 4 步改为解析
    `Authorization: Bearer <token>`，无效时抛 401。
    """
    user = await user_crud.get_by_id(session, settings.DEMO_USER_ID)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="演示用户不存在，请先执行 python -m scripts.init_db",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def _fake_token(user: User) -> TokenResponse:
    """签发假 JWT（仅用于打通前端流程，不具备任何安全性）。"""
    return TokenResponse(
        access_token=f"fake-jwt-token-for.{user.username}.step1",
        token_type="bearer",
        expires_in=7 * 24 * 3600,
        user=to_user_response(user),
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册（假数据）",
    description="第 1 步不落库、不校验唯一性，固定返回演示用户与假 token。",
)
async def register(payload: UserRegisterRequest, current_user: CurrentUser) -> AuthResponse:
    user = to_user_response(current_user).model_copy(
        update={"username": payload.username, "email": payload.email}
    )
    return AuthResponse(**user.model_dump(), token=_fake_token(current_user))


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="用户登录（假数据）",
    description="任意用户名密码均返回演示用户与假 token；第 4 步接入真实校验。",
)
async def login(current_user: CurrentUser) -> AuthResponse:
    return AuthResponse(
        **to_user_response(current_user).model_dump(), token=_fake_token(current_user)
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="获取当前用户",
    description="当前返回演示用户；第 4 步接入 JWT 后返回该 token 对应的用户。",
)
async def me(current_user: CurrentUser) -> UserResponse:
    return to_user_response(current_user)
