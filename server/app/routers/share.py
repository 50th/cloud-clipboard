"""剪贴板分享路由：登录态管理 + 公开只读访问。

路由层只做参数校验与调用，数据逻辑在 `app/crud/share.py`。
公开接口**不依赖登录态**，也不返回 token 以外的分享者信息。

安全要点：
- 公开接口统一带 `X-Robots-Tag` / `Cache-Control: no-store` / `Referrer-Policy`；
- 日志只记 user_id / share_id / item_id / 模式 / 是否设置密码 / 结果，
  绝不记 token、正文、密码；
- IP 优先取 Nginx 设置的 `X-Real-IP`，不信任客户端可伪造的 `X-Forwarded-For`。
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.crud import clipboard as clipboard_crud
from app.crud import share as share_crud
from app.db.models.share import ClipboardShare
from app.db.models.user import User
from app.db.session import get_db
from app.routers.auth import CurrentUser
from app.schemas.common import ContentType, MessageResponse
from app.schemas.share import (
    ClipboardShareCreate,
    ClipboardShareList,
    ClipboardShareListParams,
    ClipboardShareResponse,
    PublicShareAccessRequest,
    PublicShareContent,
    PublicShareMeta,
    ShareAccessLogList,
    ShareAccessLogListParams,
    ShareAccessLogResponse,
    ShareAccessResult,
    ShareMode,
    ShareStatus,
)
from app.services import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clipboard", tags=["剪贴板分享"])
public_router = APIRouter(prefix="/public/shares", tags=["公开分享"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

# 公开接口响应头（隐私最佳实践，不作为内容保密边界）
PUBLIC_HEADERS = {
    "X-Robots-Tag": "noindex, nofollow",
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
}

META_RATE_LIMIT = 60  # 次 / 分钟 / IP
ACCESS_RATE_LIMIT = 30  # 次 / 分钟 / IP
PASSWORD_RATE_LIMIT = 5  # 次 / 5 分钟 / IP + token


def _client_ip(request: Request) -> str:
    """客户端 IP：优先 `X-Real-IP`，缺失时取连接地址。"""
    forwarded = (request.headers.get("x-real-ip") or "").strip()
    if forwarded:
        return forwarded
    client = request.client
    return client.host if client is not None else "unknown"


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _to_share_response(share: ClipboardShare) -> ClipboardShareResponse:
    return ClipboardShareResponse(
        id=str(share.id),
        item_id=str(share.item_id),
        mode=ShareMode(share.mode),
        status=share_crud.share_status(share),
        title=share.title,
        token=share.token,
        url=share_crud.build_share_url(share.token),
        password_protected=share.password_hash is not None,
        expires_at=share.expires_at,
        max_views=share.max_views,
        view_count=share.view_count,
        remaining_views=share_crud.remaining_views(share),
        created_at=share.created_at,
        last_viewed_at=share.last_viewed_at,
    )


def _share_gone(detail: str = "分享已失效") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=detail,
        headers=dict(PUBLIC_HEADERS),
    )


def _share_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="分享不存在",
        headers=dict(PUBLIC_HEADERS),
    )


def _check_public_rate_limit(key: str, *, limit: int, window_seconds: int) -> None:
    """限流异常也要带公开接口的响应头。"""
    try:
        rate_limit.check_rate_limit(
            key, limit=limit, window_seconds=window_seconds
        )
    except HTTPException as exc:
        exc.headers = {**(exc.headers or {}), **PUBLIC_HEADERS}
        raise


async def _record_failure(
    session: AsyncSession,
    share: ClipboardShare,
    result: ShareAccessResult,
    ip: str,
    user_agent: str | None,
) -> None:
    """失败尝试写入记录；记录失败只写应用日志，不改变原响应。"""
    await share_crud.record_access_log(
        session,
        share,
        result=result,
        ip=share_crud.normalize_ip(ip),
        user_agent=user_agent,
    )


@router.post(
    "/items/{id}/shares",
    response_model=ClipboardShareResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建分享",
    description=(
        "为一条文字剪贴板生成受控只读链接。\n\n"
        "- `mode=snapshot` 复制当前正文；`mode=live` 跟随原记录最新内容\n"
        "- 默认有效期 7 天，可选 1 小时 / 1 天 / 30 天\n"
        "- 密码可选（4–24 字符），查看次数可选（1–10000）\n"
        "- 每用户有效分享数受全局限额约束，超限返回 409"
    ),
    responses={
        400: {"description": "阶段一仅支持文字分享"},
        404: {"description": "剪贴板项不存在或不属于当前用户"},
        409: {"description": "有效分享数达到上限"},
    },
)
async def create_share(
    id: str,
    payload: ClipboardShareCreate,
    session: DbSession,
    current_user: CurrentUser,
) -> ClipboardShareResponse:
    item = await clipboard_crud.get_item(session, current_user.id, id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"剪贴板项不存在: {id}",
        )
    if item.content_type != ContentType.TEXT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="阶段一仅支持文字分享",
        )

    try:
        share = await share_crud.create_share(
            session, current_user.id, item, payload
        )
    except share_crud.ItemShareLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"同一条记录最多 {exc.limit} 个有效分享，请先撤销旧链接",
        ) from exc
    except share_crud.ShareLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"分享数量已达上限（{exc.limit} 条），请先撤销或等待过期",
        ) from exc

    logger.info(
        "share create: user=%s share=%s item=%s mode=%s has_password=%s max_views=%s",
        current_user.id,
        share.id,
        item.id,
        share.mode,
        share.password_hash is not None,
        share.max_views,
    )
    return _to_share_response(share)


@router.get(
    "/shares",
    response_model=ClipboardShareList,
    summary="我的分享",
    description=(
        "分页查询当前用户的分享。支持 `status` 与 `item_id` 筛选；"
        "删除原记录前可用 `item_id` + `status=active` 统计有效分享数。"
    ),
)
async def list_shares(
    session: DbSession,
    current_user: CurrentUser,
    params: Annotated[ClipboardShareListParams, Depends()],
) -> ClipboardShareList:
    rows, total = await share_crud.list_shares(
        session,
        current_user.id,
        page=params.page,
        size=params.size,
        status=params.status,
        item_id=params.item_id,
        search=params.search,
    )
    return ClipboardShareList.build(
        [_to_share_response(row) for row in rows],
        page=params.page,
        size=params.size,
        total=total,
    )


@router.delete(
    "/shares/{id}",
    response_model=MessageResponse,
    summary="撤销分享",
    description="撤销后链接立即失效；重复撤销幂等。只能撤销本人的分享。",
    responses={404: {"description": "分享不存在或不属于当前用户"}},
)
async def revoke_share(
    id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
) -> MessageResponse:
    if not await share_crud.revoke_share(session, current_user.id, id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="分享不存在"
        )
    logger.warning("share revoke: user=%s share=%s", current_user.id, id)
    return MessageResponse(success=True, message="已撤销分享")


@router.get(
    "/shares/{id}/access-logs",
    response_model=ShareAccessLogList,
    summary="我的分享访问记录",
    description=(
        "分页查询某条分享的成功访问记录，按访问时间倒序。"
        "**失败记录只有管理员能查看**。IP 已脱敏。"
    ),
    responses={404: {"description": "分享不存在或不属于当前用户"}},
)
async def list_access_logs(
    id: uuid.UUID,
    session: DbSession,
    current_user: CurrentUser,
    params: Annotated[ShareAccessLogListParams, Depends()],
) -> ShareAccessLogList:
    share = await share_crud.get_share(session, current_user.id, id)
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="分享不存在"
        )
    rows, total = await share_crud.list_access_logs(
        session,
        share.id,
        page=params.page,
        size=params.size,
        include_failures=False,
    )
    return ShareAccessLogList.build(
        [
            ShareAccessLogResponse(
                id=str(row.id),
                accessed_at=row.accessed_at,
                result=ShareAccessResult(row.result),
                ip_masked=share_crud.mask_ip(row.ip),
                user_agent=(row.user_agent or "")[: share_crud.OWNER_UA_PREVIEW_LENGTH]
                or None,
            )
            for row in rows
        ],
        page=params.page,
        size=params.size,
        total=total,
    )


@public_router.get(
    "/{token}",
    response_model=PublicShareMeta,
    summary="公开分享元信息",
    description="不返回正文、不计数。有密码时 `title` 为 null。",
    responses={
        404: {"description": "分享不存在"},
        410: {"description": "分享已失效"},
        429: {"description": "请求过于频繁"},
    },
)
async def public_meta(
    token: str,
    session: DbSession,
    request: Request,
    response: Response,
) -> PublicShareMeta:
    response.headers.update(PUBLIC_HEADERS)
    ip = _client_ip(request)
    _check_public_rate_limit(
        f"share:meta:{ip}", limit=META_RATE_LIMIT, window_seconds=60
    )

    share = await share_crud.get_by_token(session, token)
    if share is None:
        raise _share_not_found()

    owner = await session.get(User, share.user_id)
    if owner is None or not owner.is_active:
        raise _share_gone()
    if share_crud.share_status(share) is not ShareStatus.ACTIVE:
        raise _share_gone()

    return PublicShareMeta(
        title=None if share.password_hash is not None else share.title,
        mode=ShareMode(share.mode),
        content_type=ContentType(share.content_type),
        password_required=share.password_hash is not None,
        expires_at=share.expires_at,
        remaining_views=share_crud.remaining_views(share),
    )


@public_router.post(
    "/{token}/access",
    response_model=PublicShareContent,
    summary="查看分享正文",
    description=(
        "**唯一计数入口**：只有用户主动查看或提交正确密码时才调用。\n\n"
        "页面加载、刷新、元信息查询均不计数。失败尝试会写入访问记录，"
        "但只有管理员能查看失败记录。"
    ),
    responses={
        403: {"description": "密码错误或未提供"},
        404: {"description": "分享不存在"},
        410: {"description": "分享已失效"},
        429: {"description": "尝试过于频繁"},
    },
)
async def public_access(
    token: str,
    payload: PublicShareAccessRequest,
    session: DbSession,
    request: Request,
    response: Response,
) -> PublicShareContent:
    response.headers.update(PUBLIC_HEADERS)
    ip = _client_ip(request)
    ua = _user_agent(request)
    _check_public_rate_limit(
        f"share:access:{ip}", limit=ACCESS_RATE_LIMIT, window_seconds=60
    )

    share = await share_crud.get_by_token(session, token)
    if share is None:
        raise _share_not_found()

    owner = await session.get(User, share.user_id)
    if owner is None or not owner.is_active:
        await _record_failure(
            session, share, ShareAccessResult.OWNER_DISABLED, ip, ua
        )
        raise _share_gone()

    current_status = share_crud.share_status(share)
    if current_status is not ShareStatus.ACTIVE:
        result = {
            ShareStatus.EXPIRED: ShareAccessResult.EXPIRED,
            ShareStatus.REVOKED: ShareAccessResult.REVOKED,
            ShareStatus.EXHAUSTED: ShareAccessResult.EXHAUSTED,
        }[current_status]
        await _record_failure(session, share, result, ip, ua)
        raise _share_gone()

    if share.password_hash is not None:
        password_key = f"share:password:{ip}:{share.id}"
        _check_public_rate_limit(
            password_key, limit=PASSWORD_RATE_LIMIT, window_seconds=300
        )
        if not payload.password or not verify_password(
            payload.password, share.password_hash
        ):
            await _record_failure(
                session, share, ShareAccessResult.PASSWORD_FAILED, ip, ua
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="密码错误或未提供",
                headers=dict(PUBLIC_HEADERS),
            )
        rate_limit.clear_rate_limit(password_key)

    resolved = await share_crud.resolve_content(session, share)
    if resolved is None:
        # 跟随模式的原记录已被删除（正常情况下外键会级联删除分享）
        raise _share_not_found()

    title, content, content_type = resolved
    consumed = await share_crud.consume_view(
        session,
        share,
        ip=share_crud.normalize_ip(ip),
        user_agent=ua,
    )
    if consumed is None:
        # 并发下刚被撤销 / 过期 / 用尽：按当前状态补一条失败记录
        latest = share_crud.share_status(share)
        result = {
            ShareStatus.EXPIRED: ShareAccessResult.EXPIRED,
            ShareStatus.REVOKED: ShareAccessResult.REVOKED,
            ShareStatus.EXHAUSTED: ShareAccessResult.EXHAUSTED,
        }.get(latest, ShareAccessResult.EXHAUSTED)
        await _record_failure(session, share, result, ip, ua)
        raise _share_gone()

    view_count, max_views = consumed
    remaining = (
        None if max_views is None else max(0, max_views - view_count)
    )
    logger.info(
        "share access: share=%s result=success view_count=%s",
        share.id,
        view_count,
    )
    return PublicShareContent(
        title=title,
        content=content,
        content_type=ContentType(content_type),
        created_at=share.created_at,
        expires_at=share.expires_at,
        remaining_views=remaining,
    )
