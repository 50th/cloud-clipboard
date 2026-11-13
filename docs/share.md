# 剪贴板分享 · 设计与执行文档

> 本文是分享功能的**执行依据**：范围、决策、数据模型、接口、文件清单与验收标准都在这里。
> 数据契约以 `server/app/schemas/` 为准；实现完成后同步 [`api.md`](api.md)；
> 进度与验证记录写 [`roadmap.md`](roadmap.md)。
>
> **新会话怎么用**：先读第 3、4、6 节确认契约，再按第 11 节顺序实现，最后用第 10、12 节验收。
> 管理端限额 / 访问记录见 6.6、6.7、8.7、8.8 与 [`admin.md`](admin.md)。

**最后更新**：2026-11-13
**状态**：设计定稿（含分享限额、计数规则、删除确认），待实现
**入口**：用户端历史卡片「分享」；公开页 `/s/<token>`

---

## 1. 目标

把一条文字剪贴板生成**受控的只读链接**：未登录访客可以查看和复制，分享者可以设置密码、有效期、查看次数，并随时撤销。

分享是独立读路径，不改变现有保存、自动保存、去重和 WebSocket 同步逻辑。

---

## 2. 范围

### 2.1 本期（P0）

- 单条剪贴板记录分享
- 公开链接 + 可选访问密码
- 内容模式：快照 / 跟随最新
- 有效期：1 小时 / 1 天 / 7 天 / 30 天，默认 7 天
- 最大查看次数：可选 1–10000
- 我的分享：列表、复制链接、撤销
- 公开查看页 `/s/<token>`：查看、解锁、复制、失效提示
- 每用户有效分享上限：默认 50，管理端可调（范围 1–10000）
- 删除原记录时，如存在有效分享，前端提示链接将立即失效
- 分享访问记录：成功获取正文时记录时间、IP、User-Agent；我的分享可分页查看
- 失败尝试记录：密码错误、已过期、已撤销、次数用尽、分享者禁用；仅管理员可查看
- 管理员访问记录：可查看全部成功/失败记录，支持按结果、分享、用户、时间筛选
- 限流、`noindex`、日志访问控制

### 2.2 不做

- 多条合集、整个剪贴板分享
- 图片 / 文件分享（阶段二、三）
- 分享给站内指定用户
- 公开分享列表 / 搜索
- 修改已有分享（只能撤销后重建）
- 永久分享
- 管理员分享管理（撤销/编辑分享，P1；访问记录查看除外）
- 按用户单独设置不同限额（P0 只做全局统一上限）
- 访客级去重计数（P0 不做；见 5.4）
- 访问记录自动清理 / 保留策略（P1）
- WebSocket 分享事件
- 新依赖

---

## 3. 已定决策

| 项 | 结论 |
|----|------|
| 分享粒度 | 单条记录 |
| 访问控制 | 公开链接；密码可选 |
| 内容语义 | `snapshot`（快照）或 `live`（跟随最新），创建时选择 |
| 有效期 | `1h` / `1d` / `7d` / `30d`，默认 `7d`；不支持永久 |
| 查看次数 | 可空；空为不限，范围 1–10000 |
| token 存储 | **方案 A：明文存储 + 唯一索引** |
| token 生成 | `secrets.token_urlsafe(32)`，约 43 字符 |
| 删除原记录 | 级联删除分享，链接失效 |
| 分享者信息 | 不在公开页展示 |
| 密码规则 | 4–24 字符，UTF-8 不超过 72 字节（bcrypt 上限） |
| 修改分享 | 不支持；撤销后重新创建 |
| 管理端 | P0 只做「分享限额」设置与访问记录查看；分享撤销/编辑为 P1 |
| 分享限额 | 每用户有效分享数；全局设置，默认 50，管理端可调，范围 1–10000 |
| 计数规则 | 只有主动点击「查看内容」并成功获取正文才计数；页面加载、刷新、meta、密码错误不计数；P0 不做访客去重 |
| 删除确认 | 删除原记录前查询有效分享数；有分享时提示链接将立即失效 |
| 访问记录 | 记录成功访问与失败尝试；字段 `accessed_at`、`result`、原始 IP、User-Agent |
| 访问记录可见性 | 所有者只看 `success`；管理员可看全部成功/失败记录 |
| 失败记录范围 | `password_failed` / `expired` / `revoked` / `exhausted` / `owner_disabled` |
| 访问记录保留 | P0 保留，随分享删除级联；自动清理 / 保留天数列为 P1 |
| token 日志 | Nginx access log **允许记录 token**（可接受风险）：token 不是账号凭证；无密码分享本就允许持链接访问，密码分享仅凭 token 无法读取正文。应用日志仍不记录 token/正文/密码。 |
| 公开页 Referer | 建议用 Nginx **server 级** `Referrer-Policy: no-referrer` 降低 token 扩散面；它是隐私最佳实践，不作为内容保密边界。 |
| 公开页 noindex | 建议用 server 级 `map $request_uri` 提供 `X-Robots-Tag`，避免搜索引擎收录；不作为内容保密边界。 |
| 历史标题 | 默认标题已改为 `剪贴板 · <月-日 时:分>`；历史记录仍可能是旧格式 `<用户名> · <月-日 时:分>`，分享时可能泄露用户名（已知限制） |

**为什么 token 明文存储（方案 A）**：我的分享页需要再次复制链接，哈希无法还原；数据库中剪贴板正文本身就是明文，哈希只防「只读库泄露后直接拿链接」，收益有限。token 仍然只在本人接口返回，公开接口不返回；应用日志脱敏。Nginx access log 可能包含 token，按敏感日志管理（限制访问与保留周期），不作为内容保密边界；公开页仍建议 `no-referrer` / `noindex` 降低扩散面。若后续安全要求改为「链接只展示一次」，再切换为哈希存储。

---

## 4. 数据模型

### 4.1 表 `clipboard_shares`

| 字段 | 类型 | 约束 / 说明 |
|------|------|-------------|
| `id` | UUID | PK |
| `user_id` | UUID | FK `users.id` `ON DELETE CASCADE`，索引 |
| `item_id` | UUID | FK `clipboard_items.id` `ON DELETE CASCADE`，索引 |
| `mode` | varchar(16) | `snapshot` / `live`，默认 `snapshot` |
| `token` | varchar(64) | 唯一；`secrets.token_urlsafe(32)` |
| `title` | varchar(200) | 创建时标题；我的分享列表展示用 |
| `content` | text, null | `snapshot` 存正文；`live` 为 `NULL` |
| `content_type` | varchar(16) | 阶段一固定 `text` |
| `password_hash` | varchar(255), null | bcrypt；空表示无密码 |
| `expires_at` | timestamptz, null | P0 创建时必填；空保留给未来永久分享 |
| `max_views` | integer, null | 空表示不限 |
| `view_count` | integer, not null | 默认 0 |
| `revoked_at` | timestamptz, null | 撤销时间 |
| `created_at` | timestamptz, not null | 默认 `now()` |
| `last_viewed_at` | timestamptz, null | 最后一次成功查看文章 |

约束与索引：

- `UniqueConstraint("token")`
- `Index("ix_clipboard_shares_user_created", "user_id", "created_at")`
- `Index("ix_clipboard_shares_expires_at", "expires_at")`
- `item_id`、`user_id` 单列索引（`index=True`）

### 4.2 表 `clipboard_share_access_logs`

| 字段 | 类型 | 约束 / 说明 |
|------|------|-------------|
| `id` | UUID | PK |
| `share_id` | UUID | FK `clipboard_shares.id` `ON DELETE CASCADE`，索引 |
| `accessed_at` | timestamptz | not null，默认 `now()` |
| `result` | varchar(16) | `success` / `password_failed` / `expired` / `revoked` / `exhausted` / `owner_disabled` |
| `ip` | inet, null | 原始 IP，仅用于安全排查；用户端返回脱敏值 |
| `user_agent` | varchar(512), null | 截断后的 User-Agent |

索引：

- `Index("ix_share_access_logs_share_accessed", "share_id", "accessed_at")`，所有者/单分享查询
- `Index("ix_share_access_logs_result_accessed", "result", "accessed_at")`，管理员按结果筛选

查询按 `accessed_at DESC`。

### 4.3 枚举

```python
class ShareMode(str, Enum):
    SNAPSHOT = "snapshot"
    LIVE = "live"

class ShareExpiresIn(str, Enum):
    HOUR_1 = "1h"
    DAY_1 = "1d"
    DAY_7 = "7d"
    DAY_30 = "30d"

class ShareStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    EXHAUSTED = "exhausted"
    REVOKED = "revoked"

class ShareAccessResult(str, Enum):
    SUCCESS = "success"
    PASSWORD_FAILED = "password_failed"
    EXPIRED = "expired"
    REVOKED = "revoked"
    EXHAUSTED = "exhausted"
    OWNER_DISABLED = "owner_disabled"
```

### 4.4 表 `share_settings`

单行配置表，`id` 固定为 `1`。

| 字段 | 类型 | 约束 / 说明 |
|------|------|-------------|
| `id` | smallint | PK，`CHECK (id = 1)` |
| `user_share_limit` | integer | not null，默认 `50`，范围 1–10000 |
| `updated_at` | timestamptz | not null |
| `updated_by` | UUID, null | FK `users.id` `ON DELETE SET NULL` |

迁移时插入 `id=1, user_share_limit=50`；代码读取时若行缺失，回退默认 50。

### 4.5 ORM 与迁移

- 模型：`server/app/db/models/share.py`（`ClipboardShare`）、
  `server/app/db/models/share_setting.py`（`ShareSetting`）、
  `server/app/db/models/share_access_log.py`（`ShareAccessLog`）
- 在 `server/app/db/models/__init__.py` 导入并加入 `__all__`
- 迁移：`0005_clipboard_shares`（`down_revision = "0004_user_invite_code"`）、
  `0006_share_settings`（`down_revision = "0005_clipboard_shares"`）、
  `0007_share_access_logs`（`down_revision = "0006_share_settings"`）
- 迁移后逐行检查，确认没有把开发库里的测试表当成删除项
- 不建 ORM relationship，公开访问用显式查询取原记录，避免异步懒加载 `MissingGreenlet`

---

## 5. 状态与业务规则

### 5.1 状态判定

按以下顺序判定，命中即返回：

1. `revoked_at` 非空 → `revoked`
2. `expires_at` 非空且 `<= now` → `expired`
3. `max_views` 非空且 `view_count >= max_views` → `exhausted`
4. 否则 → `active`

公开接口只有 `active` 才返回正文；其余统一 `410`。

### 5.2 有效期映射

| `expires_in` | `expires_at` |
|--------------|--------------|
| `1h` | `now + 1 hour` |
| `1d` | `now + 1 day` |
| `7d` | `now + 7 days` |
| `30d` | `now + 30 days` |

时间统一用 `app.schemas.common.utc_now()`，数据库 `timestamptz`。

### 5.3 快照 / 跟随最新

| 模式 | 创建时 | 公开访问时 |
|------|--------|------------|
| `snapshot` | 复制 `item.title`、`item.content`、`item.content_type` | 读分享行里的副本 |
| `live` | 只存 `item.title`、`content_type`，`content` 为 NULL | 按 `item_id` 取原记录最新标题与正文 |

- 两种模式都受密码、有效期、查看次数约束。
- 原记录被删除时，数据库级联删除分享，公开页返回 `404`（视为不存在/已失效）。
- 分享者被禁用时，公开访问额外校验 `User.is_active`，返回 `410`。
- 我的分享列表展示创建时标题；跟随模式的公开页展示原记录最新标题。
- 默认标题已改为 `剪贴板 · <月-日 时:分>`（见 `app/crud/clipboard.py` 的
  `generate_default_title()`），不再包含用户名。历史记录若仍是旧格式
  `<用户名> · <月-日 时:分>`，分享历史记录时公开页会显示该旧标题；这是本期
  「只影响新记录」的已知限制。若必须彻底脱敏，创建分享时需把匹配旧自动标题格式的
  `title` 替换为中性标题。

### 5.4 查看计数

计数规则：

- 只有用户**主动点击「查看内容」**（无密码分享）或**提交正确密码**（有密码分享）
  并成功获取正文时，才计 1 次。
- 页面加载、刷新、`GET meta`、密码错误、复制操作均不计数。
- 同一页面内重复点击「查看内容」或重复复制不重复计数；刷新后再次点击视为一次新的主动查看。
- P0 不做访客级去重（不引入 cookie / IP 记录）。如需「同一访客只计一次」，
  需要新增访客标识与记录表，列为 P1。
- 直接调用 `POST access` 仍会计数，无法阻止恶意消耗；这是本计数规则的已知边界。

用条件更新原子递增，避免并发超发：

```python
now = utc_now()
result = await session.execute(
    update(ClipboardShare)
    .where(
        ClipboardShare.id == share.id,
        ClipboardShare.revoked_at.is_(None),
        or_(ClipboardShare.expires_at.is_(None), ClipboardShare.expires_at > now),
        or_(
            ClipboardShare.max_views.is_(None),
            ClipboardShare.view_count < ClipboardShare.max_views,
        ),
    )
    .values(view_count=ClipboardShare.view_count + 1, last_viewed_at=now)
    .returning(ClipboardShare.view_count, ClipboardShare.max_views)
)
row = result.first()
if row is None:
    return None  # 由路由层转成 410，CRUD 不抛 HTTPException
await session.commit()
return row.view_count, row.max_views
```

`remaining_views = max(0, max_views - view_count)`；`max_views` 为空时返回 `None`。

### 5.5 撤销与删除

- `DELETE /clipboard/shares/{id}` 只允许本人；不存在或不属于本人返回 `404`。
- 已撤销再撤销返回成功（幂等），不重复写 `revoked_at`。
- 删除原剪贴板项或删除用户时，分享随外键级联删除。
- Web 端删除原记录前，应先查询该记录的有效分享数；有分享时确认文案包含数量和
  「链接将立即失效」提示（见 8.6）。
- P0 不做物理清理任务；过期/撤销/用尽的行保留，便于排查。

### 5.6 密码

- 可空；非空时 4–24 字符，UTF-8 不超过 72 字节。
- 用现有 `app/core/security.py` 的 `hash_password` / `verify_password`。
- 缺少密码或密码错误统一返回 `403`，detail 固定为「密码错误或未提供」，不区分两种情况。
- 有密码时，`GET meta` 的 `title` 返回 `null`，避免未解锁就泄露标题；解锁后 `access` 返回真实标题。
- 密码失败限流见第 9 节。

### 5.7 公开页边界

- 不加载用户端 Pinia store，不读取本地登录态。
- 不展示分享者用户名/昵称/邮箱；默认标题已不含用户名（历史记录见 5.3 的已知限制）。
- 不提供列表、搜索、编辑、保存到我的剪贴板。
- 正文用 Vue 文本插值渲染，禁止 `v-html`。
- 页面无外部域名资源；建议降低 token 扩散面：
  - `Referrer-Policy: no-referrer` 建议由 **Nginx server 级响应头**从第一个字节提供，
    否则首屏 `/assets/*` 请求可能把 `/s/<token>` 写进 `Referer`；只靠 `ShareView`
    挂载后写入 meta 太晚。
  - `X-Robots-Tag: noindex, nofollow` 建议由 Nginx server 级 `map $request_uri` 提供，
    避免 `/s/` 的 `add_header` 在 `try_files ... /index.html` 内部重定向后失效。
- `ShareView` 挂载后写入 `<meta name="robots">` / `<meta name="referrer">` 仅作为兜底，
  不作为主防护。
- 口径说明：即使 token 进入 Nginx access log，密码分享仅凭 token 无法读取正文；
  无密码分享本就允许持链接访问。真正的残余风险是：无密码 + `max_views` 时，
  日志读者可能消耗查看次数；密码分享的弱密码可能被针对性尝试。

### 5.8 分享限额

- `share_settings.user_share_limit` 是每用户**有效分享**上限，默认 50，范围 1–10000。
- 有效定义与 5.1 的 `active` 一致；已撤销、已过期、次数用尽不占额度。
- 创建分享时在同一事务内锁定用户行（`SELECT ... FOR UPDATE` 或 advisory lock），
  再统计有效分享数；达到上限返回 `409`，detail 包含上限值。
- 管理端调低限额不会删除已有分享；只阻止新建，直到有效分享数低于限额。
- P0 为全局统一上限；按用户单独覆盖列为 P1。

### 5.9 访问记录

- **成功记录**：`access` 路由先 `resolve_content` 确认正文可取，再调用 `consume_view`；
  成功时在同一事务内递增 `view_count` 并插入 `result="success"` 的记录。
- **失败记录**：`POST access` 在以下情况插入失败记录，**不增加** `view_count`：
  - 密码缺失或错误 → `password_failed`
  - 分享已过期 → `expired`
  - 分享已撤销 → `revoked`
  - 次数用尽 → `exhausted`
  - 分享者被禁用 → `owner_disabled`
- 失败 `result` 与实际响应一致：`403` → `password_failed`；`410` 按 5.1 的状态判定，
  分享本身 `active` 但分享者被禁用时记 `owner_disabled`。
- 失败记录使用独立事务提交；记录失败只写应用日志，不影响 `403` / `410` 响应。
- **不记录**：`GET meta`、页面加载、刷新、限流 `429`、token 不存在 `404`
  （无 `share_id`，只进应用日志）。
- 记录字段：`accessed_at`、`result`、`ip`、`user_agent`；
  **不记录 token、正文、密码、Referer**。
- IP 取值与限流一致：优先 `X-Real-IP`，缺失时 `request.client.host`。
  原始 IP 入库；**所有者接口只返回脱敏 IP**（IPv4 最后一段、IPv6 后 64 位替换为 `*`），
  管理员接口可返回原始 IP（管理端仅内网 / VPN 访问）。
- User-Agent 截断到 512 字符；列表最多展示前 200 字符。
- **可见性**：所有者接口只返回 `result="success"`；管理员接口返回全部，
  可按结果、分享、用户、时间筛选。失败记录**只有管理员能查看**。
- 访问记录接口不按分享状态过滤：撤销 / 过期后仍可查看历史；分享被删除后随级联消失。
- 访问记录从该功能上线后开始写入；历史 `view_count` 不回溯补明细。
- 访问记录随分享删除级联；P0 不做自动清理，后续按保留天数清理列为 P1。

---

## 6. API 契约

### 6.1 登录态接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/clipboard/items/{id}/shares` | 创建分享；返回 token 与完整 URL |
| GET | `/api/v1/clipboard/shares` | 我的分享分页；`page` 从 1 开始，`size` 默认 20、最大 100 |
| DELETE | `/api/v1/clipboard/shares/{id}` | 撤销分享 |
| GET | `/api/v1/clipboard/shares/{id}/access-logs` | 我的成功访问记录分页；仅所有者可查，不含失败记录 |

创建请求：

```json
{
  "mode": "snapshot",
  "expires_in": "7d",
  "password": "1234",
  "max_views": 10
}
```

创建响应 `201`：

```json
{
  "id": "uuid",
  "item_id": "uuid",
  "mode": "snapshot",
  "status": "active",
  "title": "剪贴板 · 11-12 10:00",
  "token": "AbC...",
  "url": "http://localhost:5273/s/AbC...",
  "password_protected": true,
  "expires_at": "2026-11-19T02:00:00Z",
  "max_views": 10,
  "view_count": 0,
  "remaining_views": 10,
  "created_at": "2026-11-12T02:00:00Z",
  "last_viewed_at": null
}
```

列表响应：

```json
{
  "items": [],
  "page": 1,
  "size": 20,
  "total": 0,
  "pages": 0
}
```

查询参数：`page`、`size`、`status`（`active|expired|exhausted|revoked`，可空）、
`item_id`（可选，按原记录过滤；删除确认用它统计有效分享数）。
筛选顺序与 5.1 一致：已撤销的行只算 `revoked`，不同时算 `expired` 或 `exhausted`。

撤销响应：

```json
{ "success": true, "message": "已撤销分享" }
```

访问记录响应：

```json
{
  "items": [
    {
      "id": "uuid",
      "accessed_at": "2026-11-13T02:00:00Z",
      "result": "success",
      "ip_masked": "203.0.113.*",
      "user_agent": "Mozilla/5.0 ..."
    }
  ],
  "page": 1,
  "size": 20,
  "total": 1,
  "pages": 1
}
```

查询参数：`page`、`size`（默认 20、最大 100）。按 `accessed_at DESC` 排序；
只返回 `result="success"`；分享不存在或不属于本人返回 `404`。

### 6.2 公开接口（无需登录）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/public/shares/{token}` | 元信息；不返回正文、不计数 |
| POST | `/api/v1/public/shares/{token}/access` | 校验密码后返回正文并计数 |

元信息响应：

```json
{
  "title": null,
  "mode": "snapshot",
  "content_type": "text",
  "password_required": true,
  "expires_at": "2026-11-19T02:00:00Z",
  "remaining_views": 10
}
```

- 无密码时 `title` 返回真实标题；有密码时返回 `null`。
- 已失效统一 `410`，token 不存在 `404`。
- `POST access` 是**唯一计数入口**；前端只在用户主动点击「查看内容」或提交密码时调用。

正文响应：

```json
{
  "title": "剪贴板 · 11-12 10:00",
  "content": "要分享的文字",
  "content_type": "text",
  "created_at": "2026-11-12T02:00:00Z",
  "expires_at": "2026-11-19T02:00:00Z",
  "remaining_views": 9
}
```

请求体：

```json
{ "password": "1234" }
```

无密码分享可传空对象 `{}`。

### 6.3 错误码

| 场景 | 状态码 | detail |
|------|--------|--------|
| token 不存在 | 404 | 分享不存在 |
| 已撤销 / 过期 / 次数用尽 / 分享者被禁用 | 410 | 分享已失效 |
| 缺少密码或密码错误 | 403 | 密码错误或未提供 |
| 触发限流 | 429 | 尝试过于频繁，请稍后再试 |
| 原记录不存在或不属于本人 | 404 | 剪贴板项不存在 |
| 分享不存在或不属于本人 | 404 | 分享不存在 |
| 有效分享数达到上限 | 409 | 分享数量已达上限（N 条），请先撤销或等待过期 |
| 非文字记录 | 400 | 阶段一仅支持文字分享 |

### 6.4 响应头

**公开 API** 统一加：

```
X-Robots-Tag: noindex, nofollow
Cache-Control: no-store
Referrer-Policy: no-referrer
```

**分享页 HTML** 由 Nginx 提供，不能只依赖 FastAPI 的 API 响应头；以下防护属于
**隐私最佳实践**，不作为内容保密边界：

- `Referrer-Policy: no-referrer`：server 级，降低首屏 `/assets/*` 与页面内跳转的 token 扩散面。
- `X-Robots-Tag: noindex, nofollow`：server 级 `map $request_uri`，仅对 `/s/` 生效，避免搜索引擎收录。
- `Cache-Control: no-cache`（`expires -1` 的默认效果；如需要更强可评估 `no-store`）。
- `/s/` 的 `location` **不要**再声明 `add_header`，否则会覆盖 server 级安全头；详见 9.3。

### 6.5 分享 URL

- 配置 `PUBLIC_BASE_URL`（见 9.4），拼接 `${PUBLIC_BASE_URL.rstrip('/')}/s/${token}`。
- **不要用请求的 `Host` 头拼 URL**，避免 Host 头注入。
- `url` 只在登录态接口返回；公开接口不返回 token。

### 6.6 管理端分享限额

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/settings/shares` | 读取分享限额；返回 `user_share_limit`、`updated_at`、`updated_by`、`updated_by_username` |
| PUT | `/api/v1/admin/settings/shares` | 更新分享限额；body `{ "user_share_limit": 50 }`，范围 1–10000 |

- 仅管理员可访问；普通用户返回 `403`。
- 更新与审计 `settings.share_quota.update` 同事务提交，记录 old/new；审计失败整体回滚。
- 设置立即生效：新创建分享按新限额校验；已有分享不因调低限额被删除。

### 6.7 管理端访问记录

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/share-access-logs` | 全部访问记录（成功 + 失败）；仅管理员 |

查询参数：

- `page` / `size`：默认 20，最大 100。
- `result`：`all` / `success` / `failure`；默认 `all`。
- `share_id?`：按分享过滤。
- `username?`：按分享者用户名过滤。
- `start?` / `end?`：按 `accessed_at` 时间范围过滤。

响应：

```json
{
  "items": [
    {
      "id": "uuid",
      "share_id": "uuid",
      "share_title": "剪贴板 · 11-12 10:00",
      "owner_id": "uuid",
      "owner_username": "demo",
      "accessed_at": "2026-11-13T02:00:00Z",
      "result": "password_failed",
      "ip": "203.0.113.7",
      "user_agent": "Mozilla/5.0 ..."
    }
  ],
  "page": 1,
  "size": 20,
  "total": 1,
  "pages": 1
}
```

- 按 `accessed_at DESC` 排序；`failure` 表示 `result != "success"`。
- 原始 IP 只在该接口返回；管理端仅内网 / VPN 访问。
- 普通用户访问返回 `403`；失败记录只有管理员能查看。

---

## 7. 后端实现清单

| 文件 | 内容 |
|------|------|
| `server/app/schemas/share.py` | 枚举与请求/响应模型 |
| `server/app/schemas/admin.py` | 分享限额设置、管理端访问记录模型 |
| `server/app/db/models/share.py` | `ClipboardShare` ORM 模型 |
| `server/app/db/models/share_setting.py` | `ShareSetting` ORM 模型 |
| `server/app/db/models/share_access_log.py` | `ShareAccessLog` ORM 模型 |
| `server/app/db/models/__init__.py` | 导入三个分享模型 |
| `server/alembic/versions/20261112_1200_0005_clipboard_shares.py` | 建表迁移 |
| `server/alembic/versions/20261113_1200_0006_share_settings.py` | 分享限额表迁移 |
| `server/alembic/versions/20261113_1200_0007_share_access_logs.py` | 访问记录表迁移 |
| `server/app/crud/share.py` | 数据访问、状态/计数、有效分享数、访问记录 |
| `server/app/crud/share_setting.py` | 读取/更新分享限额 |
| `server/app/routers/share.py` | 登录态路由与公开路由 |
| `server/app/routers/admin.py` | 管理端分享限额、访问记录接口 |
| `server/app/services/rate_limit.py` | 进程内滑动窗口限流 |
| `server/app/core/config.py` | `PUBLIC_BASE_URL` |
| `server/app/core/logging_utils.py` | 分享 token 路径脱敏 |
| `server/app/main.py` | 注册路由与 OpenAPI 标签 |
| `server/tests/test_shares.py` | 接口、计数与限额测试 |
| `server/tests/test_admin_share_settings.py` | 管理端限额设置测试 |
| `server/tests/test_admin_share_access_logs.py` | 管理端访问记录与失败记录可见性测试 |
| `server/.env.example` | `PUBLIC_BASE_URL` 示例 |

### 7.1 Schema

`server/app/schemas/share.py` 至少包含：

- `ShareMode` / `ShareExpiresIn` / `ShareStatus`
- `ClipboardShareCreate`
- `ClipboardShareResponse`（含 `token`、`url`）
- `ClipboardShareList`（含 `build` 分页方法）
- `ClipboardShareListParams`
- `PublicShareMeta`
- `PublicShareAccessRequest`
- `PublicShareContent`
- `ShareAccessLogResponse` / `ShareAccessLogList` / `ShareAccessLogListParams`
- `ShareSettingsResponse` / `ShareSettingsUpdate`（管理端限额）

管理端访问记录模型放在 `server/app/schemas/admin.py`：

- `AdminShareAccessLogResponse` / `AdminShareAccessLogList` / `AdminShareAccessLogParams`

字段清单：

| 模型 | 字段 |
|------|------|
| `ClipboardShareCreate` | `mode`、`expires_in`、`password?`、`max_views?` |
| `ClipboardShareResponse` | `id`、`item_id`、`mode`、`status`、`title`、`token`、`url`、`password_protected`、`expires_at?`、`max_views?`、`view_count`、`remaining_views?`、`created_at`、`last_viewed_at?` |
| `ClipboardShareList` | `items`、`page`、`size`、`total`、`pages`；`pages = (total + size - 1) // size if total else 0` |
| `ClipboardShareListParams` | `page=1`、`size=20`、`status?`、`item_id?` |
| `PublicShareMeta` | `title?`、`mode`、`content_type`、`password_required`、`expires_at?`、`remaining_views?` |
| `PublicShareAccessRequest` | `password?` |
| `PublicShareContent` | `title`、`content`、`content_type`、`created_at`、`expires_at?`、`remaining_views?` |
| `ShareAccessLogResponse` | `id`、`accessed_at`、`result`、`ip_masked?`、`user_agent?` |
| `ShareAccessLogList` | `items`、`page`、`size`、`total`、`pages` |
| `ShareAccessLogListParams` | `page=1`、`size=20`（最大 100） |
| `AdminShareAccessLogResponse` | `id`、`share_id`、`share_title`、`owner_id`、`owner_username`、`accessed_at`、`result`、`ip?`、`user_agent?` |
| `AdminShareAccessLogList` | `items`、`page`、`size`、`total`、`pages` |
| `AdminShareAccessLogParams` | `page=1`、`size=20`、`result=all`、`share_id?`、`username?`、`start?`、`end?` |
| `ShareSettingsResponse` | `user_share_limit`、`updated_at?`、`updated_by?`、`updated_by_username?` |
| `ShareSettingsUpdate` | `user_share_limit`（1–10000） |

`ClipboardShareCreate.password` 用 `field_validator` 检查 UTF-8 字节数不超过 72。

### 7.2 CRUD 函数

`server/app/crud/share.py`：

```python
async def create_share(session, user_id, item, payload) -> ClipboardShare
async def list_shares(session, user_id, *, page, size, status, item_id) -> tuple[list[ClipboardShare], int]
async def get_share(session, user_id, share_id) -> ClipboardShare | None
async def revoke_share(session, user_id, share_id) -> bool
async def get_by_token(session, token) -> ClipboardShare | None
async def count_active_shares(session, user_id) -> int
def share_status(share, now) -> ShareStatus
def remaining_views(share) -> int | None
async def consume_view(session, share, *, ip, user_agent) -> tuple[int, int | None] | None
async def resolve_content(session, share) -> tuple[str, str, str] | None
async def record_access_log(session, share, *, result, ip, user_agent) -> None
async def list_access_logs(session, share_id, *, page, size, include_failures=False) -> tuple[list[ShareAccessLog], int]
async def list_all_access_logs(session, *, page, size, result, share_id, username, start, end) -> tuple[list[ShareAccessLog], int]
def build_share_url(token) -> str
```

`server/app/crud/share_setting.py`：

```python
async def get_share_settings(session) -> int
async def update_share_settings(session, user_share_limit, admin_id) -> ShareSetting
```

- 路由层只做参数校验和调用，不直接写 SQL。
- 创建前由路由用 `clipboard_crud.get_item()` 取记录并校验归属，再把 `item` 传给 `create_share`。
- `share_status` 是纯函数，便于单测。
- `consume_view` 返回新的 `(view_count, max_views)`；条件不满足返回 `None`。
  成功时在同一事务内插入 `result="success"` 的 `ShareAccessLog`，
  记录 `accessed_at`、`ip`、`user_agent`。
  `access` 路由先 `resolve_content`，再调用 `consume_view`，确保正文可取才计数和记录。
- `resolve_content` 对 `live` 模式显式 `session.get(ClipboardItem, share.item_id)`；不存在返回 `None`。
- `count_active_shares` 统计状态为 `active` 的分享（口径同 5.1），用于限额和删除确认。
- `create_share` 在同一事务内锁定用户行、读取 `share_settings`、统计有效分享数；
  达到上限时抛业务异常，由路由转成 `409`。
- `get_share_settings` 在配置行缺失时回退默认 50；`update_share_settings`
  行缺失时创建，并同步写审计。
- `record_access_log` 写单条成功/失败记录；失败记录由路由在返回 `403` / `410` 前调用，
  使用独立事务，记录失败不影响原响应。
- `list_access_logs` 按 `share_id` 查询并按 `accessed_at DESC` 分页；路由先用
  `get_share` 校验归属，再调用；`include_failures=False` 只返回 `success`。
- `list_all_access_logs` 供管理员使用：join `ClipboardShare` + `User` 返回
  `share_title` / `owner_username`；支持 `result`、`share_id`、用户名、时间范围筛选
  （`start <= accessed_at < end`）；`failure` 等价于 `result != "success"`；
  按 `accessed_at DESC` 分页。

### 7.3 路由

`server/app/routers/share.py` 使用两个 router：

```python
router = APIRouter(prefix="/clipboard", tags=["剪贴板分享"])
public_router = APIRouter(prefix="/public/shares", tags=["公开分享"])
```

- 登录态：`POST /items/{id}/shares`、`GET /shares`、`DELETE /shares/{id}`、
  `GET /shares/{id}/access-logs`
- 公开：`GET /{token}`、`POST /{token}/access`
- 公开路由不依赖 `CurrentUser`。`access` 处理顺序：
  `get_by_token`（404）→ 分享者 `is_active`（410）→ 5.1 状态（410）→ 密码（403）
  → `resolve_content` → `consume_view`（成功记录）；每个失败分支按 5.9 写失败记录。
- `access` 成功时把 `X-Real-IP` / `request.client.host` 与 `User-Agent` 传给
  `consume_view` 写成功记录；UA 截断到 512，IP 非法时存 `NULL`。
- `access` 失败时（`password_failed` / `expired` / `revoked` / `exhausted` /
  `owner_disabled`）在返回 `403` / `410` 前调用 `record_access_log`；
  `404` 和 `429` 不写访问记录。
- 所有者访问记录接口固定 `include_failures=False`；管理端接口调用
  `list_all_access_logs`，允许查看失败记录。
- 创建时先校验原记录属于当前用户、类型为 `text`（否则 404 / 400），再进入配额检查；
  配额不足返回 `409`，不插入分享行。
- 日志只记 `user_id` / `share_id` / `item_id` / 模式 / 是否设置密码 / 结果，不记 token、正文、密码。
- 在 `app/main.py` 中 `from app.routers import ..., share`，并分别
  `include_router(share.router, prefix=settings.API_V1_PREFIX)` 与
  `include_router(share.public_router, prefix=settings.API_V1_PREFIX)`；
  同时把「剪贴板分享」「公开分享」加入 `TAGS_METADATA`。
- 管理端分享限额接口挂在 `app/routers/admin.py` 的 `/settings/shares`，
  使用现有 `AdminUser` 依赖；更新写审计 `settings.share_quota.update`。
- 管理端访问记录接口 `GET /share-access-logs` 同样使用 `AdminUser`，
  调用 `list_all_access_logs`。

### 7.4 限流

`server/app/services/rate_limit.py` 提供：

```python
def check_rate_limit(key: str, *, limit: int, window_seconds: int) -> None
```

- 内存字典 + `time.monotonic()`；超限抛 `HTTPException(429)`，带 `Retry-After`。
- 单 worker 已由启动守卫保证，进程内计数有效。
- 需要限流的键：
  - `share:meta:{ip}`：60 次/分钟
  - `share:access:{ip}`：30 次/分钟
  - `share:password:{ip}:{token}`：5 次/5 分钟；成功后清空该键
- IP 优先取 Nginx 设置的 `X-Real-IP`，缺失时取 `request.client.host`；不要直接信任客户端可伪造的 `X-Forwarded-For` 第一段。

### 7.5 日志脱敏

`server/app/core/logging_utils.py` 的 `redact_sensitive_params()` 增加：

```python
_SHARE_API_PATH = re.compile(r"(/api/v1/public/shares/)[A-Za-z0-9_-]+")
_SHARE_PAGE_PATH = re.compile(r"(/s/)[A-Za-z0-9_-]+")
```

分别替换为 `\1***`。覆盖 uvicorn 访问日志与应用日志；Nginx 侧见 9.3。

注意：上述脱敏只覆盖应用 / uvicorn 日志。Nginx `access_log` 可能包含 token，
按敏感日志管理；对公开路径关闭 `access_log` 是可选的额外防护。Nginx `error_log`
的残余风险见 9.2。

### 7.6 分享限额

- `share_settings` 单行表，`user_share_limit` 默认 50，范围 1–10000。
- 创建分享时在同一事务内：
  1. `SELECT ... FOR UPDATE` 锁定 `users` 行（或使用 advisory lock）；
  2. 读取 `share_settings.user_share_limit`；
  3. 统计该用户 `active` 分享数；
  4. 达到上限抛业务异常，路由返回 `409`。
- 限额降低不删除已有分享；只阻止新建，直到有效分享数低于限额。
- 管理端 `GET/PUT /api/v1/admin/settings/shares` 更新设置；更新写审计
  `settings.share_quota.update`，detail 只记 old/new；设置更新与审计同事务提交，
  审计失败整体回滚。

---

## 8. Web 实现清单

| 文件 | 内容 |
|------|------|
| `web/src/types/api.d.ts` | `pnpm run gen:api` 生成 |
| `web/src/api/client.ts` | `shareApi`、`publicShareApi`、类型别名 |
| `web/src/share/path.ts` | `isSharePath(pathname)` |
| `web/src/share/main.ts` | 公开页入口，挂载 `ShareView` |
| `web/src/share/ShareView.vue` | 公开查看页 |
| `web/src/components/ShareDialog.vue` | 创建分享弹窗 |
| `web/src/components/MySharesDialog.vue` | 我的分享弹窗；每行增加「访问记录」 |
| `web/src/components/ShareAccessLogsDialog.vue` | 访问记录分页弹窗 |
| `web/src/components/ClipboardItemCard.vue` | 增加「分享」按钮与事件 |
| `web/src/components/ClipboardHistory.vue` | 转发 `share` 事件；删除前查询有效分享数并提示 |
| `web/src/App.vue` | 弹窗状态、顶部「我的分享」入口 |
| `web/src/main.ts` | `/s/` 路由分发 |
| `web/src/admin/api/settings.ts` | 管理端分享限额 API |
| `web/src/admin/views/SettingsView.vue` | 分享限额设置页 |
| `web/src/admin/api/shareAccessLogs.ts` | 管理端访问记录 API |
| `web/src/admin/views/ShareAccessLogsView.vue` | 管理端访问记录页 |
| `web/src/admin/AdminApp.vue` | 增加「分享设置」「分享访问记录」导航与视图 |
| `web/src/admin/stores/adminStore.ts` | `AdminView` 增加 `settings` / `shareAccessLogs` |
| `web/tests/sharePath.test.ts` | 路径判断单测 |
| `web/tests/shares.test.ts` | 分享 API 端到端测试 |

- 弹窗复用 `ChangePasswordDialog.vue` 的 modal 结构与样式；复制链路复用 `useCopy`。
- 卡片内的「分享」按钮必须 `@click.stop`，否则会同时触发整卡载入编辑。

### 8.1 API 封装

- `shareApi` 用现有 `http`（自动带 JWT）：
  - `create(itemId, payload)`
  - `list({ page, size, status, item_id })`
  - `revoke(id)`
  - `accessLogs(id, { page, size })`
- `publicShareApi` 用**独立 axios 实例**，不挂 JWT 与 401 拦截器：
  - `meta(token)`
  - `access(token, password?)`
- 公开密码错误返回 `403`，避免误触现有 401 全局登出逻辑。

### 8.2 创建分享弹窗

字段：

- 模式：快照（默认）/ 跟随最新
- 有效期：1 小时 / 1 天 / 7 天（默认）/ 30 天
- 密码：可空，4–24 字符
- 最大查看次数：可空，1–10000

交互：

1. 提交前做本地校验；密码为空时不发送该字段。
2. 创建成功后在同一弹窗展示完整链接与「复制」按钮。
3. 提示「链接可随时在“我的分享”中再次复制；撤销后立即失效」。
4. 失败用顶部 notice 显示错误；`409` 直接展示「分享数量已达上限（N 条）」。

### 8.3 我的分享

- 顶部按钮打开，分页每页 20。
- 每行展示：标题、模式、状态、到期时间、查看次数、复制链接、访问记录、撤销。
- 状态文案：有效 / 已过期 / 次数用尽 / 已撤销。
- 撤销前 `window.confirm`，文案明确「撤销后链接立即失效」；成功后刷新列表。
- 「访问记录」打开 `ShareAccessLogsDialog`，分页每页 20，展示时间、脱敏 IP、UA；
  空状态显示「暂无访问记录」；**失败记录不会出现在这里，只有管理员能看**。
- P0 不做状态筛选 UI；接口保留 `status` 参数。

### 8.4 公开页

1. 从 `window.location.pathname` 取 `/s/` 后的 token（去掉尾部 `/`）。
2. 调 `meta(token)`：
   - 404 → 「分享不存在」
   - 410 → 「分享已失效」
   - 有密码 → 显示密码输入框
   - 无密码 → 显示「查看内容」按钮，**不自动调用 `access`**
3. 用户主动点击「查看内容」（无密码）或提交正确密码（有密码）后调 `access`：
   - 403 → 「密码错误」
   - 404 → 「分享不存在」
   - 429 → 「尝试过于频繁」
   - 410 → 「分享已失效」
4. 展示标题、正文、复制按钮、剩余查看次数（如有）；成功后隐藏「查看内容」按钮。
5. 页面加载、刷新只调 `meta`，不计数；只有第 3 步才计数。
6. 页面底部「返回云剪贴板」链接到 `/`。
7. 正文用 `<pre>` + 文本插值，不用 `v-html`。

### 8.5 路由

`web/src/main.ts`：

```ts
if (isAdminPath(window.location.pathname)) {
  void import('@/admin/main')
} else if (isSharePath(window.location.pathname)) {
  void import('@/share/main')
} else {
  void import('@/bootstrap')
}
```

`isSharePath` 覆盖 `/s` 与 `/s/...`。公开页不引入 Pinia、用户 store 或主应用 `App.vue`。

### 8.6 删除原记录确认

`ClipboardHistory.handleDelete` 当前是同步 `window.confirm`，改为：

1. 先调 `shareApi.list({ item_id: id, status: 'active', size: 1 })` 获取有效分享数。
2. `total > 0` 时确认文案：
   `该记录有 N 个有效分享，删除后这些链接将立即失效。确定删除？`
3. `total === 0` 时保留原有文案：
   `确定删除「标题」？此操作不可撤销。`
4. 查询失败按 0 处理并 `logger.debug`，不阻塞删除。
5. 用户取消则不调用 `DELETE`；确认后 `DELETE` 会级联删除分享。
6. 「清空全部」同样先查当前用户有效分享总数；`total > 0` 时提示
   `你有 N 个有效分享，清空后这些链接将立即失效。确定清空？`

### 8.7 管理端分享设置

- 导航新增「分享设置」，`AdminView` 增加 `settings`，对应 `SettingsView.vue`。
- 页面展示当前 `user_share_limit`、最近更新时间和更新人；数字输入范围 1–10000，默认 50。
- 保存后提示成功并刷新；失败用顶部 notice 显示错误。
- 只有管理员可访问；`403` 时按现有管理端未授权逻辑处理。

### 8.8 管理端访问记录

- 导航新增「分享访问记录」，`AdminView` 增加 `shareAccessLogs`，
  对应 `ShareAccessLogsView.vue`。
- 列表展示：时间、结果、分享标题、分享者、原始 IP、UA；按 `accessed_at DESC`。
- 筛选：`result=all|success|failure`、分享 ID、用户名、时间范围；分页每页 20。
- 失败记录只有该页面能查看；用户端「我的分享」只返回成功记录。
- 只有管理员可访问；普通用户 `403`。

---

## 9. 安全、日志与部署

### 9.1 限流

| 范围 | 限制 |
|------|------|
| `GET /public/shares/{token}` | 60 次/分钟/IP |
| `POST /public/shares/{token}/access` | 30 次/分钟/IP |
| 密码失败 | 5 次/5 分钟/IP+token |
| Nginx `/api/v1/public/shares/` | 60r/m，burst 20 |

- 应用层用进程内滑动窗口；多 worker 前必须先引入 Redis（与现有广播约束一致）。
- Nginx 侧作为第一层粗粒度保护。

### 9.2 日志

- 应用日志不记录 token、正文、密码。
- 应用日志只记 `user_id`、`share_id`、`item_id`、`mode`、`has_password`、`max_views`、`status`。
- `redact_sensitive_params()` 覆盖 `/api/v1/public/shares/<token>` 与 `/s/<token>`。
- Nginx `access_log` 可能包含 token，属于**可接受风险**：密码分享仅凭 token 无法读取正文，
  无密码分享本就允许持链接访问。但仍需按敏感日志管理：限制访问角色、保留周期与外送范围。
- 对 `/s/` 与 `/api/v1/public/shares/` 关闭 `access_log` 是可选的额外防护（见 9.3）。
- Nginx `error_log` 在上游 502/499 等错误时仍可能带原始 request URI（含 token），
  同样按敏感日志管理；或在日志采集侧脱敏。

### 9.3 Nginx

**限流区与 noindex 判定**（`nginx.conf` 的 `http` 块）：

```nginx
limit_req_zone $binary_remote_addr zone=share_public_limit:10m rate=60r/m;

# 只用于决定分享页的 X-Robots-Tag；$request_uri 只参与匹配，不写入日志
map $request_uri $share_robots {
    default "";
    ~^/s(/|$) "noindex, nofollow";
}
```

**server 级安全头**（`nginx.conf` 的 `server` 块；替换现有的
`Referrer-Policy strict-origin-when-cross-origin`）：

```nginx
# 建议：分享页首屏的 /assets/* 请求不要再带 Referer（Referer 里是 /s/<token>）
add_header Referrer-Policy "no-referrer" always;
# 建议：/s/ 的 noindex 在这里给，location 级 add_header 会在 try_files 内部重定向后丢失
add_header X-Robots-Tag $share_robots always;
```

**站点路由**（`locations.conf` 的 `location /` 之前）：

```nginx
location ^~ /s/ {
    # 可选：日志会外送或长期保留时再关闭；不关闭时按敏感日志管理
    access_log off;
    # 不要再写 add_header：一旦写了，就不再继承 server 级安全头
    try_files $uri /index.html;
}

location ^~ /api/v1/public/shares/ {
    # 可选：同上
    access_log off;
    limit_req zone=share_public_limit burst=20 nodelay;
    proxy_pass http://api_backend;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

- `access_log off` 是可选的额外防护：不关闭时 token 会进入 access log，但按 9.2 的口径
  属于可接受风险；若日志会外送或长期保留，建议关闭，或在采集侧脱敏。
- `/s/` 必须走 SPA fallback，否则刷新分享页会 404。
- **关键**：`try_files $uri /index.html` 会内部重定向到 `location = /index.html`；
  该 location 没有 `add_header`，会回退到 server 级配置。因此 `Referrer-Policy`
  与 `X-Robots-Tag` 建议在 server 级声明，不要写在 `/s/` 里。
- server 级 `no-referrer` 同时降低分享页首屏 `/assets/*` 和“返回云剪贴板”跳到 `/`
  的 Referer 扩散面；否则这些请求的 `Referer` 会是 `/s/<token>`，而主日志格式记录了
  `$http_referer`（见 `deploy/nginx/nginx.conf`）。
- `X-Robots-Tag` 用 `map $request_uri` 只对 `/s/` 生效；`$request_uri` 只参与匹配，
  不写入日志。
- 即使 `access_log off` 因内部重定向失效，最终 `$uri` 也会变成 `/index.html`，
  路径本身不含 token；Referer 的扩散由 server 级 `no-referrer` 处理。
- `error_log` 仍可能在上游错误时记录原始 request URI（含 token），见 9.2 的残余风险说明。
- 运行时 meta（见 5.7）只作为兜底，不能替代上述响应头。

### 9.4 配置

`server/app/core/config.py` 与 `server/.env.example` 增加：

```env
# 分享链接的站点基址；生产改为实际 HTTPS 地址
PUBLIC_BASE_URL=http://localhost:5273
```

生产当前为 `https://43.134.121.173:8443`（换域名后改为正式域名）。

---

## 10. 测试清单

### 10.1 后端 `test_shares.py` / `test_admin_share_settings.py` / `test_admin_share_access_logs.py`

- 创建快照分享：201、token/url 正确、密码存哈希、`content` 已复制
- 默认标题为 `剪贴板 · <月-日 时:分>`，不含用户名（新记录）
- 创建跟随分享：`content` 为 NULL
- 快照不随原记录编辑变化；跟随随编辑变化
- 无密码分享：meta 返回标题，access 返回正文
- 只调 meta 不计数；主动调 access 才计数
- 有密码分享：meta 的 title 为 null；缺少/错误密码 403；正确密码 200
- 有效分享达到限额：创建返回 409；撤销/过期/次数用尽后不再占额度
- `item_id` 筛选只返回该原记录的分享
- 过期：把 `expires_at` 改到过去，meta/access 返回 410
- 撤销：撤销后 410；重复撤销幂等
- 次数用尽：`max_views=1`，第一次 200、第二次 410
- 原记录删除：分享行级联删除，公开接口 404
- 分享者禁用：公开接口 410
- 跨用户：不能分享/撤销/查看他人分享，返回 404
- 列表分页与 `status` 筛选
- 公开接口带 `X-Robots-Tag`、`Cache-Control` 与 `Referrer-Policy`
- 日志脱敏：`/s/<token>` 与 `/api/v1/public/shares/<token>` 变成 `***`
- 非文字记录创建分享返回 400
- 访问记录：成功 access 新增 `success`；meta、404、429 不新增
- 失败记录：密码错误、过期、撤销、次数用尽、分享者禁用分别写入对应 `result`
- 所有者访问记录接口只返回 `success`，不返回失败记录
- 管理员接口返回成功与失败；`result=all/success/failure`、分享、用户名、时间筛选生效
- 普通用户访问管理员访问记录接口返回 403
- 访问记录分页按 `accessed_at DESC`；跨用户或分享不存在返回 404
- 删除原记录后分享与访问记录级联删除
- 管理端分享限额：普通用户 403；GET 返回默认 50；PUT 更新后新创建生效；
  审计记录 old/new；范围外返回 422

### 10.2 Web

- `sharePath.test.ts`：`/s`、`/s/abc` 为 true；`/`、`/admin`、`/sfoo` 为 false
- `shares.test.ts`（需要真实后端；使用独立测试账号，避免与其它并行套件互相干扰）：
  - 创建快照分享 → 公开读取 → 编辑原记录 → 仍读旧内容
  - 创建跟随分享 → 编辑原记录 → 读到新内容
  - 密码错误 403、正确后可读
  - 撤销后 410
  - `max_views=1` 第二次 410
  - 删除原记录后 404
  - 跨账号撤销 404
  - 打开公开页只调 meta，不计数；点击「查看内容」后计数
  - 点击「查看内容」后，我的分享「访问记录」新增一条
  - 访问记录弹窗只显示成功记录；分页、空状态、失败提示
  - 管理端分享访问记录页可筛选失败记录并分页
  - 删除有有效分享的记录：提示包含分享数量；取消不删除；确认后分享失效
  - 清空全部时如有有效分享，提示总数与链接失效
  - 管理端分享设置页可读取/保存限额
- `pnpm test`、`pnpm typecheck`、`pnpm build` 通过

### 10.3 人工验收

- 桌面：历史卡片分享 → 复制链接 → 无痕窗口打开 → 查看/复制
- 密码：设置 1234 → 无痕窗口提示输入 → 错误密码提示 → 正确密码显示正文
- 快照 / 跟随：编辑原记录后刷新分享页，行为符合选择
- 撤销：我的分享撤销后刷新分享页显示已失效
- 计数：打开无密码分享页，查看次数不变；点击「查看内容」后 +1；刷新页面不自动增加
- 访问记录：无痕窗口点击「查看内容」后，我的分享「访问记录」出现一条时间/IP/UA；
  刷新页面不自动新增
- 失败记录：无痕窗口输错密码后，用户端看不到该记录；管理端「分享访问记录」
  按 `result=failure` 能看到 `password_failed`
- 访问记录保留：确认当前为 P0 不自动清理；记录随分享删除级联消失
- 删除确认：删除有有效分享的原记录时提示分享数量；取消后记录与分享仍在；
  确认后记录删除、分享链接显示已失效
- 清空全部：有有效分享时提示总数；确认后所有记录与分享链接失效
- 分享限额：管理端把上限设为 1，用户再创建第二条返回「已达上限」；调回 50 后恢复
- 管理端「分享设置」可读取/保存限额，保存后审计日志有 old/new
- 移动端 375px：分享弹窗、我的分享、公开页可滚动、按钮可点
- 日志：`server/logs/app.log` 中无 token、正文、密码；Nginx access log 若保留 token，
  确认其访问权限、保留周期与外送范围符合预期
- Referer（隐私最佳实践）：分享页首屏之后 `/assets/*` 与“返回云剪贴板”`/` 请求的
  `$http_referer` 不含 token；分享页 HTML 从首字节带 `Referrer-Policy: no-referrer`
  与 `X-Robots-Tag: noindex, nofollow`
- 残余风险检查：无密码 + `max_views` 的分享，日志读者可能消耗查看次数；密码分享的
  弱密码仍可能被针对性尝试
- Nginx `error_log` 在上游错误时可能含 request URI；确认其访问权限与保留周期符合预期

---

## 11. 执行顺序

1. **契约**：新增 `server/app/schemas/share.py`，并在 `schemas/admin.py` 增加
   分享限额 / 管理端访问记录模型。
2. **模型与迁移**：
   ```powershell
   cd server
   $env:PYTHONUTF8='1'
   .\venv\Scripts\python.exe -m alembic revision --autogenerate -m "clipboard shares"
   .\venv\Scripts\python.exe -m alembic upgrade head
   ```
   生成后逐行检查，把 `revision` 改为 `0005_clipboard_shares`，文件名改为
   `20261112_1200_0005_clipboard_shares.py`，确认 `down_revision = "0004_user_invite_code"`；
   再生成 `0006_share_settings`，插入 `id=1, user_share_limit=50`；
   再生成 `0007_share_access_logs`。
3. **数据层**：`app/crud/share.py`、`app/crud/share_setting.py`，实现 7.2 / 7.6 的函数；
   访问记录随 `consume_view` 同事务写入。
4. **接口层**：`app/routers/share.py` 注册 `router` 与 `public_router`，
   增加 `GET /shares/{id}/access-logs`；`app/routers/admin.py` 增加分享限额 GET/PUT
   与 `GET /share-access-logs`。
5. **安全**：`app/services/rate_limit.py`、`app/core/logging_utils.py`、`PUBLIC_BASE_URL`、`.env.example`。
6. **后端测试**：`server/tests/test_shares.py`、`test_admin_share_settings.py`、
   `test_admin_share_access_logs.py`，跑 `.\venv\Scripts\python.exe -m pytest`。
7. **生成前端类型**：启动后端后执行 `cd web; pnpm run gen:api`。
8. **Web API**：`src/api/client.ts` 增加 `shareApi` / `publicShareApi`。
9. **Web UI**：
   - `ShareDialog.vue`
   - `MySharesDialog.vue`
   - `ClipboardItemCard.vue` / `ClipboardHistory.vue`（含删除确认）
   - `App.vue`
   - `share/path.ts` / `share/main.ts` / `share/ShareView.vue`
   - `ShareAccessLogsDialog.vue`
   - `main.ts` 路由
   - 管理端 `admin/api/settings.ts` / `admin/views/SettingsView.vue` /
     `admin/api/shareAccessLogs.ts` / `admin/views/ShareAccessLogsView.vue` /
     `admin/AdminApp.vue` / `admin/stores/adminStore.ts`
10. **Web 验证**：`cd web; pnpm test; pnpm typecheck; pnpm build`；隔离模式下跑 `.\scripts\run_web_tests.ps1`。
11. **文档与部署**：
    - `docs/api.md` 增加 6 个分享接口 + 3 个管理端接口（限额 2 + 访问记录 1）
    - `docs/admin.md` 同步分享设置页与接口
    - `docs/roadmap.md` 记录进度与测试数量
    - `deploy/nginx/nginx.conf` / `locations.conf`（server 级 `no-referrer` + `map` 生成 `X-Robots-Tag`）
    - 生产 `.env` 设置 `PUBLIC_BASE_URL`
12. **人工验收**：按 10.3 执行。

---

## 12. 完成标准

- 新接口出现在 `/openapi.json`，`web/src/types/api.d.ts` 已重新生成
- 后端 pytest 全绿；Web `pnpm test` / `typecheck` / `build` 全绿
- 10.3 人工验收通过
- 每用户有效分享限额默认 50，管理端可调，超限返回 409，设置更新有审计
- 页面加载/刷新不计数；只有主动查看或正确密码解锁才计数
- 成功访问写入访问记录；所有者可分页查看；记录不包含 token/正文/密码
- 失败尝试写入访问记录；只有管理员能查看失败记录
- 删除有有效分享的原记录时，确认框包含数量与链接失效提示
- 应用日志中无 token、正文、密码；Nginx access log 若保留 token，已限制访问权限、
  保留周期与外送范围
- Referer 扩散检查通过；分享页 HTML 从首字节带 `Referrer-Policy: no-referrer` 与
  `X-Robots-Tag: noindex, nofollow`
- 未新增依赖，未改动 WebSocket 协议
- `docs/api.md`、`docs/roadmap.md`、Nginx 配置与 `server/.env.example` 已同步
