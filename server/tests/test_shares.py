"""剪贴板分享接口测试（打测试库）。

覆盖创建/公开访问/计数/密码/有效期/撤销/配额/访问记录与安全边界。
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_utils import redact_sensitive_params
from app.db.models.share import ClipboardShare
from app.db.models.share_access_log import ShareAccessLog
from app.db.models.share_setting import ShareSetting
from app.db.models.user import User
from app.schemas.common import utc_now
from app.services import rate_limit

PASSWORD = "share-test-pw1"


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """限流是进程内状态，用例之间必须清空，避免互相干扰。"""
    rate_limit.reset_rate_limits()
    yield
    rate_limit.reset_rate_limits()


async def make_user(client: AsyncClient, username: str) -> tuple[dict[str, str], dict]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['token']['access_token']}"}, body


async def create_item(
    client: AsyncClient,
    headers: dict[str, str],
    content: str = "分享测试正文",
    title: str | None = None,
    content_type: str = "text",
) -> dict:
    payload: dict = {"content": content, "content_type": content_type}
    if title is not None:
        payload["title"] = title
    response = await client.post(
        "/api/v1/clipboard/items", json=payload, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_share(
    client: AsyncClient,
    headers: dict[str, str],
    item_id: str,
    **payload,
) -> dict:
    response = await client.post(
        f"/api/v1/clipboard/items/{item_id}/shares", json=payload, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestCreateShare:
    async def test_创建快照分享返回完整字段(self, client: AsyncClient) -> None:
        headers, _ = await make_user(client, "share-creator")
        item = await create_item(client, headers, "快照内容")

        body = await create_share(
            client, headers, item["id"], mode="snapshot", expires_in="7d"
        )

        assert body["mode"] == "snapshot"
        assert body["status"] == "active"
        assert body["item_id"] == item["id"]
        assert body["password_protected"] is False
        assert len(body["token"]) >= 40
        assert body["url"].endswith(f"/s/{body['token']}")
        assert body["remaining_views"] is None
        assert body["view_count"] == 0

    async def test_快照分享复制正文到分享行(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        headers, _ = await make_user(client, "share-snapshot")
        item = await create_item(client, headers, "需要被复制的内容")
        body = await create_share(client, headers, item["id"], mode="snapshot")

        session.expire_all()
        share = await session.get(ClipboardShare, uuid.UUID(body["id"]))
        assert share is not None
        assert share.content == "需要被复制的内容"
        assert share.content_type == "text"

    async def test_跟随分享的正文为_NULL(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        headers, _ = await make_user(client, "share-live")
        item = await create_item(client, headers, "跟随内容")
        body = await create_share(client, headers, item["id"], mode="live")

        session.expire_all()
        share = await session.get(ClipboardShare, uuid.UUID(body["id"]))
        assert share is not None
        assert share.content is None

    async def test_默认标题不含用户名(self, client: AsyncClient) -> None:
        headers, _ = await make_user(client, "title-owner")
        item = await create_item(client, headers)
        body = await create_share(client, headers, item["id"])

        assert body["title"].startswith("剪贴板 · ")
        assert "title-owner" not in body["title"]

    async def test_非文字记录创建分享返回_400(self, client: AsyncClient) -> None:
        headers, _ = await make_user(client, "share-image")
        item = await create_item(client, headers, "图片", content_type="image")
        response = await client.post(
            f"/api/v1/clipboard/items/{item['id']}/shares", json={}, headers=headers
        )
        assert response.status_code == 400

    async def test_他人记录创建分享返回_404(self, client: AsyncClient) -> None:
        owner_headers, _ = await make_user(client, "share-owner-a")
        other_headers, _ = await make_user(client, "share-owner-b")
        item = await create_item(client, owner_headers)

        response = await client.post(
            f"/api/v1/clipboard/items/{item['id']}/shares",
            json={},
            headers=other_headers,
        )
        assert response.status_code == 404


class TestSnapshotAndLive:
    async def test_快照不随原记录变化(
        self, client: AsyncClient
    ) -> None:
        headers, _ = await make_user(client, "share-frozen")
        item = await create_item(client, headers, "原始正文")
        share = await create_share(client, headers, item["id"], mode="snapshot")

        await client.patch(
            f"/api/v1/clipboard/items/{item['id']}",
            json={"content": "后来改过的正文"},
            headers=headers,
        )
        body = (
            await client.post(f"/api/v1/public/shares/{share['token']}/access", json={})
        ).json()
        assert body["content"] == "原始正文"

    async def test_跟随读取最新正文(self, client: AsyncClient) -> None:
        headers, _ = await make_user(client, "share-follow")
        item = await create_item(client, headers, "第一版正文")
        share = await create_share(client, headers, item["id"], mode="live")

        await client.patch(
            f"/api/v1/clipboard/items/{item['id']}",
            json={"content": "第二版正文"},
            headers=headers,
        )
        body = (
            await client.post(f"/api/v1/public/shares/{share['token']}/access", json={})
        ).json()
        assert body["content"] == "第二版正文"


class TestPublicAccess:
    async def test_无密码_meta_返回标题_access_返回正文(
        self, client: AsyncClient
    ) -> None:
        headers, _ = await make_user(client, "public-reader")
        item = await create_item(client, headers, "公开正文")
        share = await create_share(client, headers, item["id"])

        meta = await client.get(f"/api/v1/public/shares/{share['token']}")
        assert meta.status_code == 200
        assert meta.json()["title"] == share["title"]
        assert meta.json()["password_required"] is False

        access = await client.post(
            f"/api/v1/public/shares/{share['token']}/access", json={}
        )
        assert access.status_code == 200
        assert access.json()["content"] == "公开正文"

    async def test_meta_不计数_access_才计数(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        headers, _ = await make_user(client, "public-counter")
        item = await create_item(client, headers)
        share = await create_share(client, headers, item["id"])

        for _ in range(3):
            assert (
                await client.get(f"/api/v1/public/shares/{share['token']}")
            ).status_code == 200

        session.expire_all()
        row = await session.get(ClipboardShare, uuid.UUID(share["id"]))
        assert row is not None and row.view_count == 0

        await client.post(f"/api/v1/public/shares/{share['token']}/access", json={})
        session.expire_all()
        row = await session.get(ClipboardShare, uuid.UUID(share["id"]))
        assert row is not None and row.view_count == 1

    async def test_密码分享_meta_不泄露标题(self, client: AsyncClient) -> None:
        headers, _ = await make_user(client, "password-meta")
        item = await create_item(client, headers)
        share = await create_share(client, headers, item["id"], password="1234")

        meta = await client.get(f"/api/v1/public/shares/{share['token']}")
        assert meta.status_code == 200
        assert meta.json()["title"] is None
        assert meta.json()["password_required"] is True

    async def test_密码缺失或错误返回_403_正确可读(
        self, client: AsyncClient
    ) -> None:
        headers, _ = await make_user(client, "password-access")
        item = await create_item(client, headers, "受保护正文")
        share = await create_share(client, headers, item["id"], password="1234")

        assert (
            await client.post(f"/api/v1/public/shares/{share['token']}/access", json={})
        ).status_code == 403
        assert (
            await client.post(
                f"/api/v1/public/shares/{share['token']}/access",
                json={"password": "9999"},
            )
        ).status_code == 403

        ok = await client.post(
            f"/api/v1/public/shares/{share['token']}/access",
            json={"password": "1234"},
        )
        assert ok.status_code == 200
        assert ok.json()["content"] == "受保护正文"

    async def test_公开接口带安全响应头(self, client: AsyncClient) -> None:
        headers, _ = await make_user(client, "public-headers")
        item = await create_item(client, headers)
        share = await create_share(client, headers, item["id"])

        for response in (
            await client.get(f"/api/v1/public/shares/{share['token']}"),
            await client.post(
                f"/api/v1/public/shares/{share['token']}/access", json={}
            ),
        ):
            assert response.headers["x-robots-tag"] == "noindex, nofollow"
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["referrer-policy"] == "no-referrer"

    async def test_token_不存在返回_404(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/public/shares/not-a-real-token")
        assert response.status_code == 404


class TestExpiryRevokeAndViews:
    async def test_过期后返回_410(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        headers, _ = await make_user(client, "expired-share")
        item = await create_item(client, headers)
        share = await create_share(client, headers, item["id"])

        await session.execute(
            update(ClipboardShare)
            .where(ClipboardShare.id == uuid.UUID(share["id"]))
            .values(expires_at=utc_now() - timedelta(minutes=1))
        )
        await session.commit()

        assert (
            await client.get(f"/api/v1/public/shares/{share['token']}")
        ).status_code == 410
        assert (
            await client.post(f"/api/v1/public/shares/{share['token']}/access", json={})
        ).status_code == 410

    async def test_撤销后返回_410_重复撤销幂等(
        self, client: AsyncClient
    ) -> None:
        headers, _ = await make_user(client, "revoked-share")
        item = await create_item(client, headers)
        share = await create_share(client, headers, item["id"])

        first = await client.delete(
            f"/api/v1/clipboard/shares/{share['id']}", headers=headers
        )
        second = await client.delete(
            f"/api/v1/clipboard/shares/{share['id']}", headers=headers
        )
        assert first.status_code == 200 and second.status_code == 200

        assert (
            await client.get(f"/api/v1/public/shares/{share['token']}")
        ).status_code == 410
        listed = (
            await client.get(
                "/api/v1/clipboard/shares", headers=headers
            )
        ).json()
        assert listed["items"][0]["status"] == "revoked"

    async def test_次数用尽后返回_410(self, client: AsyncClient) -> None:
        headers, _ = await make_user(client, "max-views")
        item = await create_item(client, headers)
        share = await create_share(client, headers, item["id"], max_views=1)

        first = await client.post(
            f"/api/v1/public/shares/{share['token']}/access", json={}
        )
        second = await client.post(
            f"/api/v1/public/shares/{share['token']}/access", json={}
        )
        assert first.status_code == 200
        assert first.json()["remaining_views"] == 0
        assert second.status_code == 410

    async def test_原记录删除后分享级联删除(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        headers, _ = await make_user(client, "cascade-share")
        item = await create_item(client, headers)
        share = await create_share(client, headers, item["id"])

        assert (
            await client.delete(
                f"/api/v1/clipboard/items/{item['id']}", headers=headers
            )
        ).status_code == 200

        session.expire_all()
        assert await session.get(ClipboardShare, uuid.UUID(share["id"])) is None
        assert (
            await client.get(f"/api/v1/public/shares/{share['token']}")
        ).status_code == 404

    async def test_分享者被禁用后返回_410(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        headers, body = await make_user(client, "disabled-owner")
        item = await create_item(client, headers)
        share = await create_share(client, headers, item["id"])

        await session.execute(
            update(User)
            .where(User.id == uuid.UUID(body["id"]))
            .values(is_active=False)
        )
        await session.commit()

        assert (
            await client.get(f"/api/v1/public/shares/{share['token']}")
        ).status_code == 410

    async def test_跨用户不能撤销或查看他人分享(self, client: AsyncClient) -> None:
        owner_headers, _ = await make_user(client, "cross-owner")
        other_headers, _ = await make_user(client, "cross-other")
        item = await create_item(client, owner_headers)
        share = await create_share(client, owner_headers, item["id"])

        assert (
            await client.delete(
                f"/api/v1/clipboard/shares/{share['id']}", headers=other_headers
            )
        ).status_code == 404
        assert (
            await client.get(
                f"/api/v1/clipboard/shares/{share['id']}/access-logs",
                headers=other_headers,
            )
        ).status_code == 404


class TestLimitsAndFiltering:
    async def test_达到限额返回_409_撤销后恢复(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        headers, _ = await make_user(client, "quota-user")
        first_item = await create_item(client, headers, "配额甲")
        second_item = await create_item(client, headers, "配额乙")

        session.add(ShareSetting(id=1, user_share_limit=1))
        await session.commit()

        first = await create_share(client, headers, first_item["id"])
        response = await client.post(
            f"/api/v1/clipboard/items/{second_item['id']}/shares",
            json={},
            headers=headers,
        )
        assert response.status_code == 409
        assert "上限" in response.json()["detail"]

        await client.delete(
            f"/api/v1/clipboard/shares/{first['id']}", headers=headers
        )
        await create_share(client, headers, second_item["id"])

    async def test_单条记录最多_5_个有效分享(self, client: AsyncClient) -> None:
        headers, _ = await make_user(client, "item-limit")
        item = await create_item(client, headers, "单条限额")

        shares = [
            await create_share(client, headers, item["id"]) for _ in range(5)
        ]

        response = await client.post(
            f"/api/v1/clipboard/items/{item['id']}/shares",
            json={},
            headers=headers,
        )
        assert response.status_code == 409
        assert "同一条记录最多 5 个" in response.json()["detail"]

        # 撤销一个后应恢复可创建
        await client.delete(
            f"/api/v1/clipboard/shares/{shares[0]['id']}", headers=headers
        )
        await create_share(client, headers, item["id"])

    async def test_按标题与内容搜索(self, client: AsyncClient) -> None:
        headers, _ = await make_user(client, "share-search")
        snapshot_item = await create_item(
            client, headers, "正文含 needle-body 的片段", title="搜索标题甲"
        )
        live_item = await create_item(
            client, headers, "跟随模式正文 needle-live", title="搜索标题乙"
        )
        await create_share(client, headers, snapshot_item["id"])
        await create_share(client, headers, live_item["id"], mode="live")

        by_title = (
            await client.get(
                "/api/v1/clipboard/shares?search=标题乙", headers=headers
            )
        ).json()
        assert by_title["total"] == 1
        assert by_title["items"][0]["title"] == "搜索标题乙"

        # 快照：搜分享行里的正文副本
        by_snapshot = (
            await client.get(
                "/api/v1/clipboard/shares?search=needle-body", headers=headers
            )
        ).json()
        assert by_snapshot["total"] == 1
        assert by_snapshot["items"][0]["title"] == "搜索标题甲"

        # 跟随：分享行 content 为 NULL，回退到原记录正文
        by_live = (
            await client.get(
                "/api/v1/clipboard/shares?search=needle-live", headers=headers
            )
        ).json()
        assert by_live["total"] == 1
        assert by_live["items"][0]["title"] == "搜索标题乙"

    async def test_item_id_筛选与状态筛选(self, client: AsyncClient) -> None:
        headers, _ = await make_user(client, "filter-user")
        item_a = await create_item(client, headers, "筛选甲")
        item_b = await create_item(client, headers, "筛选乙")

        share_a = await create_share(client, headers, item_a["id"])
        await create_share(client, headers, item_b["id"])

        by_item = (
            await client.get(
                f"/api/v1/clipboard/shares?item_id={item_a['id']}",
                headers=headers,
            )
        ).json()
        assert by_item["total"] == 1
        assert by_item["items"][0]["id"] == share_a["id"]

        await client.delete(
            f"/api/v1/clipboard/shares/{share_a['id']}", headers=headers
        )
        active = (
            await client.get(
                "/api/v1/clipboard/shares?status=active", headers=headers
            )
        ).json()
        revoked = (
            await client.get(
                "/api/v1/clipboard/shares?status=revoked", headers=headers
            )
        ).json()
        assert active["total"] == 1
        assert revoked["total"] == 1


class TestAccessLogs:
    async def test_成功访问写入记录_meta_不写(
        self, client: AsyncClient
    ) -> None:
        headers, _ = await make_user(client, "log-success")
        item = await create_item(client, headers)
        share = await create_share(client, headers, item["id"])

        await client.get(f"/api/v1/public/shares/{share['token']}")
        await client.post(f"/api/v1/public/shares/{share['token']}/access", json={})

        logs = (
            await client.get(
                f"/api/v1/clipboard/shares/{share['id']}/access-logs",
                headers=headers,
            )
        ).json()
        assert logs["total"] == 1
        assert logs["items"][0]["result"] == "success"

    async def test_失败尝试写入记录_所有者看不到(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        headers, _ = await make_user(client, "log-failure")
        item = await create_item(client, headers)
        share = await create_share(client, headers, item["id"], password="1234")

        await client.post(
            f"/api/v1/public/shares/{share['token']}/access",
            json={"password": "wrong"},
        )

        session.expire_all()
        rows = (
            await session.scalars(
                select(ShareAccessLog).where(
                    ShareAccessLog.share_id == uuid.UUID(share["id"])
                )
            )
        ).all()
        assert [row.result for row in rows] == ["password_failed"]

        owner_logs = (
            await client.get(
                f"/api/v1/clipboard/shares/{share['id']}/access-logs",
                headers=headers,
            )
        ).json()
        assert owner_logs["total"] == 0

    async def test_访问记录随分享级联删除(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        headers, _ = await make_user(client, "log-cascade")
        item = await create_item(client, headers)
        share = await create_share(client, headers, item["id"])
        await client.post(f"/api/v1/public/shares/{share['token']}/access", json={})

        await client.delete(
            f"/api/v1/clipboard/items/{item['id']}", headers=headers
        )
        session.expire_all()
        count = await session.scalar(
            select(func.count())
            .select_from(ShareAccessLog)
            .where(ShareAccessLog.share_id == uuid.UUID(share["id"]))
        )
        assert count == 0

    async def test_访问限流返回_429(self, client: AsyncClient) -> None:
        headers, _ = await make_user(client, "log-rate")
        item = await create_item(client, headers)
        share = await create_share(client, headers, item["id"])

        for _ in range(30):
            assert (
                await client.post(
                    f"/api/v1/public/shares/{share['token']}/access", json={}
                )
            ).status_code == 200
        throttled = await client.post(
            f"/api/v1/public/shares/{share['token']}/access", json={}
        )
        assert throttled.status_code == 429


class TestLogRedaction:
    def test_分享路径_token_被脱敏(self) -> None:
        assert (
            redact_sensitive_params("/api/v1/public/shares/AbC-123_xyz")
            == "/api/v1/public/shares/***"
        )
        assert redact_sensitive_params("GET /s/AbC-123_xyz") == "GET /s/***"
