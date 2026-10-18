# 云剪贴板 · API 契约

> **本文件是速查摘要，不是事实来源，也不内嵌完整 OpenAPI。**
> 契约的事实来源是 `server/app/schemas/`（Pydantic Schema）；最新内容查运行中后端的
> [`/openapi.json`](http://127.0.0.1:8000/openapi.json) 或交互式 [`/docs`](http://127.0.0.1:8000/docs)。

## 导出 OpenAPI

```powershell
# 不启动服务即可导出（app.openapi() 是纯静态构建，不连数据库）
cd server
.\venv\Scripts\python.exe -c "import json;from app.main import app;print(json.dumps(app.openapi(),ensure_ascii=False,indent=2))" | Set-Content -Encoding utf8 ..\docs\.openapi.json
```

> ⚠️ 导出的是**临时裸 JSON** `docs/.openapi.json`，**用完请删，不要提交**
> （`.gitignore` 未覆盖它，会以未跟踪文件出现在 `git status` 里）。

## 修改流程

改契约见 AGENTS.md 的「数据契约」：改 Schema → 检查迁移 → 重启确认 `/openapi.json`
→ `cd web && pnpm run gen:api` → 刷新本文件摘要。

---

## 接口摘要

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册：落库并校验唯一性，**直接返回令牌**；重名/重邮箱 409 |
| POST | `/api/v1/auth/login` | 登录：`username` 支持用户名或邮箱，凭证错误统一 401 |
| GET | `/api/v1/auth/me` | 当前用户，依据 `Authorization: Bearer <token>` |
| POST | `/api/v1/clipboard/items` | 创建；`title` 留空时自动生成，按 `timezone` 显示本地时间 |
| GET | `/api/v1/clipboard/items` | 列表：分页 / 类型筛选 / 按标题或内容搜索 / 排序。`sort_by` 默认 `created_at`；**两个客户端都显式传 `updated_at`**（按修改时间排，编辑后会上移） |
| GET | `/api/v1/clipboard/items/{id}` | 详情 |
| PATCH | `/api/v1/clipboard/items/{id}` | 更新（只改显式传入的字段）。内容与**另一条**重复时返回 `409` |
| DELETE | `/api/v1/clipboard/items/{id}` | 删除单条 |
| DELETE | `/api/v1/clipboard/items` | 清空 |
| POST | `/api/v1/dev/reset` | ⚠️ 删数据并重建种子（仅 `ENABLE_DEV_ROUTES=true` 时注册） |
| GET | `/api/v1/dev/db` | 探测当前连接的数据库（同上，仅开发路由开启时） |
| GET | `/health` / `/` | 健康检查 / 服务信息 |
| WS | `/api/v1/clipboard/ws?token=xxx` | 实时同步（见 [`ws-protocol.md`](ws-protocol.md)） |
| POST | `/api/v1/clipboard/upload` | ⬜ 图片/文件上传（**阶段二**，尚未实现） |

> 后两项**不在 `/openapi.json` 里**：`upload` 尚未实现，而 OpenAPI 本就不描述 WebSocket 握手。
> 它们列在这里只为避免下游以为漏掉。

### 认证

**`/api/v1/clipboard/*` 全部需要认证**，不带令牌返回 `401`（带 `WWW-Authenticate: Bearer`）。

```http
POST /api/v1/auth/login      {"username": "demo", "password": "demo1234"}
→ 200 {"id": "...", "username": "demo", ..., "token": {"access_token": "<JWT>", ...}}

GET /api/v1/clipboard/items
Authorization: Bearer <JWT>
```

- 令牌为 HS256 JWT，`sub` 是用户 UUID，有效期由 `JWT_EXPIRE_MINUTES` 控制（默认 7 天）
- 密码用 **bcrypt** 哈希（`pwdlib`）入库；`password_hash` **绝不出现在任何响应里**
- `password` 上限是 **72 字节**（不是字符数）：24 个汉字即达上限，超出返回 `422`
- 登录失败时"用户不存在"与"密码错误"返回**同一条提示**，避免枚举出已注册用户名

---

## 核心数据契约

```python
class ClipboardItemResponse(BaseModel):
    id: str                    # uuid
    user_id: str               # uuid
    title: str                 # 用户填写；留空时服务端生成 "demo · 10-05 21:56"
    content_type: ContentType  # text | image | file
    content: str               # 文字内容或文件 URL
    preview: Optional[str]     # 预览文本
    metadata: Optional[dict]   # {"mime": "text/plain", "size": 1024, ...}
    created_at: datetime       # ISO 8601 UTC
    updated_at: datetime       # ISO 8601 UTC
```

列表响应 `ClipboardItemList` = `items: ClipboardItemResponse[]` + `page` / `size` / `total` / `pages`。

### 关键约定

- 时间统一 ISO 8601 UTC，形如 `2026-09-27T10:00:00Z`；数据库列用 `timestamptz`
- `content_hash` **不对外暴露**，仅服务端用于去重
- `title` 留空时服务端生成 `<用户名> · <月-日 时:分>`，时间按请求里的 `timezone`（IANA 名）
  展示；数据库**始终存 UTC**，时区只影响标题文本。未传或非法时回退 `DEFAULT_TIMEZONE`
- 去重：同一用户提交相同 `content` → 刷新 `updated_at`、不新建记录，且**不覆盖已有标题**
  （除非本次显式传 `title`）
- 搜索同时匹配 `title` 与 `content`；分页 `page` 从 1 开始、`size` 默认 20、最大 100
- 阶段一仅支持 `content_type = text`；`image` / `file` 属阶段二、阶段三
- 实时同步：写操作成功后向**同用户**的 WebSocket 连接广播事件（见 [`ws-protocol.md`](ws-protocol.md)）

逐字段定义请读运行中的 `/openapi.json` 或 `server/app/schemas/`。
