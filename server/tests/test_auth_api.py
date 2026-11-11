"""认证接口的集成测试（打测试库 `clipboard_test`）。

覆盖注册/登录/取当前用户，重点是**安全相关行为**：
密码上限按字节、失败提示不泄露账号是否存在、令牌无效一律 401。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud import invite as invite_crud

PASSWORD = "test-password-123"


async def register(
    client: AsyncClient,
    username: str,
    email: str | None = None,
    password: str = PASSWORD,
    invite_code: str | None = None,
) -> tuple[int, dict]:
    body: dict = {
        "username": username,
        "email": email or f"{username}@example.com",
        "password": password,
    }
    if invite_code is not None:
        body["invite_code"] = invite_code
    response = await client.post("/api/v1/auth/register", json=body)
    return response.status_code, response.json()


class TestRegister:
    async def test_注册成功并直接返回令牌(self, client: AsyncClient) -> None:
        status, body = await register(client, "alice")
        assert status == 201
        assert body["username"] == "alice"
        assert body["token"]["access_token"]
        assert body["token"]["token_type"] == "bearer"
        assert body["token"]["expires_in"] == settings.JWT_EXPIRE_MINUTES * 60

    async def test_响应绝不包含密码哈希(self, client: AsyncClient) -> None:
        _, body = await register(client, "bob")
        assert "password_hash" not in body
        assert "password" not in body
        assert "password_hash" not in str(body)

    async def test_重名返回_409(self, client: AsyncClient) -> None:
        await register(client, "carol")
        status, _ = await register(client, "carol", email="other@example.com")
        assert status == 409

    async def test_重复邮箱返回_409(self, client: AsyncClient) -> None:
        await register(client, "dave", email="shared@example.com")
        status, _ = await register(client, "dave2", email="shared@example.com")
        assert status == 409

    async def test_密码过短返回_422(self, client: AsyncClient) -> None:
        status, _ = await register(client, "shorty", password="12345")
        assert status == 422

    async def test_用户名过短返回_422(self, client: AsyncClient) -> None:
        status, _ = await register(client, "ab")
        assert status == 422

    async def test_密码超过_72_字节返回_422_而不是_500(self, client: AsyncClient) -> None:
        """⚠️ 关键用例：bcrypt 对 >72 字节抛错，若不预先校验会变成 500。

        用 25 个汉字（=75 字节）验证——只按字符数校验会漏掉这种情况。
        """
        status, _ = await register(client, "longpw", password="密" * 25)
        assert status == 422, "应在契约层被拒，不能冒泡成服务端错误"

    async def test_恰好_72_字节的密码可用(self, client: AsyncClient) -> None:
        # 6 个 ASCII 字符（含字母与数字）+ 22 个汉字 = 6 + 66 = 72 字节
        status, _ = await register(
            client, "exact72", password="Aa1!ab" + "密" * 22
        )
        assert status == 201

    async def test_密码缺少字母返回_422(self, client: AsyncClient) -> None:
        status, _ = await register(client, "only-digits", password="12345678")
        assert status == 422

    async def test_密码缺少数字返回_422(self, client: AsyncClient) -> None:
        status, _ = await register(client, "only-letters", password="onlyletters")
        assert status == 422

    async def test_密码不能包含用户名(self, client: AsyncClient) -> None:
        status, _ = await register(client, "alice-pw", password="Alice-pw123")
        assert status == 422

    async def test_密码不能包含用户名且不区分大小写(self, client: AsyncClient) -> None:
        status, _ = await register(client, "bob-pw", password="xxBOB-PW123")
        assert status == 422

    async def test_用户名含换行被拒(self, client: AsyncClient) -> None:
        """换行会破坏日志行结构（日志注入），必须在契约层拒绝。"""
        status, _ = await register(client, "evil\nname")
        assert status == 422


class TestRegisterInviteCode:
    """邀请码注册：默认开放；开启后必须使用数据库中的有效邀请码。"""

    async def test_未开启邀请码要求时保持开放注册(self, client: AsyncClient) -> None:
        status, _ = await register(client, "open-register")
        assert status == 201

    async def test_开启后缺少邀请码返回_403(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "REGISTRATION_REQUIRE_INVITE", True)
        status, body = await register(client, "no-invite")
        assert status == 403
        assert body["detail"] == "邀请码无效"

    async def test_开启后不存在的邀请码返回_403(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "REGISTRATION_REQUIRE_INVITE", True)
        status, _ = await register(client, "bad-invite", invite_code="NOTEXIST")
        assert status == 403

    async def test_有效邀请码可注册且大小写不敏感(
        self,
        client: AsyncClient,
        session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        code, row = await invite_crud.create_code(session, max_uses=1, label="test")
        monkeypatch.setattr(settings, "REGISTRATION_REQUIRE_INVITE", True)
        status, body = await register(client, "invite-ok", invite_code=code.lower())
        assert status == 201
        assert body["username"] == "invite-ok"
        await session.refresh(row)
        assert row.used_count == 1

    async def test_邀请码用尽后再次注册返回_403(
        self,
        client: AsyncClient,
        session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        code, _ = await invite_crud.create_code(session, max_uses=1)
        monkeypatch.setattr(settings, "REGISTRATION_REQUIRE_INVITE", True)
        first, _ = await register(client, "quota-first", invite_code=code)
        second, _ = await register(client, "quota-second", invite_code=code)
        assert first == 201
        assert second == 403

    async def test_过期邀请码返回_403(
        self,
        client: AsyncClient,
        session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        code, _ = await invite_crud.create_code(
            session,
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        monkeypatch.setattr(settings, "REGISTRATION_REQUIRE_INVITE", True)
        status, _ = await register(client, "expired-invite", invite_code=code)
        assert status == 403

    async def test_已撤销邀请码返回_403(
        self,
        client: AsyncClient,
        session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        code, row = await invite_crud.create_code(session)
        await invite_crud.revoke_code(session, code_id=row.id)
        monkeypatch.setattr(settings, "REGISTRATION_REQUIRE_INVITE", True)
        status, _ = await register(client, "revoked-invite", invite_code=code)
        assert status == 403

    async def test_不限次数的邀请码可多次使用(
        self,
        client: AsyncClient,
        session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        code, _ = await invite_crud.create_code(session, max_uses=None)
        monkeypatch.setattr(settings, "REGISTRATION_REQUIRE_INVITE", True)
        first, _ = await register(client, "unlimited-1", invite_code=code)
        second, _ = await register(client, "unlimited-2", invite_code=code)
        assert first == 201
        assert second == 201

    async def test_注册失败不会消耗邀请码(
        self,
        client: AsyncClient,
        session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """重名返回 409 时必须回滚，避免白白扣掉一次使用机会。"""
        code, row = await invite_crud.create_code(session, max_uses=2)
        monkeypatch.setattr(settings, "REGISTRATION_REQUIRE_INVITE", True)
        first, _ = await register(client, "dup-user", invite_code=code)
        duplicate, _ = await register(client, "dup-user", invite_code=code)
        assert first == 201
        assert duplicate == 409
        await session.refresh(row)
        assert row.used_count == 1

    async def test_邀请码校验失败日志不含邀请码(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setattr(settings, "REGISTRATION_REQUIRE_INVITE", True)
        with caplog.at_level(logging.WARNING, logger="app.routers.auth"):
            await register(client, "log-invite", invite_code="WRONGSECRET")
        assert "invalid_invite_code" in caplog.text
        assert "WRONGSECRET" not in caplog.text


class TestLogin:
    async def test_用户名登录(self, client: AsyncClient) -> None:
        await register(client, "erin")
        response = await client.post(
            "/api/v1/auth/login", json={"username": "erin", "password": PASSWORD}
        )
        assert response.status_code == 200
        assert response.json()["token"]["access_token"]

    async def test_邮箱登录(self, client: AsyncClient) -> None:
        await register(client, "frank", email="frank@example.com")
        response = await client.post(
            "/api/v1/auth/login", json={"username": "frank@example.com", "password": PASSWORD}
        )
        assert response.status_code == 200

    async def test_密码错误返回_401(self, client: AsyncClient) -> None:
        await register(client, "grace")
        response = await client.post(
            "/api/v1/auth/login", json={"username": "grace", "password": "wrong-password"}
        )
        assert response.status_code == 401

    async def test_登录失败会留痕但绝不含密码(
        self, client: AsyncClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        """失败日志是暴力破解审计的唯一线索；密码本身绝不能进日志。"""
        await register(client, "grace-log")
        with caplog.at_level(logging.WARNING, logger="app.routers.auth"):
            await client.post(
                "/api/v1/auth/login",
                json={"username": "grace-log", "password": "wrong-password"},
            )
        assert "登录失败" in caplog.text
        assert "wrong-password" not in caplog.text

    async def test_用户不存在返回_401(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/login", json={"username": "nobody", "password": PASSWORD}
        )
        assert response.status_code == 401

    async def test_登录用户名含换行返回_422(self, client: AsyncClient) -> None:
        """换行会破坏日志行结构（日志注入），必须在契约层拒绝。"""
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "evil\nname", "password": PASSWORD},
        )
        assert response.status_code == 422

    async def test_登录用户名超长返回_422(self, client: AsyncClient) -> None:
        """登录框允许邮箱（上限 254），超出直接拒绝而不是写进日志。"""
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "x" * 255, "password": PASSWORD},
        )
        assert response.status_code == 422

    async def test_登录失败日志带客户端地址(
        self, client: AsyncClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        """暴力破解审计需要来源 IP，否则只知道"有人试过"。"""
        with caplog.at_level(logging.WARNING, logger="app.routers.auth"):
            await client.post(
                "/api/v1/auth/login", json={"username": "nobody", "password": PASSWORD}
            )
        assert "client=" in caplog.text

    async def test_失败提示不区分账号是否存在(self, client: AsyncClient) -> None:
        """否则可用于枚举已注册用户名。"""
        await register(client, "henry")
        wrong_password = await client.post(
            "/api/v1/auth/login", json={"username": "henry", "password": "wrong"}
        )
        no_such_user = await client.post(
            "/api/v1/auth/login", json={"username": "nobody", "password": "wrong"}
        )
        assert wrong_password.status_code == no_such_user.status_code == 401
        assert wrong_password.json()["detail"] == no_such_user.json()["detail"]

    async def test_401_带_WWW_Authenticate_头(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/login", json={"username": "nobody", "password": PASSWORD}
        )
        assert response.headers.get("www-authenticate") == "Bearer"


class TestChangePassword:
    """用户自助修改密码：凭证校验、密码策略与令牌撤销。"""

    NEW_PASSWORD = "changed-password-456"

    async def test_修改成功后旧令牌与旧密码全部失效(
        self, client: AsyncClient
    ) -> None:
        _, body = await register(client, "pw-change")
        headers = {"Authorization": f"Bearer {body['token']['access_token']}"}

        response = await client.post(
            "/api/v1/auth/change-password",
            json={"old_password": PASSWORD, "new_password": self.NEW_PASSWORD},
            headers=headers,
        )
        assert response.status_code == 200
        assert "重新登录" in response.json()["message"]

        # 当前令牌因 token_version +1 立即失效
        assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401

        old_login = await client.post(
            "/api/v1/auth/login", json={"username": "pw-change", "password": PASSWORD}
        )
        assert old_login.status_code == 401

        new_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "pw-change", "password": self.NEW_PASSWORD},
        )
        assert new_login.status_code == 200

    async def test_当前密码错误返回_400_且不修改密码(
        self, client: AsyncClient
    ) -> None:
        _, body = await register(client, "pw-wrong-old")
        headers = {"Authorization": f"Bearer {body['token']['access_token']}"}

        response = await client.post(
            "/api/v1/auth/change-password",
            json={"old_password": "wrong-password", "new_password": self.NEW_PASSWORD},
            headers=headers,
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "当前密码错误"

        # 原密码仍然有效
        login = await client.post(
            "/api/v1/auth/login",
            json={"username": "pw-wrong-old", "password": PASSWORD},
        )
        assert login.status_code == 200

    async def test_新密码不能包含用户名(self, client: AsyncClient) -> None:
        _, body = await register(client, "pw-username")
        headers = {"Authorization": f"Bearer {body['token']['access_token']}"}

        response = await client.post(
            "/api/v1/auth/change-password",
            json={
                "old_password": PASSWORD,
                "new_password": "Pw-Username-456",
            },
            headers=headers,
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "密码不能包含用户名"

    async def test_新密码不满足复杂度返回_422(self, client: AsyncClient) -> None:
        _, body = await register(client, "pw-weak-new")
        headers = {"Authorization": f"Bearer {body['token']['access_token']}"}

        response = await client.post(
            "/api/v1/auth/change-password",
            json={"old_password": PASSWORD, "new_password": "onlyletters"},
            headers=headers,
        )
        assert response.status_code == 422

    async def test_未登录返回_401(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/change-password",
            json={"old_password": PASSWORD, "new_password": self.NEW_PASSWORD},
        )
        assert response.status_code == 401


class TestCurrentUser:
    async def test_带令牌可取当前用户(self, client: AsyncClient) -> None:
        _, body = await register(client, "ivan")
        token = body["token"]["access_token"]
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["username"] == "ivan"

    async def test_无令牌返回_401(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_401_带请求_id_响应头且日志有原因(
        self, client: AsyncClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        """⚠️ 401 必须能对上日志：响应头给出 request id，日志说明具体原因。"""
        with caplog.at_level(logging.INFO, logger="app.routers.auth"):
            response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401
        request_id = response.headers.get("x-request-id")
        assert request_id and len(request_id) == 12
        assert "鉴权失败" in caplog.text
        assert "missing token" in caplog.text
        assert "path=/api/v1/auth/me" in caplog.text

    async def test_乱码令牌返回_401(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer not.a.jwt"}
        )
        assert response.status_code == 401

    async def test_格式错误的头返回_401(self, client: AsyncClient) -> None:
        """缺少 Bearer 前缀。"""
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "some-token"}
        )
        assert response.status_code == 401

    async def test_令牌有效但用户已不存在返回_401(self, client: AsyncClient) -> None:
        from app.core import security

        orphan = security.create_access_token("00000000-0000-0000-0000-000000000000")
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {orphan}"}
        )
        assert response.status_code == 401
