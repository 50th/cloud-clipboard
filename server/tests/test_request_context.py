"""`app/core/request_context.py` 的单元测试。

请求 id 是排查"这次保存为什么没推送"的唯一串联线索，失效时不会报错、
只会让日志失去关联，因此需要单独的回归用例守住。
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.request_context import (
    NO_REQUEST_ID,
    REQUEST_ID_HEADER,
    RequestIdFilter,
    RequestIdMiddleware,
    current_request_id,
    new_request_id,
    reset_request_id,
    set_request_id,
)


def _http_scope(headers: list[tuple[bytes, bytes]] | None = None) -> dict[str, Any]:
    return {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/clipboard/items",
        "headers": headers or [],
    }


async def _noop_receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


class RecordingApp:
    """记录中间件内看到的请求 id，并返回一个最小响应。"""

    def __init__(self) -> None:
        self.seen: list[str] = []

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        self.seen.append(current_request_id())
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


class TestRequestId:
    def test_生成的_id_是短十六进制(self) -> None:
        value = new_request_id()
        assert len(value) == 12
        assert int(value, 16) >= 0

    def test_默认无请求上下文时为占位符(self) -> None:
        assert current_request_id() == NO_REQUEST_ID

    def test_可以设置与还原(self) -> None:
        token = set_request_id("abc123")
        try:
            assert current_request_id() == "abc123"
        finally:
            reset_request_id(token)
        assert current_request_id() == NO_REQUEST_ID

    def test_filter_把_id_写进_record(self) -> None:
        record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "hi", None, None)
        assert RequestIdFilter().filter(record) is True
        assert record.request_id == NO_REQUEST_ID


class TestMiddleware:
    async def test_响应头带请求_id_且业务日志能读到(self) -> None:
        app = RecordingApp()
        middleware = RequestIdMiddleware(app)
        messages: list[dict[str, Any]] = []

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        await middleware(_http_scope(), _noop_receive, send)

        headers = dict(messages[0]["headers"])
        request_id = headers[REQUEST_ID_HEADER.lower().encode()].decode()
        assert app.seen == [request_id], "中间件内的日志必须能读到同一个 id"
        assert len(request_id) == 12

    async def test_沿用上游传入的合法_id(self) -> None:
        app = RecordingApp()
        middleware = RequestIdMiddleware(app)
        messages: list[dict[str, Any]] = []

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        scope = _http_scope([(REQUEST_ID_HEADER.lower().encode(), b"gateway-0001")])
        await middleware(scope, _noop_receive, send)

        assert app.seen == ["gateway-0001"]

    async def test_非法_id_被丢弃并重新生成(self) -> None:
        """请求头来自外部，含换行等字符时不能直接进日志（日志注入）。"""
        app = RecordingApp()
        middleware = RequestIdMiddleware(app)
        messages: list[dict[str, Any]] = []

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        scope = _http_scope([(REQUEST_ID_HEADER.lower().encode(), b"bad id\ninjected")])
        await middleware(scope, _noop_receive, send)

        assert app.seen[0] != "bad id\ninjected"
        assert len(app.seen[0]) == 12

    async def test_请求结束后还原上下文(self) -> None:
        middleware = RequestIdMiddleware(RecordingApp())

        async def send(message: dict[str, Any]) -> None:
            return None

        await middleware(_http_scope(), _noop_receive, send)
        assert current_request_id() == NO_REQUEST_ID

    async def test_非_http_请求不分配_id也不注入响应头(self) -> None:
        app = RecordingApp()

        async def passthrough(scope: dict, receive: Any, send: Any) -> None:
            app.seen.append(current_request_id())

        middleware = RequestIdMiddleware(passthrough)
        sent: list[dict[str, Any]] = []

        async def send(message: dict[str, Any]) -> None:
            sent.append(message)

        await middleware({"type": "lifespan"}, _noop_receive, send)

        assert sent == [], "lifespan 不走应用层，应原样放行"
        assert app.seen == [NO_REQUEST_ID], "非请求场景不分配 id"
