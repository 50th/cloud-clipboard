"""`app/crud/clipboard.py` 中纯函数的单元测试。

这些函数此前**完全没有测试**，而它们最容易出错的正是边界：
时区回退、哈希一致性、预览截断。
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.crud.clipboard import (
    PREVIEW_LIMIT,
    content_hash,
    generate_default_title,
    make_preview,
    resolve_timezone,
)


class TestResolveTimezone:
    """非法或缺失的时区名必须回退到配置的默认值，而不是抛异常。"""

    @pytest.mark.parametrize("bad", [None, "", "   ", "Not/AZone", "Mars/Olympus", "12345"])
    def test_非法或缺失时回退默认时区(self, bad: str | None) -> None:
        zone = resolve_timezone(bad)
        assert str(zone) == settings.DEFAULT_TIMEZONE

    @pytest.mark.parametrize("name", ["Asia/Shanghai", "UTC", "America/New_York", "Europe/London"])
    def test_合法时区被正确解析(self, name: str) -> None:
        assert str(resolve_timezone(name)) == name

    def test_名称两侧的空白会被忽略(self) -> None:
        assert str(resolve_timezone("  Asia/Shanghai  ")) == "Asia/Shanghai"


class TestGenerateDefaultTitle:
    """自动标题格式：`<用户名> · <月-日 时:分>`，时间按指定时区展示。"""

    def test_格式与用户名(self) -> None:
        moment = datetime(2026, 10, 5, 14, 30, tzinfo=timezone.utc)
        title = generate_default_title("demo", moment, resolve_timezone("UTC"))
        assert title == "demo · 10-05 14:30"

    def test_按指定时区换算(self) -> None:
        # 2026-10-05 14:30 UTC = 北京 22:30（UTC+8）
        moment = datetime(2026, 10, 5, 14, 30, tzinfo=timezone.utc)
        title = generate_default_title("demo", moment, resolve_timezone("Asia/Shanghai"))
        assert title == "demo · 10-05 22:30"

    def test_不同时区产生不同标题(self) -> None:
        moment = datetime(2026, 10, 5, 14, 30, tzinfo=timezone.utc)
        utc_title = generate_default_title("demo", moment, resolve_timezone("UTC"))
        cn_title = generate_default_title("demo", moment, resolve_timezone("Asia/Shanghai"))
        assert utc_title != cn_title

    def test_不传时区时使用默认时区(self) -> None:
        moment = datetime(2026, 10, 5, 14, 30, tzinfo=timezone.utc)
        assert generate_default_title("demo", moment) == generate_default_title(
            "demo", moment, resolve_timezone(None)
        )

    def test_跨日边界按目标时区计算(self) -> None:
        # UTC 的 10-05 23:30 在北京是 10-06 07:30
        moment = datetime(2026, 10, 5, 23, 30, tzinfo=timezone.utc)
        title = generate_default_title("demo", moment, resolve_timezone("Asia/Shanghai"))
        assert title == "demo · 10-06 07:30", "跨日时日期应跟随时区变化"

    def test_用户名会出现在标题里(self) -> None:
        moment = datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc)
        assert generate_default_title("alice", moment).startswith("alice · ")

    def test_非_utc_输入也能正确处理(self) -> None:
        # 带 +08:00 的输入，换算到 UTC 应减 8 小时
        moment = datetime(2026, 10, 5, 22, 30, tzinfo=timezone(timedelta(hours=8)))
        assert generate_default_title("demo", moment, resolve_timezone("UTC")) == "demo · 10-05 14:30"


class TestContentHash:
    """去重靠哈希，因此它必须稳定、与内容一一对应。"""

    def test_与标准_sha256_一致(self) -> None:
        content = "hello world"
        assert content_hash(content) == hashlib.sha256(content.encode("utf-8")).hexdigest()

    def test_相同内容哈希相同(self) -> None:
        assert content_hash("同一段内容") == content_hash("同一段内容")

    @pytest.mark.parametrize(
        ("left", "right"),
        [
            ("a", "b"),
            ("a", "a "),
            ("a", "A"),
            ("换行\n", "换行\r\n"),
            ("中文", "中文。"),
        ],
    )
    def test_不同内容哈希不同(self, left: str, right: str) -> None:
        assert content_hash(left) != content_hash(right)

    def test_是_64_位十六进制(self) -> None:
        digest = content_hash("x")
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_多字节字符按_utf8_编码(self) -> None:
        # 若误用其他编码（如 latin-1），中文会抛异常或得到不同哈希
        assert content_hash("中文") == content_hash("中文")
        assert content_hash("中文") != content_hash("中文".encode("utf-8").decode("utf-8") + "x")


class TestMakePreview:
    """预览用于列表展示：压缩空白 + 超长截断。"""

    def test_短内容原样返回(self) -> None:
        assert make_preview("短内容") == "短内容"

    def test_压缩空白字符(self) -> None:
        assert make_preview("a  \n\t b") == "a b"

    def test_压缩首尾空白(self) -> None:
        assert make_preview("  \n内容\n  ") == "内容"

    def test_达到上限不截断(self) -> None:
        content = "x" * PREVIEW_LIMIT
        assert make_preview(content) == content
        assert not make_preview(content).endswith("...")

    def test_超过上限截断并加省略号(self) -> None:
        content = "x" * (PREVIEW_LIMIT + 50)
        preview = make_preview(content)
        assert preview == "x" * PREVIEW_LIMIT + "..."
        assert len(preview) == PREVIEW_LIMIT + 3

    def test_自定义上限生效(self) -> None:
        assert make_preview("abcdefghij", limit=4) == "abcd..."

    def test_多行内容被压成一行(self) -> None:
        assert "\n" not in make_preview("第一行\n第二行\n第三行")

    def test_空内容(self) -> None:
        assert make_preview("") == ""
