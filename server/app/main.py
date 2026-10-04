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

from app.core.config import settings
from app.routers import auth, clipboard, dev

TAGS_METADATA: list[dict[str, Any]] = [
    {
        "name": "认证",
        "description": (
            "注册、登录、获取当前用户。**第 4 步接入真实 JWT 后**才会校验凭证；"
            "当前所有接口都返回演示用户。"
        ),
    },
    {
        "name": "剪贴板",
        "description": (
            "文字剪贴板的上传、列表、详情、删除。"
            "数据保存在进程内存中，**重启即重置为种子数据**（第 3 步接入 PostgreSQL 后消除）。"
        ),
    },
    {
        "name": "系统",
        "description": "健康检查与服务信息。",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期钩子。

    第 3 步在此初始化数据库连接池，第 5 步在此初始化 Redis 订阅。
    """
    print(f"[startup] {settings.APP_NAME} v{settings.APP_VERSION} ({settings.APP_ENV})")
    print(f"[startup] Swagger UI: http://127.0.0.1:8000/docs")
    yield
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

    # 跨域：Web 端（Vite 5173）与鸿蒙调试端需要
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
    # 第 5 步在此注册 WebSocket 路由：application.include_router(ws.router, ...)

    # 开发/测试辅助路由（重置种子数据）。
    # 受独立的 ENABLE_DEV_ROUTES 控制，**不复用 DEBUG**：
    # 第 3 步接入数据库后该路由会变成"清库"，绝不能因为调试开了 DEBUG 就跟着可用。
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
