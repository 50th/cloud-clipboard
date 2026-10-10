"""剪贴板接口的集成测试（打测试库）。

重点是**认证边界**与**跨用户隔离**——这两类问题一旦漏掉就是越权访问。
"""

from __future__ import annotations

from httpx import AsyncClient

PASSWORD = "clipboard-test-pw"


async def make_user(client: AsyncClient, username: str) -> dict[str, str]:
    """注册一个用户并返回可用的 Authorization 头。"""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["token"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestAuthRequired:
    """`/clipboard/*` 全部需要认证。"""

    async def test_列表无令牌返回_401(self, client: AsyncClient) -> None:
        assert (await client.get("/api/v1/clipboard/items")).status_code == 401

    async def test_创建无令牌返回_401(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/clipboard/items", json={"content": "x"})
        assert response.status_code == 401

    async def test_清空无令牌返回_401(self, client: AsyncClient) -> None:
        assert (await client.delete("/api/v1/clipboard/items")).status_code == 401

    async def test_乱码令牌返回_401(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/v1/clipboard/items", headers={"Authorization": "Bearer bad.token"}
        )
        assert response.status_code == 401


class TestCreateAndList:
    async def test_创建返回_201_与完整字段(self, client: AsyncClient) -> None:
        headers = await make_user(client, "creator1")
        response = await client.post(
            "/api/v1/clipboard/items", json={"content": "hello"}, headers=headers
        )
        assert response.status_code == 201
        body = response.json()
        assert body["content"] == "hello"
        assert body["content_type"] == "text"
        assert body["title"]
        assert body["created_at"] and body["updated_at"]

    async def test_响应不含_content_hash(self, client: AsyncClient) -> None:
        headers = await make_user(client, "creator2")
        response = await client.post(
            "/api/v1/clipboard/items", json={"content": "secret-hash"}, headers=headers
        )
        assert "content_hash" not in response.json()

    async def test_空内容返回_422(self, client: AsyncClient) -> None:
        headers = await make_user(client, "creator3")
        response = await client.post(
            "/api/v1/clipboard/items", json={"content": ""}, headers=headers
        )
        assert response.status_code == 422

    async def test_列表返回分页元信息(self, client: AsyncClient) -> None:
        headers = await make_user(client, "lister1")
        response = await client.get("/api/v1/clipboard/items", headers=headers)
        body = response.json()
        assert set(body) >= {"items", "page", "size", "total", "pages"}
        assert body["page"] == 1

    async def test_分页参数越界返回_422(self, client: AsyncClient) -> None:
        headers = await make_user(client, "lister2")
        assert (
            await client.get("/api/v1/clipboard/items?page=0", headers=headers)
        ).status_code == 422
        assert (
            await client.get("/api/v1/clipboard/items?size=0", headers=headers)
        ).status_code == 422
        assert (
            await client.get("/api/v1/clipboard/items?size=101", headers=headers)
        ).status_code == 422

    async def test_分页可以取到第二页(self, client: AsyncClient) -> None:
        headers = await make_user(client, "pager")
        for i in range(3):
            await client.post(
                "/api/v1/clipboard/items", json={"content": f"page-item-{i}"}, headers=headers
            )
        first = (
            await client.get("/api/v1/clipboard/items?size=2&page=1", headers=headers)
        ).json()
        second = (
            await client.get("/api/v1/clipboard/items?size=2&page=2", headers=headers)
        ).json()
        assert first["total"] == 3 and first["pages"] == 2
        assert len(first["items"]) == 2 and len(second["items"]) == 1

    async def test_搜索同时匹配标题与正文(self, client: AsyncClient) -> None:
        headers = await make_user(client, "searcher")
        await client.post(
            "/api/v1/clipboard/items",
            json={"content": "正文里有 needle 这个词", "title": "无关标题"},
            headers=headers,
        )
        await client.post(
            "/api/v1/clipboard/items",
            json={"content": "无关注释", "title": "标题含 needle"},
            headers=headers,
        )
        await client.post(
            "/api/v1/clipboard/items", json={"content": "完全无关"}, headers=headers
        )

        by_content = (
            await client.get("/api/v1/clipboard/items?search=needle", headers=headers)
        ).json()
        assert by_content["total"] == 2, "标题与正文都应被搜索到"

    async def test_自定义标题原样保存(self, client: AsyncClient) -> None:
        headers = await make_user(client, "titled")
        response = await client.post(
            "/api/v1/clipboard/items",
            json={"content": "x", "title": "我的标题"},
            headers=headers,
        )
        assert response.json()["title"] == "我的标题"


class TestDeduplication:
    """去重契约：不新建、刷新 updated_at、不覆盖标题。"""

    async def test_重复内容不新建记录(self, client: AsyncClient) -> None:
        headers = await make_user(client, "dedup1")
        first = (
            await client.post(
                "/api/v1/clipboard/items", json={"content": "same"}, headers=headers
            )
        ).json()
        second = (
            await client.post(
                "/api/v1/clipboard/items", json={"content": "same"}, headers=headers
            )
        ).json()
        assert first["id"] == second["id"]
        assert (await client.get("/api/v1/clipboard/items", headers=headers)).json()["total"] == 1

    async def test_去重保留原标题(self, client: AsyncClient) -> None:
        """未显式传 title 时，不得用自动标题覆盖用户标题。"""
        headers = await make_user(client, "dedup2")
        first = (
            await client.post(
                "/api/v1/clipboard/items",
                json={"content": "keep-title", "title": "我的标题"},
                headers=headers,
            )
        ).json()
        second = (
            await client.post(
                "/api/v1/clipboard/items", json={"content": "keep-title"}, headers=headers
            )
        ).json()
        assert second["id"] == first["id"]
        assert second["title"] == "我的标题"

    async def test_去重时显式传标题才覆盖(self, client: AsyncClient) -> None:
        headers = await make_user(client, "dedup3")
        await client.post(
            "/api/v1/clipboard/items",
            json={"content": "retitle", "title": "旧标题"},
            headers=headers,
        )
        updated = (
            await client.post(
                "/api/v1/clipboard/items",
                json={"content": "retitle", "title": "新标题"},
                headers=headers,
            )
        ).json()
        assert updated["title"] == "新标题"

    async def test_去重不改_created_at(self, client: AsyncClient) -> None:
        headers = await make_user(client, "dedup4")
        first = (
            await client.post(
                "/api/v1/clipboard/items", json={"content": "ts"}, headers=headers
            )
        ).json()
        second = (
            await client.post(
                "/api/v1/clipboard/items", json={"content": "ts"}, headers=headers
            )
        ).json()
        assert second["created_at"] == first["created_at"]


class TestUserIsolation:
    """跨用户越权是严重缺陷，必须有测试守住。"""

    async def test_列表只返回自己的记录(self, client: AsyncClient) -> None:
        alice = await make_user(client, "iso_alice")
        bob = await make_user(client, "iso_bob")
        await client.post(
            "/api/v1/clipboard/items", json={"content": "alice-data"}, headers=alice
        )
        bob_list = (await client.get("/api/v1/clipboard/items", headers=bob)).json()
        assert bob_list["total"] == 0

    async def test_不能读取他人记录(self, client: AsyncClient) -> None:
        alice = await make_user(client, "iso_carol")
        bob = await make_user(client, "iso_dave")
        item = (
            await client.post(
                "/api/v1/clipboard/items", json={"content": "private"}, headers=alice
            )
        ).json()
        response = await client.get(f"/api/v1/clipboard/items/{item['id']}", headers=bob)
        assert response.status_code == 404, "越权读取应表现为 404（不暴露存在性）"

    async def test_不能删除他人记录(self, client: AsyncClient) -> None:
        alice = await make_user(client, "iso_erin")
        bob = await make_user(client, "iso_frank")
        item = (
            await client.post(
                "/api/v1/clipboard/items", json={"content": "keep-me"}, headers=alice
            )
        ).json()
        assert (
            await client.delete(f"/api/v1/clipboard/items/{item['id']}", headers=bob)
        ).status_code == 404
        # 原主仍能读到
        assert (
            await client.get(f"/api/v1/clipboard/items/{item['id']}", headers=alice)
        ).status_code == 200

    async def test_清空只影响自己(self, client: AsyncClient) -> None:
        alice = await make_user(client, "iso_grace")
        bob = await make_user(client, "iso_henry")
        await client.post("/api/v1/clipboard/items", json={"content": "a"}, headers=alice)
        await client.post("/api/v1/clipboard/items", json={"content": "b"}, headers=bob)
        assert (await client.delete("/api/v1/clipboard/items", headers=alice)).status_code == 200
        assert (await client.get("/api/v1/clipboard/items", headers=alice)).json()["total"] == 0
        assert (await client.get("/api/v1/clipboard/items", headers=bob)).json()["total"] == 1

    async def test_不同用户提交相同内容各自成条(self, client: AsyncClient) -> None:
        """去重按 (user_id, content_hash)，不应跨用户。"""
        alice = await make_user(client, "iso_ivan")
        bob = await make_user(client, "iso_judy")
        a = (
            await client.post(
                "/api/v1/clipboard/items", json={"content": "identical"}, headers=alice
            )
        ).json()
        b = (
            await client.post(
                "/api/v1/clipboard/items", json={"content": "identical"}, headers=bob
            )
        ).json()
        assert a["id"] != b["id"], "不同用户的内容不应互相去重"


class TestUpdateAndDelete:
    async def test_更新只改传入字段(self, client: AsyncClient) -> None:
        headers = await make_user(client, "updater1")
        item = (
            await client.post(
                "/api/v1/clipboard/items",
                json={"content": "original", "title": "原题"},
                headers=headers,
            )
        ).json()
        updated = (
            await client.patch(
                f"/api/v1/clipboard/items/{item['id']}",
                json={"title": "改后"},
                headers=headers,
            )
        ).json()
        assert updated["title"] == "改后"
        assert updated["content"] == "original", "未传的字段不应被改动"

    async def test_更新不存在的记录返回_404(self, client: AsyncClient) -> None:
        headers = await make_user(client, "updater2")
        response = await client.patch(
            "/api/v1/clipboard/items/00000000-0000-0000-0000-000000000000",
            json={"title": "x"},
            headers=headers,
        )
        assert response.status_code == 404

    async def test_删除后不再出现在列表(self, client: AsyncClient) -> None:
        headers = await make_user(client, "deleter1")
        item = (
            await client.post(
                "/api/v1/clipboard/items", json={"content": "to-delete"}, headers=headers
            )
        ).json()
        assert (
            await client.delete(f"/api/v1/clipboard/items/{item['id']}", headers=headers)
        ).status_code == 200
        assert (await client.get("/api/v1/clipboard/items", headers=headers)).json()["total"] == 0

    async def test_重复删除返回_404(self, client: AsyncClient) -> None:
        headers = await make_user(client, "deleter2")
        item = (
            await client.post(
                "/api/v1/clipboard/items", json={"content": "once"}, headers=headers
            )
        ).json()
        await client.delete(f"/api/v1/clipboard/items/{item['id']}", headers=headers)
        assert (
            await client.delete(f"/api/v1/clipboard/items/{item['id']}", headers=headers)
        ).status_code == 404

    async def test_详情返回_content_type(self, client: AsyncClient) -> None:
        headers = await make_user(client, "detail1")
        item = (
            await client.post(
                "/api/v1/clipboard/items", json={"content": "detail"}, headers=headers
            )
        ).json()
        detail = (
            await client.get(f"/api/v1/clipboard/items/{item['id']}", headers=headers)
        ).json()
        assert detail["content_type"] == "text", "阶段一只有 text 类型"


class TestTimezoneTitle:
    async def test_标题按传入时区展示(self, client: AsyncClient) -> None:
        headers = await make_user(client, "tz_user")
        utc = (
            await client.post(
                "/api/v1/clipboard/items",
                json={"content": "tz-utc", "timezone": "UTC"},
                headers=headers,
            )
        ).json()
        shanghai = (
            await client.post(
                "/api/v1/clipboard/items",
                json={"content": "tz-cn", "timezone": "Asia/Shanghai"},
                headers=headers,
            )
        ).json()
        assert utc["title"] != shanghai["title"]
        assert utc["title"].startswith("tz_user · ")
        assert shanghai["title"].startswith("tz_user · ")

    async def test_非法时区回退默认而非报错(self, client: AsyncClient) -> None:
        headers = await make_user(client, "tz_bad")
        response = await client.post(
            "/api/v1/clipboard/items",
            json={"content": "tz-bad", "timezone": "Not/AZone"},
            headers=headers,
        )
        assert response.status_code == 201
        assert response.json()["title"].startswith("tz_bad · ")
