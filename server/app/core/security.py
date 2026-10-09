"""认证原语：密码哈希与 JWT 签发/校验。

**分层约定**：本模块只提供纯函数式的原语，不碰数据库、不读请求头。
解析 `Authorization` 头、查库取用户等 HTTP 相关逻辑放在 `app/routers/auth.py`，
这样本模块可被 WebSocket 鉴权（`app/routers/ws.py`）直接复用。

依赖选择：
- 密码哈希用 `pwdlib`（bcrypt 后端）。不用 passlib：Python 3.13 已按 PEP 594
  移除标准库 `crypt`，passlib 在 import 阶段就会失败。
- JWT 用 `PyJWT`。只需 HS256 对称签名，无需 python-jose 的算法矩阵。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

# ⚠️ 必须显式构造，不能用 `PasswordHash.recommended()`：
#    后者只返回 Argon2Hasher，而本项目安装的是 `pwdlib[bcrypt]`，
#    未装 argon2-cffi 时会抛 HasherNotAvailable。
# rounds=12 是 bcrypt 的常用默认值（pwdlib 默认值一致，这里写出来避免隐式依赖）。
password_hasher = PasswordHash((BcryptHasher(rounds=12),))

# bcrypt 只取密码的前 72 字节，超过会直接抛 ValueError（5.x 起不再静默截断）。
# Schema 层的 max_length=72 与此对应；此处再挡一道，避免绕过 Schema 的调用方炸掉。
MAX_PASSWORD_BYTES = 72


class PasswordTooLongError(ValueError):
    """密码超过 bcrypt 的 72 字节上限。"""


def hash_password(password: str) -> str:
    """把明文密码转成可入库的 bcrypt 哈希（60 字符，含算法与盐）。"""
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(
            f"密码不能超过 {MAX_PASSWORD_BYTES} 字节（bcrypt 上限）"
        )
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """校验明文密码与哈希是否匹配。

    `password_hash` 为 None（如早期无密码的演示用户）或格式无法识别时一律返回 False，
    不抛异常——调用方只关心"能不能登录"，不该被存储层的脏数据打断。

    注意：本函数不做长度校验。**校验与哈希必须用同一个算法**，
    而 bcrypt 对超长密码抛异常而非截断，所以这里也直接返回 False 更安全。
    """
    if not password_hash:
        return False
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return False
    try:
        return password_hasher.verify(password, password_hash)
    except Exception:  # noqa: BLE001 - 哈希损坏/算法未知，一律视为校验失败
        return False


def create_access_token(
    subject: str | uuid.UUID,
    *,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """签发 JWT。

    `subject` 写入标准 `sub` 声明（本项目的用户 UUID）。
    同时写入 `iat` 与 `exp`，`exp` 由 `JWT_EXPIRE_MINUTES` 推导。
    """
    now = datetime.now(timezone.utc)
    delta = expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + delta).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """校验并解码 JWT；无效、过期或签名不符时返回 None。

    刻意不抛异常：调用方（HTTP 依赖、WebSocket 握手）只需区分"有效/无效"。
    算法白名单固定为配置值，避免 `alg: none` 之类的降级攻击。
    """
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError:
        return None


def get_token_subject(token: str) -> str | None:
    """取出 token 的 `sub`（用户 id）；无效或缺失时返回 None。"""
    payload = decode_access_token(token)
    if payload is None:
        return None
    subject = payload.get("sub")
    return str(subject) if subject else None


def access_token_expires_in() -> int:
    """token 有效期（秒），用于响应体里的 `expires_in`。"""
    return settings.JWT_EXPIRE_MINUTES * 60
