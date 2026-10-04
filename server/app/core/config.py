"""应用配置。

所有配置项均可通过环境变量或 `server/.env` 覆盖。
**禁止在代码中硬编码密钥**（见 AGENT.md 第 9 节）。
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
        "当前为阶段一（文字剪贴板 MVP）第 1 步：骨架 + 数据契约。"
    )
    APP_ENV: str = "development"
    # ⚠️ 默认关闭。DEBUG 会影响错误详情暴露与开发路由的行为，
    # 生产环境务必保持 False（见 docs/roadmap.md 的 P1）。
    DEBUG: bool = False
    # 开发/测试辅助路由（如 /api/v1/dev/reset）的总开关。
    # 故意与 DEBUG 解耦：DEBUG 可能因调试临时打开，而清库类接口绝不该跟着被打开。
    ENABLE_DEV_ROUTES: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # --- CORS ---
    # Web 端开发服务器（Vite）与鸿蒙调试端
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
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
