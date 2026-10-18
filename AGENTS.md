# AGENTS.md

> 本文件为 AI 编码助手（Claude Code / Cursor / Copilot / Gemini CLI / Codex 等）提供**稳定约定**：
> 项目上下文、技术栈、目录职责、规范与关键约束。
> **每次开始工作前先读本文件**；进度、验收记录、已知问题一律看 [`docs/roadmap.md`](docs/roadmap.md)。
>
> 📌 本文件按行业标准命名为 `AGENTS.md`（复数）。历史引用里的「AGENT.md 第 N 节」指的就是本文件。

---

## 1. 项目概述

**云剪贴板（Cloud Clipboard）**：跨平台云剪贴板服务，多设备间剪贴板内容实时同步。

- 客户端：鸿蒙 App（ArkTS + ArkUI，✅ 已可编译、待签名上机）、Web 端（Vue 3 + TS + Vite，✅ 可用）
- 后端：FastAPI + PostgreSQL + WebSocket（Redis 见「技术栈」，本阶段未引入）
- 当前阶段：**阶段一（文字剪贴板）已完成**——只处理文字，图片与文件属后续阶段

---

## 2. 技术栈

**版本号以 `server/requirements.txt` 与 `web/package.json` 为准，本文件不重复列。**

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + uvicorn（ASGI）；配置用 pydantic / pydantic-settings |
| 数据库 | PostgreSQL 16（本地与生产统一 16，本地走容器） |
| ORM / 迁移 | SQLAlchemy 2.x（async）+ asyncpg + Alembic |
| 时区数据 | `tzdata` —— **Windows 无系统时区库，缺它 `zoneinfo` 解析 `Asia/Shanghai` 会抛 `ZoneInfoNotFoundError`**（与 asyncpg 无关） |
| 认证 | `pwdlib[bcrypt]` + `PyJWT`（HS256）。**不用 `passlib`**：Python 3.13 移除了它依赖的 `crypt` 模块 |
| 广播 | 进程内 `ConnectionManager`（按用户隔离）；Redis ⬜ 本阶段不引入 |
| Web 前端 | Vue 3 + TypeScript + Vite；Pinia（setup store）；Axios |
| 鸿蒙 | ArkTS + ArkUI，API 12+（Stage 模型）—— ✅ 已创建，构建用 `harmony/build.ps1` |

**Web 端要点**：`pnpm-workspace.yaml` 的 `allowBuilds` 需放行 esbuild 与 vue-demi；
导入别名两套并存——`.vue` 与 `main.ts` 用 `@/*`，**store / composables / api / utils 必须用
`#src/*.ts`**（Node 不读 tsconfig 的 `paths`，测试直接跑源码）。误换别名会让 `pnpm test`
报模块找不到。

---

## 3. 目录结构

> ✅ = 已创建；⬜ = 尚未创建。**只表示文件是否存在，不代表步骤进度**（进度见 roadmap）。
> 本树只列职责，具体文件 `ls` 即可见。

```
cloud-clipboard/
├── AGENTS.md / README.md   # 本文件 / 项目说明（面向人类）
├── docs/                   # api.md（契约摘要）/ ws-protocol.md / roadmap.md
├── infra/                  # ✅ docker-compose.yml（Postgres 容器，宿主 5433）
├── scripts/                # ✅ verify_postgres.py（连通性）/ start_server_lan.ps1（0.0.0.0 供真机）/ run_web_tests.ps1（Web 隔离测试）
├── server/                 # app/{core,db,schemas,crud,routers,services} + alembic/ + tests/
│   └── alembic.ini         # ⚠️ 必须保持纯 ASCII（见「添加/修改数据库模型」）
├── web/                    # src/{api,types,utils,stores,composables,components} + tests/*.test.ts
│   └── pnpm-workspace.yaml # ✅ allowBuilds 放行 esbuild 与 vue-demi
└── harmony/                # ✅ 鸿蒙 App（ArkTS）；构建用 harmony/build.ps1，见 harmony/README.md
```

---

## 4. 数据契约

**契约唯一事实来源**：`server/app/schemas/`。字段摘要见 [`docs/api.md`](docs/api.md)，在线见 `/docs`。

### 关键约定（容易踩错，必须遵守）

- **时间**统一 ISO 8601 UTC，形如 `2026-09-27T10:00:00Z`；数据库列用 `timestamptz`
- **`content_hash` 不对外暴露**，仅服务端用于去重
- **`title`**：留空时服务端生成 `<用户名> · <月-日 时:分>`，时间按请求里的 `timezone`
  （IANA 名，前端传浏览器时区）展示，如 `demo · 10-05 22:26`；数据库始终存 UTC，
  时区只影响标题文本。未传或非法时回退 `DEFAULT_TIMEZONE`
- **去重**：同一用户提交相同 `content` → 只刷新 `updated_at`、不新建记录，
  **不覆盖已有标题**（除非显式传了 `title`）；去重分支**也必须广播** `clipboard.updated`（易漏）
- **搜索**同时匹配 `title` 与 `content`；**分页** `page` 从 1 开始、`size` 默认 20、最大 100
- **列表按修改时间排序**：后端 `sort_by` 默认是 `created_at`，**两个客户端必须显式传
  `updated_at`**。否则编辑一条旧记录后它不会上移，用户会以为"没保存成功"
  （`web/tests/e2e.test.ts` 与 `harmony` 的 `ApiClient.listItems` 各有对应实现/用例）

### 改接口必须做的事

1. 改 `server/app/schemas/`（先改契约，再改实现）
2. 涉及表结构 → 生成并**逐行检查**迁移（见「添加/修改数据库模型」）
3. 重启 FastAPI，确认 `/openapi.json` 已更新
4. `cd web && pnpm run gen:api` 重新生成前端类型
5. 同步鸿蒙模型（`harmony/entry/src/main/ets/models/Types.ets`）；刷新 `docs/api.md` 摘要

---

## 5. API 与 WebSocket

**路径与参数见 [`docs/api.md`](docs/api.md) 与 `/docs`**；开发路由仅在 `ENABLE_DEV_ROUTES=true` 时注册。
**WebSocket 协议以 [`docs/ws-protocol.md`](docs/ws-protocol.md) 为准。**

**两条极易踩的硬约束**：

- ⚠️ **WS 的 token 走 query string 会被 uvicorn 访问日志明文记录**（浏览器无法自定义
  WebSocket 请求头），必须对日志脱敏。⚠️ **脱敏不能用 `logging.Filter` 改写 `record.args`**——
  uvicorn 的 `AccessFormatter` 要求 args 恰好 5 个字段，清空会让每个请求抛 `ValueError`，
  整个访问日志报废
- ⚠️ **多 worker 会打破广播**：连接表是**进程内**结构，`--workers > 1` 时
  A 连 worker 1、B 连 worker 2 → 事件送不到（**数据一致、推送不一致**，现象隐蔽）。
  **已决策：强制单 worker**，由 `app/core/single_worker.py` 守卫拦住。
  ⚠️ 守卫**必须包含固定端口独占那道**：uvicorn 的 CLI `--workers N` **不写进环境变量**，
  只查 `WEB_CONCURRENCY` 会漏掉最常见的手误。机制见 roadmap 第 5 步踩坑

---

## 6. 开发规范

**后端（Python）**
- 遵循 PEP 8；类型注解完整；I/O 一律 `async def`
- 路由层只做参数校验与调用，业务逻辑放 `services/` 或 `crud/`；**路由不直接写 SQL**

**Web 端（Vue 3 + TypeScript）**
- 组件一律 `<script setup lang="ts">`；状态管理用 Pinia setup store，避免 prop drilling
- 可复用逻辑放 `src/composables/`，命名 `useXxx`
- 剪贴板 API 封装在 `utils/clipboard.ts`，**组件不直接调 `navigator.clipboard`**
- **组件不直接调 axios**，统一经 `api/client.ts`；类型从 `types/api.d.ts` 导入，不手写重复类型
- 响应式优先 `ref`（对象/数组也统一 `ref`，避免 `reactive` 解构丢响应性）
- 不用 `v-html` 渲染剪贴板内容；模板用 `{{ }}` 自动转义

**鸿蒙端（ArkTS）**
- 剪贴板读写与监听隔离在 `services/ClipboardService.ets`，网络请求统一在 `services/ApiClient.ets`
- 模型字段与后端 Schema 严格对齐（`models/Types.ets`）
- 后端地址在 `common/Config.ets`；真机调试需改成开发机局域网 IP
- **构建用 `harmony/build.ps1`**，不要直接调 `hvigorw`（缺 `JAVA_HOME` 会报
  `spawn java ENOENT`，错误码 00308018，看起来像签名问题）

**提交规范**：Conventional Commits（`feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:`）。
**分支策略**：`master` 是稳定分支（`git init` 默认命名，未改名；远程为
`git@github.com:50th/cloud-clipboard.git`）；功能分支 `feature/*`，紧急修复 `hotfix/*`。

---

## 7. 关键约束（必须遵守）

**安全**
- **绝不**硬编码密钥，一律走 `.env`；`.env` 必须被 `.gitignore` 忽略，迁移配置里也不要写连接串
- 生产必须 HTTPS / WSS；JWT 密钥生产必须更换
- 会删数据的开发辅助接口必须由**独立开关**控制，不要复用 `DEBUG`

**剪贴板 API**
- 浏览器剪贴板 API **仅在 HTTPS 或 localhost 可用**（用 `127.0.0.1`/`localhost` 访问）
- 读取剪贴板**必须由用户手势触发**（点击、Ctrl+V），不能后台自动读
- 写回剪贴板要设标志位，避免触发自身监听造成死循环
- 鸿蒙 API 12+：读剪贴板需 `READ_PASTEBOARD` 权限，监听用 `on('update')` 无需权限

**数据一致性**
- 接口字段变更必须同步三端（Schema → Web 类型 → 鸿蒙模型）
- 去重分支也必须广播 WebSocket 消息

**性能与隔离**
- 图片、文件不要 base64 存数据库（阶段二）；列表查询必须带分页
- WebSocket 广播**按用户隔离，不群发**

**测试隔离**
- **测试库名必须含 `test`**：Web 端测试以此判定"这是可丢弃的库"，
  名字不含 `test` 的库**不允许**执行破坏性用例（`dev/reset`、清空全部）。
  改名等于解除保护，不要图简洁改成 `clipboard_e2e` 之类
- **每套测试各用一个库**：`clipboard`（开发）/ `clipboard_test`（pytest）/
  `clipboard_web_test`（Web 隔离测试）。pytest 每个用例都会 `drop_all` 重建表，
  共用库会互相删表
- Web 隔离测试跑 `.\scripts\run_web_tests.ps1`（自动建库 + 起独立后端 + 跑完停掉）；
  它依赖 `CLIPBOARD_LOCK_PORT` 与开发实例错开锁端口

**平台注意**：Windows 保留了 `5141-5240`（吃掉 5173 → Web 端用 **5273**）与
`8903-9002`（吃掉 MinIO 的 9000 → 阶段二换端口）。
排查：`netsh int ipv4 show excludedportrange protocol=tcp`

---

## 8. 开发顺序

**原则：契约优先，后端先行，Web 验证，鸿蒙接入。严格按顺序，不要跳步。**
每一步的细化任务与**当前状态**见 [`docs/roadmap.md`](docs/roadmap.md)——本表只定义顺序。

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

**阶段划分**：阶段一 = 1～6 步（文字）；阶段二 = 图片 + 对象存储；
阶段三 = 文件 + 体验优化；阶段四 = 端到端加密 + 生产部署。

---

## 9. 常见任务操作指引

> 启动、迁移、排错等完整命令见 [`server/README.md`](server/README.md) 与
> [`web/README.md`](web/README.md)，此处只列**跨端容易漏的流程**。

### 添加接口

改 Schema → 改路由 → 确认 `/docs` → `pnpm run gen:api` → 刷新 `docs/api.md`（详见「数据契约」）

### 修改会被测试引入的模块

`tests/*.test.ts` **直接跑源码**（Node 类型擦除），不经过打包：

- `stores/`、`composables/`、`api/`、`utils/` 的导入必须用 **`#src/*` 且带 `.ts` 扩展名**
  （`@/xxx` 会被当裸包名报 `ERR_MODULE_NOT_FOUND`）；只有 `.vue` 与 `main.ts` 用 `@/*`
- 新增测试放 `web/tests/`、以 `.test.ts` 结尾即会被 `pnpm test` 收集
- 改完跑 `pnpm test`，**别只跑 `typecheck`**（`vue-tsc` 会过但 Node 跑不起来）
- ⚠️ 测试运行器**并行**执行各文件：多个套件共用同一账号会互相干扰，需各用独立账号

### 添加/修改数据库模型

1. 在 `app/db/models/` 定义或修改，并在 `models/__init__.py` 导入（注册进 `Base.metadata`）
2. `alembic revision --autogenerate -m "描述"`
3. **逐行检查生成的迁移**（见下方坑）
4. `alembic upgrade head`，确认 `alembic current` 与模型一致（再 autogenerate 应无变更）

> ⚠️ **坑 1：autogenerate 会记录"多余的表"**——开发库里手工建过的临时表会被写成
> `op.drop_table('xxx')`，在干净库（CI、测试库）上必然失败。生成后必须删掉这类噪声语句。
>
> ⚠️ **坑 2：`alembic.ini` 必须保持纯 ASCII**——Windows 上 configparser 按 locale（GBK）
> 读取，中文注释会让 Alembic 直接崩溃。跑迁移建议设 `$env:PYTHONUTF8='1'`。

### 生成 Web 端类型

```powershell
cd web
pnpm run gen:api
```

---

## 10. 参考文档

| 文档 | 内容 |
|------|------|
| [`docs/roadmap.md`](docs/roadmap.md) | **进度、踩坑记录、技术债、环境前置条件、下一步行动** |
| [`docs/api.md`](docs/api.md) | API 契约摘要（含 OpenAPI 导出脚本） |
| [`docs/ws-protocol.md`](docs/ws-protocol.md) | WebSocket 协议 |
| [`server/README.md`](server/README.md) | 后端启动、迁移、数据库结构、排错 |
| [`web/README.md`](web/README.md) | Web 端启动、界面结构、验证步骤 |
| [`README.md`](README.md) | 项目介绍与快速开始 |

---

**给 AI 助手的提示**：
- 本文件只维护**稳定约定**：进度、勾选框、实测记录、版本号流水一律写进 `docs/roadmap.md`。
- 契约涉及的**字段与路径枚举**不要在本文展开，指向 `docs/api.md` 与 `/docs`。
- **源码注释不要引用 roadmap 的 P 编号或本文节号**（易变）；指向稳定载体：
  `app/schemas/`、`.env.example`、`docs/api.md`、`docs/ws-protocol.md`。
- 改动涉及**改名、章节号、路径、命令、依赖版本**时，改完 grep 旧关键词确认引用已同步。
