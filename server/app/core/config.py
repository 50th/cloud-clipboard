"""应用配置。

所有配置项均可通过环境变量或 `server/.env` 覆盖。
**禁止在代码中硬编码密钥**（见 AGENTS.md 的「关键约束 · 安全」）。
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
        "阶段一已完成（仅文字），数据持久化在 PostgreSQL。"
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

    # --- JWT 认证 ---
    # ⚠️ 默认值仅用于本地开发。生产必须通过 .env 覆盖，否则任何人都能签发合法 token。
    # 启动时 `assert_production_secret()` 会拦下"生产环境仍用默认密钥"的情况。
    # 长度按 RFC 7518 3.2：HS256 的密钥不应短于 32 字节，否则 PyJWT 会发
    # InsecureKeyLengthWarning，故开发默认值也保持 32 字节以上。
    JWT_SECRET: str = "dev-only-insecure-secret-change-me-in-production-32b"
    JWT_ALGORITHM: str = "HS256"
    # 默认 7 天（10080 分钟）
    JWT_EXPIRE_MINUTES: int = 10080

    # --- 演示用户（仅用于本地开发/测试播种；真实登录已接入，不再是兜底身份）---
    DEMO_USER_ID: str = "3f1a9c62-7d4b-4e18-9f2a-6b0c5d8e1a34"
    DEMO_USERNAME: str = "demo"
    DEMO_EMAIL: str = "demo@cloud-clipboard.dev"
    # 演示用户的初始密码，供 init_db 播种一个可直接登录的演示账号。
    DEMO_PASSWORD: str = "demo1234"

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

# 默认密钥（仅限本地开发）。生产环境仍在用它就必须拦下。
DEFAULT_JWT_SECRET = "dev-only-insecure-secret-change-me-in-production-32b"


def assert_production_secret() -> None:
    """生产环境下若仍使用默认 JWT 密钥，直接拒绝启动。

    失败即退出胜过"悄悄用弱密钥上线"：默认密钥是公开可见的，
    任何人都能伪造出通过校验的 token。
    """
    if settings.APP_ENV != "production":
        return
    if settings.JWT_SECRET == DEFAULT_JWT_SECRET or len(settings.JWT_SECRET) < 32:
        raise RuntimeError(
            "生产环境必须通过 .env 设置足够长的 JWT_SECRET（至少 32 字符），"
            "当前仍是开发默认值。"
        )
