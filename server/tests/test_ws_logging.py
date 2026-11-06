"""WebSocket 端点的日志相关单元测试。

只测**不发数据库请求**的部分：鉴权失败原因必须可区分（日志要用它判断是
"没带 token"还是"token 坏了"），以及日志里出现的客户端标识不能崩。

⚠️ 端点里的 `logger.warning("ws 鉴权失败: ...")` 因此必须保留 reason 字段，
否则告警时无法区分"配置漏传 token"与"有人在暴力试 token"。
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from app.routers.ws import _authenticate, _client_label
from app.services.ws_manager import ConnectionManager


class TestAuthenticateReason:
    async def test_缺少_token(self) -> None:
        assert await _authenticate(None) == (None, "missing token")

    async def test_空_token_等同于缺失(self) -> None:
        assert await _authenticate("") == (None, "missing token")

    async def test_无法解析的_token(self) -> None:
        user_id, reason = await _authenticate("not-a-jwt")
        assert user_id is None
        assert reason == "invalid token"


class TestClientLabel:
    def test_没有客户端地址时返回_unknown(self) -> None:
        class _FakeWebSocket:
            client = None

        assert _client_label(_FakeWebSocket()) == "unknown"  # type: ignore[arg-type]


class _BrokenSocket:
    """握手成功后立刻断开的连接：发送必然失败。"""

    async def send_json(self, payload: dict[str, Any]) -> None:
        raise RuntimeError("socket closed")


class TestBroadcastLogging:
    """广播失败必须留痕，否则"推送丢了"在日志里完全看不出来。"""

    async def test_失效连接被摘除并记_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        manager = ConnectionManager()
        broken = _BrokenSocket()
        await manager.connect("user-1", broken)  # type: ignore[arg-type]

        with caplog.at_level(logging.WARNING, logger="app.services.ws_manager"):
            delivered = await manager.send_to_user(
                "user-1", "clipboard.updated", {"id": "x"}
            )

        assert delivered == 0
        assert manager.connection_count() == 0, "失效连接应被摘除"
        assert "ws 广播部分失败" in caplog.text
        assert "dropped=1" in caplog.text
