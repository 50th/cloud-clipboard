"""后端测试夹具（第 8 步将在此基础上扩充单元测试）。

设计要点：
- **测试打独立数据库**（默认 `clipboard_test`），不碰开发库，避免测试清空真实数据
- 每个测试函数一个会话，结束后回滚，测试之间互不干扰
- 表结构由 `Base.metadata.create_all` 建立；迁移本身另用 `alembic upgrade` 验证

依赖（尚未安装，第 8 步补齐）：
    .\\venv\\Scripts\\python.exe -m pip install pytest pytest-asyncio httpx

用法：
    .\\venv\\Scripts\\python.exe -m pytest
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ⚠️ 必须在导入 app 之前设置，否则 settings 会先被 .env 里的 DATABASE_URL 填充
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://clipboard:clipboard@127.0.0.1:5433/clipboard_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.db.base import Base  # noqa: E402
from app.db.models import ClipboardItem, User  # noqa: E402,F401  （导入以注册 metadata）
from app.db.session import get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


@pytest_asyncio.fixture
async def engine() -> AsyncEngine:
    """**函数级**引擎：每个测试建一次表。

    ⚠️ 不能改成 session 级。pytest-asyncio 默认**每个测试用新的事件循环**，
    而引擎的连接池会把连接绑定在创建它的循环上；session 级引擎在第二个测试里
    就会失败：`RuntimeError: got Future attached to a different loop`
    （实测踩过）。改成函数级后，引擎的创建与释放都在同一个循环内。

    代价是每个测试重建一次表；本套件规模下耗时可忽略。
    """
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncSession:
    """函数级会话：测试结束回滚，保证互不干扰。"""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(engine: AsyncEngine) -> AsyncClient:
    """HTTP 客户端：覆盖 `get_db` 依赖，指向测试库。"""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    fastapi_app.dependency_overrides.clear()


def pytest_configure(config: pytest.Config) -> None:
    """注册 marker，并打印实际使用的测试库，便于确认没有误连开发库。"""
    config.addinivalue_line("markers", "integration: 需要真实数据库的测试")
    print(f"\n[pytest] 测试数据库: {TEST_DATABASE_URL}")
