"""认证接口的集成测试（打测试库 `clipboard_test`）。

覆盖注册/登录/取当前用户，重点是**安全相关行为**：
密码上限按字节、失败提示不泄露账号是否存在、令牌无效一律 401。
"""

from __future__ import annotations

from httpx import AsyncClient

from app.core.config import settings

PASSWORD = "test-password-123"


async def register(
    client: AsyncClient, username: str, email: str | None = None, password: str = PASSWORD
) -> tuple[int, dict]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email or f"{username}@example.com",
            "password": password,
        },
    )
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
        status, _ = await register(client, "exact72", password="密" * 24)
        assert status == 201


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

    async def test_用户不存在返回_401(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/login", json={"username": "nobody", "password": PASSWORD}
        )
        assert response.status_code == 401

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
