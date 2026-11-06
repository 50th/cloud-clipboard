"""`app/core/logging_config.py` 的单元测试。

覆盖两类回归：

- **日志不可观测**：root 没有 handler / 级别不对时，业务代码的 `logger.info`
  会被静默丢弃（实测：WS 连上了但日志里什么都没有）
- **日志泄密**：新增的文件 handler 没被 `install_log_redaction()` 包住时，
  WS 的 token 会明文落盘

每个用例结束都要还原 root / uvicorn 的 handler，否则会污染同进程内的其他测试。
"""

from __future__ import annotations

import logging
import logging.handlers
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core import logging_config
from app.core.logging_utils import REDACTED, install_log_redaction

_LOGGERS_TO_RESTORE = ("uvicorn", "uvicorn.access")


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    """保存并还原全局日志状态（配置会改动 root 与 uvicorn 的 handler）。"""
    root = logging.getLogger()
    saved_root_handlers = list(root.handlers)
    saved_root_level = root.level
    saved_uvicorn: dict[str, tuple[list[logging.Handler], int]] = {}
    for name in _LOGGERS_TO_RESTORE:
        logger = logging.getLogger(name)
        saved_uvicorn[name] = (list(logger.handlers), logger.level)

    yield

    logging_config._detach_installed_handlers()
    root.handlers[:] = saved_root_handlers
    root.setLevel(saved_root_level)
    for name, (handlers, level) in saved_uvicorn.items():
        logger = logging.getLogger(name)
        logger.handlers[:] = handlers
        logger.setLevel(level)


class TestFileHandler:
    def test_默认写入_RotatingFileHandler(self, tmp_path: Path) -> None:
        log_path = tmp_path / "app.log"
        result = logging_config.configure_logging(log_file=log_path, console=False)

        assert result == log_path
        handlers = logging.getLogger().handlers
        assert len(handlers) == 1
        handler = handlers[0]
        assert isinstance(handler, logging.handlers.RotatingFileHandler)
        assert handler.maxBytes == logging_config.settings.LOG_MAX_BYTES
        assert handler.backupCount == logging_config.settings.LOG_BACKUP_COUNT

    def test_INFO_带时间戳与_logger_名落盘(self, tmp_path: Path) -> None:
        log_path = tmp_path / "app.log"
        logging_config.configure_logging(log_file=log_path, level="INFO", console=False)

        logging.getLogger("app.test").info("hello %s", "world")

        text = log_path.read_text(encoding="utf-8")
        assert "hello world" in text
        assert "INFO" in text
        assert "app.test" in text
        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", text), "日志必须带时间戳"

    def test_时间戳含毫秒与时区偏移(self, tmp_path: Path) -> None:
        """只精确到秒时，同一秒内的多次保存/重连无法排序；没有偏移则跨时区无法对齐。"""
        log_path = tmp_path / "app.log"
        logging_config.configure_logging(log_file=log_path, level="INFO", console=False)

        logging.getLogger("app.test").info("tick")

        text = log_path.read_text(encoding="utf-8")
        assert re.search(
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{2}:\d{2}", text
        ), f"时间戳应为「毫秒 + 时区偏移」：{text}"

    def test_每行带请求_id占位(self, tmp_path: Path) -> None:
        """不在请求上下文里（启动日志等）时用 `-` 占位，格式才不会缺字段。"""
        log_path = tmp_path / "app.log"
        logging_config.configure_logging(log_file=log_path, level="INFO", console=False)

        logging.getLogger("app.test").info("boot")

        assert "[-] app.test boot" in log_path.read_text(encoding="utf-8")

    def test_级别过滤生效(self, tmp_path: Path) -> None:
        log_path = tmp_path / "app.log"
        logging_config.configure_logging(log_file=log_path, level="WARNING", console=False)

        logger = logging.getLogger("app.test.level")
        logger.info("这条不该出现")
        logger.warning("这条应该出现")

        text = log_path.read_text(encoding="utf-8")
        assert "这条不该出现" not in text
        assert "这条应该出现" in text

    def test_非法级别回退到_INFO(self, tmp_path: Path) -> None:
        logging_config.configure_logging(
            log_file=tmp_path / "app.log", level="VERBOSE", console=False
        )
        assert logging.getLogger().level == logging.INFO

    def test_空_LOG_FILE_退回终端(self) -> None:
        assert logging_config.configure_logging(log_file="", console=False) is None
        handlers = logging.getLogger().handlers
        assert len(handlers) == 1
        assert not isinstance(handlers[0], logging.FileHandler)

    def test_文件打不开时退回终端而不是启动失败(self, tmp_path: Path) -> None:
        """⚠️ `dictConfig` 会把文件打不开的 PermissionError 包成 ValueError，
        只捕 OSError 会漏掉这条降级路径（实测：目录不可写时启动直接失败）。"""
        target = tmp_path / "app.log"
        target.mkdir()  # 占位成目录，RotatingFileHandler 无法把它当文件打开

        assert logging_config.configure_logging(log_file=target, console=False) is None
        handlers = logging.getLogger().handlers
        assert len(handlers) == 1
        assert not isinstance(handlers[0], logging.FileHandler)

    def test_console_开关叠加文件输出(self, tmp_path: Path) -> None:
        logging_config.configure_logging(
            log_file=tmp_path / "app.log", console=True
        )
        handlers = logging.getLogger().handlers
        assert len(handlers) == 2
        assert any(isinstance(h, logging.handlers.RotatingFileHandler) for h in handlers)
        assert any(
            isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
            for h in handlers
        )

    def test_重复调用不堆叠_handler(self, tmp_path: Path) -> None:
        first = tmp_path / "first.log"
        second = tmp_path / "second.log"
        logging_config.configure_logging(log_file=first, console=False)
        logging_config.configure_logging(log_file=second, console=False)

        root_handlers = logging.getLogger().handlers
        assert len(root_handlers) == 1
        assert Path(root_handlers[0].baseFilename) == second
        assert len(logging.getLogger("uvicorn.access").handlers) == 1


class TestUvicornAndRedaction:
    def test_uvicorn_日志写入同一文件(self, tmp_path: Path) -> None:
        log_path = tmp_path / "app.log"
        logging_config.configure_logging(log_file=log_path, console=False)

        file_handler = logging.getLogger().handlers[0]
        assert file_handler in logging.getLogger("uvicorn").handlers
        assert file_handler in logging.getLogger("uvicorn.access").handlers

        logging.getLogger("uvicorn.access").info(
            '127.0.0.1:5000 - "GET /health HTTP/1.1" 200'
        )
        assert "GET /health" in log_path.read_text(encoding="utf-8")

    def test_token_在文件里也被脱敏(self, tmp_path: Path) -> None:
        """文件 handler 必须和终端 handler 一样被脱敏包住。"""
        log_path = tmp_path / "app.log"
        logging_config.configure_logging(log_file=log_path, console=False)
        install_log_redaction()

        logging.getLogger("uvicorn.access").info(
            '127.0.0.1:5000 - "GET /ws?token=SECRET_VALUE_123 HTTP/1.1" 200'
        )

        text = log_path.read_text(encoding="utf-8")
        assert "SECRET_VALUE_123" not in text
        assert f"token={REDACTED}" in text

    def test_search_参数在文件里也被脱敏(self, tmp_path: Path) -> None:
        """访问日志会带 query string，搜索词同样不能落盘。"""
        log_path = tmp_path / "app.log"
        logging_config.configure_logging(log_file=log_path, console=False)
        install_log_redaction()

        logging.getLogger("uvicorn.access").info(
            '127.0.0.1:5000 - "GET /clipboard/items?search=SECRET_SEARCH HTTP/1.1" 200'
        )

        text = log_path.read_text(encoding="utf-8")
        assert "SECRET_SEARCH" not in text
        assert f"search={REDACTED}" in text

    def test_脱敏是幂等的(self, tmp_path: Path) -> None:
        logging_config.configure_logging(log_file=tmp_path / "app.log", console=False)
        assert install_log_redaction() >= 1, "至少包住 file handler"
        assert install_log_redaction() == 0, "重复调用不应再次包装"

    def test_纯终端模式的应用日志也被脱敏(self) -> None:
        """⚠️ `LOG_FILE` 为空时只剩 root 的 console handler。

        只包 uvicorn 的 handler 会让业务日志（如登录失败里的用户名）裸奔。
        """
        from app.core.logging_utils import _RedactingFormatter

        logging_config.configure_logging(log_file="", console=True)
        install_log_redaction()

        root_handlers = logging.getLogger().handlers
        assert root_handlers, "纯终端模式必须有 console handler"
        assert all(
            isinstance(handler.formatter, _RedactingFormatter) for handler in root_handlers
        ), "root 上所有 handler 都必须被脱敏包住"


class TestResolveLogPath:
    def test_相对路径按_server_目录解析(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(logging_config.settings, "LOG_FILE", "logs/x.log")
        assert logging_config.resolve_log_path() == logging_config.BASE_DIR / "logs" / "x.log"

    def test_空白值表示不写文件(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(logging_config.settings, "LOG_FILE", "   ")
        assert logging_config.resolve_log_path() is None

    def test_绝对路径原样使用(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        target = tmp_path / "abs.log"
        monkeypatch.setattr(logging_config.settings, "LOG_FILE", str(target))
        assert logging_config.resolve_log_path() == target


def test_应用代码不再使用_print() -> None:
    """启动日志必须走 logging：print 没有级别/时间戳，重定向时还会被缓冲。"""
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders = [
        str(path.relative_to(app_dir))
        for path in app_dir.rglob("*.py")
        if "print(" in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"这些文件仍在使用 print(): {offenders}"
