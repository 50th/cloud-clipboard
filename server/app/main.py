"""云剪贴板后端应用入口。

启动：
    cd server
    .\\venv\\Scripts\\python.exe -m uvicorn app.main:app --reload --port 8000

文档：
    http://127.0.0.1:8000/docs        Swagger UI
    http://127.0.0.1:8000/redoc       ReDoc
    http://127.0.0.1:8000/openapi.json
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import assert_production_secret, settings
from app.core.logging_utils import install_log_redaction
from app.core.single_worker import assert_single_worker, release_single_worker
from app.db.session import dispose_engine, ping
from app.routers import auth, clipboard, dev, ws

TAGS_METADATA: list[dict[str, Any]] = [
    {
        "name": "认证",
        "description": (
            "注册、登录、获取当前用户。登录后返回 JWT，"
            "后续请求需在 `Authorization: Bearer <token>` 中携带。"
        ),
    },
    {
        "name": "剪贴板",
        "description": (
            "文字剪贴板的上传、列表、详情、删除。"
            "数据持久化在 PostgreSQL；同一用户提交相同内容会命中去重，不新建记录。"
        ),
    },
    {
        "name": "系统",
        "description": "健康检查、服务信息，以及仅开发环境可用的辅助接口。",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期：启动时探测数据库，退出时释放连接池。

    第 5 步将在此初始化 Redis 订阅。
    """
    print(f"[startup] {settings.APP_NAME} v{settings.APP_VERSION} ({settings.APP_ENV})")
    # 生产环境若仍用开发默认密钥，直接拒绝启动（宁可起不来，也不要弱密钥上线）
    assert_production_secret()
    # WebSocket 广播是进程内实现：多 worker 会导致"数据一致但推送丢事件"。
    # 用单实例锁端口检测，CLI 的 --workers 与环境变量两条路径都能拦下。
    lock_port = assert_single_worker()
    print(f"[startup] 单实例守卫已生效（锁端口 {lock_port}）；WebSocket 广播依赖单 worker")
    # WS 的 token 走 query string，会被访问日志明文记录，必须脱敏。
    # 主防线是端点里的 scrub_scope_token（日志里压根不出现 token），
    # 这里再包一层 formatter 兜住其他 logger。
    install_log_redaction()
    try:
        info = await ping()
        print(f"[startup] 数据库已连接: {info['database']} · {info['version']}")
    except Exception as exc:  # noqa: BLE001 - 启动阶段要把原因打清楚
        print(f"[startup] ⚠️ 数据库连接失败: {type(exc).__name__}: {exc}")
        print("[startup] 请确认容器已启动: docker compose -f infra/docker-compose.yml up -d")
    print("[startup] Swagger UI: http://127.0.0.1:8000/docs")
    yield
    await dispose_engine()
    release_single_worker()
    print("[shutdown] bye")


def create_app() -> FastAPI:
    """构造并配置 FastAPI 应用。"""
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # 跨域：Web 端开发服务器（Vite，端口见 web/vite.config.ts）与鸿蒙调试端需要
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 业务路由统一挂在 /api/v1 下
    application.include_router(auth.router, prefix=settings.API_V1_PREFIX)
    application.include_router(clipboard.router, prefix=settings.API_V1_PREFIX)
    # WebSocket 实时同步（与 clipboard 路由同为 /clipboard 前缀，挂在 /clipboard/ws）
    application.include_router(ws.router, prefix=settings.API_V1_PREFIX)

    # 开发/测试辅助路由。受独立的 ENABLE_DEV_ROUTES 控制，**不复用 DEBUG**：
    # /dev/reset 会删数据，绝不能因为调试开了 DEBUG 就跟着可用。
    if settings.ENABLE_DEV_ROUTES:
        application.include_router(dev.router, prefix=settings.API_V1_PREFIX)

    @application.get("/", tags=["系统"], summary="服务信息")
    async def root() -> dict[str, Any]:
        """返回服务基本信息与关键入口，便于健康检查。"""
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "env": settings.APP_ENV,
            "api_prefix": settings.API_V1_PREFIX,
            "docs": "/docs",
            "openapi": "/openapi.json",
            "ws_endpoint": f"{settings.API_V1_PREFIX}/clipboard/ws",
        }

    @application.get("/health", tags=["系统"], summary="健康检查")
    async def health() -> dict[str, str]:
        """存活探针。"""
        return {"status": "ok"}

    return application


app = create_app()
