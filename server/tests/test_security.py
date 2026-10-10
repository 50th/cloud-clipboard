"""`app/core/security.py` 的单元测试。

密码哈希与 JWT 校验是项目的安全底座，此前只有 Web 端间接覆盖。
这里直接测原语本身，包含若干**安全性质**（伪造、篡改、降级攻击必须被拒）。
"""

from __future__ import annotations

import time
import uuid
from datetime import timedelta

import jwt as pyjwt
import pytest

from app.core import security
from app.core.config import settings


class TestPasswordHashing:
    def test_哈希后可校验(self) -> None:
        hashed = security.hash_password("correct horse battery")
        assert security.verify_password("correct horse battery", hashed) is True

    def test_错误密码不通过(self) -> None:
        hashed = security.hash_password("right-password")
        assert security.verify_password("wrong-password", hashed) is False

    def test_输出是_bcrypt_格式且不含明文(self) -> None:
        plain = "my-secret-password"
        hashed = security.hash_password(plain)
        assert hashed.startswith("$2b$"), "应为 bcrypt 哈希（$2b$ 前缀）"
        assert len(hashed) == 60, "bcrypt 哈希固定 60 字符"
        assert plain not in hashed

    def test_相同密码两次哈希不同_因为盐随机(self) -> None:
        first = security.hash_password("same-password")
        second = security.hash_password("same-password")
        assert first != second, "加盐后哈希应不同，否则可被彩虹表攻击"
        # 但两者都能校验通过
        assert security.verify_password("same-password", first)
        assert security.verify_password("same-password", second)

    @pytest.mark.parametrize("password", ["密码1234", "emoji🔒pass", "内有'引号\"和空格"])
    def test_支持多字节与特殊字符(self, password: str) -> None:
        assert security.verify_password(password, security.hash_password(password))

    def test_超过_72_字节抛错而不是静默截断(self) -> None:
        """bcrypt 只取前 72 字节；若静默截断，超长密码的前缀就能登录。"""
        with pytest.raises(security.PasswordTooLongError):
            security.hash_password("a" * 73)

    def test_恰好_72_字节可用(self) -> None:
        assert security.hash_password("a" * 72)

    def test_多字节按字节数判断(self) -> None:
        """24 个汉字 = 72 字节（可用），25 个 = 75 字节（超限）。"""
        assert security.hash_password("密" * 24)
        with pytest.raises(security.PasswordTooLongError):
            security.hash_password("密" * 25)

    @pytest.mark.parametrize("bad_hash", [None, "", "not-a-hash", "$2b$12$too-short"])
    def test_哈希缺失或损坏时返回_False_而不抛异常(self, bad_hash: str | None) -> None:
        """调用方只关心能不能登录，不该被存储层的脏数据打断。"""
        assert security.verify_password("any-password", bad_hash) is False

    def test_超长密码校验直接返回_False(self) -> None:
        """避免 bcrypt 抛 ValueError 冒泡成 500。"""
        hashed = security.hash_password("normal-password")
        assert security.verify_password("a" * 73, hashed) is False


class TestAccessToken:
    def test_签发的令牌可解码出主体(self) -> None:
        subject = str(uuid.uuid4())
        token = security.create_access_token(subject)
        assert security.get_token_subject(token) == subject

    def test_接受_UUID_对象作为主体(self) -> None:
        subject = uuid.uuid4()
        token = security.create_access_token(subject)
        assert security.get_token_subject(token) == str(subject)

    def test_载荷含标准声明(self) -> None:
        token = security.create_access_token("abc")
        payload = security.decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "abc"
        assert "iat" in payload and "exp" in payload
        assert payload["exp"] > payload["iat"]

    def test_有效期与配置一致(self) -> None:
        token = security.create_access_token("abc")
        payload = security.decode_access_token(token)
        assert payload is not None
        expected = settings.JWT_EXPIRE_MINUTES * 60
        # 允许几秒误差（签发到断言之间的耗时）
        assert abs((payload["exp"] - payload["iat"]) - expected) <= 5

    def test_access_token_expires_in_返回秒(self) -> None:
        assert security.access_token_expires_in() == settings.JWT_EXPIRE_MINUTES * 60

    def test_自定义有效期(self) -> None:
        token = security.create_access_token("abc", expires_delta=timedelta(seconds=30))
        payload = security.decode_access_token(token)
        assert payload is not None
        assert 25 <= payload["exp"] - payload["iat"] <= 30

    def test_额外声明会被写入(self) -> None:
        token = security.create_access_token("abc", extra_claims={"role": "admin"})
        payload = security.decode_access_token(token)
        assert payload is not None
        assert payload["role"] == "admin"

    def test_已过期令牌被拒(self) -> None:
        token = security.create_access_token("abc", expires_delta=timedelta(seconds=-1))
        assert security.decode_access_token(token) is None
        assert security.get_token_subject(token) is None

    @pytest.mark.parametrize(
        "bad_token",
        ["", "garbage", "a.b", "a.b.c", "not.a.jwt", ".."],
    )
    def test_格式非法令牌被拒(self, bad_token: str) -> None:
        assert security.decode_access_token(bad_token) is None

    def test_篡改签名被拒(self) -> None:
        token = security.create_access_token("abc")
        tampered = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")
        assert security.decode_access_token(tampered) is None

    def test_篡改载荷被拒(self) -> None:
        """改 sub 但保留原签名 → 签名校验必须失败。"""
        import base64
        import json

        token = security.create_access_token("victim")
        header, payload, signature = token.split(".")
        decoded = json.loads(base64.urlsafe_b64decode(payload + "=="))
        decoded["sub"] = "attacker"
        forged_payload = (
            base64.urlsafe_b64encode(json.dumps(decoded).encode()).rstrip(b"=").decode()
        )
        forged = f"{header}.{forged_payload}.{signature}"
        assert security.decode_access_token(forged) is None

    def test_他人密钥签发的令牌被拒(self) -> None:
        # 密钥长度按 RFC 7518 给足 32 字节，免得测试输出里混入 PyJWT 的长度警告
        forged = pyjwt.encode(
            {"sub": "attacker", "exp": int(time.time()) + 3600},
            "attacker-secret-with-enough-length-32b",
            algorithm="HS256",
        )
        assert security.decode_access_token(forged) is None
        assert security.get_token_subject(forged) is None

    def test_alg_none_降级攻击被拒(self) -> None:
        """经典的 JWT 攻击：把算法改成 none 绕过签名。"""
        import base64
        import json

        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).rstrip(b"=")
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "attacker", "exp": int(time.time()) + 3600}).encode()
        ).rstrip(b"=")
        forged = f"{header.decode()}.{payload.decode()}."
        assert security.decode_access_token(forged) is None

    def test_令牌缺少_sub_时返回_None(self) -> None:
        token = pyjwt.encode({"exp": int(time.time()) + 3600}, settings.JWT_SECRET, algorithm="HS256")
        assert security.get_token_subject(token) is None

    def test_空_sub_返回_None(self) -> None:
        token = security.create_access_token("")
        # sub 为空字符串时不应被当作有效用户
        assert security.get_token_subject(token) is None
