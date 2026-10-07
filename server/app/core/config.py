"""应用配置。

所有配置项均可通过环境变量或 `server/.env` 覆盖。
**禁止在代码中硬编码密钥**（见 AGENTS.md 第 9 节）。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """云剪贴板后端配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- 应用 ---
    APP_NAME: str = "Cloud Clipboard"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = (
        "跨平台云剪贴板服务 —— 多设备剪贴板内容实时同步。"
        "当前为阶段一（文字剪贴板 MVP），数据已持久化到 PostgreSQL。"
    )
    APP_ENV: str = "development"
    # ⚠️ 默认关闭。DEBUG 会影响错误详情暴露，生产务必保持 False。
    # 决策理由（为何与 ENABLE_DEV_ROUTES 解耦）见 `.env.example` 的「安全开关」注释。
    DEBUG: bool = False
    # 开发/测试辅助路由（如 /api/v1/dev/reset）的总开关。
    # 故意与 DEBUG 解耦：DEBUG 可能因调试临时打开，而该路由会清库，绝不该跟着被打开。
    ENABLE_DEV_ROUTES: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # --- 数据库 ---
    # 本地容器：宿主 5433（5432 被本机原生 PostgreSQL 18 占用）
    DATABASE_URL: str = (
        "postgresql+asyncpg://clipboard:clipboard@127.0.0.1:5433/clipboard"
    )
    # 打开后会把每条 SQL 打到日志，排查问题时用
    DB_ECHO: bool = False

    # --- 时区 ---
    # 自动生成标题时展示用的时区。数据库统一存 UTC，这里只影响标题里的时间文本。
    # 前端会把自己的 IANA 时区（如 Asia/Shanghai）随创建请求传来并优先使用；
    # 本配置是前端未传或传了非法值时的兜底。
    DEFAULT_TIMEZONE: str = "Asia/Shanghai"

    # --- 演示用户（第 4 步接入真实登录前，所有请求都归属该用户）---
    DEMO_USER_ID: str = "3f1a9c62-7d4b-4e18-9f2a-6b0c5d8e1a34"
    DEMO_USERNAME: str = "demo"
    DEMO_EMAIL: str = "demo@cloud-clipboard.dev"

    # --- CORS ---
    # Web 端开发服务器（Vite）+ 鸿蒙调试端
    CORS_ORIGINS: list[str] = [
        "http://localhost:5273",
        "http://127.0.0.1:5273",
        "http://localhost:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """允许用逗号分隔的字符串代替 JSON 数组。"""
        if isinstance(value, str) and not value.strip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """返回全局唯一的配置实例（带缓存）。"""
    return Settings()


settings = get_settings()
