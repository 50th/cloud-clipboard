"""日志安全工具。

**要解决的问题**：WebSocket 的 token 走 query string（浏览器 WebSocket API 不允许
自定义请求头），因此 uvicorn 的访问日志会把它明文打出来：

    "WebSocket /api/v1/clipboard/ws?token=eyJhbGciOi... [accepted]"

令牌一旦进了日志文件/终端回滚缓冲就等于泄露（可直接冒充该用户）。

这里提供两层防护，**建议都用**：

1. `scrub_scope_token()` —— 在端点到手后立刻把 token 从 ASGI scope 里删掉。
   日志里**根本不会出现** token，最干净。
2. `install_log_redaction()` —— 包一层 formatter，对最终格式化出来的文本再脱敏。
   用于兜住第 1 层覆盖不到的地方（其他 logger、异常堆栈等）。

⚠️ **不要用 logging.Filter 去改写 `record.args`**：uvicorn 的 `AccessFormatter`
依赖 args 里的 5 个字段（client、method、path、status、时间），
把 args 清空会让每个请求都抛 `ValueError: not enough values to unpack`，
**直接搞坏全部访问日志**。这一条是实测踩出来的。
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import parse_qsl

# 匹配 `token=<值>`，值到下一个 `&`、空白或引号为止
_TOKEN_PATTERN = re.compile(r"(token=)[^&\s\"']+", re.IGNORECASE)

REDACTED = "***"


def redact_tokens(text: str) -> str:
    """把文本里所有 `token=...` 的值替换成 `***`。"""
    return _TOKEN_PATTERN.sub(rf"\1{REDACTED}", text)


def scrub_scope_token(scope: dict[str, Any]) -> None:
    """从 ASGI scope 里移除 token 查询参数（原地修改），让日志路径里根本没有它。

    为什么可行：uvicorn 的访问日志在**连接结束时**才用 scope 拼路径，
    而 FastAPI 的 Query 参数在进入端点前就已解析成函数入参，
    所以此时改写 scope 不影响鉴权，只影响日志。

    实现上**只清空 `query_string`、不改 `path`**：
    uvicorn 只在 `query_string` 非空时才把它拼进日志路径，清空后日志只剩
    `/api/v1/clipboard/ws`（没有 token，也就没有可泄露的内容）。
    若把 `?token=***` 拼进 `path`，uvicorn 会把 `?`、`=` 重新百分号编码成
    `%3Ftoken%3D...`，既难看又不好 grep——所以不这么做。

    日志里显示 `token=***` 这层可读性由 `install_log_redaction()` 的 formatter 负责。
    """
    raw = scope.get("query_string")
    if not raw:
        return
    try:
        text = raw.decode("latin-1") if isinstance(raw, bytes) else str(raw)
        pairs = parse_qsl(text, keep_blank_values=True)
        if any(key.lower() == "token" for key, _ in pairs):
            scope["query_string"] = b""
    except Exception:  # noqa: BLE001 - 脱敏失败绝不能影响请求本身
        return


class _RedactingFormatter(logging.Formatter):
    """包住已有的 formatter，对最终文本再脱敏。

    刻意不改 `record.msg` / `record.args`：那样会破坏依赖 args 的自定义 formatter
    （见本模块顶部说明）。
    """

    def __init__(self, inner: logging.Formatter) -> None:
        # 不调用 super().__init__ 的 fmt 参数——格式化全部委托给 inner
        super().__init__()
        self._inner = inner

    def format(self, record: logging.LogRecord) -> str:
        return redact_tokens(self._inner.format(record))

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return self._inner.formatTime(record, datefmt)

    @property
    def inner(self) -> logging.Formatter:
        return self._inner


def _wrap_handler(handler: logging.Handler) -> bool:
    """给单个 handler 套上脱敏 formatter；已套过或没有 formatter 则不动。"""
    formatter = handler.formatter
    if formatter is None or isinstance(formatter, _RedactingFormatter):
        return False
    handler.setFormatter(_RedactingFormatter(formatter))
    return True


def install_log_redaction(logger_names: tuple[str, ...] = ("uvicorn.access",)) -> int:
    """给指定 logger 的 handler 套上脱敏 formatter，返回被包装的 handler 数。

    幂等：重复调用不会重复包装。
    """
    wrapped = 0
    for name in logger_names:
        for handler in logging.getLogger(name).handlers:
            if _wrap_handler(handler):
                wrapped += 1
    return wrapped
