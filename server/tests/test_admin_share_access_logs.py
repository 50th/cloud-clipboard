"""管理端分享访问记录测试（成功 / 失败可见性、筛选与分页）。"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.services import rate_limit

PASSWORD = "admin-logs-pw1"


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
    return {"Authorization": f"Bearer {login.json()['token']['access_token']}"}


async def prepare_share(
    client: AsyncClient, username: str, *, password: str | None = None
) -> tuple[dict[str, str], dict]:
    """注册用户、建记录并创建分享，返回 (请求头, 分享体)。"""
    body = await register(client, username)
    headers = {"Authorization": f"Bearer {body['token']['access_token']}"}
    item = await client.post(
        "/api/v1/clipboard/items",
        json={"content": f"{username} 的正文"},
        headers=headers,
    )
    payload = {"password": password} if password else {}
    share = await client.post(
        f"/api/v1/clipboard/items/{item.json()['id']}/shares",
        json=payload,
        headers=headers,
    )
    assert share.status_code == 201, share.text
    return headers, share.json()


class TestAdminShareAccessLogs:
    async def test_普通用户返回_403(self, client: AsyncClient) -> None:
        body = await register(client, "logs-normal")
        headers = {"Authorization": f"Bearer {body['token']['access_token']}"}
        assert (
            await client.get("/api/v1/admin/share-access-logs", headers=headers)
        ).status_code == 403

    async def test_管理员可见成功与失败记录(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        _, share = await prepare_share(client, "logs-owner", password="1234")
        await client.post(
            f"/api/v1/public/shares/{share['token']}/access",
            json={"password": "1234"},
        )
        await client.post(
            f"/api/v1/public/shares/{share['token']}/access",
            json={"password": "bad"},
        )

        admin_headers = await make_admin(client, session, "logs-admin")
        all_logs = (
            await client.get(
                "/api/v1/admin/share-access-logs", headers=admin_headers
            )
        ).json()
        assert all_logs["total"] == 2
        assert {item["result"] for item in all_logs["items"]} == {
            "success",
            "password_failed",
        }
        assert all_logs["items"][0]["owner_username"] == "logs-owner"
        assert all_logs["items"][0]["share_title"] == share["title"]

        failures = (
            await client.get(
                "/api/v1/admin/share-access-logs?result=failure",
                headers=admin_headers,
            )
        ).json()
        assert failures["total"] == 1
        assert failures["items"][0]["result"] == "password_failed"

        successes = (
            await client.get(
                "/api/v1/admin/share-access-logs?result=success",
                headers=admin_headers,
            )
        ).json()
        assert successes["total"] == 1
        assert successes["items"][0]["result"] == "success"

    async def test_按用户名与分享筛选(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        _, first = await prepare_share(client, "logs-alice")
        _, second = await prepare_share(client, "logs-bob")
        await client.post(f"/api/v1/public/shares/{first['token']}/access", json={})
        await client.post(f"/api/v1/public/shares/{second['token']}/access", json={})

        admin_headers = await make_admin(client, session, "logs-filter-admin")
        by_user = (
            await client.get(
                "/api/v1/admin/share-access-logs?username=alice",
                headers=admin_headers,
            )
        ).json()
        assert by_user["total"] == 1
        assert by_user["items"][0]["owner_username"] == "logs-alice"

        by_share = (
            await client.get(
                f"/api/v1/admin/share-access-logs?share_id={second['id']}",
                headers=admin_headers,
            )
        ).json()
        assert by_share["total"] == 1
        assert by_share["items"][0]["share_id"] == second["id"]

    async def test_分页按访问时间倒序(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        _, share = await prepare_share(client, "logs-paging")
        for _ in range(3):
            await client.post(
                f"/api/v1/public/shares/{share['token']}/access", json={}
            )

        admin_headers = await make_admin(client, session, "logs-paging-admin")
        first = (
            await client.get(
                "/api/v1/admin/share-access-logs?page=1&size=2",
                headers=admin_headers,
            )
        ).json()
        second = (
            await client.get(
                "/api/v1/admin/share-access-logs?page=2&size=2",
                headers=admin_headers,
            )
        ).json()

        assert first["total"] == 3 and first["pages"] == 2
        assert len(first["items"]) == 2 and len(second["items"]) == 1
        assert (
            first["items"][0]["accessed_at"] >= first["items"][1]["accessed_at"]
        )
