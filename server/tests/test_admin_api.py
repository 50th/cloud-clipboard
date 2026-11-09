"""后台管理接口测试。

重点覆盖认证边界、令牌撤销、审计原子性与跨用户管理。
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import security
from app.core.config import settings
from app.crud import audit as audit_crud
from app.db.models import AdminAuditLog, ClipboardItem, User
from app.routers import ws as ws_router
from app.services.ws_manager import ConnectionManager, manager

PASSWORD = "admin-test-pw"
NEW_PASSWORD = "new-password-123"


async def register_user(client: AsyncClient, username: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def login_token(client: AsyncClient, username: str, password: str = PASSWORD) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]["access_token"]


async def make_admin(
    client: AsyncClient, session: AsyncSession, username: str
) -> tuple[dict[str, str], dict]:
    """注册、提权、重新登录，返回管理员请求头与用户信息。"""
    body = await register_user(client, username)
    await session.execute(
        update(User).where(User.id == uuid.UUID(body["id"])).values(is_admin=True)
    )
    await session.commit()
    token = await login_token(client, username)
    return {"Authorization": f"Bearer {token}"}, body


async def make_user_items(
    client: AsyncClient, username: str, contents: list[str]
) -> tuple[dict[str, str], dict]:
    body = await register_user(client, username)
    headers = {"Authorization": f"Bearer {body['token']['access_token']}"}
    for content in contents:
        response = await client.post(
            "/api/v1/clipboard/items", json={"content": content}, headers=headers
        )
        assert response.status_code == 201, response.text
    return headers, body


class TestAdminAuth:
    async def test_未登录返回_401(self, client: AsyncClient) -> None:
        assert (await client.get("/api/v1/admin/stats")).status_code == 401

    async def test_普通用户返回_403(self, client: AsyncClient) -> None:
        body = await register_user(client, "normal-user")
        headers = {"Authorization": f"Bearer {body['token']['access_token']}"}
        response = await client.get("/api/v1/admin/stats", headers=headers)
        assert response.status_code == 403

    async def test_管理员可访问概览(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        headers, _ = await make_admin(client, session, "admin-stats")
        response = await client.get("/api/v1/admin/stats", headers=headers)
        assert response.status_code == 200

    async def test_管理员登录有效期更短(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        body = await register_user(client, "admin-expire")
        await session.execute(
            update(User).where(User.id == uuid.UUID(body["id"])).values(is_admin=True)
        )
        await session.commit()
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin-expire", "password": PASSWORD},
        )
        assert response.status_code == 200
        assert (
            response.json()["token"]["expires_in"]
            == settings.ADMIN_JWT_EXPIRE_MINUTES * 60
        )

    async def test_管理员登录写入审计(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        body = await register_user(client, "admin-login-audit")
        await session.execute(
            update(User).where(User.id == uuid.UUID(body["id"])).values(is_admin=True)
        )
        await session.commit()
        await login_token(client, "admin-login-audit")

        entries = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.action == audit_crud.ACTION_ADMIN_LOGIN
                )
            )
        ).all()
        assert len(entries) == 1
        assert entries[0].admin_username == "admin-login-audit"

    async def test_管理员登录审计失败不影响登录(
        self,
        client: AsyncClient,
        session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        body = await register_user(client, "admin-audit-fail-login")
        await session.execute(
            update(User).where(User.id == uuid.UUID(body["id"])).values(is_admin=True)
        )
        await session.commit()

        def broken_build(*args, **kwargs):
            raise RuntimeError("audit failed")

        monkeypatch.setattr(audit_crud, "build_audit_entry", broken_build)
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin-audit-fail-login", "password": PASSWORD},
        )
        assert response.status_code == 200
        assert response.json()["token"]["access_token"]

    async def test_禁用用户后登录_403_且旧令牌_401(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-disable")
        user_headers, user = await make_user_items(client, "target-disable", ["x"])
        target_id = user["id"]

        response = await client.patch(
            f"/api/v1/admin/users/{target_id}",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert (await client.get("/api/v1/clipboard/items", headers=user_headers)).status_code == 401
        login = await client.post(
            "/api/v1/auth/login",
            json={"username": "target-disable", "password": PASSWORD},
        )
        assert login.status_code == 403

        entries = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.action == audit_crud.ACTION_USER_DISABLE
                )
            )
        ).all()
        assert len(entries) == 1

    async def test_重置密码撤销旧令牌(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-reset")
        user_headers, user = await make_user_items(client, "target-reset", ["x"])
        target_id = user["id"]

        response = await client.post(
            f"/api/v1/admin/users/{target_id}/reset-password",
            json={"password": NEW_PASSWORD},
            headers=admin_headers,
        )
        assert response.status_code == 200

        # 旧令牌立即失效
        assert (await client.get("/api/v1/clipboard/items", headers=user_headers)).status_code == 401
        # 旧密码不可登录，新密码可登录
        old_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "target-reset", "password": PASSWORD},
        )
        assert old_login.status_code == 401
        assert await login_token(client, "target-reset", NEW_PASSWORD)

        entries = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.action == audit_crud.ACTION_USER_RESET_PASSWORD
                )
            )
        ).all()
        assert len(entries) == 1

    async def test_ws_鉴权拒绝禁用与撤销的令牌(
        self,
        client: AsyncClient,
        session: AsyncSession,
        engine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        body = await register_user(client, "ws-disabled")
        user_id = uuid.UUID(body["id"])

        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        monkeypatch.setattr(ws_router, "get_session_factory", lambda: factory)

        token = security.create_access_token(user_id, extra_claims={"sv": 0})
        assert (await ws_router._authenticate(token))[1] == "ok"

        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_active=False, token_version=1)
        )
        await session.commit()

        assert (await ws_router._authenticate(token))[1] == "account disabled"

        # 启用后令牌版本仍不匹配，旧令牌不能复活
        await session.execute(update(User).where(User.id == user_id).values(is_active=True))
        await session.commit()
        assert (await ws_router._authenticate(token))[1] == "token revoked"


class TestAdminUsers:
    async def test_列表搜索状态与分页(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-list")
        await make_user_items(client, "alice-search", ["a"])
        await make_user_items(client, "bob-search", ["b"])
        await make_user_items(client, "carol-page", ["c", "c2"])

        response = await client.get(
            "/api/v1/admin/users?search=search", headers=admin_headers
        )
        body = response.json()
        assert response.status_code == 200
        assert body["total"] == 2
        assert {item["username"] for item in body["items"]} == {
            "alice-search",
            "bob-search",
        }

        response = await client.get(
            "/api/v1/admin/users?search=carol-page", headers=admin_headers
        )
        item = response.json()["items"][0]
        assert item["item_count"] == 2

        response = await client.get(
            "/api/v1/admin/users?status=disabled", headers=admin_headers
        )
        assert response.json()["total"] == 0

        admins = await client.get(
            "/api/v1/admin/users?role=admin", headers=admin_headers
        )
        assert admins.json()["total"] == 1
        assert admins.json()["items"][0]["is_admin"] is True

        normal = await client.get(
            "/api/v1/admin/users?role=user", headers=admin_headers
        )
        assert normal.json()["total"] == 3
        assert all(item["is_admin"] is False for item in normal.json()["items"])

        first = await client.get(
            "/api/v1/admin/users?page=1&size=2", headers=admin_headers
        )
        assert len(first.json()["items"]) == 2
        assert first.json()["pages"] >= 2

    async def test_用户详情不存在返回_404(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-404")
        response = await client.get(
            f"/api/v1/admin/users/{uuid.uuid4()}", headers=admin_headers
        )
        assert response.status_code == 404

    async def test_不能禁用或降权自己(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers, admin = await make_admin(client, session, "admin-self")
        response = await client.patch(
            f"/api/v1/admin/users/{admin['id']}",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert response.status_code == 400

        response = await client.patch(
            f"/api/v1/admin/users/{admin['id']}",
            json={"is_admin": False},
            headers=admin_headers,
        )
        assert response.status_code == 400

    async def test_启用禁用与角色变更(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-toggle")
        _, user = await make_user_items(client, "target-toggle", [])

        response = await client.patch(
            f"/api/v1/admin/users/{user['id']}",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

        response = await client.patch(
            f"/api/v1/admin/users/{user['id']}",
            json={"is_active": True},
            headers=admin_headers,
        )
        assert response.json()["is_active"] is True

        response = await client.patch(
            f"/api/v1/admin/users/{user['id']}",
            json={"is_admin": True},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["is_admin"] is True

    async def test_删除用户级联删除剪贴板(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers, admin = await make_admin(client, session, "admin-delete")
        _, user = await make_user_items(client, "target-delete", ["one", "two"])
        target_id = uuid.UUID(user["id"])

        response = await client.delete(
            f"/api/v1/admin/users/{target_id}", headers=admin_headers
        )
        assert response.status_code == 200
        assert "2 条剪贴板" in response.json()["message"]

        assert (
            await session.scalar(
                select(func.count())
                .select_from(ClipboardItem)
                .where(ClipboardItem.user_id == target_id)
            )
            == 0
        )
        assert (
            await client.get(
                f"/api/v1/admin/users/{target_id}", headers=admin_headers
            )
        ).status_code == 404

        entries = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.action == audit_crud.ACTION_USER_DELETE
                )
            )
        ).all()
        assert entries[0].detail == {"deleted_items": 2}

        # 不能删除自己
        response = await client.delete(
            f"/api/v1/admin/users/{admin['id']}", headers=admin_headers
        )
        assert response.status_code == 400

    async def test_清空用户剪贴板(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-clear")
        _, user = await make_user_items(client, "target-clear", ["a", "b", "c"])
        target_id = uuid.UUID(user["id"])

        response = await client.delete(
            f"/api/v1/admin/users/{target_id}/clipboards",
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["message"] == "已清空 3 条记录"

        entries = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.action == audit_crud.ACTION_USER_CLIPBOARDS_CLEAR
                )
            )
        ).all()
        assert entries[0].detail == {"deleted_items": 3}

    async def test_修改邮箱冲突返回_409(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-email")
        _, first = await make_user_items(client, "email-first", [])
        _, second = await make_user_items(client, "email-second", [])
        response = await client.patch(
            f"/api/v1/admin/users/{second['id']}",
            json={"email": "email-first@example.com"},
            headers=admin_headers,
        )
        assert response.status_code == 409


class TestAdminClipboards:
    async def test_列表筛选与详情(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-clipboard")
        _, alice = await make_user_items(client, "clip-alice", ["alice-secret", "other"])
        _, bob = await make_user_items(client, "clip-bob", ["bob-secret"])

        response = await client.get(
            "/api/v1/admin/clipboards?search=secret", headers=admin_headers
        )
        body = response.json()
        assert response.status_code == 200
        assert body["total"] == 2
        assert {item["username"] for item in body["items"]} == {"clip-alice", "clip-bob"}

        response = await client.get(
            f"/api/v1/admin/clipboards?user_id={alice['id']}", headers=admin_headers
        )
        assert response.json()["total"] == 2

        response = await client.get(
            f"/api/v1/admin/clipboards?username=clip-bob", headers=admin_headers
        )
        assert response.json()["total"] == 1

        item_id = response.json()["items"][0]["id"]
        detail = await client.get(
            f"/api/v1/admin/clipboards/{item_id}", headers=admin_headers
        )
        assert detail.status_code == 200
        assert detail.json()["content"] == "bob-secret"
        assert "content_hash" not in detail.json()

    async def test_删除单条剪贴板并广播(
        self, client: AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-clip-delete")
        _, user = await make_user_items(client, "target-clip-delete", ["to-delete"])
        item_id = (
            await client.get(
                f"/api/v1/admin/clipboards?user_id={user['id']}", headers=admin_headers
            )
        ).json()["items"][0]["id"]

        sent: list[tuple[str, str]] = []

        async def fake_send(user_id, event, data):
            sent.append((str(user_id), event))
            return 1

        monkeypatch.setattr(manager, "send_to_user", fake_send)
        response = await client.delete(
            f"/api/v1/admin/clipboards/{item_id}", headers=admin_headers
        )
        assert response.status_code == 200
        assert sent == [(user["id"], "clipboard.deleted")]

        assert (
            await client.get(
                f"/api/v1/admin/clipboards/{item_id}", headers=admin_headers
            )
        ).status_code == 404

    async def test_删除不存在的剪贴板返回_404(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-clip-404")
        response = await client.delete(
            f"/api/v1/admin/clipboards/{uuid.uuid4()}", headers=admin_headers
        )
        assert response.status_code == 404


class TestAdminStatsAndAudit:
    async def test_概览统计(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-overview")
        await make_user_items(client, "stat-one", ["123", "4567"])
        await make_user_items(client, "stat-two", ["x"])

        body = (await client.get("/api/v1/admin/stats", headers=admin_headers)).json()
        assert body["user_count"] == 3
        assert body["admin_count"] == 1
        assert body["active_user_count"] == 3
        assert body["item_count"] == 3
        assert body["total_bytes"] >= 8
        assert body["new_users_7d"] == 3
        assert "top_users" not in body

    async def test_审计列表筛选(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-audit-list")
        _, user = await make_user_items(client, "target-audit", [])
        await client.patch(
            f"/api/v1/admin/users/{user['id']}",
            json={"is_active": False},
            headers=admin_headers,
        )

        response = await client.get(
            "/api/v1/admin/audit-logs?action=user.disable", headers=admin_headers
        )
        body = response.json()
        assert response.status_code == 200
        assert body["total"] >= 1
        assert all(item["action"] == "user.disable" for item in body["items"])

        response = await client.get(
            "/api/v1/admin/audit-logs?admin_username=admin-audit-list",
            headers=admin_headers,
        )
        assert response.json()["total"] >= 1

    async def test_高危操作审计失败会回滚(
        self,
        client: AsyncClient,
        session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-audit-fail")
        _, user = await make_user_items(client, "target-audit-fail", [])
        target_id = uuid.UUID(user["id"])

        def broken_build(*args, **kwargs):
            raise RuntimeError("audit failed")

        monkeypatch.setattr(audit_crud, "build_audit_entry", broken_build)

        # httpx 的 ASGITransport 默认会把未捕获异常抛给测试；依赖层已先回滚。
        with pytest.raises(RuntimeError, match="audit failed"):
            await client.patch(
                f"/api/v1/admin/users/{target_id}",
                json={"is_active": False},
                headers=admin_headers,
            )

        refreshed = await session.get(User, target_id)
        assert refreshed is not None
        await session.refresh(refreshed)
        assert refreshed.is_active is True


class TestAdminInviteCodes:
    async def test_生成邀请码只返回一次明文(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-invite-create")
        response = await client.post(
            "/api/v1/admin/invite-codes",
            json={"label": "alice", "max_uses": 3, "expires_days": 7},
            headers=admin_headers,
        )
        assert response.status_code == 201
        body = response.json()
        assert len(body["code"]) > 0
        assert body["code_hint"] == body["code"][:8]
        assert body["max_uses"] == 3
        assert body["used_count"] == 0
        assert body["status"] == "active"

        listing = await client.get(
            "/api/v1/admin/invite-codes", headers=admin_headers
        )
        item = listing.json()["items"][0]
        assert "code" not in item
        assert item["code_hint"] == body["code_hint"]

        entries = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.action == audit_crud.ACTION_INVITE_CREATE
                )
            )
        ).all()
        assert len(entries) == 1

    async def test_使用次数为必填且至少为_1(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-invite-validate")
        missing = await client.post(
            "/api/v1/admin/invite-codes",
            json={"label": "x"},
            headers=admin_headers,
        )
        assert missing.status_code == 422
        zero = await client.post(
            "/api/v1/admin/invite-codes",
            json={"max_uses": 0},
            headers=admin_headers,
        )
        assert zero.status_code == 422

    async def test_用尽后无法继续注册(
        self,
        client: AsyncClient,
        session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-invite-limit")
        monkeypatch.setattr(settings, "REGISTRATION_REQUIRE_INVITE", True)
        created = await client.post(
            "/api/v1/admin/invite-codes",
            json={"max_uses": 1, "expires_days": 0},
            headers=admin_headers,
        )
        code = created.json()["code"]

        first = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "invite-first",
                "email": "invite-first@example.com",
                "password": PASSWORD,
                "invite_code": code,
            },
        )
        assert first.status_code == 201
        second = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "invite-second",
                "email": "invite-second@example.com",
                "password": PASSWORD,
                "invite_code": code,
            },
        )
        assert second.status_code == 403

        exhausted = await client.get(
            "/api/v1/admin/invite-codes?status=exhausted", headers=admin_headers
        )
        assert exhausted.json()["total"] == 1
        assert exhausted.json()["items"][0]["used_count"] == 1

        active = await client.get(
            "/api/v1/admin/invite-codes?status=active", headers=admin_headers
        )
        assert active.json()["total"] == 0

    async def test_撤销邀请码(
        self,
        client: AsyncClient,
        session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        admin_headers, _ = await make_admin(client, session, "admin-invite-revoke-ok")
        monkeypatch.setattr(settings, "REGISTRATION_REQUIRE_INVITE", True)
        created = (
            await client.post(
                "/api/v1/admin/invite-codes",
                json={"max_uses": 5, "expires_days": 0},
                headers=admin_headers,
            )
        ).json()

        revoked = await client.post(
            f"/api/v1/admin/invite-codes/{created['id']}/revoke",
            headers=admin_headers,
        )
        assert revoked.status_code == 200
        assert revoked.json()["status"] == "revoked"

        register_attempt = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "revoked-user",
                "email": "revoked-user@example.com",
                "password": PASSWORD,
                "invite_code": created["code"],
            },
        )
        assert register_attempt.status_code == 403

        entries = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.action == audit_crud.ACTION_INVITE_REVOKE
                )
            )
        ).all()
        assert len(entries) == 1

        missing = await client.post(
            f"/api/v1/admin/invite-codes/{uuid.uuid4()}/revoke",
            headers=admin_headers,
        )
        assert missing.status_code == 404


class TestConnectionManagerCloseUser:
    async def test_close_user_关闭并移除全部连接(self) -> None:
        manager = ConnectionManager()

        class FakeSocket:
            def __init__(self) -> None:
                self.closed_with: tuple[int, str] | None = None

            async def close(self, code: int, reason: str) -> None:
                self.closed_with = (code, reason)

        first, second = FakeSocket(), FakeSocket()
        await manager.connect("user-1", first)  # type: ignore[arg-type]
        await manager.connect("user-1", second)  # type: ignore[arg-type]
        assert manager.connection_count("user-1") == 2

        closed = await manager.close_user("user-1")
        assert closed == 2
        assert manager.connection_count("user-1") == 0
        assert first.closed_with == (4401, "account disabled")
        assert second.closed_with == (4401, "account disabled")
