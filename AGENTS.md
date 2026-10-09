# AGENTS.md

> 本文件为 AI 编码助手（Claude Code / Cursor / Copilot / Gemini CLI / Codex 等）提供**稳定约定**：项目上下文、技术栈、目录职责、开发规范、关键约束与开发顺序。
> **每次开始工作前先读本文件。** 进度、验收记录、已知问题见 [`docs/roadmap.md`](docs/roadmap.md)——凡是每完成一步就要改一遍的内容都放那里，本文件不放。
> `README.md` 面向人类访客，Agent 按需查即可。
>
> 📌 本文件按行业标准命名为 `AGENTS.md`（复数），可被上述工具自动读取。
> 历史引用里的「AGENT.md 第 N 节」（含 `docs/` 与源码注释）**指的就是本文件**。

---

## 1. 项目概述

**云剪贴板（Cloud Clipboard）**：跨平台云剪贴板服务，实现多设备间剪贴板内容实时同步。

客户端为鸿蒙 App（ArkTS + ArkUI）与 Web 端（Vue 3 + TS + Vite）；后端为 FastAPI + PostgreSQL + Redis + WebSocket。

**当前阶段**：阶段一 —— 文字剪贴板 MVP（阶段划分见 §10 与 [`docs/roadmap.md`](docs/roadmap.md)）。

---

## 2. 技术栈

**版本号以 `server/requirements.txt` 与 `web/package.json` 为准（`pnpm-lock.yaml` 含精确锁定值），本文件不再重复列版本。**

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + uvicorn（ASGI）；配置用 pydantic / pydantic-settings |
| 数据库 | PostgreSQL 16（**本地与生产统一 16**，本地走容器） |
| ORM / 迁移 | SQLAlchemy 2.x（async）+ asyncpg + Alembic |
| 时区数据 | tzdata：**Windows 没有系统时区数据库，`zoneinfo` 靠它才能解析 `Asia/Shanghai`**（缺失抛 `ZoneInfoNotFoundError`，创建剪贴板项直接 500）。注意：与 asyncpg 无关 |
| 缓存 / 广播 | Redis —— ⬜ 未启用（第 5 步需要时引入） |
| 认证 | ✅ 已接入：`pwdlib[bcrypt]`（密码哈希）+ `PyJWT`（HS256 令牌）。**不用 `passlib`**：Python 3.13 按 PEP 594 移除了 `crypt` 模块，passlib 在 import 阶段就会失败（pin 老版本 bcrypt 也救不回来） |
| Web 前端 | Vue 3 + TypeScript + Vite；状态管理 Pinia（setup store）；HTTP 客户端 Axios |
| 鸿蒙 | ArkTS + ArkUI，API 12+ —— ⬜ 未创建（第 7 步） |

**Web 端要点**：`pnpm-workspace.yaml` 的 `allowBuilds` 需放行 esbuild 与 vue-demi；导入别名
两套并存——`.vue` 与 `main.ts` 用 `@/*`，**store / composables / api / utils 必须用 `#src/*.ts`**
（Node 不读 tsconfig 的 paths，端到端测试直接跑源码，靠 `package.json` 的 `imports` 解析）。
改动时误换别名会让 `pnpm test` 报模块找不到。前端框架原为 React 18，已迁移为 Vue 3 + Pinia。

---

## 3. 目录结构

> ✅ = 已创建；⬜ = 尚未创建（`（第 N 步）`只说明归属，不代表当前进度）。
> 本树只列职责，**具体文件不在此展开**（`ls` 即可见）；步骤进度见 [`docs/roadmap.md`](docs/roadmap.md)。

```
cloud-clipboard/
├── AGENTS.md / README.md   # 本文件 / 项目说明（面向人类）
├── docs/                   # api.md（契约摘要）/ ws-protocol.md / roadmap.md
├── infra/                  # ✅ docker-compose.yml（Postgres 容器，宿主 5433）
├── scripts/                # ✅ verify_postgres.py（宿主侧连通性验证）
├── server/                 # 后端：app/{core,db,schemas,crud,routers,services} + alembic/ + tests/
│   │                       #   core/security.py ✅（密码哈希 + JWT）；routers/ws.py、services/ws_manager.py ⬜第5步
│   └── alembic.ini         # ⚠️ 必须保持纯 ASCII（见 §11）
├── web/                    # 前端：src/{api,types,utils,stores,composables,components} + tests/*.test.ts
│   │                       #   vite.config.ts 端口 5273（见 §12）；登录页是 components/LoginPanel.vue
│   └── pnpm-workspace.yaml # ✅ allowBuilds 放行 esbuild 与 vue-demi
└── harmony/                # ⬜ 第 7 步：鸿蒙 App（entry/src/main/ets/{pages,components,services,models}）
```

---

## 4. 数据契约

**契约唯一事实来源**：`server/app/schemas/`（Pydantic Schema）。
**字段清单不在本文件重复**——摘要见 [`docs/api.md`](docs/api.md)，在线见 `/docs`。

### 关键约定（这些容易踩错，必须遵守）

- **时间**统一 ISO 8601 UTC，形如 `2026-09-27T10:00:00Z`；数据库列用 `timestamptz`
- **`content_hash` 不对外暴露**，仅服务端用于去重；响应模型里不得出现该字段
- **`title`**：用户可填；留空时服务端生成 `<用户名> · <月-日 时:分>`，
  **时间按请求里的 `timezone`（IANA 名，前端自动传浏览器时区）展示**，如 `demo · 10-05 22:26`；
  数据库**始终存 UTC**，时区只影响标题里的时间文本。未传或非法时回退 `DEFAULT_TIMEZONE`（默认 `Asia/Shanghai`）
- **去重**：同一用户提交相同 `content` → 刷新 `updated_at`、**不新建记录**；
  **不覆盖已有标题**（除非本次请求显式传了 `title`）。去重分支也必须广播 `clipboard.updated`（易漏）
- **搜索**同时匹配 `title` 与 `content`；**分页** `page` 从 1 开始、`size` 默认 20、最大 100

### 改接口必须做的事

1. 改 `server/app/schemas/`（先改契约，再改实现）
2. 若涉及表结构 → 生成并检查迁移（见 §11）
3. 重启 FastAPI，确认 `/openapi.json` 已更新
4. `cd web && pnpm run gen:api` 重新生成前端类型
5. 同步 `harmony/.../models/ClipboardItem.ets`（第 7 步落地后）
6. 刷新 `docs/api.md` 的契约摘要

---

## 5. API 与 WebSocket（§6 已并入本节）

**API 路径与参数见 [`docs/api.md`](docs/api.md) 与 `/docs`**；仅开发路由在 `ENABLE_DEV_ROUTES=true` 时注册。

**WebSocket 协议细节以 [`docs/ws-protocol.md`](docs/ws-protocol.md) 为准**（事件表、消息格式、调试方法）。
连接：`ws://localhost:8000/api/v1/clipboard/ws?token=<JWT>`

**本节只记两条容易漏的硬约束**：

- ⚠️ **token 走 query string 会被 uvicorn 访问日志明文记录**，实现时必须对 `token` 参数脱敏
- ⚠️ **多 worker 会打破广播**：`ConnectionManager` 是进程内结构，`--workers > 1` 时
  A 连 worker 1、B 连 worker 2 → 事件送不到。第 5 步必须二选一：
  **强制 `--workers 1`** 或**同时引入 Redis Pub/Sub**

---

## 7. 当前进度

> **全部进度、验收记录、已知问题与环境前置条件见 [`docs/roadmap.md`](docs/roadmap.md)。**
> **开始工作前**：先读其「已知问题」与「环境前置条件」，确认没有必须先修的高危项。

---

## 8. 开发规范

**后端（Python）**
- 遵循 PEP 8；类型注解必须完整；I/O 一律 `async def`
- 路由层只做参数校验与调用，业务逻辑放 `services/` 或 `crud/`；**路由不直接写 SQL**

**Web 端（Vue 3 + TypeScript）**
- 组件一律用 `<script setup lang="ts">` 单文件组件（SFC）
- 状态管理用 Pinia，**setup store 写法**；避免 prop drilling
- 可复用逻辑放 `src/composables/`，命名 `useXxx`；只在组件内一次性使用的逻辑不必抽 composable
- 剪贴板 API 封装在 `utils/clipboard.ts`，**组件不直接调 `navigator.clipboard`**
- **组件不直接调 axios**，统一经 `api/client.ts`；类型从 `types/api.d.ts` 导入，不手写重复类型
- 响应式优先用 `ref`（对象/数组也统一 `ref`，避免 `reactive` 解构丢响应性）
- 不要用 `v-html` 渲染剪贴板内容；模板里用 `{{ }}` 自动转义

**鸿蒙端（ArkTS）**
- 剪贴板监听隔离在 `services/clipboardMonitor.ets`，网络请求统一在 `services/api.ets`
- 模型字段与后端 Schema 严格对齐

**提交规范**：遵循 Conventional Commits（`feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:`）。
**分支策略**：`master` 是当前稳定分支（本仓库由 `git init` 默认命名为 `master`，尚未改名，
也**未配置任何远程**）；功能分支用 `feature/*`，紧急修复用 `hotfix/*`。

---

## 9. 关键约束（必须遵守）

### 安全

- **绝不**在代码中硬编码密钥，一律走 `.env`；`.env` 必须被 `.gitignore` 忽略，迁移配置里也不要写连接串
- 生产环境必须 HTTPS / WSS；JWT 密钥生产必须更换
- 会删数据的开发辅助接口必须由**独立开关**控制，不要复用 `DEBUG`

### 剪贴板 API

- 浏览器剪贴板 API **仅在 HTTPS 或 localhost 可用**（用 `127.0.0.1`/`localhost` 访问）
- 读取剪贴板**必须由用户手势触发**（点击、Ctrl+V），不能后台自动读
- 写回剪贴板要设标志位，避免触发自身监听造成死循环
- 鸿蒙 API 12+：读剪贴板需 `READ_PASTEBOARD` 权限，监听用 `on('update')` 无需权限

### 数据一致性

- 任何接口字段变更必须同步三端（Schema → Web 类型 → 鸿蒙模型）
- 去重分支也必须广播 WebSocket 消息
- 分页：见 §4「关键约定」（本文件与 `docs/api.md` 不得各写一份）

### 性能与隔离

- 图片、文件不要 base64 存数据库（阶段二）；列表查询必须带分页
- WebSocket 广播**按用户隔离，不群发**；同时注意 §5 的 worker 约束

---

## 10. 开发顺序

**原则：契约优先，后端先行，Web 验证，鸿蒙接入。严格按顺序推进，不要跳步。**
每一步的细化任务、完成标准与**当前状态**见 [`docs/roadmap.md`](docs/roadmap.md)——本表只定义顺序，不记录状态。

| 步骤 | 内容 |
|------|------|
| 1 | FastAPI 骨架 + 数据契约 |
| 2 | Web 端骨架 + 单端闭环 |
| 3 | 接入数据库（PostgreSQL + SQLAlchemy + Alembic） |
| 4 | JWT 认证 |
| 5 | WebSocket 实时同步（含 worker / Redis 决策） |
| 6 | 内容去重（去重逻辑与广播） |
| 7 | 鸿蒙 App |
| 8 | 联调与测试（含后端 pytest） |

**阶段划分**：阶段一 = 第 1～6 步（文字剪贴板 MVP）；阶段二 = 图片剪贴板 + 对象存储；
阶段三 = 文件剪贴板 + 体验优化；阶段四 = 端到端加密 + 生产部署。各阶段状态见 [`docs/roadmap.md`](docs/roadmap.md)。

---

## 11. 常见任务操作指引

> 启动、迁移、排错等完整命令见 [`server/README.md`](server/README.md) 与 [`web/README.md`](web/README.md)，
> 此处只列**跨端协作时容易漏的流程**。

### 添加接口

改 Schema → 改路由 → 确认 `/docs` → `pnpm run gen:api` → 刷新 `docs/api.md`（详见 §4）

### 修改会被测试引入的模块

`tests/*.test.ts` **直接跑源码**（Node 类型擦除），不经过打包。因此：

- `stores/`、`composables/`、`api/`、`utils/` 里的导入必须用 **`#src/*` 且带 `.ts` 扩展名**——
  Node 不读 tsconfig 的 `paths`，`@/xxx` 会被当裸包名报 `ERR_MODULE_NOT_FOUND`
- 只有 `.vue` 组件与 `main.ts` 用 `@/*`
- 新增测试文件放在 `web/tests/` 下、以 `.test.ts` 结尾即会被 `pnpm test` 收集
- 改完跑 `pnpm test` 验证，别只跑 `typecheck`（`vue-tsc` 会通过但 Node 跑不起来）

### 添加/修改数据库模型

1. 在 `app/db/models/` 定义或修改模型
2. 在 `app/db/models/__init__.py` 导入，确保注册进 `Base.metadata`
3. `alembic revision --autogenerate -m "描述"`
4. **逐行检查生成的迁移**——见下方两条坑
5. `alembic upgrade head`，并确认 `alembic current` 与模型一致（再 autogenerate 应无变更）

> ⚠️ **坑 1：autogenerate 会记录"多余的表"**
> 若开发库里存在手工建的临时表，迁移会包含 `op.drop_table('xxx')`，
> 在干净库（CI、测试库）上执行必然失败。生成后必须删掉这类噪声语句。
>
> ⚠️ **坑 2：`alembic.ini` 必须保持纯 ASCII**
> Windows 上 configparser 按 locale（GBK）读取该文件，中文注释会让 Alembic 直接崩溃。
> 运行迁移前建议设 `$env:PYTHONUTF8='1'`。

### 生成 Web 端类型

```powershell
cd web
pnpm run gen:api
```

> bash / macOS / Linux 等价命令：`cd web && pnpm run gen:api`

---

## 12. 已知风险与注意事项

| 风险 | 说明 | 应对 |
|------|------|------|
| 浏览器剪贴板兼容性 | 部分浏览器不支持 `read()` | 已封装降级 + 手动粘贴入口 |
| WebSocket 循环同步 | 写回剪贴板触发监听 | 见 **§9 剪贴板 API**（`isSelfWrite()` 标志位） |
| 广播多实例不一致 | 多 worker 时事件送不到 | 见 **§5**（单 worker 或 Redis Pub/Sub），细则见 `docs/ws-protocol.md` |
| **Windows 保留端口段** | `5141-5240` 吃掉 5173、`8903-9002` 吃掉 9000 | Web 端已改 **5273**；MinIO 阶段二需换端口。排查：`netsh int ipv4 show excludedportrange protocol=tcp` |
| 端到端加密与搜索冲突 | 服务端无法搜明文 | 搜索仅在客户端本地做（阶段四） |

---

## 13. 参考文档

| 文档 | 内容 |
|------|------|
| [`docs/roadmap.md`](docs/roadmap.md) | **进度、已知问题与技术债、环境前置条件、下一步行动** |
| [`docs/api.md`](docs/api.md) | API 契约摘要（含 OpenAPI 导出脚本） |
| [`docs/ws-protocol.md`](docs/ws-protocol.md) | WebSocket 协议全量说明 |
| [`server/README.md`](server/README.md) | 后端启动、迁移、数据库结构、排错 |
| [`web/README.md`](web/README.md) | Web 端启动、界面结构、验证步骤 |
| [`README.md`](README.md) | 项目介绍与快速开始（面向人类访客） |

---

**维护者**：云剪贴板项目组 · **最后更新**：见 [`docs/roadmap.md`](docs/roadmap.md) 顶部（本文件不记日期流水）

**给 AI 助手的提示**：
- 本文件只维护**稳定约定**。不要往这里加勾选框、实测记录或版本号流水——那些写进 `docs/roadmap.md`。
- 进度、已知问题、开工前置条件：**看 `docs/roadmap.md`**。
- §3 的 ✅/⬜ **只表示文件是否已创建**（⬜ = 尚未创建），不表示步骤进度；它随骨架搭建一次性补齐，不要按步改成"进行中"。
- 字段与路径的**枚举**不要在 AGENTS.md 里展开，指向 `docs/api.md` 与 `/docs`。
- 严格按 §10 的顺序推进；改代码前先确认是否影响契约（影响则走 §4 流程）。
- **源码注释不要引用 `docs/roadmap.md` 的 P 编号或本文件的节号**（易变）；指向稳定载体：
  `app/schemas/`、`.env.example`、`docs/api.md`、`docs/ws-protocol.md`。
- 改动涉及**文件改名、章节编号、路径、命令、依赖版本**时，改完必须 grep 相关关键词
  （旧文件名、旧章节号、旧路径、旧包名），确认所有引用已同步。常见关键词：`hooks/`、
  `npm`、`AGENT.md`（单数）、`内存`、旧端口号、旧版本号。
