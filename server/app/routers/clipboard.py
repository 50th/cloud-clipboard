"""剪贴板路由 —— 假数据实现。

路由层只做参数校验与调用，业务逻辑在 `app/crud/`；
第 3 步把 crud 换成数据库实现，路由无需改动。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.crud import clipboard as clipboard_crud
from app.routers.auth import CurrentUser
from app.schemas.clipboard import (
    ClipboardDeleteResponse,
    ClipboardItemCreate,
    ClipboardItemList,
    ClipboardItemResponse,
    ClipboardListParams,
)
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/clipboard", tags=["剪贴板"])


def _get_owned_item(user_id: str, item_id: str) -> ClipboardItemResponse:
    """取出属于当前用户的剪贴板项，否则 404。"""
    item = clipboard_crud.get_item(user_id, item_id)
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
        "提交文字内容。`title` 留空时由服务端自动生成（`<用户名> · <月-日 时:分>`）。\n\n"
        "**已内置内容去重**：同一用户提交相同 `content` 时不创建新记录，"
        "只更新 `updated_at`；此时仅当显式传了 `title` 才覆盖标题"
        "（第 6 步对应广播 `clipboard.updated`）。"
    ),
)
async def create_item(
    payload: ClipboardItemCreate,
    current_user: CurrentUser,
) -> ClipboardItemResponse:
    item, _created = clipboard_crud.create_item(
        current_user.id,
        payload,
        username=current_user.username,
    )
    return clipboard_crud.to_response(item)


@router.get(
    "/items",
    response_model=ClipboardItemList,
    summary="获取剪贴板列表",
    description="支持分页、按 `content_type` 筛选、按**标题或内容**关键字搜索与排序。",
)
async def list_items(
    current_user: CurrentUser,
    params: Annotated[ClipboardListParams, Depends()],
) -> ClipboardItemList:
    rows, total = clipboard_crud.list_items(
        current_user.id,
        page=params.page,
        size=params.size,
        content_type=params.content_type,
        search=params.search,
        sort_by=params.sort_by,
        order=params.order,
    )
    return ClipboardItemList.build(
        [clipboard_crud.to_response(item) for item in rows],
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
async def get_item(id: str, current_user: CurrentUser) -> ClipboardItemResponse:
    return clipboard_crud.to_response(_get_owned_item(current_user.id, id))


@router.delete(
    "/items/{id}",
    response_model=ClipboardDeleteResponse,
    summary="删除单条剪贴板项",
    responses={404: {"description": "剪贴板项不存在或不属于当前用户"}},
)
async def delete_item(id: str, current_user: CurrentUser) -> ClipboardDeleteResponse:
    _get_owned_item(current_user.id, id)
    clipboard_crud.delete_item(current_user.id, id)
    return ClipboardDeleteResponse(success=True, message="删除成功", id=id)


@router.delete(
    "/items",
    response_model=MessageResponse,
    summary="清空剪贴板",
    description="删除当前用户的全部剪贴板项（第 5 步对应广播 `clipboard.cleared`）。",
)
async def clear_items(current_user: CurrentUser) -> MessageResponse:
    removed = clipboard_crud.clear_items(current_user.id)
    return MessageResponse(success=True, message=f"已清空 {removed} 条记录")
