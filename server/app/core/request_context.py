"""请求 ID：把同一次请求的多条日志串起来。

**要解决的问题**：访问日志、业务日志（写审计）、WS 广播日志原本是三条孤立记录。
排查"这次保存为什么没推送到手机"时，只能靠时间戳猜，同一秒内的多次操作无法区分。

做法：

- `RequestIdMiddleware`（**纯 ASGI**，同时覆盖 HTTP 与 WebSocket）为每个请求
  生成一个 id 写进 `contextvars`，并在 HTTP 响应头回写 `X-Request-ID`；
- `RequestIdFilter` 挂在日志 handler 上，把 contextvar 的值塞进
  `record.request_id`，格式串用 `%(request_id)s` 输出。

⚠️ 与 `logging_utils.py` 相同的红线：**只新增 `record.request_id` 属性**，
不改写 `record.args` / `record.msg`——uvicorn 的 `AccessFormatter` 依赖 args
里的 5 个字段，清空后每个请求都会抛 `ValueError`。

为什么用纯 ASGI 中间件而不是 `@app.middleware("http")`：后者不覆盖 WebSocket
握手；而 WS 的 `ws connected` 日志恰恰最需要与后续广播日志对应上。
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Awaitable, Callable, MutableMapping
from contextvars import ContextVar, Token
from typing import Any

# 响应头名（客户端/网关可据此回传排查线索）
REQUEST_ID_HEADER = "X-Request-ID"

# 日志里没有请求上下文时的占位符（启动、脚本等场景）
NO_REQUEST_ID = "-"

# 只接受安全字符：请求头来自外部，直接落盘等于给了日志注入的入口。
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_request_id: ContextVar[str] = ContextVar("request_id", default=NO_REQUEST_ID)


def current_request_id() -> str:
    """当前请求的 id；不在请求上下文中时返回 `-`。"""
    return _request_id.get()


def new_request_id() -> str:
    """生成短 id（12 位十六进制），足够在日志里区分同一次请求。"""
    return uuid.uuid4().hex[:12]


def set_request_id(value: str) -> Token[str]:
    """设置当前上下文的请求 id，返回可用于还原的 token。"""
    return _request_id.set(value)


def reset_request_id(token: Token[str]) -> None:
    """把请求 id 还原到设置前的值。"""
    _request_id.reset(token)


class RequestIdFilter(logging.Filter):
    """把 contextvar 里的请求 id 填进 `record.request_id`。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


def _incoming_request_id(scope: MutableMapping[str, Any]) -> str | None:
    """沿用上游传来的 `X-Request-ID`（便于跨服务追踪）；不合法时丢弃。"""
    for key, value in scope.get("headers") or ():
        if key.lower() != REQUEST_ID_HEADER.lower().encode():
            continue
        try:
            candidate = value.decode("latin-1")
        except UnicodeDecodeError:
            return None
        return candidate if _SAFE_REQUEST_ID.match(candidate) else None
    return None


class RequestIdMiddleware:
    """为每个 HTTP / WebSocket 请求分配 id，并写入响应头。"""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[Any]],
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
    ) -> None:
        if scope.get("type") not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or new_request_id()
        token = _request_id.set(request_id)
        try:
            if scope["type"] != "http":
                # WebSocket 没有响应头，只靠 contextvar 让握手与后续日志可关联
                await self.app(scope, receive, send)
                return

            async def send_with_header(message: MutableMapping[str, Any]) -> None:
                if message.get("type") == "http.response.start":
                    headers = list(message.get("headers") or [])
                    headers.append(
                        (REQUEST_ID_HEADER.lower().encode(), request_id.encode())
                    )
                    message = {**message, "headers": headers}
                await send(message)

            await self.app(scope, receive, send_with_header)
        finally:
            reset_request_id(token)
