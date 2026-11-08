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

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import assert_production_secret, settings
from app.core.logging_config import configure_logging
from app.core.logging_utils import install_log_redaction
from app.core.request_context import RequestIdMiddleware
from app.core.single_worker import assert_single_worker, release_single_worker
from app.db.session import dispose_engine, ping
from app.routers import auth, clipboard, dev, ws

logger = logging.getLogger(__name__)

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
    """应用生命周期：配置日志、探测数据库，退出时释放连接池。

    如后续引入 Redis Pub/Sub，在此初始化订阅。
    """
    # 必须最先做：root 默认没有 handler、级别是 WARNING，不先配日志的话
    # 下面所有 logger.info 都会被静默丢弃。
    log_path = configure_logging()
    # 脱敏要紧跟日志配置：此时 uvicorn 的 access handler 与刚装上的 file handler
    # 都已存在，才能一起包上（WS 的 token 在 query string 里）。
    install_log_redaction()

    logger.info(
        "%s v%s (%s) 启动", settings.APP_NAME, settings.APP_VERSION, settings.APP_ENV
    )
    if log_path is None:
        logger.info("日志输出: 终端（LOG_FILE 为空或不可写）")
    else:
        logger.info("日志文件: %s（级别 %s）", log_path, settings.LOG_LEVEL)

    # 生产环境若仍用开发默认密钥，直接拒绝启动（宁可起不来，也不要弱密钥上线）
    assert_production_secret()
    # WebSocket 广播是进程内实现：多 worker 会导致"数据一致但推送丢事件"。
    # 用单实例锁端口检测，CLI 的 --workers 与环境变量两条路径都能拦下。
    lock_port = assert_single_worker()
    logger.info(
        "单实例守卫已生效（锁端口 %s）；WebSocket 广播依赖单 worker", lock_port
    )
    try:
        info = await ping()
        logger.info("数据库已连接: %s · %s", info["database"], info["version"])
    except Exception as exc:  # noqa: BLE001 - 启动阶段要把原因打清楚
        logger.warning("数据库连接失败: %s: %s", type(exc).__name__, exc)
        logger.warning(
            "请确认容器已启动: docker compose -f infra/docker-compose.yml up -d"
        )
    logger.info("Swagger UI: http://127.0.0.1:8000/docs")
    yield
    await dispose_engine()
    release_single_worker()
    logger.info("服务已停止")


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
    # 请求 id 放在最外层（最后注册）：这样被 CORS 与异常处理器提前返回的响应
    # 也会带上 X-Request-ID，日志里的 request_id 才不会缺口。
    application.add_middleware(RequestIdMiddleware)

    @application.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        """兜底 5xx：把方法、路径与堆栈记下来，响应体不暴露内部细节。

        request_id 由日志格式统一带出，是客户端反馈问题时唯一的对齐线索。
        """
        logger.exception(
            "未捕获异常: %s %s (%s)", request.method, request.url.path, type(exc).__name__
        )
        return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})

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
