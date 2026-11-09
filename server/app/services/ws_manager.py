"""WebSocket 连接管理与按用户广播。

⚠️ **本模块是进程内数据结构**，因此应用必须以**单 worker** 运行
（`--workers 1`）：一旦多 worker，用户 A 连 worker 1、用户 B 连 worker 2，
事件永远送不到，而数据库层是共享的——数据一致、推送不一致，现象很隐蔽。
详见 `docs/ws-protocol.md` 的「多实例问题」。同机多进程需改造成 Redis Pub/Sub。

广播**按用户隔离，不群发**：只推给 `user_id` 相同的连接。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# 单条消息的发送超时。慢客户端不能拖住整个广播。
SEND_TIMEOUT_SECONDS = 5.0


class ConnectionManager:
    """按用户分组的 WebSocket 连接表。

    同一个用户可以有多条连接（多个浏览器标签、手机 + 桌面），
    每条都要收到同一条事件。
    """

    def __init__(self) -> None:
        # user_id(str) -> 该用户当前的连接集合
        self._connections: dict[str, set[WebSocket]] = {}
        # 广播串行化：避免多个请求同时遍历/修改同一集合
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str | uuid.UUID, websocket: WebSocket) -> None:
        """登记一条**已完成握手**的连接。

        调用方负责先 `await websocket.accept()` 再调用本方法。
        """
        key = str(user_id)
        async with self._lock:
            self._connections.setdefault(key, set()).add(websocket)

    async def disconnect(self, user_id: str | uuid.UUID, websocket: WebSocket) -> None:
        """移除连接；该用户没有连接了就清掉整个键。"""
        key = str(user_id)
        async with self._lock:
            sockets = self._connections.get(key)
            if sockets is None:
                return
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(key, None)

    async def close_user(
        self,
        user_id: str | uuid.UUID,
        *,
        code: int = 4401,
        reason: str = "account disabled",
    ) -> int:
        """关闭并移除某用户的全部连接，返回成功关闭的数量。

        用于禁用/删除/重置密码后立即终止会话；复用 4401 关闭码，
        客户端会停止重连，下一次 HTTP 请求的 401 再清理登录态。
        """
        key = str(user_id)
        async with self._lock:
            targets = list(self._connections.pop(key, ()))

        if not targets:
            return 0

        results = await asyncio.gather(
            *(self._safe_close(socket, code, reason) for socket in targets),
            return_exceptions=True,
        )
        failed = sum(1 for result in results if result is not True)
        if failed:
            logger.warning(
                "ws 强制关闭部分失败: user=%s closed=%d failed=%d",
                key,
                len(targets) - failed,
                failed,
            )
        return len(targets) - failed

    @staticmethod
    async def _safe_close(socket: WebSocket, code: int, reason: str) -> bool:
        """关闭单条连接；已断开/异常都按失败处理但不抛出。"""
        try:
            await socket.close(code=code, reason=reason)
            return True
        except Exception:  # noqa: BLE001 - 对端可能已经断开
            return False

    async def send_to_user(
        self, user_id: str | uuid.UUID, event: str, data: Any
    ) -> int:
        """把事件推给该用户的全部连接，返回成功送达的条数。

        发送失败的连接会被立即摘除（对端多半已经断开，只是还没触发断开事件）。
        """
        payload = {"event": event, "data": data}
        key = str(user_id)

        async with self._lock:
            targets = list(self._connections.get(key, ()))

        if not targets:
            return 0

        results = await asyncio.gather(
            *(self._safe_send(socket, payload) for socket in targets),
            return_exceptions=True,
        )

        delivered = 0
        dead: list[WebSocket] = []
        for socket, ok in zip(targets, results, strict=True):
            if ok is True:
                delivered += 1
            else:
                dead.append(socket)

        # 清理已失效的连接
        if dead:
            async with self._lock:
                sockets = self._connections.get(key)
                if sockets is not None:
                    for socket in dead:
                        sockets.discard(socket)
                    if not sockets:
                        self._connections.pop(key, None)
            # 发送失败在 `_safe_send` 里被吞掉了，这里是唯一可见的落点：
            # 不记的话"推送丢了"在日志里完全看不出来。
            logger.warning(
                "ws 广播部分失败: user=%s event=%s delivered=%d dropped=%d",
                key,
                event,
                delivered,
                len(dead),
            )
        return delivered

    @staticmethod
    async def _safe_send(socket: WebSocket, payload: dict[str, Any]) -> bool:
        """发送单条消息，带超时；失败返回 False 而不是抛异常。"""
        try:
            await asyncio.wait_for(socket.send_json(payload), timeout=SEND_TIMEOUT_SECONDS)
            return True
        except Exception as exc:  # noqa: BLE001 - 断连/超时都按"这条连接不可用"处理
            # 断线是常态，用 DEBUG 避免刷屏；排查推送丢失时再调高日志级别。
            logger.debug(
                "ws 发送失败: event=%s reason=%s: %s",
                payload.get("event"),
                type(exc).__name__,
                exc,
            )
            return False

    async def send_personal(self, websocket: WebSocket, event: str, data: Any) -> bool:
        """只发给指定的单条连接（如心跳回应）。"""
        return await self._safe_send(websocket, {"event": event, "data": data})

    def connection_count(self, user_id: str | uuid.UUID | None = None) -> int:
        """连接数。不传 `user_id` 时返回全局连接数（状态查看/测试用）。"""
        if user_id is None:
            return sum(len(sockets) for sockets in self._connections.values())
        return len(self._connections.get(str(user_id), ()))

    def user_count(self) -> int:
        """当前有连接的用户数。"""
        return len(self._connections)


# 进程内单例。路由与业务代码都从这里取，保证是同一份连接表。
manager = ConnectionManager()
