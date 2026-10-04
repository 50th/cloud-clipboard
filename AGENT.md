# AGENT.md

> 本文件为 AI 编码助手（Claude Code / Cursor / Copilot 等）提供**稳定约定**：项目上下文、技术栈、目录职责、开发规范、关键约束与开发顺序。
> **每次开始工作前先读本文件。** 进度、验收记录、已知问题见 [`docs/roadmap.md`](docs/roadmap.md)——凡是每完成一步就要改一遍的内容都放那里，本文件不放。

---

## 1. 项目概述

**项目名称**：云剪贴板（Cloud Clipboard）

**目标**：跨平台云剪贴板服务，实现多设备间剪贴板内容实时同步。

| 项 | 内容 |
|----|------|
| 客户端 | 鸿蒙 App（ArkTS + ArkUI）、Web 端（Vue 3 + TS + Vite） |
| 后端 | FastAPI + PostgreSQL + Redis + WebSocket |
| 当前阶段 | 阶段一 —— 文字剪贴板 MVP |

**MVP 范围**：文字内容的上传 / 查询 / 删除、多端实时同步（WebSocket）、JWT 认证、内容去重。

**明确不做（本期）**：图片与文件剪贴板、端到端加密、团队协作。

---

## 2. 技术栈与版本

技术要求与实际锁定版本并列——**新增依赖请写进 `server/requirements.txt` 与 `web/package.json`**。

| 层级 | 技术 | 要求 | 实际锁定 |
|------|------|------|----------|
| 后端框架 | FastAPI | 最新稳定版 | 0.142.2 |
| ASGI 服务器 | uvicorn[standard] | 最新稳定版 | 0.54.0 |
| 配置 | pydantic-settings | - | 2.15.0 |
| 数据库 | PostgreSQL | 14+，**本地与生产统一 16** | 16.15（容器） |
| ORM | SQLAlchemy（async） | 2.0+ | 2.1.3 |
| 数据库驱动 | asyncpg | - | 0.31.0 |
| 迁移 | Alembic | 最新稳定版 | 1.20.0 |
| 缓存/广播 | Redis | 6+ | ⬜ 第 5 步 |
| 认证 | ⚠️ **待定**：`pwdlib` 或 pin `bcrypt==4.0.1` | - | ⬜ 第 4 步 |
| Web 前端 | **Vue 3 + TypeScript + Vite** | HTML/CSS/JS | 见下 |
| Web 状态 | **Pinia** | - | 见下 |
| HTTP 客户端 | Axios | 最新稳定版 | 1.20.0 |
| 鸿蒙 | ArkTS + ArkUI | API 12+ | ⬜ 第 7 步 |

**Web 端锁定版本**（完整清单见 `web/package.json`）：
Vue 3.5 · Vite 5.4.21 · TypeScript 5.9.3 · Pinia 2.2 · vue-tsc 2.1

**⚠️ 认证依赖待定**：原先指定的 `passlib[bcrypt]` 已停止维护，且与 `bcrypt 4.x` 存在兼容问题。
第 4 步开工前必须在 `pwdlib` 与 pin `bcrypt==4.0.1` 之间二选一，并在上表登记结果。
详见 [`docs/roadmap.md`](docs/roadmap.md) 的 P5。

---

## 3. 目录结构

> ✅ = 已落地；⬜ = 待创建。**只描述职责，不记录进度状态。**

```
cloud-clipboard/
├── AGENT.md                  # 本文件：稳定约定
├── README.md                 # 项目说明与快速开始
├── docs/
│   ├── api.md                # API 契约存档 + 导出脚本
│   ├── ws-protocol.md        # WebSocket 协议
│   └── roadmap.md            # 进度、验收记录、已知问题
│
├── infra/
│   ├── docker-compose.yml    # ✅ PostgreSQL 16（宿主 5433 → 容器 5432）
│   └── .env.example          # ✅ 容器账号与端口（第 5 步在此加 Redis）
│
├── scripts/
│   └── verify_postgres.py    # ✅ 数据库连通性与数据往返验证
│
├── server/                   # 后端 FastAPI
│   ├── app/
│   │   ├── main.py           # ✅ 入口：路由注册、CORS、lifespan（启动探测数据库）
│   │   ├── core/
│   │   │   ├── config.py     # ✅ 环境变量（pydantic-settings）
│   │   │   └── security.py   # ⬜ 第 4 步：密码哈希、JWT
│   │   ├── db/               # ✅ 数据库层
│   │   │   ├── base.py       #   声明式 Base + 约束命名约定
│   │   │   ├── session.py    #   异步引擎 / 会话 / get_db / ping
│   │   │   └── models/       #   user.py、clipboard.py
│   │   ├── schemas/          # ✅ 数据契约（唯一事实来源）
│   │   │   ├── common.py     #   ContentType / SortOrder / SortBy / PageMeta
│   │   │   ├── user.py
│   │   │   └── clipboard.py
│   │   ├── crud/             # ✅ 数据访问层（异步；路由不写 SQL）
│   │   ├── routers/          # auth.py / clipboard.py / dev.py ✅
│   │   │   └── ws.py         # ⬜ 第 5 步
│   │   └── services/
│   │       └── ws_manager.py # ⬜ 第 5 步：WebSocket 连接管理
│   ├── alembic/              # ✅ 迁移（env.py 异步 + versions/）
│   ├── scripts/init_db.py    # ✅ 建表 + 演示用户 + 种子数据
│   ├── tests/                # ✅ conftest.py（默认打 clipboard_test 库）
│   ├── venv/                 # 虚拟环境（已忽略）
│   ├── requirements.txt
│   ├── alembic.ini           # ⚠️ 必须保持纯 ASCII（见 §11）
│   ├── .env.example
│   └── README.md             # 后端启动、迁移与排错
│
├── web/                      # Web 端 Vue 3 + TS + Vite
│   ├── src/
│   │   ├── api/client.ts     # ✅ axios 封装 + token 拦截器 + 错误归一化
│   │   ├── types/api.d.ts    # ✅ 由 OpenAPI 生成，勿手改
│   │   ├── utils/            # ✅ clipboard.ts（含自身写入标志）、format.ts
│   │   ├── stores/           # ✅ Pinia：clipboardStore、userStore
│   │   ├── composables/      # ✅ useClipboard / useCopy / useAutoSave；⬜ useWebSocket 待实现
│   │   ├── components/       # ✅ ClipboardHistory / ClipboardItemCard / InputPanel
│   │   ├── views/            # ⬜ 第 4 步加登录页时创建
│   │   ├── App.vue           # ✅ 两栏布局（左历史 / 右输入）
│   │   └── main.ts          # ✅ 挂载 + 安装 Pinia
│   ├── tests/e2e.test.ts     # ✅ 端到端闭环测试（驱动 store + client，与框架无关）
│   ├── scripts/generate-api-types.mjs  # ✅ pnpm run gen:api
│   ├── vite.config.ts        # ✅ 端口 5273（见 §12）、@ 别名
│   ├── pnpm-workspace.yaml   # ✅ pnpm 11 项目设置（allowBuilds 放行 esbuild）
│   └── README.md             # 启动、界面结构、验证步骤
│
└── harmony/                  # ⬜ 第 7 步：鸿蒙 App
    └── entry/src/main/ets/{pages,components,services,models}/
```

---

## 4. 数据契约

**契约唯一事实来源**：`server/app/schemas/`（Pydantic Schema）。
**字段清单不在本文件重复**——存档见 [`docs/api.md`](docs/api.md)，在线见 `/docs`。

### 关键约定（这些容易踩错，必须遵守）

- **时间**统一 ISO 8601 UTC，形如 `2026-09-27T10:00:00Z`；数据库列用 `timestamptz`
- **`content_hash` 不对外暴露**，仅服务端用于去重；响应模型里不得出现该字段
- **`title`**：用户可填；留空时服务端生成 `<用户名> · <月-日 时:分>`（如 `demo · 10-04 14:30`）
- **去重**：同一用户提交相同 `content` → 刷新 `updated_at`、**不新建记录**；
  **不覆盖已有标题**（除非本次请求显式传了 `title`）。去重分支也必须广播 `clipboard.updated`（易漏）
- **搜索**同时匹配 `title` 与 `content`
- **分页**：`page` 从 1 开始，`size` 默认 20、最大 100

### 改接口必须做的事

1. 改 `server/app/schemas/`（先改契约，再改实现）
2. 若涉及表结构 → 生成并检查迁移（见 §11）
3. 重启 FastAPI，确认 `/openapi.json` 已更新
4. `cd web && pnpm run gen:api` 重新生成前端类型
5. 同步 `harmony/.../models/ClipboardItem.ets`（第 7 步落地后）
6. 刷新 `docs/api.md` 的契约存档

---

## 5. API 概览

模块级摘要；**完整路径、参数与响应以 `/docs` 为准**，存档见 [`docs/api.md`](docs/api.md)。

| 模块 | 前缀 | 内容 |
|------|------|------|
| 健康检查 | `/health`、`/` | 存活探针、服务信息 |
| 认证 | `/api/v1/auth` | `register` / `login` / `me`（当前为假数据，第 4 步接真实 JWT） |
| 剪贴板 | `/api/v1/clipboard` | `items` 的创建 / 列表 / 详情 / 删除 / 清空；第 5 步加 `ws` |
| 开发辅助 | `/api/v1/dev` | `reset`（⚠️ 删数据）、`db`（探测当前库）；**仅 `ENABLE_DEV_ROUTES=true` 时注册** |

---

## 6. WebSocket 协议

**协议细节以 [`docs/ws-protocol.md`](docs/ws-protocol.md) 为准**（事件表、消息格式、调试方法）。

连接：`ws://localhost:8000/api/v1/clipboard/ws?token=<JWT>`

**本文件只记两条容易漏的硬约束**：

- ⚠️ **token 走 query string 会被 uvicorn 访问日志明文记录**，实现时必须对 `token` 参数脱敏
- ⚠️ **多 worker 会打破广播**：`ConnectionManager` 是进程内结构，`--workers > 1` 时
  A 连 worker 1、B 连 worker 2 → 事件送不到。第 5 步必须二选一：
  **强制 `--workers 1`** 或**同时引入 Redis Pub/Sub**

---

## 7. 当前进度

> **全部进度、验收记录、已知问题与环境前置条件见 [`docs/roadmap.md`](docs/roadmap.md)。**
> 本文件不再维护任何勾选框或状态标记。

**开始工作前**：先读 `docs/roadmap.md` 的「已知问题」与「环境前置条件」，确认没有必须先修的高危项。

---

## 8. 开发规范

### 代码风格

**后端（Python）**
- 遵循 PEP 8；类型注解必须完整；I/O 一律 `async def`
- 路由层只做参数校验与调用，业务逻辑放 `services/` 或 `crud/`
- 数据库操作统一走 `crud/`，**路由不直接写 SQL**

**Web 端（Vue 3 + TypeScript）**
- 组件一律用 `<script setup lang="ts">` 单文件组件（SFC）
- 状态管理用 Pinia，**setup store 写法**；避免 prop drilling
- 可复用逻辑放 `src/composables/`，命名 `useXxx`；只在组件内一次性使用的逻辑不必抽 composable
- 剪贴板 API 封装在 `utils/clipboard.ts`，**组件不直接调 `navigator.clipboard`**
- **组件不直接调 axios**，统一经 `api/client.ts`
- 类型从 `types/api.d.ts` 导入，不手写重复类型
- 响应式优先用 `ref`（对象/数组也统一 `ref`，避免 `reactive` 解构丢响应性）
- 不要用 `v-html` 渲染剪贴板内容；模板里用 `{{ }}` 自动转义

**鸿蒙端（ArkTS）**
- 剪贴板监听隔离在 `services/clipboardMonitor.ets`，网络请求统一在 `services/api.ets`
- 模型字段与后端 Schema 严格对齐

### 提交规范

遵循 Conventional Commits：`feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:`

### 分支策略

`main` 稳定分支；`feature/*` 功能分支；`hotfix/*` 紧急修复

---

## 9. 关键约束（必须遵守）

### 安全

- **绝不**在代码中硬编码密钥，一律走 `.env`
- `.env` 必须被 `.gitignore` 忽略；迁移配置里也不要写连接串
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
- 分页默认 `page=1`、`size=20`

### 性能与隔离

- 图片、文件不要 base64 存数据库（阶段二）
- 列表查询必须带分页
- WebSocket 广播**按用户隔离，不群发**；同时注意 §6 的 worker 约束

---

## 10. 开发顺序

**原则：契约优先，后端先行，Web 验证，鸿蒙接入。严格按顺序推进，不要跳步。**
每一步的细化任务、完成标准与当前状态见 [`docs/roadmap.md`](docs/roadmap.md)。

| 步骤 | 内容 | 状态 |
|------|------|------|
| 1 | FastAPI 骨架 + 数据契约 | ✅ |
| 2 | Web 端骨架 + 单端闭环 | ✅ |
| 3 | 接入数据库（PostgreSQL + SQLAlchemy + Alembic） | ✅ |
| 4 | JWT 认证 | ⬅ 下一步 |
| 5 | WebSocket 实时同步（含 worker / Redis 决策） | ⬜ |
| 6 | 内容去重（去重逻辑与广播） | ⬜ |
| 7 | 鸿蒙 App | ⬜ |
| 8 | 联调与测试（含后端 pytest） | ⬜ |

---

## 11. 常见任务操作指引

> 启动、迁移、排错等完整命令见 [`server/README.md`](server/README.md) 与 [`web/README.md`](web/README.md)，
> 此处只列**跨端协作时容易漏的流程**。

### 添加接口

改 Schema → 改路由 → 确认 `/docs` → `pnpm run gen:api` → 刷新 `docs/api.md`（详见 §4）

### 修改会被端到端测试引入的模块

`tests/e2e.test.ts` **直接跑源码**（Node 类型擦除），不经过打包。因此：

- `stores/`、`composables/`、`api/`、`utils/` 里的导入必须用 **`#src/*` 且带 `.ts` 扩展名**——
  Node 不读 tsconfig 的 `paths`，`@/xxx` 会被当裸包名报 `ERR_MODULE_NOT_FOUND`
- 只有 `.vue` 组件与 `main.ts` 用 `@/*`
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

```bash
cd web && pnpm run gen:api
```

---

## 12. 已知风险与注意事项

| 风险 | 说明 | 应对 |
|------|------|------|
| 浏览器剪贴板兼容性 | 部分浏览器不支持 `read()` | 已封装降级 + 手动粘贴入口 |
| 剪贴板需安全上下文 | 非 HTTPS 或 localhost 时读取被拒 | 本地固定用 `127.0.0.1` |
| WebSocket 循环同步 | 写回剪贴板触发监听 | `isSelfWrite()` 标志位 |
| 广播多实例不一致 | 多 worker 时事件送不到 | §6：单 worker 或 Redis Pub/Sub |
| **Windows 保留端口段** | `5141-5240` 吃掉 5173、`8903-9002` 吃掉 9000 | Web 端已改 **5273**；MinIO 阶段二需换端口。排查：`netsh int ipv4 show excludedportrange protocol=tcp` |
| 端到端加密与搜索冲突 | 服务端无法搜明文 | 搜索仅在客户端本地做（阶段四） |

---

## 13. 参考文档

| 文档 | 内容 |
|------|------|
| [`README.md`](README.md) | 项目介绍与快速开始 |
| [`docs/roadmap.md`](docs/roadmap.md) | **进度、验收记录、已知问题与技术债、环境前置条件** |
| [`docs/api.md`](docs/api.md) | API 契约存档（含导出脚本） |
| [`docs/ws-protocol.md`](docs/ws-protocol.md) | WebSocket 协议全量说明 |
| [`server/README.md`](server/README.md) | 后端启动、迁移、数据库结构、排错 |
| [`web/README.md`](web/README.md) | Web 端启动、界面结构、验证步骤 |

---

**最后更新**：2026-10-04（精简：删除与 docs/ 重复的枚举，补齐锁定版本与缺失约束）
**维护者**：云剪贴板项目组

**给 AI 助手的提示**：
- 本文件只维护**稳定约定**。不要往这里加勾选框、实测记录或版本号流水——那些写进 `docs/roadmap.md`。
- 进度、已知问题、开工前置条件：**看 `docs/roadmap.md`**。
- 字段与路径的**枚举**不要在 AGENT.md 里展开，指向 `docs/api.md` 与 `/docs`。
- 严格按 §10 的顺序推进；改代码前先确认是否影响契约（影响则走 §4 流程）。
