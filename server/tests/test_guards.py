"""`app/core/single_worker.py` 与 `app/core/logging_utils.py` 的单元测试。

这两处都是本会话新增的**防护机制**，一旦失效后果不轻：
- 单 worker 守卫失效 → 多 worker 下"数据一致但推送丢事件"，极难排查
- 日志脱敏失效 → WS 令牌明文进日志，可被用来冒充用户
"""

from __future__ import annotations

import logging
import socket

import pytest

from app.core import single_worker
from app.core.logging_utils import (
    REDACTED,
    redact_tokens,
    scrub_scope_token,
)


@pytest.fixture(autouse=True)
def _release_lock():
    """每个测试前后都释放锁并清理环境变量，避免相互影响。"""
    single_worker.release_single_worker()
    yield
    single_worker.release_single_worker()


@pytest.fixture
def free_port(monkeypatch: pytest.MonkeyPatch) -> int:
    """把锁端口换成一个当前空闲的端口。

    ⚠️ 必须这么做：真实的 `LOCK_PORT` 很可能正被**本地运行的后端**占着
    （它启动时就抢了这个锁），直接测会被判成"已有实例"。
    这里只替换端口号，守卫逻辑本身照常验证。
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    monkeypatch.setattr(single_worker, "LOCK_PORT", port)
    return port


class TestDefaultLockPort:
    """锁端口可被 `CLIPBOARD_LOCK_PORT` 覆盖——让测试用独立后端与开发实例并存。"""

    def test_未设置时用模块常量(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLIPBOARD_LOCK_PORT", raising=False)
        monkeypatch.setattr(single_worker, "LOCK_PORT", 49137)
        assert single_worker.default_lock_port() == 49137

    @pytest.mark.parametrize("value", ["", "   "])
    def test_空值退回模块常量(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setattr(single_worker, "LOCK_PORT", 49137)
        monkeypatch.setenv("CLIPBOARD_LOCK_PORT", value)
        assert single_worker.default_lock_port() == 49137

    def test_环境变量可覆盖(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLIPBOARD_LOCK_PORT", "49138")
        assert single_worker.default_lock_port() == 49138

    def test_非法值被拒(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLIPBOARD_LOCK_PORT", "abc")
        with pytest.raises(single_worker.MultipleWorkersError):
            single_worker.default_lock_port()

    @pytest.mark.parametrize("value", ["80", "70000", "0", "-1"])
    def test_越界值被拒(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("CLIPBOARD_LOCK_PORT", value)
        with pytest.raises(single_worker.MultipleWorkersError):
            single_worker.default_lock_port()

    def test_不同锁端口的两个实例可以并存(
        self, monkeypatch: pytest.MonkeyPatch, free_port: int
    ) -> None:
        """这正是测试后端能与开发后端同时跑的原因。"""
        other = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        other.bind(("127.0.0.1", 0))
        other_port = other.getsockname()[1]
        other.close()

        monkeypatch.setenv("CLIPBOARD_LOCK_PORT", str(free_port))
        assert single_worker.lock_single_worker() == free_port

        # 换一个锁端口，同一个进程也能再抢一个（模拟另一个实例用的不同端口）
        single_worker.release_single_worker()
        monkeypatch.setenv("CLIPBOARD_LOCK_PORT", str(other_port))
        assert single_worker.lock_single_worker() == other_port


class TestLockSingleWorker:
    def test_首次抢占成功并返回端口(self, free_port: int) -> None:
        port = single_worker.lock_single_worker()
        assert port == free_port
        assert single_worker.locked_port() == port

    def test_重复调用是幂等的(self, free_port: int) -> None:
        first = single_worker.lock_single_worker()
        second = single_worker.lock_single_worker()
        assert first == second

    def test_端口被占用时抛错(self, free_port: int) -> None:
        """第二个实例绑定时应拿到 WSAEADDRINUSE / EADDRINUSE。"""
        holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            holder.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            holder.bind(("127.0.0.1", free_port))
        except OSError:
            pytest.skip(f"端口 {free_port} 已被占用")

        try:
            with pytest.raises(single_worker.MultipleWorkersError):
                single_worker.lock_single_worker()
        finally:
            holder.close()

    def test_释放后可重新抢占(self, free_port: int) -> None:
        single_worker.lock_single_worker()
        single_worker.release_single_worker()
        assert single_worker.locked_port() is None
        assert single_worker.lock_single_worker() == free_port

    def test_显式传入端口优先于模块常量(self, free_port: int) -> None:
        assert single_worker.lock_single_worker(free_port) == free_port


class TestAssertSingleWorker:
    def test_未设环境变量时放行(
        self, monkeypatch: pytest.MonkeyPatch, free_port: int
    ) -> None:
        monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
        assert single_worker.assert_single_worker() == free_port

    @pytest.mark.parametrize("value", ["", "   "])
    def test_环境变量为空时放行(
        self, monkeypatch: pytest.MonkeyPatch, free_port: int, value: str
    ) -> None:
        monkeypatch.setenv("WEB_CONCURRENCY", value)
        assert single_worker.assert_single_worker() == free_port

    def test_workers_为_1_时放行(
        self, monkeypatch: pytest.MonkeyPatch, free_port: int
    ) -> None:
        monkeypatch.setenv("WEB_CONCURRENCY", "1")
        assert single_worker.assert_single_worker() == free_port

    @pytest.mark.parametrize("value", ["2", "4", "8"])
    def test_workers_大于_1_时抛错(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("WEB_CONCURRENCY", value)
        with pytest.raises(single_worker.MultipleWorkersError):
            single_worker.assert_single_worker()

    def test_非法值抛错(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WEB_CONCURRENCY", "abc")
        with pytest.raises(single_worker.MultipleWorkersError):
            single_worker.assert_single_worker()

    def test_被拦下时打印醒目横幅(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """uvicorn supervisor 会反复重启崩溃的 worker，报错容易被淹没。"""
        monkeypatch.setenv("WEB_CONCURRENCY", "2")
        with pytest.raises(single_worker.MultipleWorkersError):
            single_worker.assert_single_worker()
        output = capsys.readouterr().out
        assert "致命" in output
        assert "WebSocket" in output


class TestRedactTokens:
    def test_抹掉令牌值(self) -> None:
        secret = "eyJhbGciOiJIUzI1NiJ9.PAYLOAD.SIGNATURE"
        result = redact_tokens(f"/ws?token={secret}")
        assert secret not in result
        assert f"token={REDACTED}" in result

    def test_只抹_token_保留其他参数(self) -> None:
        assert redact_tokens("/ws?token=abc&foo=bar") == f"/ws?token={REDACTED}&foo=bar"

    def test_保留_token_之前的其他参数(self) -> None:
        assert redact_tokens("/ws?foo=bar&token=abc") == f"/ws?foo=bar&token={REDACTED}"

    def test_无_token_时原样返回(self) -> None:
        assert redact_tokens("/health") == "/health"

    def test_空字符串(self) -> None:
        assert redact_tokens("") == ""

    def test_大小写不敏感(self) -> None:
        assert "secret" not in redact_tokens("/ws?Token=secret")

    def test_多个_token_都被抹掉(self) -> None:
        result = redact_tokens("?token=aaa&x=1&token=bbb")
        assert "aaa" not in result and "bbb" not in result

    def test_令牌后紧跟引号时正确截断(self) -> None:
        result = redact_tokens('"WebSocket /ws?token=secret" [accepted]')
        assert "secret" not in result
        assert "[accepted]" in result


class TestScrubScopeToken:
    def test_清空含_token_的查询串(self) -> None:
        scope: dict = {"path": "/api/v1/clipboard/ws", "query_string": b"token=secret"}
        scrub_scope_token(scope)
        assert scope["query_string"] == b""

    def test_不改_path_避免被百分号编码(self) -> None:
        """若把 ?token=*** 拼进 path，uvicorn 会编码成 %3Ftoken%3D...，难看且难 grep。"""
        scope: dict = {"path": "/api/v1/clipboard/ws", "query_string": b"token=secret"}
        scrub_scope_token(scope)
        assert scope["path"] == "/api/v1/clipboard/ws"

    def test_不含_token_时不动(self) -> None:
        scope: dict = {"path": "/health", "query_string": b"foo=bar"}
        scrub_scope_token(scope)
        assert scope["query_string"] == b"foo=bar"

    def test_缺失_query_string_不报错(self) -> None:
        scrub_scope_token({"path": "/x"})

    def test_空_query_string_不报错(self) -> None:
        scrub_scope_token({"path": "/x", "query_string": b""})

    def test_字符串形式的_query_string_也能处理(self) -> None:
        scope: dict = {"path": "/x", "query_string": "token=secret"}
        scrub_scope_token(scope)
        assert scope["query_string"] == b""

    def test_大小写不敏感(self) -> None:
        scope: dict = {"path": "/x", "query_string": b"Token=secret"}
        scrub_scope_token(scope)
        assert scope["query_string"] == b""


class TestFormatterRedaction:
    """兜底那层：包住已有 formatter，对最终文本再脱敏。"""

    def test_不改动_record_args(self) -> None:
        """⚠️ 改写 record.args 会让 uvicorn 的 AccessFormatter 对每个请求抛
        ValueError（它要求 args 恰好 5 个字段），直接搞坏全部访问日志。"""
        from app.core.logging_utils import _RedactingFormatter

        inner = logging.Formatter("%(message)s")
        formatter = _RedactingFormatter(inner)
        record = logging.LogRecord(
            "uvicorn.access", logging.INFO, __file__, 1, "%s - %s", ("a", "b"), None
        )
        formatter.format(record)
        assert record.args == ("a", "b"), "args 必须保持原样"
        assert record.msg == "%s - %s", "msg 必须保持原样"

    def test_包装后输出被脱敏(self) -> None:
        from app.core.logging_utils import _RedactingFormatter

        formatter = _RedactingFormatter(logging.Formatter("%(message)s"))
        record = logging.LogRecord(
            "uvicorn.access",
            logging.INFO,
            __file__,
            1,
            "GET /ws?token=secret done",
            None,
            None,
        )
        output = formatter.format(record)
        assert "secret" not in output
        assert REDACTED in output

    def test_无_formatter_的_handler_被跳过(self) -> None:
        """没有 formatter 就没什么可脱敏的，跳过而不是报错。"""
        from app.core.logging_utils import install_log_redaction

        name = "test.redaction.noformatter"
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.addHandler(logging.StreamHandler())  # 未设 formatter
        logger.propagate = False
        try:
            assert install_log_redaction((name,)) == 0
        finally:
            logger.handlers.clear()

    def test_包装是幂等的(self) -> None:
        from app.core.logging_utils import install_log_redaction

        name = "test.redaction.idempotent"
        logger = logging.getLogger(name)
        logger.handlers.clear()
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.propagate = False

        try:
            assert install_log_redaction((name,)) == 1, "首次应包装"
            assert install_log_redaction((name,)) == 0, "重复调用不应再次包装"
        finally:
            logger.handlers.clear()
