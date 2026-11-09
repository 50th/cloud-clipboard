# 后台管理页 · 设计与开发步骤

> 本文是后台管理功能的**设计载体与实施步骤**。
> 进度、勾选框与实测记录写 [`roadmap.md`](roadmap.md)；接口摘要同步 [`api.md`](api.md)。
> 数据契约以 `server/app/schemas/` 为准。

**最后更新**：2026-11-08
**状态**：已实现；P1 安全项未纳入本轮，网络边界待部署时启用
**入口**：`/admin`（与用户端同一构建产物）

---

## 1. 目标与范围

管理员登录后，可以查看、搜索和管理**所有用户及其剪贴板内容**。

**本期范围**

- 概览统计：用户数、剪贴板条数、总占用、近 7 天新增（统计卡片可点击进入对应页面）
- 用户管理：列表、搜索、分页、详情、禁用/启用、重置密码、删除
- 剪贴板管理：全局列表、按用户/关键字筛选、查看完整正文、删除、按用户清空
- 邀请码管理：列表、按状态筛选、生成（**必须设置最大使用次数**）、撤销
- 操作审计：管理员登录与全部写操作同时写应用日志与 `admin_audit_logs` 表

**不在本期**

- 图片/文件管理（阶段二）
- 多级 RBAC、审批流
- 管理端移动端专项适配（桌面优先，窄屏可滚动即可）

---

## 2. 已确认决策

| 项 | 决策 |
|----|------|
| 管理能力 | 完整管理：查看/搜索、禁用/启用、重置密码、删除用户、删除/清空剪贴板 |
| 入口形态 | 同站 `/admin`，复用现有 Web 工程与构建产物 |
| 删除策略 | **禁用优先**；物理删除为独立操作，二次确认后级联删除剪贴板 |
| 审计方式 | 应用日志 + 独立 `admin_audit_logs` 表，并提供后台「操作日志」页 |
| 首次管理员 | 通过 CLI `scripts/set_admin.py` 指定，不开放页面自助注册 |
| 网络暴露 | **仅内网 / VPN / Nginx IP 白名单**，不对公网直接开放 |

---

## 3. 总体架构

```
同一 Web 构建产物
  /         → 现有用户端（App.vue）
  /admin    → 管理端（src/admin/AdminApp.vue，独立登录态）
                     │
                     ▼
          /api/v1/admin/*  ← 依赖 get_current_admin（is_admin）
                     │
        PostgreSQL + 现有进程内广播 manager
```

### 3.1 为什么同站 `/admin`

- 不新增构建、镜像与部署流程；Nginx 现有 SPA fallback 已支持 `/admin`。
- 用户端与管理端共享类型、样式变量与 API 基础配置，维护成本低。
- 管理端代码通过动态 `import()` 拆包，普通用户访问 `/` 不会加载管理端代码。

### 3.2 会话隔离

管理端 token 只写独立 `sessionStorage`，key 为 `cloud-clipboard.admin.token`（关闭标签页即失效）。
管理员令牌使用更短有效期（见 5.11），不保存密码；两端的 401 处理各自清理自己的 token，互不影响。

---

## 4. 数据模型与契约

### 4.1 `users` 新增列

| 字段 | 类型 | 默认值 | 用途 |
|------|------|--------|------|
| `is_admin` | boolean, not null | false | 管理端权限 |
| `is_active` | boolean, not null | true | 禁用后禁止登录，旧令牌立即失效 |
| `token_version` | integer, not null | 0 | 令牌版本；密码重置 / 禁用时 +1，旧 JWT 立即失效 |
| `last_login_at` | timestamptz, null | null | 活跃度与最后登录时间展示 |

### 4.2 新表 `admin_audit_logs`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID, PK | 主键 |
| `admin_id` | UUID, null, FK `users.id` `ON DELETE SET NULL` | 操作管理员；管理员被删后置空 |
| `admin_username` | varchar(32) | 冗余快照，保证事后可读 |
| `action` | varchar(32) | 动作标识，见 4.4 |
| `target_type` | varchar(16) | `user` / `clipboard` |
| `target_id` | UUID, null | 目标对象 id，不做外键（目标可能已删除） |
| `detail` | JSONB, null | 仅非敏感元数据：变更字段名、删除条数等 |
| `created_at` | timestamptz | 操作时间 |

索引：`created_at DESC`、`admin_id`、`action`。

⚠️ `detail` **绝不写入剪贴板正文、密码、完整邮箱等敏感值**。

### 4.3 Schema 变更

新增 `server/app/schemas/admin.py`：

- `AdminUserResponse`：用户公开字段 + `is_admin` / `is_active` / `last_login_at` / `item_count` / `last_item_at`
- `AdminUserList`：分页列表
- `AdminUserUpdate`：`nickname` / `email` / `is_active` / `is_admin`，全部可选
- `AdminPasswordResetRequest`：`password`，复用 6 字符与 72 字节校验
- `AdminClipboardItemResponse`：剪贴板字段 + `username`
- `AdminClipboardItemList`：分页列表
- `AdminStatsResponse`：概览统计
- `AdminAuditLogResponse` / `AdminAuditLogList`：审计记录
- `AdminUserListParams` / `AdminClipboardListParams` / `AdminAuditLogListParams`：查询参数

修改 `server/app/schemas/user.py`：`UserResponse` 增加 `is_admin`，供管理端登录后判断权限。
管理员登录的 `TokenResponse.expires_in` 使用 `ADMIN_JWT_EXPIRE_MINUTES`，不是默认 7 天。

> 契约变更后必须执行 `pnpm run gen:api` 刷新 Web 端类型。

### 4.4 审计动作

| action | target_type | 触发点 |
|--------|-------------|--------|
| `admin.login` | - | 管理员成功登录 |
| `user.update` | `user` | 修改昵称/邮箱/状态/角色 |
| `user.enable` / `user.disable` | `user` | 启用 / 禁用账号 |
| `user.promote` / `user.demote` | `user` | 设为 / 取消管理员 |
| `user.reset_password` | `user` | 重置密码 |
| `user.delete` | `user` | 物理删除用户 |
| `user.clipboards.clear` | `user` | 清空某用户剪贴板 |
| `clipboard.delete` | `clipboard` | 删除单条剪贴板 |
| `invite.create` | `invite` | 生成邀请码 |
| `invite.revoke` | `invite` | 撤销邀请码 |

---

## 5. 权限与安全

1. `get_current_user` 查到用户后检查 `is_active`；已禁用一律返回 **401**（详情“账号已被禁用”），
   这样 Web 端会按既有 401 逻辑清除令牌并退出。
2. 新增 `get_current_admin`：在 `get_current_user` 之上校验 `is_admin`，否则返回 **403**
   （详情“需要管理员权限”）。`AdminUser` 别名供管理路由使用。
3. 登录时若 `is_active=False`，返回 **403**“账号已被禁用”，不签发令牌。
4. 登录成功后更新 `last_login_at`；`is_admin=True` 同时写一条 `admin.login` 审计。
5. 管理接口**始终注册**，靠后端角色校验保护；前端 `is_admin` 判断只用于界面展示。
6. 自保护：管理员不能禁用、降权或删除**自己**，返回 400。
7. 删除/清空后向目标用户广播；广播失败只记日志，不影响接口成功。
8. **高危操作审计失败即回滚**：删除用户、重置密码、升/降管理员、清空剪贴板必须与审计在同一事务提交；
   审计写入失败则整个操作失败并返回 500。低危操作（如改昵称）可 fail-open，由应用日志兜底。
9. **WebSocket 必须覆盖禁用状态**：`ws._authenticate` 除校验令牌与用户存在外，还要校验 `is_active` 与 `token_version`。
   禁用或删除用户后调用 `manager.close_user(user_id)` 主动断开其全部连接；复用既有 **4401** 关闭码，
   客户端停止重连，下一次 HTTP 请求的 401 会清理登录态。
10. **令牌可撤销**：JWT 增加 `sv`（token_version）声明，HTTP 与 WS 都校验 `sv == user.token_version`；
    缺失 `sv` 视为 0，兼容升级前的用户令牌。密码重置与禁用账号时 `token_version += 1`。
11. **管理员令牌更短命**：新增配置 `ADMIN_JWT_EXPIRE_MINUTES`（默认 720，即 12 小时）；
    管理员登录走该有效期，`TokenResponse.expires_in` 同步返回。
12. **前端不落盘密码**：管理端 token 只写 `sessionStorage`；登录页不提供“记住密码”，
    也不复用用户端 `LoginPanel` 的明文密码存储逻辑。

---

## 6. 管理接口

统一前缀 `/api/v1/admin`，标签「后台管理」，全部依赖 `AdminUser`。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/stats` | 概览：用户数、启用用户数、管理员数、剪贴板数、总字节、近 7 天新增用户/记录 |
| GET | `/users` | 用户分页列表；`search` 匹配用户名/邮箱，`status=all/active/disabled`，`role=all/admin/user` |
| GET | `/users/{id}` | 用户详情与统计；不存在 404 |
| PATCH | `/users/{id}` | 修改昵称/邮箱/启用状态/管理员标记；邮箱冲突 409 |
| POST | `/users/{id}/reset-password` | 重置密码；成功后旧密码立即失效 |
| DELETE | `/users/{id}` | 物理删除用户并级联删除其剪贴板；不能删除自己 |
| DELETE | `/users/{id}/clipboards` | 清空该用户全部剪贴板 |
| GET | `/clipboards` | 全局列表；`user_id` / `username` / `search` / `content_type` 筛选 |
| GET | `/clipboards/{id}` | 详情，返回完整正文 |
| DELETE | `/clipboards/{id}` | 删除单条并广播 `clipboard.deleted` |
| GET | `/audit-logs` | 审计分页列表；按管理员、动作、目标、时间范围筛选 |
| GET | `/invite-codes` | 邀请码分页列表；`status=all/active/exhausted/expired/revoked` |
| POST | `/invite-codes` | 生成邀请码；`max_uses` 必填，**明文只返回一次** |
| POST | `/invite-codes/{id}/revoke` | 撤销邀请码 |

通用约定：

- 分页 `page` 从 1 开始，`size` 默认 20、最大 100。
- 列表只返回 `preview`，详情才返回完整 `content`。
- **`content_hash` 始终不对外暴露**。
- 排序默认 `created_at DESC`；用户列表可按 `last_login_at` / `item_count` 排序。
- 所有写操作写应用日志（只记 id、动作、数量）与审计表；高危操作的审计与业务在同一事务。
- 禁用/删除用户后必须关闭该用户的全部 WebSocket 连接。

---

## 7. 后端开发步骤

> 顺序遵循“契约 → 数据层 → 权限 → 接口 → 验证”。

### S1 契约先行

**文件**

- 新增 `server/app/schemas/admin.py`
- 修改 `server/app/schemas/user.py`（`UserResponse.is_admin`）

**做法**

- 按第 4.3 节定义全部模型；复用 `app/schemas/common.py` 的分页与消息响应。
- `AdminPasswordResetRequest` 复用 `schemas/user.py` 的 72 字节密码校验逻辑，避免两处规则漂移。

**验证**

```powershell
cd server
.\venv\Scripts\python.exe -c "from app.schemas.admin import AdminUserResponse; print('ok')"
```

### S2 模型与迁移

**文件**

- 修改 `server/app/db/models/user.py`：新增 4 列（含 `token_version`）
- 新增 `server/app/db/models/admin_audit_log.py`
- 修改 `server/app/db/models/__init__.py`：导入新模型，保证 metadata 注册
- 新增迁移 `server/alembic/versions/*_0003_admin_users_and_audit_logs.py`

**做法**

- 迁移只做**新增**，不改动既有列：`add_column` ×4 + `create_table(admin_audit_logs)` + 索引。
- 生成后**逐行检查**迁移，删除 autogenerate 误判的无关表。
- `downgrade` 反向：删索引、删表、删列。

**验证**

```powershell
cd server
$env:PYTHONUTF8 = '1'
.\venv\Scripts\python.exe -m alembic -x db_url=postgresql+asyncpg://clipboard:clipboard@127.0.0.1:5433/clipboard_test upgrade head
.\venv\Scripts\python.exe -m alembic -x db_url=postgresql+asyncpg://clipboard:clipboard@127.0.0.1:5433/clipboard_test downgrade -1
.\venv\Scripts\python.exe -m alembic -x db_url=postgresql+asyncpg://clipboard:clipboard@127.0.0.1:5433/clipboard_test upgrade head
```

### S3 认证与权限

**文件**

- 修改 `server/app/routers/auth.py`
- 修改 `server/app/routers/ws.py`、`server/app/services/ws_manager.py`

**做法**

- `to_user_response` 增加 `is_admin=user.is_admin`。
- `security.py`：新增读取完整 claims 的函数；签发令牌时写入 `sv=user.token_version`。
- `get_current_user`：取到用户后先判 `is_active`，再校验令牌 `sv == user.token_version`（缺失按 0）；
  不满足一律返回 401。
- 新增 `get_current_admin(current_user: CurrentUser)` 与 `AdminUser = Annotated[User, Depends(get_current_admin)]`。
- `login`：禁用账号返回 403；成功后写 `last_login_at` 并提交；管理员登录写 `admin.login` 审计。
- 管理员登录时用 `ADMIN_JWT_EXPIRE_MINUTES` 签发更短令牌。
- `ws._authenticate`：增加 `is_active` 与 `token_version` 校验；失败返回既有 4401。
- `ConnectionManager` 新增 `close_user(user_id)`：关闭并移除该用户全部连接，异常只记日志。

**验证**

- 普通用户请求任意 `/api/v1/admin/*` 得 403；无令牌得 401。
- 禁用账号：登录 403；已签发令牌访问任意受保护接口 401；已连接的 WS 被服务端关闭且重连失败。
- 管理员登录返回的 `expires_in` 为 `ADMIN_JWT_EXPIRE_MINUTES`，不是 7 天。

### S4 审计写入

**文件**

- 新增 `server/app/crud/audit.py`

**做法**

- 定义动作常量（第 4.4 节），避免字符串散落。
- 提供两个入口：
  - `build_audit_entry(admin, action, ...)`：只构造并 `session.add`，不 commit，交给高危操作的事务统一提交。
  - `record_admin_action(...)`：用于低危操作，自行 commit；失败只记 `logger.exception`，不阻断。
- 高危操作（删除用户、重置密码、升/降管理员、清空剪贴板）必须使用前者，
  与业务修改在同一个 `session.commit()` 中提交；审计写入失败时抛出异常并回滚业务。
- `detail` 只接受可 JSON 序列化的非敏感字典。

**验证**

- 单元测试：写入后能按 `admin_id` / `action` 查到。
- 模拟审计写入失败：高危操作必须回滚并返回 500；低危操作仍成功且有应用日志。

### S5 管理数据访问层

**文件**

- 新增 `server/app/crud/admin.py`

**函数清单**

- `list_users(...) -> (rows, total)`：用户名/邮箱 `ilike` 搜索、状态筛选、排序、分页；
  `item_count` 与 `last_item_at` 用相关子查询，避免逐行 count。
- `get_user(...)`：返回用户与统计；不存在返回 `None`。
- `update_user(...)`：只改显式字段；邮箱冲突返回明确错误。
- `delete_user(...)`：删除并返回被级联删除的剪贴板条数（先 count 再 delete）。
- `list_clipboards(...) -> (rows, total)`：join `User` 取 `username`，按用户/用户名/关键字筛选。
- `get_clipboard(...)`：管理员视角，不限用户。
- `delete_clipboard(...)`：删除任意用户单条，返回被删记录或 `None`。
- `clear_user_clipboards(...)`：返回删除条数。
- `get_stats(...)`：聚合查询，一次返回第 6 节统计项。
- `list_audit_logs(...)`：筛选与分页。

**约定**

- 路由层不写 SQL，全部逻辑留在此文件。
- 所有查询必须带分页上限，禁止全表返回。
- 高危写函数（删除用户、重置密码、角色/状态变更、清空剪贴板）必须接受审计参数，
  在同一事务内完成业务修改 + 审计写入；不能先 commit 再由路由补审计。

### S6 管理路由与注册

**文件**

- 新增 `server/app/routers/admin.py`
- 修改 `server/app/main.py`：`application.include_router(admin.router, prefix=settings.API_V1_PREFIX)`

**做法**

- 高危写接口：在 `crud/admin.py` 内完成“业务修改 + 审计”后单次 commit；失败整体回滚。
- `PATCH` 分支判断：禁用/启用、升权/降权分别记录不同 action；自操作返回 400。
- 禁用账号时 `token_version += 1`，成功后调用 `manager.close_user(user_id)`。
- `DELETE /users/{id}`：先取用户与条数，再删；成功后调用 `manager.close_user(user_id)`
  并向该用户广播 `clipboard.cleared`。
- `DELETE /clipboards/{id}`：删除后广播 `clipboard.deleted`。
- 重置密码时 `token_version += 1`，使旧令牌立即失效。
- 审计 `detail` 示例：`{"deleted_items": 12}`、`{"fields": ["is_active"]}`。
- 应用日志统一 `logger.warning("admin action: ...")`，不记正文。

**验证**

- `/openapi.json` 出现全部管理路径与模型。
- 用 Swagger 依次验证：列表、详情、禁用、重置密码、删除、审计查询。

---

## 8. 前端开发步骤

### S7 入口拆分

**文件**

- 修改 `web/src/main.ts`：只做路径分发
- 新增 `web/src/bootstrap.ts`：承载现有用户端启动逻辑（Pinia、401 处理器、挂载 `App.vue`）
- 新增 `web/src/admin/main.ts`、`web/src/admin/AdminApp.vue`
- 新增 `web/src/admin/path.ts`：`isAdminPath(pathname)` 纯函数

**做法**

```ts
// main.ts
const admin = isAdminPath(window.location.pathname)
void (admin ? import('@/admin/main') : import('@/bootstrap'))
```

- `bootstrap.ts` 保留现有 `setUnauthorizedHandler` 与 `App.vue` 挂载。
- `admin/main.ts` 创建独立 Pinia、挂载 `AdminApp.vue`、设置 `document.title = '后台管理'`。
- 不引入 vue-router；管理端用 store 内的 `activeView` 切换页面。

**验证**

- `pnpm dev`：`/` 与 `/admin` 都能正常加载；`/` 不加载管理端 chunk。

### S8 管理端 API 与登录态

**文件**

- 新增 `web/src/admin/api/client.ts`
- 新增 `web/src/admin/stores/adminStore.ts`
- 新增 `web/src/admin/api/{users,clipboards,stats,audit}.ts`

**做法**

- 独立 axios 实例，token 只写 `sessionStorage`，key 为 `cloud-clipboard.admin.token`。
- 管理端登录页**不提供“记住密码”**，不读写任何密码到 `localStorage` / `sessionStorage`。
- 401 只清管理端 token，并通知 `adminStore` 回到登录页。
- 登录复用 `POST /auth/login`，成功后校验 `user.is_admin`：
  - 非管理员：不保存 token，提示“该账号没有管理权限”
  - 管理员：保存 token，进入概览页
- 首屏 `restoreSession()`：本地有 token 时调 `/auth/me`，校验后恢复。
- 所有类型从 `#src/types/api.ts` 导入，禁止手写重复类型。

**验证**

- 普通账号在 `/admin` 登录被拒；管理员可进入。
- 管理端登出不影响用户端登录态。

### S9 管理端页面

**文件**

- 新增 `web/src/admin/views/{Login,Dashboard,Users,UserDetail,Clipboards,AuditLogs}.vue`
- 新增 `web/src/admin/components/{Pagination,ConfirmDialog}.vue`
- 新增 `web/src/admin/admin.css`

**页面要求**

| 页面 | 内容 |
|------|------|
| 登录 | 用户名/密码、错误提示、非管理员提示；**不提供“记住密码”** |
| 概览 | 可点击的统计卡片（跳转到用户或剪贴板管理）、刷新按钮 |
| 用户管理 | 搜索、状态与角色筛选、分页表格；操作：详情、禁用/启用、删除 |
| 用户详情 | 资料卡、启用/禁用、重置密码、清空剪贴板、删除用户、该用户剪贴板列表 |
| 剪贴板管理 | 关键字、所属用户、类型筛选、分页；查看全文以模态对话框展示、删除 |
| 邀请码 | 状态筛选、分页列表；生成（备注 / 最大使用次数 / 有效期）后一次性展示明文，可复制；撤销 |
| 操作日志 | 管理员、动作、时间范围筛选、分页 |

**交互与样式**

- 交互：所有筛选控件保持同一行（窄屏横向滚动）；剪贴板正文用模态对话框查看。
- 删除/禁用/清空必须二次确认，文案明确后果。
- 管理端不得复用用户端 `LoginPanel` 的“记住密码”逻辑（该逻辑会把明文密码写入 localStorage）。
- 正文用 `<pre class="clipboard-content">{{ item.content }}</pre>`，**禁止 `v-html`**；
  `white-space: pre-wrap; word-break: break-all; max-height` 防止撑破布局。
- 复用 `styles.css` 的 CSS 变量与按钮风格，管理端差异化样式只放 `admin.css`。
- 桌面优先；窄屏表格横向滚动，不做移动端专项重构。

**验证**

```powershell
cd web
pnpm typecheck
pnpm build
```

### S10 前端测试

**文件**

- 新增 `web/tests/admin.test.ts`

**覆盖**

- `isAdminPath`：`/admin`、`/admin/`、`/admin/users` 为真；`/`、`/administrator` 为假。
- 管理端 token 与管理端错误映射的纯逻辑。
- 管理员完整流程建议用隔离库做一次手工 e2e：设置管理员 → 登录 → 禁用 → 删除。

---

## 9. 后端测试计划

新增 `server/tests/test_admin_api.py`，夹具增加管理员账号与普通账号。

| 用例 | 断言 |
|------|------|
| 无令牌访问管理接口 | 401 |
| 普通用户访问管理接口 | 403 |
| 禁用用户后登录 / 旧令牌访问 | 403 / 401 |
| 禁用后 WebSocket | 已连接被关闭；用旧 token 重连被 4401 拒绝 |
| 重置密码后旧令牌 | 401；新登录令牌可用 |
| 管理员登录有效期 | `expires_in` 等于 `ADMIN_JWT_EXPIRE_MINUTES` |
| 高危操作审计失败 | 业务回滚，返回 500 |
| 用户列表搜索、状态筛选、分页、item_count | 结果正确 |
| 用户详情不存在 | 404 |
| 修改自己是禁用/降权 | 400 |
| 禁用他人 | 成功，审计表有 `user.disable`，目标登录被拒 |
| 重置密码 | 旧密码失败、新密码成功、审计有记录 |
| 删除用户 | 用户与其剪贴板消失、审计有 `user.delete` |
| 删除单条剪贴板 | 记录消失、目标用户收到广播、审计有记录 |
| 清空用户剪贴板 | 返回条数正确、审计有记录 |
| 剪贴板列表筛选 | 按用户/用户名/关键字结果正确 |
| 剪贴板详情 | 返回正文，且**不含 `content_hash`** |
| 概览统计 | 数字与构造数据一致 |
| 审计列表筛选 | 按 action / admin / 时间范围正确 |

运行：

```powershell
cd server
$env:PYTHONUTF8 = '1'
.\venv\Scripts\python.exe -m pytest
```

---

## 10. 部署与回滚

### 10.1 发布顺序

1. 后端契约与迁移先行；迁移只新增列与表，旧镜像仍可运行。
2. 本地验证通过后出包并部署（部署脚本已包含备份与 `alembic upgrade head`）：

```powershell
.\scripts\build_release.ps1 -ApiBaseUrl "https://43.134.121.173:8443" -Tag "<new-tag>"
.\scripts\deploy_release.ps1 -Tag "<new-tag>"
```

3. 首次部署后设置管理员：

```powershell
ssh ubuntu@43.134.121.173
cd /opt/cloud-clipboard
docker compose -f deploy/docker-compose.prod.yml run --rm api \
  python -m scripts.set_admin --username <用户名>
```

4. 访问 `https://<host>:8443/admin`，用管理员账号登录并完成一次查看/禁用/删除验证。

### 10.2 回滚

- 应用回滚：`deploy/.env` 的 `IMAGE_TAG` 改回上一版本并重启容器。
- 迁移**不需要**回滚：新增列与审计表对旧版本代码无影响。
- 仅当确认要撤销功能时才执行 `alembic downgrade -1`；会删除管理员标记与审计记录。

### 10.3 网络边界（必须）

后台管理端**只允许内网 / VPN / Nginx IP 白名单访问**，不对公网直接开放：

- 对 `/admin` 页面与 `/api/v1/admin/` 接口**同时**启用限制；只限制页面没有意义。
- IP 白名单方式：在 `deploy/nginx/locations.conf` 中为两者加 `allow <固定IP>; deny all;`，
  且必须放在通用 `location /api/` 与 `location /` 之前。
- VPN 方式：只让管理端监听 VPN 网段，或在云安全组限制来源。
- 启用前先确认自己的出口 IP 已加入白名单，并保留服务器 SSH 通道，避免把自己锁在门外。
- 上线验收必须从非白名单网络访问一次，确认返回 403/404。

同时在 `server/.env` 中设置管理员令牌有效期：

```ini
ADMIN_JWT_EXPIRE_MINUTES=720
```

---

## 11. 验收清单

- [ ] 普通用户无法登录 `/admin`，直接调管理接口返回 403
- [ ] 管理员可登录，概览数字与数据库一致
- [ ] 用户列表支持搜索、状态筛选、分页
- [ ] 禁用用户后立即无法登录，旧令牌失效
- [ ] 禁用后该用户已连接的 WebSocket 立即断开，且无法用旧 token 重连
- [ ] 启用后可恢复登录
- [ ] 重置密码后旧密码失效、新密码可用，旧令牌返回 401
- [ ] 管理端 token 只存在 sessionStorage，关闭标签页后需重新登录；登录页无“记住密码”
- [ ] 删除/重置密码/角色变更时，模拟审计写入失败会使操作整体回滚
- [ ] 非白名单网络无法访问 `/admin` 与 `/api/v1/admin/`
- [ ] 删除用户后其剪贴板级联删除，且无法删除自己
- [ ] 全局剪贴板可搜索、查看全文、删除，删除后用户端实时收到事件
- [ ] 审计表与应用日志均有对应记录，且不含正文/密码
- [ ] 用户端 `/` 功能与实时同步无回归
- [ ] `pytest`、`pnpm typecheck`、`pnpm build`、Web 测试全部通过

---

## 12. 文档同步

| 文档 | 需要补充 |
|------|----------|
| [`api.md`](api.md) | 管理接口摘要、认证与 403 约定 |
| [`ws-protocol.md`](ws-protocol.md) | 禁用/删除后服务端以 4401 关闭连接的行为说明 |
| [`roadmap.md`](roadmap.md) | 开发进度、踩坑、验收记录 |
| [`AGENTS.md`](../AGENTS.md) | 文档地图增加 `docs/admin.md` |
| [`server/README.md`](../server/README.md) | 常用命令增加 `scripts.set_admin` |
| `server/.env.example` | 增加 `ADMIN_JWT_EXPIRE_MINUTES` |
| 本文 | 实施过程中的设计变更同步到这里 |

---

## 13. 实现记录

**后端**

- 契约：`server/app/schemas/admin.py`；`UserResponse` 增加 `is_admin`
- 数据：`users` 增加 `is_admin` / `is_active` / `token_version` / `last_login_at`；
  新增 `admin_audit_logs` 与迁移 `0003`
- 权限：`get_current_admin`；HTTP 与 WebSocket 都校验 `is_active` 与 `token_version`
- 管理接口：`server/app/routers/admin.py`、`server/app/crud/admin.py`、`server/app/crud/audit.py`
- 会话终止：`ConnectionManager.close_user`，禁用/删除/重置密码后关闭该用户全部连接
- CLI：`server/scripts/set_admin.py`

**前端**

- 入口：`web/src/main.ts` 按路径分发；用户端启动逻辑移到 `web/src/bootstrap.ts`
- 管理端：`web/src/admin/`（独立 Pinia、`sessionStorage` 令牌、六个视图）
- 剪贴板正文统一用 `<pre>` 文本插值，未引入 `v-html`

**验证（2026-11-08）**

- 后端 `pytest`：**247 项通过**
- Web 测试：**62 项通过**
- `pnpm typecheck`、`pnpm build` 通过
- 浏览器手工验证：登录、概览、用户列表、用户详情、剪贴板列表、操作日志、邀请码生成与撤销均正常，控制台无报错

**界面调整（2026-11-09）**

- 概览统计卡片可点击，跳转到用户管理或剪贴板管理；移除“剪贴板最多的用户”
  （后端 `top_users` 一并删除）
- 用户列表新增角色筛选（`role=all/admin/user`）
- 所有管理页筛选控件强制同一行，窄屏横向滚动
- 剪贴板详情改用模态对话框
- 操作日志的时间选择框与下拉、按钮统一高度并基线对齐
- 筛选条搜索框改为可收缩并设置上限，各管理页不再出现过宽与横向滚动条
- 剪贴板详情模态框补全标题、所属用户、类型、大小、创建/更新时间、记录 ID
- 分页新增「每页条数」选择（10 / 20 / 50 / 100），默认 **10 条**
- 新增「邀请码」页：按状态筛选、生成（最大使用次数必填）、一次性明文展示与复制、撤销；
  后端新增 `GET/POST /admin/invite-codes` 与撤销接口，审计动作 `invite.create` / `invite.revoke`

**本轮未做（P1，保留为后续技术债）**

- CSP / `Cache-Control: no-store`
- 最后一名管理员保护、管理员间提权/重置密码限制
- 明文查看审计、422 密码回显脱敏、管理 API 限流
- 生产 Nginx IP 白名单 / VPN 的实际配置（部署时按 §10.3 执行）
