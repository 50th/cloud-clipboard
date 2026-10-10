"""开发/测试辅助路由。

**仅在 `ENABLE_DEV_ROUTES=true` 时注册**（见 `app/main.py`）：
提供把数据恢复为初始种子数据、以及数据库连通性探测的能力。

⚠️ 该开关**故意与 `DEBUG` 解耦**：调试时可能临时打开 DEBUG，但清库类接口绝不能跟着可用。
**本路由的 `/dev/reset` 会删除数据**，只应指向本地开发库或测试库。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import clipboard as clipboard_crud
from app.crud import user as user_crud
from app.db.session import get_db, ping
from app.schemas.clipboard import ClipboardItemCreate
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/dev", tags=["系统"])

# 种子数据：与第 1 步的假数据保持一致，便于 Web 端对照
SEED_ITEMS: list[tuple[str, str]] = [
    ("FastAPI 官方教程", "https://fastapi.tiangolo.com/tutorial/"),
    ("后端依赖安装命令", "pip install fastapi uvicorn[standard]"),
    (
        "阶段一范围备忘",
        "云剪贴板阶段一：文字内容的上传、查询、删除 + WebSocket 实时同步 + JWT 认证 + 内容去重。",
    ),
    ("提交规范示例", 'git commit -m "feat: 新增 WebSocket 广播"'),
]


@router.post(
    "/reset",
    response_model=MessageResponse,
    summary="重置为种子数据（⚠️ 会删除数据）",
    description=(
        "删除演示用户的全部剪贴板项，并重新写入 4 条种子数据。\n\n"
        "**仅用于本地开发与自动化测试收尾**：\n"
        "- 生产环境必须保持 `ENABLE_DEV_ROUTES=false`（此时本路由不注册，返回 404）\n"
        "- 只应指向开发库或测试库，绝不要指向生产库"
    ),
)
async def reset_store(session: AsyncSession = Depends(get_db)) -> MessageResponse:
    # reset_password=True：本地重置后演示账号始终能用配置里的口令登录，
    # 避免"改了密码就再进不去"的死角。
    user = await user_crud.ensure_demo_user(session, reset_password=True)
    await clipboard_crud.clear_items(session, user.id)
    for title, content in SEED_ITEMS:
        await clipboard_crud.create_item(
            session,
            user.id,
            ClipboardItemCreate(content=content, title=title),
            username=user.username,
        )
    total = await clipboard_crud.count_items(session, user.id)
    return MessageResponse(success=True, message=f"已重置为种子数据，共 {total} 条")


@router.get(
    "/db",
    summary="数据库连通性探测",
    description="返回当前连接的数据库名与 PostgreSQL 版本，用于确认后端连的是哪个库。",
)
async def db_info() -> dict[str, str]:
    return await ping()
