# 后台管理页 · 设计与实现

> 本文是后台管理的**设计载体**：范围、决策、数据契约、接口与安全约束。
> 进度与验证记录写 [`roadmap.md`](roadmap.md)；接口摘要同步 [`api.md`](api.md)；
> 数据契约以 `server/app/schemas/` 为准。

**最后更新**：2026-11-10
**状态**：已实现并通过本地验证；待部署，P1 安全项未纳入本轮
**入口**：`/admin`（与用户端同一构建产物）

---

## 1. 目标与范围

管理员登录后可查看、搜索和管理**所有用户及其剪贴板内容**。

- 概览统计：用户、剪贴板、总占用、近 7 天新增、邀请码总数/可用数/使用次数
  （统计卡片可点击进入对应页面）
- 用户管理：列表、搜索、分页、详情、禁用/启用、重置密码、删除
- 剪贴板管理：全局列表、按用户/关键字筛选、查看完整正文、删除、按用户清空
- 邀请码管理：列表、按状态筛选、生成（**必须设置最大使用次数**）、使用详情、撤销
- 操作审计：管理员登录与全部写操作同时写应用日志与 `admin_audit_logs` 表

**不在本期**：图片/文件管理、多级 RBAC、审批流、管理端移动端专项适配。

---

## 2. 已确认决策

| 项 | 决策 |
|----|------|
| 管理能力 | 查看/搜索、禁用/启用、重置密码、删除用户、删除/清空剪贴板、邀请码生成/撤销 |
| 入口形态 | 同站 `/admin`，复用现有 Web 工程与构建产物 |
| 删除策略 | **禁用优先**；物理删除为独立操作，二次确认后级联删除剪贴板 |
| 审计方式 | 应用日志 + 独立 `admin_audit_logs` 表，并提供后台「操作日志」页 |
| 首次管理员 | 通过 CLI `scripts/set_admin.py` 指定，不开放页面自助注册 |
| 网络暴露 | **仅内网 / VPN / Nginx IP 白名单**，不对公网直接开放 |

---

## 3. 总体架构

```
同一 Web 构建产物
  /         → 用户端（bootstrap.ts + App.vue）
  /admin    → 管理端（admin/main.ts + AdminApp.vue，独立登录态）
                     │
                     ▼
          /api/v1/admin/*  ← 依赖 get_current_admin（is_admin）
                     │
        PostgreSQL + 现有进程内广播 manager
```

- 不新增构建与镜像；Nginx 现有 SPA fallback 已支持 `/admin`。
- 管理端代码通过动态 `import()` 拆包，普通用户访问 `/` 不会加载管理端代码。
- 管理端 token 只写 `sessionStorage`（`cloud-clipboard.admin.token`），关闭标签页即失效；
  两端 401 各自清理自己的 token，互不影响。

---

## 4. 数据与契约

### 4.1 `users` 新增列

| 字段 | 类型 | 默认值 | 用途 |
|------|------|--------|------|
| `is_admin` | boolean, not null | false | 管理端权限 |
| `is_active` | boolean, not null | true | 禁用后禁止登录，旧令牌立即失效 |
| `token_version` | integer, not null | 0 | 令牌版本；密码重置 / 禁用时 +1 |
| `last_login_at` | timestamptz, null | null | 最后登录时间 |
| `invite_code_id` | UUID, null, FK `invite_codes.id` `ON DELETE SET NULL` | null | 注册时使用的邀请码 |

### 4.2 新表 `admin_audit_logs`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID, PK | 主键 |
| `admin_id` | UUID, null, FK `users.id` `ON DELETE SET NULL` | 管理员被删后置空 |
| `admin_username` | varchar(32) | 冗余快照，保证事后可读 |
| `action` | varchar(32) | 动作标识，见 4.4 |
| `target_type` | varchar(16) | `user` / `clipboard` / `invite` |
| `target_id` | UUID, null | 目标 id，不做外键（目标可能已删除） |
| `detail` | JSONB, null | 仅非敏感元数据（变更字段、删除条数） |
| `created_at` | timestamptz | 操作时间 |

索引：`created_at`、`admin_id`、`action`。
⚠️ `detail` **绝不写入剪贴板正文、密码、完整邮箱等敏感值**。

### 4.3 Schema

`server/app/schemas/admin.py`：

- `AdminUserResponse` / `AdminUserList` / `AdminUserUpdate` / `AdminPasswordResetRequest`
- `AdminClipboardItemResponse` / `AdminClipboardItemList`
- `AdminStatsResponse`：用户、剪贴板与邀请码统计
- `AdminInviteCodeResponse` / `AdminInviteCodeCreated` / `AdminInviteCodeList`
- `AdminInviteCodeUsage` / `AdminInviteCodeUsageList`
- `AdminAuditLogResponse` / `AdminAuditLogList`
- 各列表查询参数类（分页、筛选、排序）

`UserResponse` 增加 `is_admin`，仅用于前端展示。契约变更后执行 `pnpm run gen:api`。

### 4.4 审计动作

| action | target_type | 触发点 |
|--------|-------------|--------|
| `admin.login` | - | 管理员成功登录 |
| `user.update` | `user` | 修改昵称/邮箱 |
| `user.enable` / `user.disable` | `user` | 启用 / 禁用账号 |
| `user.promote` / `user.demote` | `user` | 设为 / 取消管理员 |
| `user.reset_password` | `user` | 重置密码 |
| `user.delete` | `user` | 物理删除用户 |
| `user.clipboards.clear` | `user` | 清空某用户剪贴板 |
| `clipboard.delete` | `clipboard` | 删除单条剪贴板 |
| `invite.create` / `invite.revoke` | `invite` | 生成 / 撤销邀请码 |

---

## 5. 权限与安全

1. `get_current_user` 校验 `is_active` 与令牌 `sv`（token_version，缺失按 0）；不满足返回 **401**。
   这样 Web 端按既有 401 逻辑清除令牌并退出。
2. `get_current_admin` 在普通认证之上校验 `is_admin`，否则 **403**；**权限每次请求都查库**，
   取消管理员后立即生效。
3. 登录时 `is_active=False` 返回 **403**；管理员登录写 `admin.login` 审计并使用更短令牌
   （`ADMIN_JWT_EXPIRE_MINUTES`，默认 12 小时）。
4. 管理接口始终注册，靠后端角色校验保护；前端 `is_admin` 只用于界面展示。
5. 自保护：管理员不能禁用、降权或删除**自己**（400）。
6. **高危操作审计失败即回滚**：删除用户、重置密码、升/降管理员、清空剪贴板、
   邀请码生成/撤销，必须与审计在同一事务提交；失败整体回滚并返回 500。
   低危操作（如改昵称、管理员登录）可 fail-open，由应用日志兜底。
7. **WebSocket 覆盖禁用状态**：`ws._authenticate` 校验 `is_active` 与 `token_version`；
   禁用/删除/重置密码后调用 `manager.close_user(user_id)` 关闭其全部连接（关闭码 4401）。
8. 删除/清空后向目标用户广播；广播失败只记日志，不影响接口成功。
9. 管理端不保存密码、不复用用户端「记住密码」逻辑；token 只存 `sessionStorage`。
10. 邀请码明文只返回一次；列表只返回 `code_hint`（前 8 位）。
11. 邀请码状态优先级：**撤销 > 过期 > 用尽 > 可用**；用尽后注册返回 403。

---

## 6. 管理接口

统一前缀 `/api/v1/admin`，标签「后台管理」，全部依赖 `AdminUser`。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/stats` | 概览：用户 / 剪贴板 / 邀请码统计 |
| GET | `/users` | 分页；`search`、`status=all/active/disabled`、`role=all/admin/user` |
| GET | `/users/{id}` | 用户详情与统计；不存在 404 |
| PATCH | `/users/{id}` | 修改昵称/邮箱/启用状态/管理员标记；邮箱冲突 409 |
| POST | `/users/{id}/reset-password` | 重置密码；旧令牌立即失效 |
| DELETE | `/users/{id}` | 物理删除用户并级联删除剪贴板；不能删除自己 |
| DELETE | `/users/{id}/clipboards` | 清空该用户剪贴板 |
| GET | `/clipboards` | 全局列表；`user_id` / `username` / `search` / `content_type` |
| GET | `/clipboards/{id}` | 详情，返回完整正文 |
| DELETE | `/clipboards/{id}` | 删除单条并广播 `clipboard.deleted` |
| GET | `/audit-logs` | 审计分页；按管理员、动作、目标、时间范围筛选 |
| GET | `/invite-codes` | 邀请码分页；`status=all/active/exhausted/expired/revoked` |
| POST | `/invite-codes` | 生成；`max_uses` 必填，明文只返回一次 |
| POST | `/invite-codes/{id}/revoke` | 撤销邀请码 |
| GET | `/invite-codes/{id}/usages` | 使用详情：通过该码注册的用户，分页 |

通用约定：

- 分页 `page` 从 1 开始，`size` 最大 100；后台页面默认每页 **10** 条（可选 10/20/50/100）。
- 列表只返回 `preview`，详情才返回完整 `content`；**`content_hash` 始终不对外暴露**。
- 排序默认 `created_at DESC`；用户列表可按 `last_login_at` / `item_count` 排序。
- 所有写操作写应用日志（只记 id、动作、数量）与审计表。

---

## 7. 实现结构

**后端**

- 契约：`server/app/schemas/admin.py`；`UserResponse.is_admin`
- 数据：`users` 新增 5 列；`admin_audit_logs`；迁移 `0003`（管理列 + 审计）、
  `0004`（`users.invite_code_id`）
- 权限：`get_current_admin`；HTTP 与 WebSocket 校验 `is_active` / `token_version`
- 接口：`app/routers/admin.py`、`app/crud/admin.py`、`app/crud/audit.py`
- 会话终止：`ConnectionManager.close_user`
- CLI：`scripts/set_admin.py`；邀请码 CLI 保留为兜底

**前端**

- 入口：`web/src/main.ts` 按路径分发；用户端启动逻辑在 `web/src/bootstrap.ts`
- 管理端：`web/src/admin/`（独立 Pinia、`sessionStorage` 令牌、六个视图）
- 剪贴板正文统一用 `<pre>` 文本插值，未引入 `v-html`；模态框默认不显示右上角关闭按钮

**测试与验证**

- 后端：`server/tests/test_admin_api.py`；Web：`web/tests/admin.test.ts`
- 当前测试数量与最近验证结果见 [`roadmap.md`](roadmap.md) 的「测试现状」与「后台管理页」。

---

## 8. 部署与回滚

### 8.1 发布顺序

1. 后端契约与迁移先行；迁移只新增列与表，旧镜像仍可运行。
2. 本地验证通过后出包并部署（脚本已包含备份与 `alembic upgrade head`）：

```powershell
.\scripts\build_release.ps1 -ApiBaseUrl "https://<服务器IP>:8443" -Tag "<new-tag>"
.\scripts\deploy_release.ps1 -Tag "<new-tag>"
```

3. 首次部署后设置管理员：

```powershell
ssh ubuntu@43.134.121.173
cd /opt/cloud-clipboard
docker compose -f deploy/docker-compose.prod.yml run --rm api \
  python -m scripts.set_admin --username <用户名>
```

4. 访问 `https://<host>:8443/admin`，用管理员账号完成一次查看/禁用/删除验证。

### 8.2 回滚

- 应用回滚：`deploy/.env` 的 `IMAGE_TAG` 改回上一版本并重启容器。
- 迁移不需要回滚：新增列与表对旧版本代码无影响（`upgrade head` 会依次应用 `0003`、`0004`）。
- `alembic downgrade -1` 只撤销 `0004`；回退到 `0002` 才会删除管理员标记、审计表与邀请码关联。

### 8.3 网络边界（必须）

后台管理端**只允许内网 / VPN / Nginx IP 白名单访问**，不对公网直接开放：

- 对 `/admin` 页面与 `/api/v1/admin/` 接口**同时**限制；只限制页面没有意义。
- IP 白名单：在 `deploy/nginx/locations.conf` 为两者加 `allow <固定IP>; deny all;`，
  且必须放在通用 `location /api/` 与 `location /` 之前。
- VPN：只让管理端监听 VPN 网段，或在云安全组限制来源。
- 启用前确认自己的出口 IP 已加入白名单，并保留 SSH 通道，避免把自己锁在门外。
- 上线验收必须从非白名单网络访问一次，确认返回 403/404。

同时在 `server/.env` 中设置管理员令牌有效期：

```ini
ADMIN_JWT_EXPIRE_MINUTES=720
```

---

## 9. 验收清单

- [ ] 普通用户无法登录 `/admin`，直接调管理接口返回 403
- [ ] 管理员可登录，概览数字与数据库一致
- [ ] 用户列表支持搜索、状态与角色筛选、分页
- [ ] 禁用用户后立即无法登录，旧令牌失效
- [ ] 禁用后该用户已连接的 WebSocket 立即断开，且无法用旧 token 重连
- [ ] 启用后可恢复登录
- [ ] 重置密码后旧密码失效、新密码可用，旧令牌返回 401
- [ ] 管理端 token 只存在 sessionStorage；登录页无「记住密码」
- [ ] 删除/重置密码/角色变更时，审计写入失败会使操作整体回滚
- [ ] 非白名单网络无法访问 `/admin` 与 `/api/v1/admin/`
- [ ] 删除用户后其剪贴板级联删除，且无法删除自己
- [ ] 全局剪贴板可搜索、查看全文、删除，删除后用户端实时收到事件
- [ ] 邀请码明文只显示一次；达到最大使用次数后无法继续注册
- [ ] 邀请码「使用详情」列出通过该码注册的用户
- [ ] 审计表与应用日志均有对应记录，且不含正文/密码
- [ ] 用户端 `/` 功能与实时同步无回归
- [ ] `pytest`、`pnpm typecheck`、`pnpm build`、Web 测试全部通过

---

## 10. 文档同步

| 文档 | 内容 |
|------|------|
| [`api.md`](api.md) | 管理接口摘要、认证与 403 约定 |
| [`ws-protocol.md`](ws-protocol.md) | 禁用/删除后以 4401 关闭连接的行为 |
| [`roadmap.md`](roadmap.md) | 进度、踩坑、验收记录、测试数量 |
| [`AGENTS.md`](../AGENTS.md) | 文档地图与安全约束 |
| [`server/README.md`](../server/README.md) | 迁移、数据表、`scripts.set_admin` |
| `server/.env.example` | `ADMIN_JWT_EXPIRE_MINUTES` |
