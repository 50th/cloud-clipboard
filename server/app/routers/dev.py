"""开发/测试辅助路由。

**仅在 `ENABLE_DEV_ROUTES=true` 时注册**（见 `app/main.py`）：
提供把数据恢复为初始种子数据的能力，方便反复手工验证与自动化测试。

⚠️ 该开关**故意与 `DEBUG` 解耦**：调试时可能临时打开 DEBUG，但清库类接口绝不能跟着可用。
第 3 步接入真实数据库后，本路由应改为清空表 + 重新灌入种子数据，且仅允许指向测试库。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.crud import clipboard as clipboard_crud
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/dev", tags=["系统"])


@router.post(
    "/reset",
    response_model=MessageResponse,
    summary="重置数据为种子数据（仅开发环境）",
    description=(
        "清空当前数据并重新灌入 4 条种子数据，用于自动化测试收尾和反复手工验证。\n\n"
        "**⚠️ 第 3 步接入数据库后本接口会变成清库操作**，因此：\n"
        "- 生产环境必须保持 `ENABLE_DEV_ROUTES=false`（此时本路由不注册，返回 404）\n"
        "- 只应指向测试数据库使用"
    ),
)
async def reset_store() -> MessageResponse:
    clipboard_crud.reset_store()
    total = clipboard_crud.count_items()
    return MessageResponse(success=True, message=f"已重置为种子数据，共 {total} 条")
