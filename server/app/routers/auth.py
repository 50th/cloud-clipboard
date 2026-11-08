"""认证路由：注册、登录、获取当前用户。

分层：本模块负责 HTTP 语义（解析请求头、抛 401、查库取用户），
密码哈希与 JWT 的纯逻辑在 `app/core/security.py`。
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.core.logging_utils import safe_log_value
from app.crud import invite as invite_crud
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["认证"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

# auto_error=False：缺少 Authorization 头时不直接 403，交给我们统一抛 401 并带上
# WWW-Authenticate 头（RFC 6750 要求）。
_bearer_scheme = HTTPBearer(auto_error=False, description="JWT，形如 `Bearer <token>`")

_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


def _unauthorized(detail: str) -> HTTPException:
    """构造 401，并带上标准 WWW-Authenticate 头。"""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=_UNAUTHORIZED_HEADERS,
    )


def _client_ip(request: Request) -> str:
    """客户端 IP，仅用于审计日志；`request.client` 可能为 None。"""
    client = request.client
    return client.host if client is not None else "unknown"


def _log_auth_failure(request: Request, reason: str) -> None:
    """记录 401 的具体原因。

    只到 INFO：令牌过期是常态，WARNING 会淹没真正的异常；但也必须留痕，
    否则"页面上突然掉线"在日志里没有任何线索。**绝不记录令牌本身**。
    """
    logger.info(
        "鉴权失败: reason=%s path=%s client=%s",
        reason,
        request.url.path,
        _client_ip(request),
    )


def to_user_response(user: User) -> UserResponse:
    """把 ORM 用户对象转换为对外响应模型。**绝不包含 password_hash**。"""
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
    )


def issue_token(user: User) -> TokenResponse:
    """为用户签发访问令牌。"""
    return TokenResponse(
        access_token=security.create_access_token(user.id),
        token_type="bearer",
        expires_in=security.access_token_expires_in(),
        user=to_user_response(user),
    )


async def get_current_user(
    request: Request,
    session: DbSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ] = None,
) -> User:
    """认证依赖：解析 `Authorization: Bearer <token>` 并取出对应用户。

    401 的三种情形：
    - 完全没有带 Authorization 头
    - 令牌无效 / 过期 / 签名不符
    - 令牌有效但用户已不存在（如已被删除）

    注意：这里**不做**"token 里的用户名与库中是否一致"之类的额外校验，
    `sub` 是唯一事实来源。
    """
    if credentials is None or not credentials.credentials:
        _log_auth_failure(request, "missing token")
        raise _unauthorized("未提供访问令牌，请在 Authorization 头中携带 Bearer token")

    subject = security.get_token_subject(credentials.credentials)
    if subject is None:
        _log_auth_failure(request, "invalid token")
        raise _unauthorized("访问令牌无效或已过期")

    user = await user_crud.get_by_id(session, subject)
    if user is None:
        _log_auth_failure(request, "user not found")
        raise _unauthorized("访问令牌对应的用户不存在")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
    description=(
        "创建账号并**直接返回令牌**，前端无需再登录一次。\n\n"
        "`password` 上限 72 字节是 bcrypt 的硬限制（超出会抛错，不会被截断）。"
    ),
    responses={
        403: {"description": "邀请码无效（服务端已开启注册验证）"},
        409: {"description": "用户名或邮箱已被占用"},
    },
)
async def register(
    payload: UserRegisterRequest, session: DbSession, request: Request
) -> AuthResponse:
    """注册新用户：先校验邀请码，再校验用户名与邮箱唯一性。"""
    if settings.REGISTRATION_REQUIRE_INVITE:
        provided = (payload.invite_code or "").strip()
        if not provided or await invite_crud.consume_code(session, provided) is None:
            # 只记来源与原因，绝不记录邀请码本身
            logger.warning(
                "注册被拒: reason=invalid_invite_code client=%s", _client_ip(request)
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="邀请码无效"
            )

    if await user_crud.get_by_username(session, payload.username) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"用户名已被占用: {payload.username}",
        )
    if await user_crud.get_by_email(session, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"邮箱已被占用: {payload.email}",
        )

    user = await user_crud.create(
        session,
        username=payload.username,
        email=payload.email,
        password_hash=security.hash_password(payload.password),
    )
    logger.info(
        "注册成功: user=%s id=%s", safe_log_value(user.username), user.id
    )
    return AuthResponse(**to_user_response(user).model_dump(), token=issue_token(user))


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="用户登录",
    description="`username` 支持用户名或邮箱。凭证错误统一返回 401，不区分是哪一个错。",
    responses={401: {"description": "用户名或密码错误"}},
)
async def login(
    payload: UserLoginRequest, session: DbSession, request: Request
) -> AuthResponse:
    """校验凭证并签发令牌。"""
    user = await user_crud.get_by_username(session, payload.username)
    if user is None:
        user = await user_crud.get_by_email(session, payload.username)

    # 用户不存在与密码错误返回同一个提示：避免枚举出哪些用户名已注册。
    if user is None or not security.verify_password(payload.password, user.password_hash):
        # 失败必须留痕（暴力破解审计）；密码本身绝不进日志。
        # 用户名做转义+截断，避免换行伪造日志行、超长输入刷屏。
        logger.warning(
            "登录失败: username=%s client=%s",
            safe_log_value(payload.username),
            _client_ip(request),
        )
        raise _unauthorized("用户名或密码错误")

    logger.info(
        "登录成功: user=%s id=%s", safe_log_value(user.username), user.id
    )
    return AuthResponse(**to_user_response(user).model_dump(), token=issue_token(user))


@router.get(
    "/me",
    response_model=UserResponse,
    summary="获取当前用户",
    description="依据 `Authorization: Bearer <token>` 返回对应账号；令牌无效返回 401。",
    responses={401: {"description": "未提供令牌，或令牌无效/已过期"}},
)
async def me(current_user: CurrentUser) -> UserResponse:
    """返回当前登录用户。"""
    return to_user_response(current_user)
