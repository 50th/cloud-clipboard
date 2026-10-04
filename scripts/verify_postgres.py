"""PostgreSQL 16 容器连通性与数据往返验证。

用法（宿主侧，使用 server 的 venv）：
    server\\venv\\Scripts\\python.exe scripts\\verify_postgres.py

验证项：
1. 连接可用、服务端版本与编码
2. 中文 / emoji / 引号 / 多行 / 超长文本的写入-读出往返一致性
3. timestamptz 是否带时区
4. 与 ORM 相关的类型（text / timestamptz）行为符合契约要求
"""

from __future__ import annotations

import asyncio
import sys

import asyncpg

DSN = "postgresql://clipboard:clipboard@127.0.0.1:5433/clipboard"

CASES: list[tuple[str, str]] = [
    ("自动标题样例", "demo · 10-04 14:30"),
    ("中文与标点", "云剪贴板 MVP：上传、查询、删除。"),
    ("特殊字符", "emoji 🚀 ✓ \"quotes\" 'apos' <tag> & amp"),
    ("多行文本", "line1\nline2\ttabbed"),
    ("超长内容", "x" * 5000),
]


async def main() -> int:
    conn = await asyncpg.connect(DSN)
    try:
        version = await conn.fetchval("select version()")
        encoding = await conn.fetchval("show server_encoding")
        timezone = await conn.fetchval("show TimeZone")
        print(f"  连接      : {version.split(' on ')[0]}")
        print(f"  服务端编码: {encoding}")
        print(f"  时区      : {timezone}")

        await conn.execute(
            """
            create table if not exists roundtrip(
                id serial primary key,
                title text not null,
                content text not null,
                created_at timestamptz default now()
            )
            """
        )

        for title, content in CASES:
            await conn.execute(
                "insert into roundtrip(title, content) values($1, $2)",
                title,
                content,
            )
        print(f"  写入      : {len(CASES)} 条")

        all_same = True
        for title, content in CASES:
            got = await conn.fetchval(
                "select content from roundtrip where title = $1", title
            )
            same = got == content
            all_same = all_same and same
            mark = "一致" if same else "不一致"
            print(f"  往返 {title:6}: {mark}（长度 {len(got)}）")
        print(f"  往返总判定: {'全部一致' if all_same else '存在不一致'}")

        row = await conn.fetchrow(
            "select title, created_at from roundtrip order by id limit 1"
        )
        has_tz = row["created_at"].tzinfo is not None
        print(f"  timestamptz: 带时区={has_tz} 值={row['created_at']}")

        await conn.execute("drop table roundtrip")
        print("  已清理测试表")
        return 0 if (all_same and has_tz) else 1
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
