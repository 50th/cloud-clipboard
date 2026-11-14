"""管理端分享限额设置测试。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import audit as audit_crud
from app.db.models.admin_audit_log import AdminAuditLog
from app.db.models.user import User
from app.services import rate_limit

PASSWORD = "admin-share-pw1"


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    rate_limit.reset_rate_limits()
    yield
    rate_limit.reset_rate_limits()


async def register(client: AsyncClient, username: str) -> dict:
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


async def make_admin(
    client: AsyncClient, session: AsyncSession, username: str
) -> dict[str, str]:
    body = await register(client, username)
    await session.execute(
        update(User).where(User.id == uuid.UUID(body["id"])).values(is_admin=True)
    )
    await session.commit()
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": PASSWORD},
    )
    token = login.json()["token"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def make_item(client: AsyncClient, headers: dict[str, str], content: str) -> dict:
    response = await client.post(
        "/api/v1/clipboard/items", json={"content": content}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestShareSettings:
    async def test_普通用户返回_403(self, client: AsyncClient) -> None:
        body = await register(client, "settings-normal")
        headers = {"Authorization": f"Bearer {body['token']['access_token']}"}
        assert (
            await client.get("/api/v1/admin/settings/shares", headers=headers)
        ).status_code == 403

    async def test_默认限额为_50(self, client: AsyncClient, session: AsyncSession) -> None:
        headers = await make_admin(client, session, "settings-admin")
        response = await client.get("/api/v1/admin/settings/shares", headers=headers)
        assert response.status_code == 200
        assert response.json()["user_share_limit"] == 50

    async def test_更新限额并写入审计(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        headers = await make_admin(client, session, "settings-update")
        response = await client.put(
            "/api/v1/admin/settings/shares",
            json={"user_share_limit": 3},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["user_share_limit"] == 3
        assert response.json()["updated_by_username"] == "settings-update"

        session.expire_all()
        entry = await session.scalar(
            select(AdminAuditLog).where(
                AdminAuditLog.action == audit_crud.ACTION_SHARE_QUOTA_UPDATE
            )
        )
        assert entry is not None
        assert entry.detail == {"old": 50, "new": 3}

    async def test_更新后新创建按新限额校验(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers = await make_admin(client, session, "settings-quota")
        await client.put(
            "/api/v1/admin/settings/shares",
            json={"user_share_limit": 1},
            headers=admin_headers,
        )

        body = await register(client, "settings-user")
        headers = {"Authorization": f"Bearer {body['token']['access_token']}"}
        first = await make_item(client, headers, "限额甲")
        second = await make_item(client, headers, "限额乙")

        assert (
            await client.post(
                f"/api/v1/clipboard/items/{first['id']}/shares",
                json={},
                headers=headers,
            )
        ).status_code == 201
        assert (
            await client.post(
                f"/api/v1/clipboard/items/{second['id']}/shares",
                json={},
                headers=headers,
            )
        ).status_code == 409

    async def test_管理员全局分享列表(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers = await make_admin(client, session, "all-shares-admin")

        shares: dict[str, dict] = {}
        for name in ("all-shares-alice", "all-shares-bob"):
            body = await register(client, name)
            headers = {"Authorization": f"Bearer {body['token']['access_token']}"}
            item = await make_item(client, headers, f"{name} 的内容")
            response = await client.post(
                f"/api/v1/clipboard/items/{item['id']}/shares",
                json={},
                headers=headers,
            )
            assert response.status_code == 201, response.text
            shares[name] = response.json()

        await client.delete(
            f"/api/v1/clipboard/shares/{shares['all-shares-bob']['id']}",
            headers={
                "Authorization": (
                    "Bearer "
                    + (
                        await client.post(
                            "/api/v1/auth/login",
                            json={"username": "all-shares-bob", "password": PASSWORD},
                        )
                    ).json()["token"]["access_token"]
                )
            },
        )

        all_shares = (
            await client.get("/api/v1/admin/shares", headers=admin_headers)
        ).json()
        assert all_shares["total"] == 2
        assert {item["owner_username"] for item in all_shares["items"]} == {
            "all-shares-alice",
            "all-shares-bob",
        }
        assert "token" not in all_shares["items"][0]

        active = (
            await client.get(
                "/api/v1/admin/shares?status=active", headers=admin_headers
            )
        ).json()
        assert active["total"] == 1
        assert active["items"][0]["status"] == "active"

        revoked = (
            await client.get(
                "/api/v1/admin/shares?status=revoked", headers=admin_headers
            )
        ).json()
        assert revoked["total"] == 1
        assert revoked["items"][0]["status"] == "revoked"

        by_user = (
            await client.get(
                "/api/v1/admin/shares?username=alice", headers=admin_headers
            )
        ).json()
        assert by_user["total"] == 1
        assert by_user["items"][0]["owner_username"] == "all-shares-alice"

        normal = await client.post(
            "/api/v1/auth/login",
            json={"username": "all-shares-alice", "password": PASSWORD},
        )
        normal_headers = {
            "Authorization": f"Bearer {normal.json()['token']['access_token']}"
        }
        assert (
            await client.get("/api/v1/admin/shares", headers=normal_headers)
        ).status_code == 403

    async def test_概览包含分享统计(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers = await make_admin(client, session, "stats-shares-admin")
        body = await register(client, "stats-shares-user")
        user_headers = {"Authorization": f"Bearer {body['token']['access_token']}"}
        items = [
            await make_item(client, user_headers, f"概览分享 {index}")
            for index in range(2)
        ]

        first = await client.post(
            f"/api/v1/clipboard/items/{items[0]['id']}/shares",
            json={},
            headers=user_headers,
        )
        second = await client.post(
            f"/api/v1/clipboard/items/{items[1]['id']}/shares",
            json={},
            headers=user_headers,
        )
        assert first.status_code == 201 and second.status_code == 201
        await client.delete(
            f"/api/v1/clipboard/shares/{second.json()['id']}",
            headers=user_headers,
        )

        stats = (
            await client.get("/api/v1/admin/stats", headers=admin_headers)
        ).json()
        assert stats["share_count"] == 2
        assert stats["active_share_count"] == 1

    async def test_管理员查看指定用户分享记录(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers = await make_admin(client, session, "user-shares-admin")
        body = await register(client, "user-shares-target")
        user_headers = {"Authorization": f"Bearer {body['token']['access_token']}"}
        items = [
            await make_item(client, user_headers, f"分享记录 {index}")
            for index in range(2)
        ]

        first = await client.post(
            f"/api/v1/clipboard/items/{items[0]['id']}/shares",
            json={},
            headers=user_headers,
        )
        second = await client.post(
            f"/api/v1/clipboard/items/{items[1]['id']}/shares",
            json={"mode": "live"},
            headers=user_headers,
        )
        assert first.status_code == 201 and second.status_code == 201
        await client.delete(
            f"/api/v1/clipboard/shares/{second.json()['id']}",
            headers=user_headers,
        )

        all_shares = await client.get(
            f"/api/v1/admin/users/{body['id']}/shares", headers=admin_headers
        )
        assert all_shares.status_code == 200
        payload = all_shares.json()
        assert payload["total"] == 2
        assert {item["status"] for item in payload["items"]} == {
            "active",
            "revoked",
        }
        assert "token" not in payload["items"][0]

        active = await client.get(
            f"/api/v1/admin/users/{body['id']}/shares?status=active",
            headers=admin_headers,
        )
        assert active.json()["total"] == 1
        assert active.json()["items"][0]["status"] == "active"

        assert (
            await client.get(
                f"/api/v1/admin/users/{body['id']}/shares", headers=user_headers
            )
        ).status_code == 403
        assert (
            await client.get(
                f"/api/v1/admin/users/{uuid.uuid4()}/shares", headers=admin_headers
            )
        ).status_code == 404

    async def test_用户单独限额优先于全局(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers = await make_admin(client, session, "per-user-admin")
        await client.put(
            "/api/v1/admin/settings/shares",
            json={"user_share_limit": 1},
            headers=admin_headers,
        )

        body = await register(client, "per-user-share")
        user_headers = {"Authorization": f"Bearer {body['token']['access_token']}"}
        items = [
            await make_item(client, user_headers, f"单独限额 {index}")
            for index in range(4)
        ]

        updated = await client.patch(
            f"/api/v1/admin/users/{body['id']}",
            json={"share_limit": 2},
            headers=admin_headers,
        )
        assert updated.status_code == 200
        assert updated.json()["share_limit"] == 2

        # 单独限额 2 覆盖全局 1：前两条成功，第三条 409
        for item in items[:2]:
            response = await client.post(
                f"/api/v1/clipboard/items/{item['id']}/shares",
                json={},
                headers=user_headers,
            )
            assert response.status_code == 201, response.text
        third = await client.post(
            f"/api/v1/clipboard/items/{items[2]['id']}/shares",
            json={},
            headers=user_headers,
        )
        assert third.status_code == 409
        assert "2 条" in third.json()["detail"]

        session.expire_all()
        entry = await session.scalar(
            select(AdminAuditLog).where(
                AdminAuditLog.action == audit_crud.ACTION_USER_SHARE_LIMIT_UPDATE
            )
        )
        assert entry is not None
        assert entry.detail == {"old": None, "new": 2}

        # 显式传 null 清除单独设置，回落到全局 1
        cleared = await client.patch(
            f"/api/v1/admin/users/{body['id']}",
            json={"share_limit": None},
            headers=admin_headers,
        )
        assert cleared.status_code == 200
        assert cleared.json()["share_limit"] is None
        assert (
            await client.post(
                f"/api/v1/clipboard/items/{items[3]['id']}/shares",
                json={},
                headers=user_headers,
            )
        ).status_code == 409

    async def test_用户单独限额范围外_422(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        admin_headers = await make_admin(client, session, "per-user-range")
        body = await register(client, "per-user-range-user")
        for value in (0, 10_001):
            response = await client.patch(
                f"/api/v1/admin/users/{body['id']}",
                json={"share_limit": value},
                headers=admin_headers,
            )
            assert response.status_code == 422

    async def test_范围外返回_422(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        headers = await make_admin(client, session, "settings-range")
        for value in (0, 10_001):
            response = await client.put(
                "/api/v1/admin/settings/shares",
                json={"user_share_limit": value},
                headers=headers,
            )
            assert response.status_code == 422
