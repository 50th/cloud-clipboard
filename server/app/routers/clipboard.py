"""剪贴板路由。

路由层只做参数校验与调用，业务/数据逻辑在 `app/crud/`（AGENT.md 第 8 节）。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import clipboard as clipboard_crud
from app.db.models.clipboard import ClipboardItem
from app.db.session import get_db
from app.routers.auth import CurrentUser
from app.schemas.clipboard import (
    ClipboardDeleteResponse,
    ClipboardItemCreate,
    ClipboardItemList,
    ClipboardItemResponse,
    ClipboardItemUpdate,
    ClipboardListParams,
)
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/clipboard", tags=["剪贴板"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def to_item_response(item: ClipboardItem) -> ClipboardItemResponse:
    """把 ORM 对象转换为对外响应模型。**content_hash 不外露**。"""
    return ClipboardItemResponse(
        id=str(item.id),
        user_id=str(item.user_id),
        title=item.title,
        content_type=item.content_type,
        content=item.content,
        preview=item.preview,
        metadata=item.meta,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def _get_owned_item(
    session: AsyncSession, user_id: object, item_id: str
) -> ClipboardItem:
    """取出属于当前用户的剪贴板项，否则 404。"""
    item = await clipboard_crud.get_item(session, user_id, item_id)  # type: ignore[arg-type]
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"剪贴板项不存在: {item_id}",
        )
    return item


@router.post(
    "/items",
    response_model=ClipboardItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建剪贴板项",
    description=(
        "提交文字内容。`title` 留空时由服务端自动生成（`<用户名> · <月-日 时:分>`），"
        "时间按 `timezone`（IANA 时区名，前端会传浏览器时区）展示，例如 `demo · 10-05 21:56`。\n\n"
        "**已内置内容去重**：同一用户提交相同 `content` 时不创建新记录，"
        "只更新 `updated_at`；此时仅当显式传了 `title` 才覆盖标题"
        "（第 6 步对应广播 `clipboard.updated`）。"
    ),
)
async def create_item(
    payload: ClipboardItemCreate,
    session: DbSession,
    current_user: CurrentUser,
) -> ClipboardItemResponse:
    item, _created = await clipboard_crud.create_item(
        session,
        current_user.id,
        payload,
        username=current_user.username,
    )
    return to_item_response(item)


@router.get(
    "/items",
    response_model=ClipboardItemList,
    summary="获取剪贴板列表",
    description="支持分页、按 `content_type` 筛选、按**标题或内容**关键字搜索与排序。",
)
async def list_items(
    session: DbSession,
    current_user: CurrentUser,
    params: Annotated[ClipboardListParams, Depends()],
) -> ClipboardItemList:
    rows, total = await clipboard_crud.list_items(
        session,
        current_user.id,
        page=params.page,
        size=params.size,
        content_type=params.content_type,
        search=params.search,
        sort_by=params.sort_by,
        order=params.order,
    )
    return ClipboardItemList.build(
        [to_item_response(item) for item in rows],
        page=params.page,
        size=params.size,
        total=total,
    )


@router.get(
    "/items/{id}",
    response_model=ClipboardItemResponse,
    summary="获取剪贴板详情",
    responses={404: {"description": "剪贴板项不存在或不属于当前用户"}},
)
async def get_item(
    id: str, session: DbSession, current_user: CurrentUser
) -> ClipboardItemResponse:
    item = await _get_owned_item(session, current_user.id, id)
    return to_item_response(item)


@router.patch(
    "/items/{id}",
    response_model=ClipboardItemResponse,
    summary="更新剪贴板项",
    description=(
        "只更新显式传入的字段。\n\n"
        "**用途：自动保存复用同一条草稿记录**——打字过程中每隔一段时间保存一次，"
        "而不是每个中间态都新建一行。\n\n"
        "内容变化且未传 `title` 时，标题会按更新时刻与 `timezone` 重新生成。"
    ),
    responses={404: {"description": "剪贴板项不存在或不属于当前用户"}},
)
async def update_item(
    id: str,
    payload: ClipboardItemUpdate,
    session: DbSession,
    current_user: CurrentUser,
) -> ClipboardItemResponse:
    item = await clipboard_crud.update_item(
        session,
        current_user.id,
        id,
        payload,
        username=current_user.username,
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"剪贴板项不存在: {id}",
        )
    return to_item_response(item)


@router.delete(
    "/items/{id}",
    response_model=ClipboardDeleteResponse,
    summary="删除单条剪贴板项",
    responses={404: {"description": "剪贴板项不存在或不属于当前用户"}},
)
async def delete_item(
    id: str, session: DbSession, current_user: CurrentUser
) -> ClipboardDeleteResponse:
    await _get_owned_item(session, current_user.id, id)
    await clipboard_crud.delete_item(session, current_user.id, id)
    return ClipboardDeleteResponse(success=True, message="删除成功", id=id)


@router.delete(
    "/items",
    response_model=MessageResponse,
    summary="清空剪贴板",
    description="删除当前用户的全部剪贴板项（第 5 步对应广播 `clipboard.cleared`）。",
)
async def clear_items(session: DbSession, current_user: CurrentUser) -> MessageResponse:
    removed = await clipboard_crud.clear_items(session, current_user.id)
    return MessageResponse(success=True, message=f"已清空 {removed} 条记录")
