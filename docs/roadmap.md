# 项目路线图与进度

> **本文件记录动态进度。** AGENT.md 只保存稳定约定（技术栈、契约、规范、开发顺序），
> 凡是"每完成一步就要改一遍"的内容都放这里。

**最后更新**：2026-10-03
**当前进度**：第 1、2 步已完成 → **下一步：第 3 步（接入 PostgreSQL）**

---

## 阶段划分（AGENT.md 第 1 节）

| 阶段 | 内容 | 状态 |
|------|------|------|
| 阶段一 | 文字剪贴板 MVP：上传/查询/删除 + 实时同步 + JWT + 去重 | 🚧 进行中 |
| 阶段二 | 图片剪贴板 + 对象存储 | 📋 计划中 |
| 阶段三 | 文件剪贴板 + 体验优化 | 📋 计划中 |
| 阶段四 | 端到端加密 + 生产部署 | 📋 计划中 |

---

## 开发步骤进度（AGENT.md 第 10 节）

### ✅ 第 1 步：FastAPI 骨架 + 数据契约（已完成）

- [x] `server/` 目录结构与虚拟环境
- [x] `fastapi 0.142.2`、`uvicorn[standard] 0.54.0`、`pydantic-settings 2.15.0`
- [x] Pydantic Schema：`app/schemas/`（common / user / clipboard）
- [x] 假数据路由：`app/routers/`（auth / clipboard）+ `app/crud/`（内存存储 + 4 条种子数据）
- [x] 入口 `app/main.py`：注册路由、CORS、OpenAPI 元信息、`/health`
- [x] `/docs`、`/redoc`、`/openapi.json` 均可用

**验收记录**：创建 / 列表（分页·筛选·搜索·排序）/ 详情 / 删除 / 清空 / 404 / 422 全部实测通过。

### ✅ 第 2 步：Web 端骨架 + 单端闭环（已完成）

- [x] Vite 5.4.21 + React 18.3.1 + TypeScript 5.9.3，端口固定 5173
- [x] 从 OpenAPI 生成类型：`pnpm run gen:api` → `web/src/types/api.d.ts`
- [x] axios 客户端封装：`web/src/api/client.ts`
- [x] 剪贴板读写工具：`web/src/utils/clipboard.ts`
- [x] 列表页 + 同步按钮 + 两栏布局（左历史 / 右输入）
- [x] 标题字段（留空服务端自动生成）、加高输入区、清空输入、防抖自动保存
- [x] 端到端测试：`pnpm test`（11 用例，驱动真实后端）

**验收记录**：`pnpm run typecheck` 0 错误；`pnpm run build` 110 模块 / gzip 72 KB；`pnpm test` 11/11 通过。
**待人工确认**：浏览器侧「读取剪贴板 → 上传 → 列表展示 → 点击复制」（剪贴板 API 依赖用户手势，无法自动化）。

### ⬜ 第 3 步：接入数据库（下一步）

- [ ] `docker-compose.yml`（PostgreSQL + Redis）或复用本机 PostgreSQL 18
- [ ] 安装 `sqlalchemy[asyncio]`、`asyncpg`、`alembic`
- [ ] `db/session.py`、`db/base.py`
- [ ] SQLAlchemy 模型（`user.py`、`clipboard.py`）
- [ ] Alembic 初始化 + 生成并执行迁移
- [ ] 实现 `crud/` 层
- [ ] 替换路由中的假数据为真实 CRUD
- [ ] 验证重启后数据不丢失

**完成标准**：数据持久化，`/docs` 接口全部正常。

### ⬜ 第 4 步：JWT 认证

- [ ] `core/security.py`：密码哈希、JWT 签发/校验
- [ ] 真实的注册、登录接口
- [ ] 认证依赖 `get_current_user`
- [ ] 剪贴板路由加认证保护
- [ ] Web 端登录页，token 存 localStorage

**完成标准**：未带 token 请求返回 401，带 token 正常。

### ⬜ 第 5 步：WebSocket 实时同步

- [ ] `services/ws_manager.py` 连接管理
- [ ] `routers/ws.py` 端点（token 校验）
- [ ] 创建剪贴板项时广播
- [ ] Web 端接入，实时更新列表
- [ ] 验证多标签页同步

**完成标准**：标签 A 上传，标签 B 秒级收到。
**⚠️ 前置约束**：见下方「已知问题 P3」——必须同时决定单 worker 还是引入 Redis Pub/Sub。

### ⬜ 第 6 步：内容去重

- [ ] 创建时计算 `content_hash`（内存版已实现，需迁移到数据库层）
- [ ] 相同内容更新时间戳，不创建新记录（**已实现**）
- [ ] 去重分支也广播 `clipboard.updated`（待第 5 步）
- [ ] Web 端处理 `updated` 事件

**完成标准**：连续复制相同内容只产生一条记录。**该标准目前已在假数据层成立（有 e2e 用例覆盖）。**

### ⬜ 第 7 步：鸿蒙 App

- [ ] DevEco 创建项目、配置网络权限
- [ ] 封装 HTTP 客户端与 WebSocket
- [ ] 剪贴板读写（读取需 `READ_PASTEBOARD` 权限）
- [ ] 剪贴板变化监听（`on('update')`，无需权限）
- [ ] 列表页 + 手动同步 + 接入 WebSocket

**完成标准**：鸿蒙与 Web 双向实时同步。

### ⬜ 第 8 步：联调与测试

- [ ] 三端同时运行，验证双向同步
- [ ] 补充后端单元测试（pytest）
- [ ] 修复边界问题

---

## 已知问题与技术债

按严重程度排序，**建议在对应步骤开工前解决**。

### 🔴 P1 · `DEBUG` 默认 true + 开发重置路由

`server/app/core/config.py` 的 `DEBUG` 默认 `True`，`.env.example` 也是 `true`，
而 `POST /api/v1/dev/reset` 目前按 `DEBUG` 注册。

- 现状：重置的是内存种子数据，无害
- **第 3 步之后**：它将变成"清空数据库"，一旦以 `DEBUG=true` 部署并接库 → 用户数据丢失
- 处理：默认改 `False`；开发路由改用独立的 `ENABLE_DEV_ROUTES` 开关（不复用 `DEBUG`）

### 🔴 P2 · `pnpm test` 会清空真实库

`web/tests/e2e.test.ts` 收尾调用 `clearAll()` + `dev/reset`。

- 现状：数据在内存，无所谓
- **第 3 步之后**：跑一次测试清空真实数据库
- 处理：测试指向独立测试库（通过 `VITE_API_BASE_URL` 或专用环境变量注入），
  或用例加环境守卫，非测试环境直接跳过破坏性用例

### 🟠 P3 · 多 worker 会打破 WebSocket 广播

`_STORE` 是模块级内存；第 5 步的 `ConnectionManager` 同样是进程内结构。

- uvicorn `--workers > 1` 时：数据一致（都在数据库），但**推送送不到另一个 worker**
- 处理：第 5 步要么强制 `--workers 1` 并禁止扩容，要么同时引入 Redis Pub/Sub
- **AGENT.md 第 12 节把 Redis 列为"后期"风险，实际约束比它写的更早**

### 🟡 P4 · 文档文件名曾三处矛盾（已解决）

原先 AGENT.md 说 `docs/api.yaml`、README 说 `docs/api.md` 与 `docs/architecture.md`。
**现已统一为**：`api.md`（契约 + 导出脚本）、`ws-protocol.md`、`roadmap.md`。

### 🟡 P5 · 第 4 步依赖有已知兼容问题

AGENT.md 第 2 节指定 `python-jose + passlib[bcrypt]`：

- `passlib 1.7.4` 已停止维护，与 `bcrypt 4.x` 存在版本探测告警/报错
- 处理：改用 `pwdlib`，或显式 pin `bcrypt==4.0.1`。偏离 AGENT.md 前需确认

### 🟡 P6 · WS token 走 query string 会被日志记录

`ws?token=<JWT>` 会被 uvicorn 访问日志明文记录。第 5 步需对 `token` 脱敏。

### 🟡 P7 · 根 `.gitignore` 缺 `dist/`

`web/.gitignore` 有，但根目录没有兜底。构建产物位于 `web/dist/`。

### 🟡 P8 · README 路由表口径不一致

README API 表里的 `POST /api/v1/clipboard/upload`（图片/文件）在 AGENT.md 第 5 节不存在，
且第 1 节明确"本期不做图片、文件"。**已标注为阶段二。**

---

## 环境前置条件（实测）

| 组件 | 状态 | 说明 |
|------|------|------|
| Python 3.13.7 | ✅ | `server/venv` 已建 |
| Node 24.11.1 + pnpm 11.7.0 | ✅ | `web/node_modules` 已装 |
| **Docker Desktop** | ❌ **守护进程未运行** | `com.docker.service` 为 Stopped；第 3 步若走容器需先启动 |
| **本机 PostgreSQL 18** | ✅ 服务 Running，`port = 5432`、`listen_addresses = '*'` | 5432 已被占用，Docker 映射会冲突；也可直接复用它 |
| Redis | ⬜ 6379 空闲 | 未安装/未启动 |
| MinIO | ⬜ 9000 空闲 | 阶段二才需要 |

**第 3 步的两条路**（待定）：

1. **复用本机 PostgreSQL 18**：省掉容器一层，避开 5432 冲突；Redis 需另想办法
2. **启动 Docker Desktop 用容器**：PostgreSQL 映射 `5433:5432`、Redis `6379:6379`

---

## 下一步行动

1. 决定第 3 步的数据库方案（复用本机实例 / 启动 Docker）
2. 先修 P1、P2（趁数据还在内存里改，成本最低）
3. 提交第 1、2 步的代码作为版本保护点
