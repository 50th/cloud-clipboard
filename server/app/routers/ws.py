"""WebSocket 端点：剪贴板实时同步。

协议见 `docs/ws-protocol.md`（事件表、信封结构、心跳、重连约定）。

**鉴权是幂等的**：token 缺失/无效/用户不存在一律关闭连接并返回关闭码 `4401`。
注意：`websocket.headers` 与 `websocket.query_params` 都是按首次访问缓存的，
若将来新增依赖去读请求头，必须用更早的中间件实现，否则会拿到空字典。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core import security
from app.core.logging_utils import scrub_scope_token
from app.crud import user as user_crud
from app.db.session import get_session_factory
from app.services import events
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clipboard", tags=["剪贴板"])

# 自定义关闭码：4401 = 未授权（与 HTTP 401 对应）
CLOSE_UNAUTHORIZED = 4401


async def _authenticate(token: str | None) -> str | None:
    """校验 token，返回用户 id 字符串；无效时返回 None。"""
    if not token:
        return None
    subject = security.get_token_subject(token)
    if subject is None:
        return None
    # 令牌有效但用户可能已被删除，同样拒绝
    factory = get_session_factory()
    async with factory() as session:
        user = await user_crud.get_by_id(session, subject)
    return str(user.id) if user is not None else None


@router.websocket("/ws")
async def clipboard_ws(
    websocket: WebSocket,
    token: str | None = Query(None, description="JWT 访问令牌"),
) -> None:
    """剪贴板实时同步端点。

    先 `accept()` 再校验：这样客户端能收到明确的关闭码 `4401`，
    而不是一个笼统的握手失败（浏览器里只能看到 code 1006，难以排查）。
    """
    # ⚠️ 必须在最前面：把 token 从 ASGI scope 里抹掉，否则访问日志会明文记录它。
    # 此时 Query 已把 token 解析成入参，改写 scope 不影响鉴权。
    scrub_scope_token(websocket.scope)

    await websocket.accept()

    user_id = await _authenticate(token)
    if user_id is None:
        await websocket.close(code=CLOSE_UNAUTHORIZED, reason="invalid or missing token")
        return

    await manager.connect(user_id, websocket)
    logger.info("ws connected: user=%s connections=%d", user_id, manager.connection_count())

    try:
        while True:
            # 客户端只会发心跳；文本帧解析失败也不该断开连接（可能是代理发的噪声）
            message = await websocket.receive_text()
            if '"ping"' in message:
                await manager.send_personal(websocket, events.EVENT_PONG, {})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(user_id, websocket)
        logger.info(
            "ws disconnected: user=%s connections=%d", user_id, manager.connection_count()
        )
