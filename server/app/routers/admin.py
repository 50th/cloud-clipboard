"""后台管理路由。

全部接口依赖 `AdminUser`（后端强制校验管理员），前端展示判断不承担安全职责。
高危写操作的业务修改与审计在 `crud/admin.py` 的同一事务中完成。
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import admin as admin_crud
from app.crud import share as share_crud
from app.crud import share_setting as share_setting_crud
from app.db.models.admin_audit_log import AdminAuditLog
from app.db.models.invite_code import InviteCode
from app.db.session import get_db
from app.routers.auth import AdminUser
from app.schemas.admin import (
    AdminAuditLogList,
    AdminAuditLogListParams,
    AdminAuditLogResponse,
    AdminClipboardItemList,
    AdminClipboardItemResponse,
    AdminClipboardListParams,
    AdminInviteCodeCreate,
    AdminInviteCodeCreated,
    AdminInviteCodeList,
    AdminInviteCodeListParams,
    AdminInviteCodeResponse,
    AdminInviteCodeUsage,
    AdminInviteCodeUsageList,
    AdminInviteCodeUsageListParams,
    AdminPasswordResetRequest,
    AdminShareAccessLogList,
    AdminShareAccessLogParams,
    AdminShareAccessLogResponse,
    AdminShareList,
    AdminShareListParams,
    AdminShareResponse,
    AdminStatsResponse,
    AdminUserList,
    AdminUserListParams,
    AdminUserResponse,
    AdminUserShareList,
    AdminUserShareListParams,
    AdminUserShareResponse,
    AdminUserUpdate,
)
from app.schemas.clipboard import ClipboardDeleteResponse
from app.schemas.common import ContentType, MessageResponse
from app.schemas.share import ShareSettingsResponse, ShareSettingsUpdate
from app.services import events
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["后台管理"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _to_user_response(row: admin_crud.UserWithStats) -> AdminUserResponse:
    user = row.user
    return AdminUserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        nickname=user.nickname,
        is_admin=user.is_admin,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        item_count=row.item_count,
        last_item_at=row.last_item_at,
        share_limit=user.share_limit,
    )


def _to_clipboard_response(
    row: admin_crud.ClipboardWithUsername,
) -> AdminClipboardItemResponse:
    item = row.item
    return AdminClipboardItemResponse(
        id=str(item.id),
        user_id=str(item.user_id),
        username=row.username,
        title=item.title,
        content_type=ContentType(item.content_type),
        content=item.content,
        preview=item.preview,
        metadata=item.meta,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _to_invite_response(row: InviteCode) -> AdminInviteCodeResponse:
    """把邀请码 ORM 记录转换为响应；明文不在其中。"""
    return AdminInviteCodeResponse(
        id=str(row.id),
        code_hint=row.code_hint,
        label=row.label,
        max_uses=row.max_uses,
        used_count=row.used_count,
        status=admin_crud.invite_code_status(row),
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        last_used_at=row.last_used_at,
        created_at=row.created_at,
    )


def _to_audit_response(entry: AdminAuditLog) -> AdminAuditLogResponse:
    return AdminAuditLogResponse(
        id=str(entry.id),
        admin_id=str(entry.admin_id) if entry.admin_id else None,
        admin_username=entry.admin_username,
        action=entry.action,
        target_type=entry.target_type,
        target_id=str(entry.target_id) if entry.target_id else None,
        detail=entry.detail,
        created_at=entry.created_at,
    )


async def _broadcast(user_id: object, event: str, data: object) -> int:
    """向目标用户广播；失败只记日志，不影响管理操作成功。"""
    try:
        return await manager.send_to_user(str(user_id), event, data)
    except Exception:  # noqa: BLE001 - 推送是尽力而为
        logger.exception("管理端广播失败: event=%s user=%s", event, user_id)
        return 0


@router.get(
    "/stats",
    response_model=AdminStatsResponse,
    summary="后台概览统计",
)
async def get_stats(
    session: DbSession, _current_admin: AdminUser
) -> AdminStatsResponse:
    return AdminStatsResponse(**await admin_crud.get_stats(session))


@router.get(
    "/users",
    response_model=AdminUserList,
    summary="用户分页列表",
)
async def list_users(
    session: DbSession,
    _current_admin: AdminUser,
    params: Annotated[AdminUserListParams, Depends()],
) -> AdminUserList:
    rows, total = await admin_crud.list_users(
        session,
        page=params.page,
        size=params.size,
        search=params.search,
        status=params.status,
        role=params.role,
        sort_by=params.sort_by,
        order=params.order,
    )
    return AdminUserList.build(
        [_to_user_response(row) for row in rows],
        page=params.page,
        size=params.size,
        total=total,
    )


@router.get(
    "/users/{user_id}",
    response_model=AdminUserResponse,
    summary="用户详情",
    responses={404: {"description": "用户不存在"}},
)
async def get_user(
    user_id: uuid.UUID, session: DbSession, _current_admin: AdminUser
) -> AdminUserResponse:
    row = await admin_crud.get_user_with_stats(session, user_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户不存在: {user_id}",
        )
    return _to_user_response(row)


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserResponse,
    summary="修改用户资料 / 状态 / 角色",
    responses={
        400: {"description": "试图禁用或降权当前管理员自己"},
        404: {"description": "用户不存在"},
        409: {"description": "邮箱已被占用"},
    },
)
async def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    session: DbSession,
    current_admin: AdminUser,
) -> AdminUserResponse:
    if user_id == current_admin.id:
        if payload.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能禁用当前管理员账号",
            )
        if payload.is_admin is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能取消当前管理员权限",
            )

    try:
        row = await admin_crud.update_user(session, current_admin, user_id, payload)
    except admin_crud.EmailConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户不存在: {user_id}",
        )

    if not row.user.is_active:
        await manager.close_user(row.user.id)

    logger.warning(
        "admin user update: admin=%s target=%s fields=%s",
        current_admin.id,
        user_id,
        ",".join(sorted(payload.model_dump(exclude_none=True).keys())),
    )
    return _to_user_response(row)


@router.post(
    "/users/{user_id}/reset-password",
    response_model=MessageResponse,
    summary="重置用户密码",
    description=(
        "重置后该用户的全部旧令牌与 WebSocket 连接立即失效。"
        "新密码至少 8 个字符、同时包含字母和数字、不能包含目标用户名。"
    ),
    responses={404: {"description": "用户不存在"}},
)
async def reset_password(
    user_id: uuid.UUID,
    payload: AdminPasswordResetRequest,
    session: DbSession,
    current_admin: AdminUser,
) -> MessageResponse:
    try:
        row = await admin_crud.reset_password(
            session, current_admin, user_id, payload.password
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户不存在: {user_id}",
        )
    await manager.close_user(row.user.id)
    logger.warning(
        "admin reset password: admin=%s target=%s", current_admin.id, user_id
    )
    return MessageResponse(success=True, message="密码已重置，旧登录状态已失效")


@router.delete(
    "/users/{user_id}",
    response_model=MessageResponse,
    summary="删除用户（级联删除剪贴板）",
    responses={
        400: {"description": "不能删除当前管理员自己"},
        404: {"description": "用户不存在"},
    },
)
async def delete_user(
    user_id: uuid.UUID, session: DbSession, current_admin: AdminUser
) -> MessageResponse:
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除当前管理员账号",
        )

    deleted_items = await admin_crud.delete_user(session, current_admin, user_id)
    if deleted_items is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户不存在: {user_id}",
        )

    delivered = await _broadcast(user_id, events.EVENT_CLEARED, {})
    await manager.close_user(user_id)
    logger.warning(
        "admin delete user: admin=%s target=%s items=%d delivered=%d",
        current_admin.id,
        user_id,
        deleted_items,
        delivered,
    )
    return MessageResponse(
        success=True,
        message=f"已删除用户及其 {deleted_items} 条剪贴板",
    )


@router.delete(
    "/users/{user_id}/clipboards",
    response_model=MessageResponse,
    summary="清空指定用户的剪贴板",
    responses={404: {"description": "用户不存在"}},
)
async def clear_user_clipboards(
    user_id: uuid.UUID, session: DbSession, current_admin: AdminUser
) -> MessageResponse:
    deleted = await admin_crud.clear_user_clipboards(
        session, current_admin, user_id
    )
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户不存在: {user_id}",
        )
    delivered = await _broadcast(user_id, events.EVENT_CLEARED, {})
    logger.warning(
        "admin clear clipboards: admin=%s target=%s removed=%d delivered=%d",
        current_admin.id,
        user_id,
        deleted,
        delivered,
    )
    return MessageResponse(
        success=True,
        message=f"已清空 {deleted} 条记录",
    )


@router.get(
    "/users/{user_id}/shares",
    response_model=AdminUserShareList,
    summary="指定用户的分享记录",
    description=(
        "分页查看某位用户的分享记录（不返回 token / 链接）。"
        "分享撤销等管理操作不在本期范围。"
    ),
    responses={404: {"description": "用户不存在"}},
)
async def list_user_shares(
    user_id: uuid.UUID,
    session: DbSession,
    _current_admin: AdminUser,
    params: Annotated[AdminUserShareListParams, Depends()],
) -> AdminUserShareList:
    if await admin_crud.get_user_with_stats(session, user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户不存在: {user_id}",
        )
    rows, total = await share_crud.list_shares(
        session,
        user_id,
        page=params.page,
        size=params.size,
        status=params.status,
        item_id=None,
    )
    return AdminUserShareList.build(
        [
            AdminUserShareResponse(
                id=str(share.id),
                item_id=str(share.item_id),
                mode=share.mode,
                status=share_crud.share_status(share),
                title=share.title,
                password_protected=share.password_hash is not None,
                expires_at=share.expires_at,
                max_views=share.max_views,
                view_count=share.view_count,
                remaining_views=share_crud.remaining_views(share),
                created_at=share.created_at,
                revoked_at=share.revoked_at,
            )
            for share in rows
        ],
        page=params.page,
        size=params.size,
        total=total,
    )


@router.get(
    "/shares",
    response_model=AdminShareList,
    summary="全局分享分页列表",
    description=(
        "管理员查看全站分享；支持按状态与分享者用户名筛选。"
        "不返回 token / 链接；分享撤销等管理操作不在本期范围。"
    ),
)
async def list_all_shares(
    session: DbSession,
    _current_admin: AdminUser,
    params: Annotated[AdminShareListParams, Depends()],
) -> AdminShareList:
    rows, total = await share_crud.list_all_shares(
        session,
        page=params.page,
        size=params.size,
        status=params.status,
        username=params.username,
    )
    return AdminShareList.build(
        [
            AdminShareResponse(
                id=str(row.share.id),
                item_id=str(row.share.item_id),
                title=row.share.title,
                owner_id=str(row.share.user_id),
                owner_username=row.owner_username,
                mode=row.share.mode,
                status=share_crud.share_status(row.share),
                password_protected=row.share.password_hash is not None,
                view_count=row.share.view_count,
                max_views=row.share.max_views,
                remaining_views=share_crud.remaining_views(row.share),
                expires_at=row.share.expires_at,
                created_at=row.share.created_at,
                revoked_at=row.share.revoked_at,
            )
            for row in rows
        ],
        page=params.page,
        size=params.size,
        total=total,
    )


@router.get(
    "/clipboards",
    response_model=AdminClipboardItemList,
    summary="全局剪贴板分页列表",
)
async def list_clipboards(
    session: DbSession,
    _current_admin: AdminUser,
    params: Annotated[AdminClipboardListParams, Depends()],
) -> AdminClipboardItemList:
    rows, total = await admin_crud.list_clipboards(
        session,
        page=params.page,
        size=params.size,
        user_id=params.user_id,
        username=params.username,
        search=params.search,
        content_type=params.content_type,
        sort_by=params.sort_by,
        order=params.order,
    )
    return AdminClipboardItemList.build(
        [_to_clipboard_response(row) for row in rows],
        page=params.page,
        size=params.size,
        total=total,
    )


@router.get(
    "/clipboards/{item_id}",
    response_model=AdminClipboardItemResponse,
    summary="剪贴板详情（含完整正文）",
    responses={404: {"description": "剪贴板项不存在"}},
)
async def get_clipboard(
    item_id: uuid.UUID, session: DbSession, _current_admin: AdminUser
) -> AdminClipboardItemResponse:
    row = await admin_crud.get_clipboard(session, item_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"剪贴板项不存在: {item_id}",
        )
    return _to_clipboard_response(row)


@router.delete(
    "/clipboards/{item_id}",
    response_model=ClipboardDeleteResponse,
    summary="删除任意用户的单条剪贴板",
    responses={404: {"description": "剪贴板项不存在"}},
)
async def delete_clipboard(
    item_id: uuid.UUID, session: DbSession, current_admin: AdminUser
) -> ClipboardDeleteResponse:
    owner_id = await admin_crud.delete_clipboard(session, current_admin, item_id)
    if owner_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"剪贴板项不存在: {item_id}",
        )
    delivered = await _broadcast(
        owner_id, events.EVENT_DELETED, events.deleted_payload(item_id)
    )
    logger.warning(
        "admin delete clipboard: admin=%s item=%s owner=%s delivered=%d",
        current_admin.id,
        item_id,
        owner_id,
        delivered,
    )
    return ClipboardDeleteResponse(success=True, message="删除成功", id=str(item_id))


@router.get(
    "/audit-logs",
    response_model=AdminAuditLogList,
    summary="管理员操作审计列表",
)
async def list_audit_logs(
    session: DbSession,
    _current_admin: AdminUser,
    params: Annotated[AdminAuditLogListParams, Depends()],
) -> AdminAuditLogList:
    rows, total = await admin_crud.list_audit_logs(
        session,
        page=params.page,
        size=params.size,
        admin_username=params.admin_username,
        action=params.action,
        target_id=params.target_id,
        start=params.start,
        end=params.end,
    )
    return AdminAuditLogList.build(
        [_to_audit_response(row) for row in rows],
        page=params.page,
        size=params.size,
        total=total,
    )


@router.get(
    "/invite-codes",
    response_model=AdminInviteCodeList,
    summary="邀请码分页列表",
)
async def list_invite_codes(
    session: DbSession,
    _current_admin: AdminUser,
    params: Annotated[AdminInviteCodeListParams, Depends()],
) -> AdminInviteCodeList:
    rows, total = await admin_crud.list_invite_codes(
        session,
        page=params.page,
        size=params.size,
        status=params.status,
    )
    return AdminInviteCodeList.build(
        [_to_invite_response(row) for row in rows],
        page=params.page,
        size=params.size,
        total=total,
    )


@router.post(
    "/invite-codes",
    response_model=AdminInviteCodeCreated,
    status_code=status.HTTP_201_CREATED,
    summary="生成邀请码",
    description=(
        "`max_uses` 必填，表示最大使用次数，用尽后邀请码自动失效。\n\n"
        "**明文只在本次响应中返回一次**，数据库只保存 SHA-256 哈希。"
    ),
)
async def create_invite_code(
    payload: AdminInviteCodeCreate,
    session: DbSession,
    current_admin: AdminUser,
) -> AdminInviteCodeCreated:
    plaintext, row = await admin_crud.create_invite_code(
        session,
        current_admin,
        label=(payload.label or "").strip() or None,
        max_uses=payload.max_uses,
        expires_days=payload.expires_days,
    )
    logger.warning(
        "admin create invite: admin=%s hint=%s max_uses=%d expires_days=%d",
        current_admin.id,
        row.code_hint,
        payload.max_uses,
        payload.expires_days,
    )
    return AdminInviteCodeCreated(
        **_to_invite_response(row).model_dump(),
        code=plaintext,
    )


@router.post(
    "/invite-codes/{code_id}/revoke",
    response_model=AdminInviteCodeResponse,
    summary="撤销邀请码",
    responses={404: {"description": "邀请码不存在"}},
)
async def revoke_invite_code(
    code_id: uuid.UUID,
    session: DbSession,
    current_admin: AdminUser,
) -> AdminInviteCodeResponse:
    row = await admin_crud.revoke_invite_code(session, current_admin, code_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"邀请码不存在: {code_id}",
        )
    logger.warning(
        "admin revoke invite: admin=%s hint=%s", current_admin.id, row.code_hint
    )
    return _to_invite_response(row)


@router.get(
    "/invite-codes/{code_id}/usages",
    response_model=AdminInviteCodeUsageList,
    summary="邀请码使用详情",
    description="列出通过该邀请码注册的用户，按注册时间倒序。",
    responses={404: {"description": "邀请码不存在"}},
)
async def list_invite_code_usages(
    code_id: uuid.UUID,
    session: DbSession,
    _current_admin: AdminUser,
    params: Annotated[AdminInviteCodeUsageListParams, Depends()],
) -> AdminInviteCodeUsageList:
    code = await session.get(InviteCode, code_id)
    if code is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"邀请码不存在: {code_id}",
        )
    rows, total = await admin_crud.list_invite_code_usages(
        session,
        code_id,
        page=params.page,
        size=params.size,
    )
    return AdminInviteCodeUsageList.build(
        [
            AdminInviteCodeUsage(
                user_id=str(user.id),
                username=user.username,
                email=user.email,
                registered_at=user.created_at,
            )
            for user in rows
        ],
        page=params.page,
        size=params.size,
        total=total,
    )


@router.get(
    "/settings/shares",
    response_model=ShareSettingsResponse,
    summary="读取分享限额设置",
    description="返回每用户有效分享上限与最近更新人。普通用户返回 403。",
)
async def get_share_settings(
    session: DbSession, _current_admin: AdminUser
) -> ShareSettingsResponse:
    state = await share_setting_crud.get_share_settings_state(session)
    return ShareSettingsResponse(
        user_share_limit=state.user_share_limit,
        updated_at=state.updated_at,
        updated_by=str(state.updated_by) if state.updated_by else None,
        updated_by_username=state.updated_by_username,
    )


@router.put(
    "/settings/shares",
    response_model=ShareSettingsResponse,
    summary="更新分享限额设置",
    description=(
        "更新后立即生效：新创建分享按新限额校验，已有分享不会因调低限额被删除。\n\n"
        "更新与审计 `settings.share_quota.update` 同事务提交，审计失败整体回滚。"
    ),
    responses={422: {"description": "限额超出 1–10000 范围"}},
)
async def update_share_settings(
    payload: ShareSettingsUpdate,
    session: DbSession,
    current_admin: AdminUser,
) -> ShareSettingsResponse:
    await share_setting_crud.update_share_settings(
        session, payload.user_share_limit, current_admin
    )
    state = await share_setting_crud.get_share_settings_state(session)
    logger.warning(
        "admin update share quota: admin=%s limit=%d",
        current_admin.id,
        payload.user_share_limit,
    )
    return ShareSettingsResponse(
        user_share_limit=state.user_share_limit,
        updated_at=state.updated_at,
        updated_by=str(state.updated_by) if state.updated_by else None,
        updated_by_username=state.updated_by_username,
    )


@router.get(
    "/share-access-logs",
    response_model=AdminShareAccessLogList,
    summary="分享访问记录（成功 + 失败）",
    description=(
        "管理员专用。失败记录只有本接口可见；用户端「我的分享」只返回成功记录。\n\n"
        "支持按结果、分享、分享者用户名与时间范围筛选，按访问时间倒序。"
    ),
)
async def list_share_access_logs(
    session: DbSession,
    _current_admin: AdminUser,
    params: Annotated[AdminShareAccessLogParams, Depends()],
) -> AdminShareAccessLogList:
    rows, total = await share_crud.list_all_access_logs(
        session,
        page=params.page,
        size=params.size,
        result=params.result.value,
        share_id=params.share_id,
        username=params.username,
        start=params.start,
        end=params.end,
    )
    return AdminShareAccessLogList.build(
        [
            AdminShareAccessLogResponse(
                id=str(row.log.id),
                share_id=str(row.log.share_id),
                share_title=row.share_title,
                owner_id=str(row.owner_id),
                owner_username=row.owner_username,
                accessed_at=row.log.accessed_at,
                result=row.log.result,
                ip=str(row.log.ip) if row.log.ip is not None else None,
                user_agent=row.log.user_agent,
            )
            for row in rows
        ],
        page=params.page,
        size=params.size,
        total=total,
    )
