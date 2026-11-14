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
> （`.gitignore` 已忽略它，但仍不要入库）。

## 修改流程

改契约见 AGENTS.md 的「数据契约」：改 Schema → 检查迁移 → 重启确认 `/openapi.json`
→ `cd web && pnpm run gen:api` → 刷新本文件摘要。

---

## 接口摘要

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册：先校验邀请码，再落库并校验唯一性，**直接返回令牌**；邀请码无效 403，重名/重邮箱 409 |
| POST | `/api/v1/auth/login` | 登录：`username` 支持用户名或邮箱，凭证错误统一 401 |
| POST | `/api/v1/auth/change-password` | 修改密码：校验当前密码，成功后该账号**全部令牌与 WebSocket 立即失效**，需用新密码重新登录 |
| GET | `/api/v1/auth/me` | 当前用户，依据 `Authorization: Bearer <token>` |
| POST | `/api/v1/clipboard/items` | 创建；`title` 留空时自动生成，按 `timezone` 显示本地时间 |
| GET | `/api/v1/clipboard/items` | 列表：分页 / 类型筛选 / 按标题或内容搜索 / 排序。`sort_by` 默认 `created_at`；**Web 端（及保留的鸿蒙端）都显式传 `updated_at`**（按修改时间排，编辑后会上移） |
| GET | `/api/v1/clipboard/items/{id}` | 详情 |
| PATCH | `/api/v1/clipboard/items/{id}` | 更新（只改显式传入的字段）。内容与**另一条**重复时返回 `409` |
| DELETE | `/api/v1/clipboard/items/{id}` | 删除单条（级联删除该记录的分享） |
| DELETE | `/api/v1/clipboard/items` | 清空（级联删除全部分享） |
| POST | `/api/v1/clipboard/items/{id}/shares` | 创建分享：快照/跟随、有效期、可选密码与查看次数；超限额 `409` |
| GET | `/api/v1/clipboard/shares` | 我的分享分页；支持 `status` / `item_id` / `search`（标题或内容）筛选 |
| DELETE | `/api/v1/clipboard/shares/{id}` | 撤销分享；重复撤销幂等，跨用户 `404` |
| GET | `/api/v1/clipboard/shares/{id}/access-logs` | 我的成功访问记录分页（失败记录仅管理员可见） |
| GET | `/api/v1/public/shares/{token}` | 公开元信息：不返回正文、不计数；有密码时 `title=null` |
| POST | `/api/v1/public/shares/{token}/access` | 公开查看正文：**唯一计数入口**；密码错误 `403`，失效 `410` |
| GET | `/api/v1/admin/stats` | 后台概览：用户 / 剪贴板 / 分享总数与有效分享 / 总占用 / 近 7 天新增 / 邀请码统计 |
| GET | `/api/v1/admin/users` | 用户分页：搜索用户名/邮箱、状态筛选、角色筛选、排序 |
| GET | `/api/v1/admin/users/{id}` | 用户详情与剪贴板统计 |
| GET | `/api/v1/admin/users/{id}/shares` | 指定用户的分享记录分页；`status` 可筛选，不返回 token / 链接 |
| PATCH | `/api/v1/admin/users/{id}` | 修改昵称 / 邮箱 / 启用状态 / 管理员标记 / 单独分享上限；`share_limit=null` 表示跟随全局 |
| POST | `/api/v1/admin/users/{id}/reset-password` | 重置密码，旧令牌立即失效 |
| DELETE | `/api/v1/admin/users/{id}` | 物理删除用户并级联删除剪贴板 |
| DELETE | `/api/v1/admin/users/{id}/clipboards` | 清空指定用户剪贴板 |
| GET | `/api/v1/admin/clipboards` | 全局剪贴板分页，支持用户/用户名/关键字筛选 |
| GET | `/api/v1/admin/clipboards/{id}` | 剪贴板详情（返回完整正文） |
| DELETE | `/api/v1/admin/clipboards/{id}` | 删除任意用户的单条剪贴板 |
| GET | `/api/v1/admin/audit-logs` | 管理员操作审计分页 |
| GET | `/api/v1/admin/invite-codes` | 邀请码分页；`status=all/active/exhausted/expired/revoked` |
| POST | `/api/v1/admin/invite-codes` | 生成邀请码；`max_uses` 必填，明文仅返回一次 |
| POST | `/api/v1/admin/invite-codes/{id}/revoke` | 撤销邀请码 |
| GET | `/api/v1/admin/invite-codes/{id}/usages` | 使用详情：通过该码注册的用户，分页 |
| GET | `/api/v1/admin/settings/shares` | 读取每用户有效分享上限（默认 50，范围 1–10000） |
| PUT | `/api/v1/admin/settings/shares` | 更新分享上限；更新与审计 `settings.share_quota.update` 同事务 |
| GET | `/api/v1/admin/shares` | 全局分享分页；`status` / `username` 筛选，不返回 token / 链接 |
| GET | `/api/v1/admin/share-access-logs` | 全部分享访问记录（成功 + 失败）；普通用户 `403` |
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

> 示例中的 `demo` 是**本地开发库**播种账号；生产环境不播种，注册需邀请码。

- 令牌为 HS256 JWT，`sub` 是用户 UUID，有效期由 `JWT_EXPIRE_MINUTES` 控制（默认 7 天）；
  管理员令牌由 `ADMIN_JWT_EXPIRE_MINUTES` 控制（默认 12 小时）
- JWT 带 `sv`（token_version）声明；密码重置、用户修改密码或账号被禁用后 `token_version += 1`，旧令牌返回 `401`
- `/api/v1/admin/*` **全部要求 `is_admin=true`**，普通用户返回 `403`；
  `is_admin` 仅在 `UserResponse` 中用于展示，权限每次请求都查库
- 密码用 **bcrypt** 哈希（`pwdlib`）入库；`password_hash` **绝不出现在任何响应里**
- 密码策略（注册、修改密码、管理员重置、`set_admin` 创建账号统一适用）：
  **至少 8 个字符**、**同时包含字母和数字**、**不能包含用户名**（不区分大小写）；
  上限是 **72 字节**（不是字符数）：24 个汉字即达上限，超出返回 `422`
- 修改密码必须提供 `old_password`，当前密码错误返回 `400`（不触发登出）；
  成功后 `token_version += 1` 并关闭该用户全部 WebSocket，所有设备都需重新登录
- `username` 不允许换行等控制字符（避免日志注入）；注册为 3-32 字符，登录（用户名或邮箱）上限 254
- 注册可选携带 `invite_code`：服务端开启 `REGISTRATION_REQUIRE_INVITE` 时，必须是
  `invite_codes` 表中未过期、未撤销且未用尽的邀请码，否则返回 `403`；
  注册成功后会把 `users.invite_code_id` 指向该码，供后台查询使用详情
- 登录失败时"用户不存在"与"密码错误"返回**同一条提示**，避免枚举出已注册用户名

---

## 核心数据契约

```python
class ClipboardItemResponse(BaseModel):
    id: str                    # uuid
    user_id: str               # uuid
    title: str                 # 用户填写；留空时服务端生成 "剪贴板 · 10-05 21:56"
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
- `title` 留空时服务端生成 `剪贴板 · <月-日 时:分>`，时间按请求里的 `timezone`（IANA 名）
  展示；数据库**始终存 UTC**，时区只影响标题文本。未传或非法时回退 `DEFAULT_TIMEZONE`
- 去重：同一用户提交相同 `content` → 刷新 `updated_at`、不新建记录，且**不覆盖已有标题**
  （除非本次显式传 `title`）
- 搜索同时匹配 `title` 与 `content`；分页 `page` 从 1 开始、`size` 默认 10、最大 100
- 阶段一仅支持 `content_type = text`；`image` / `file` 属阶段二、阶段三
- 实时同步：写操作成功后向**同用户**的 WebSocket 连接广播事件（见 [`ws-protocol.md`](ws-protocol.md)）
- 每个响应都带 `X-Request-ID`（12 位十六进制）；反馈问题时提供它即可定位到服务端日志。
  上游若已传同名请求头且格式合法（`[A-Za-z0-9._-]{1,64}`）则沿用

逐字段定义请读运行中的 `/openapi.json` 或 `server/app/schemas/`。

---

## 分享契约

事实来源：`server/app/schemas/share.py` 与 `schemas/admin.py`；
完整设计与边界见 [`share.md`](share.md)。

```python
class ClipboardShareCreate(BaseModel):
    mode: ShareMode            # snapshot | live（默认 snapshot）
    expires_in: ShareExpiresIn # 1h | 1d | 7d（默认） | 30d
    password: Optional[str]    # 4–24 字符，UTF-8 ≤ 72 字节
    max_views: Optional[int]   # 1–10000；空表示不限

class ClipboardShareResponse(BaseModel):
    id: str
    item_id: str
    mode: ShareMode
    status: ShareStatus        # active | expired | exhausted | revoked
    title: str
    token: str                 # secrets.token_urlsafe(32)
    url: str                   # ${PUBLIC_BASE_URL}/s/<token>
    password_protected: bool
    expires_at: Optional[datetime]
    max_views: Optional[int]
    view_count: int
    remaining_views: Optional[int]
    created_at: datetime
    last_viewed_at: Optional[datetime]
```

- 限额：`users.share_limit` 非空时优先于全局默认值，为空则跟随 `share_settings.user_share_limit`
- 单条记录最多 5 个有效分享，超出返回 `409`（需先撤销旧链接）
- 状态判定顺序：`revoked` → `expired` → `exhausted` → `active`
- **计数规则**：页面加载、刷新、`GET meta`、密码错误均不计数；
  只有 `POST access` 成功返回正文才计 1 次
- 快照分享复制创建时的正文；跟随分享按 `item_id` 读取原记录最新内容
- 访问记录只记 `accessed_at` / `result` / 原始 IP / User-Agent，
  **不记 token、正文、密码**；所有者接口返回脱敏 IP，管理端返回原始 IP
- 失败 `result`：`password_failed` / `expired` / `revoked` / `exhausted` / `owner_disabled`
- 公开接口统一响应头：`X-Robots-Tag: noindex, nofollow`、`Cache-Control: no-store`、
  `Referrer-Policy: no-referrer`
