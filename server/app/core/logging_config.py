"""统一日志配置。

**为什么需要这个模块**：uvicorn 只配置自己的 `uvicorn*` logger，**不动 root**。
业务代码里的 `logging.getLogger(__name__)`（如 `app.routers.ws`）会一路 propagate
到 root，而 root 既没有 handler、级别又是 WARNING——结果所有 `logger.info` 被
**静默丢弃**：线上看不到 WS 连接数、看不到断连，排查时只能靠猜。

`configure_logging()` 在 lifespan 最前面调用一次，效果：

- root（`app.*` 都挂它下面）级别由 `LOG_LEVEL` 控制，默认 INFO
- 默认输出到 **`RotatingFileHandler`**（`LOG_FILE`，相对路径按 `server/` 解析），
  UTF-8、单文件 `LOG_MAX_BYTES`、保留 `LOG_BACKUP_COUNT` 份
- `LOG_CONSOLE=true` 时**额外**输出到终端；`LOG_FILE` 置空则只走终端
- uvicorn 自己的日志（access / error）也会追加进同一个文件，避免排查时
  在"终端日志"和"文件日志"之间来回翻（uvicorn 原有的终端 handler 保留）
- 每行带 `request_id`（见 `app/core/request_context.py`）与毫秒级时间戳

⚠️ **RotatingFileHandler 不能多进程写同一个文件**（轮转时互相抢文件，Windows 上
直接 `PermissionError`）。本项目强制单 worker，因此安全；但并行起的独立实例
（`scripts/run_web_tests.ps1` 的 8001 端口）必须用 `LOG_FILE` 指向别的文件。

⚠️ 日志文件里的 token 脱敏由 `install_log_redaction()` 负责，它必须在
`configure_logging()` **之后**调用，才能把这里新加的 file handler 一起包上。
"""

from __future__ import annotations

import logging
import logging.config
import logging.handlers
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.core.request_context import RequestIdFilter

# `server/` 目录：日志相对路径以它为基准，避免"从哪个目录启动就写到哪"。
BASE_DIR = Path(__file__).resolve().parents[2]

LOG_FORMAT = (
    "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s %(message)s"
)

# handler 上挂的 filter 名（dictConfig 内引用）
_REQUEST_ID_FILTER = "request_id"


class IsoTimestampFormatter(logging.Formatter):
    """本地时间的 ISO 8601：**带毫秒与时区偏移**。

    为什么不用默认的 `%(asctime)s`：它只精确到秒、且不带时区。同一秒内的
    多次自动保存、WS 重连与广播日志无法排序；跨时区（服务器 UTC、本机东八区）
    排查时也看不出偏移。
    """

    def formatTime(
        self, record: logging.LogRecord, datefmt: str | None = None
    ) -> str:
        moment = datetime.fromtimestamp(record.created).astimezone()
        return moment.isoformat(sep=" ", timespec="milliseconds")


_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# handler 命名，便于重复调用时精确移除，避免在 uvicorn logger 上越堆越多。
_FILE_HANDLER_NAME = "clipboard-file"
_CONSOLE_HANDLER_NAME = "clipboard-console"

# `uvicorn.error` 会 propagate 到 `uvicorn`，挂一次即可；
# `uvicorn.access` 是 propagate=False，必须单独挂。
_UVICORN_LOGGERS = ("uvicorn", "uvicorn.access")


def resolve_log_path() -> Path | None:
    """把 `settings.LOG_FILE` 解析成绝对路径；空字符串表示只输出到终端。"""
    return _to_path(settings.LOG_FILE)


def _to_path(value: str | Path) -> Path | None:
    text = str(value).strip()
    if not text:
        return None
    path = Path(text).expanduser()
    return path if path.is_absolute() else BASE_DIR / path


def _file_handler_config(target: Path) -> dict[str, object]:
    return {
        "class": "logging.handlers.RotatingFileHandler",
        "formatter": "default",
        "filters": [_REQUEST_ID_FILTER],
        "filename": str(target),
        "maxBytes": settings.LOG_MAX_BYTES,
        "backupCount": settings.LOG_BACKUP_COUNT,
        "encoding": "utf-8",
    }


def _console_handler_config() -> dict[str, object]:
    return {
        "class": "logging.StreamHandler",
        "formatter": "default",
        "filters": [_REQUEST_ID_FILTER],
        "stream": "ext://sys.stderr",
    }


def _formatters() -> dict[str, object]:
    """自定义 formatter：ISO 8601 时间戳 + 请求 id。"""
    return {"default": {"()": IsoTimestampFormatter, "format": LOG_FORMAT}}


def _filters() -> dict[str, object]:
    return {_REQUEST_ID_FILTER: {"()": RequestIdFilter}}


def configure_logging(
    *,
    log_file: str | Path | None = None,
    level: str | None = None,
    console: bool | None = None,
) -> Path | None:
    """安装全局日志配置，返回日志文件路径（纯控制台模式返回 None）。

    参数留空时分别回落到 `settings.LOG_FILE` / `settings.LOG_LEVEL` /
    `settings.LOG_CONSOLE`；显式传参主要供测试使用。重复调用是安全的：
    上一次装上的 handler 会先被移除并关闭。
    """
    target = resolve_log_path() if log_file is None else _to_path(log_file)
    use_console = settings.LOG_CONSOLE if console is None else console
    raw_level = (settings.LOG_LEVEL if level is None else level).strip().upper()
    level_value = _LEVELS.get(raw_level, logging.INFO)
    if target is None:
        # 没有文件出口，必须留控制台，否则日志彻底消失
        use_console = True

    handlers: dict[str, dict[str, object]] = {}
    root_handlers: list[str] = []
    if target is not None:
        handlers["file"] = _file_handler_config(target)
        root_handlers.append("file")
    if use_console:
        handlers["console"] = _console_handler_config()
        root_handlers.append("console")

    config: dict[str, object] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": _formatters(),
        "filters": _filters(),
        "handlers": handlers,
        "root": {"handlers": root_handlers, "level": level_value},
    }

    _detach_installed_handlers()

    try:
        if target is not None:
            target.parent.mkdir(parents=True, exist_ok=True)
        logging.config.dictConfig(config)  # type: ignore[arg-type]
    except (OSError, ValueError) as exc:
        # ⚠️ 文件打不开时 `dictConfig` 会把 PermissionError 包成
        # `ValueError("Unable to configure handler 'file'")`，只捕 OSError 会漏掉
        # 这条最常见的降级路径（实测：目录不可写时启动直接失败）。
        # 磁盘满 / 目录无权限时不能拖垮整个服务：退回终端并说清楚原因。
        _install_console_fallback(level_value, exc)
        target = None

    _name_root_handlers()
    _attach_file_handler_to_uvicorn()

    logger = logging.getLogger(__name__)
    if raw_level not in _LEVELS:
        logger.warning(
            "LOG_LEVEL=%r 不是合法级别（%s），已按 INFO 处理",
            raw_level,
            " / ".join(_LEVELS),
        )
    return target


def _install_console_fallback(level_value: int, exc: OSError | ValueError) -> None:
    """文件 handler 建不起来时的降级配置：只写终端。"""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": _formatters(),
            "filters": _filters(),
            "handlers": {"console": _console_handler_config()},
            "root": {"handlers": ["console"], "level": level_value},
        }
    )
    logging.getLogger(__name__).warning("日志文件不可用（%s），已退回终端输出", exc)


def _name_root_handlers() -> None:
    """给 root 上的 handler 打标记，供下次配置时精确移除。"""
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            handler.set_name(_FILE_HANDLER_NAME)
        else:
            handler.set_name(_CONSOLE_HANDLER_NAME)


def _file_handler() -> logging.Handler | None:
    for handler in logging.getLogger().handlers:
        if getattr(handler, "name", None) == _FILE_HANDLER_NAME:
            return handler
    return None


def _attach_file_handler_to_uvicorn() -> None:
    """让 uvicorn 的 access/error 日志也进同一个文件。

    uvicorn 在 lifespan 之前就已经配好自己的 handler，这里只**追加**、不替换，
    因此终端上的 uvicorn 输出保持不变。
    """
    handler = _file_handler()
    if handler is None:
        return
    for name in _UVICORN_LOGGERS:
        logger = logging.getLogger(name)
        if handler not in logger.handlers:
            logger.addHandler(handler)


def _detach_installed_handlers() -> None:
    """移除上一次 `configure_logging()` 装上的 handler（并关闭文件句柄）。"""
    for name in ("", *_UVICORN_LOGGERS):
        logger = logging.getLogger(name)
        for handler in list(logger.handlers):
            if getattr(handler, "name", None) in (
                _FILE_HANDLER_NAME,
                _CONSOLE_HANDLER_NAME,
            ):
                logger.removeHandler(handler)
                handler.close()
