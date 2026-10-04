# AGENT.md

> 本文件为 AI 编码助手（Claude Code / Cursor / Copilot 等）提供项目上下文、开发规范与任务指引。**每次开始工作前先读本文件**，确保代码风格、目录结构、接口契约保持一致。

---

## 1. 项目概述

**项目名称**：云剪贴板（Cloud Clipboard）

**目标**：跨平台云剪贴板服务，实现多设备间剪贴板内容实时同步。

**客户端**：
- 鸿蒙 App（ArkTS + ArkUI）
- Web 端（React + TypeScript + Vite）

**后端**：FastAPI + PostgreSQL + Redis + WebSocket

**当前阶段**：阶段一 —— 文字剪贴板 MVP

**MVP 范围**：
- 文字内容的上传、查询、删除
- 多端实时同步（WebSocket）
- JWT 认证
- 内容去重

**明确不做（本期）**：
- 图片、文件剪贴板
- 端到端加密
- 团队协作

---

## 2. 技术栈与版本

| 层级 | 技术 | 版本要求 |
|------|------|----------|
| 后端框架 | FastAPI | 最新稳定版 |
| ASGI 服务器 | uvicorn[standard] | 最新稳定版 |
| 数据库 | PostgreSQL | 14+ |
| ORM | SQLAlchemy（async） | 2.0+ |
| 迁移 | Alembic | 最新稳定版 |
| 缓存/广播 | Redis | 6+ |
| 认证 | python-jose + passlib[bcrypt] | - |
| Web 前端 | React + TypeScript + Vite | React 18+ |
| Web 状态 | Zustand | 最新稳定版 |
| HTTP 客户端 | Axios | 最新稳定版 |
| 鸿蒙 | ArkTS + ArkUI | API 12+ |

---

## 3. 目标目录结构

> 目标结构。`server/` 已在第 1 步落地（见下方 ✅ 标注），`web/` 与 `harmony/` 仍为待创建。

```
cloud-clipboard/
├── AGENT.md                  # 本文件
├── README.md                 # 已存在
├── docs/
│   ├── api.md                # API 契约存档 + 导出脚本（契约来源是 schemas/）
│   ├── ws-protocol.md        # WebSocket 协议
│   └── roadmap.md            # 进度、验收记录、已知问题
│
├── infra/                    # ✅ 本地基础设施（第 3 步已落地）
│   ├── docker-compose.yml    # ✅ PostgreSQL 16（宿主 5433 → 容器 5432）
│   └── .env.example          # ✅ 容器账号与端口（第 5 步在此加 Redis）
│
├── scripts/                  # ✅ 运维/验证脚本
│   └── verify_postgres.py    # ✅ 数据库连通性与数据往返验证
│
├── server/                   # ✅ 后端 FastAPI（第 1 步已落地）
│   ├── app/
│   │   ├── main.py           # ✅ 应用入口：注册路由、CORS、OpenAPI 元信息
│   │   ├── core/
│   │   │   ├── config.py     # ✅ 环境变量（pydantic-settings）
│   │   │   └── security.py   # ⬜ 第 4 步：JWT、密码哈希
│   │   ├── db/
│   │   │   ├── base.py       # ⬜ 第 3 步
│   │   │   ├── session.py    # ⬜ 第 3 步
│   │   │   └── models/
│   │   │       ├── user.py       # ⬜ 第 3 步
│   │   │       └── clipboard.py  # ⬜ 第 3 步
│   │   ├── schemas/          # ✅ Pydantic 模型（数据契约）
│   │   │   ├── common.py     #   ContentType / SortOrder / SortBy / PageMeta
│   │   │   ├── user.py
│   │   │   └── clipboard.py
│   │   ├── crud/             # ✅ 数据访问层（当前为内存假数据）
│   │   │   ├── store.py      #   内存存储 + 种子数据
│   │   │   ├── user.py
│   │   │   └── clipboard.py
│   │   ├── routers/          # API 路由
│   │   │   ├── auth.py       # ✅ 注册 / 登录 / 当前用户（假数据）
│   │   │   ├── clipboard.py  # ✅ 剪贴板 CRUD（假数据）
│   │   │   └── ws.py         # ⬜ 第 5 步
│   │   └── services/
│   │       └── ws_manager.py # ⬜ 第 5 步：WebSocket 连接管理
│   ├── tests/
│   ├── alembic/              # ⬜ 第 3 步
│   ├── venv/                 # 虚拟环境（已创建，已加入 .gitignore）
│   ├── requirements.txt      # ✅ fastapi / uvicorn[standard] / pydantic-settings
│   ├── .env.example          # ✅
│   └── README.md             # ✅ 后端启动与目录说明
│
├── web/                      # ✅ Web 端（第 2 步：骨架 + 单端闭环）
│   ├── index.html            # ✅
│   ├── vite.config.ts        # ✅ @ 别名、固定端口 5273
│   ├── tsconfig.json         # ✅
│   ├── package.json          # ✅ imports: #src/* → ./src/*
│   ├── pnpm-workspace.yaml   # ✅ pnpm 11 项目设置（allowBuilds 放行 esbuild）
│   ├── scripts/
│   │   └── generate-api-types.mjs  # ✅ pnpm run gen:api
│   ├── tests/
│   │   └── e2e.test.ts       # ✅ 端到端闭环测试（真实后端，9 用例）
│   ├── src/
│   │   ├── main.tsx          # ✅
│   │   ├── App.tsx           # ✅ 同步按钮 + 搜索/排序 + 手动输入 + 列表
│   │   ├── api/
│   │   │   └── client.ts     # ✅ axios 封装 + token + 错误归一化
│   │   ├── components/       # ✅ ClipboardList / ClipboardItemCard / ManualInput
│   │   ├── hooks/
│   │   │   ├── useClipboard.ts   # ✅ 读剪贴板 → 上传
│   │   │   ├── useCopy.ts        # ✅ 复制回剪贴板
│   │   │   └── useWebSocket.ts   # ⬜ 第 5 步：实时同步（占位）
│   │   ├── pages/            # ⬜ 第 4 步加入登录页时创建
│   │   ├── stores/           # ✅ Zustand：clipboardStore / userStore
│   │   ├── types/
│   │   │   └── api.d.ts      # ✅ 由 OpenAPI 生成，勿手改
│   │   └── utils/
│   │       ├── clipboard.ts  # ✅ 剪贴板读写（自身写入标志 + execCommand 降级）
│   │       └── format.ts     # ✅ 时间/大小/截断
│   └── README.md             # ✅ 启动、验证步骤与规范对照
│
└── harmony/                  # 鸿蒙 App（待创建）
    └── entry/src/main/ets/
        ├── pages/
        ├── components/
        ├── services/
        │   ├── api.ets
        │   ├── websocket.ets
        │   └── clipboardMonitor.ets
        └── models/
            └── ClipboardItem.ets
```

---

## 4. 核心数据契约（目标设计）

**契约是唯一事实来源**。任何字段变更必须先改 `server/app/schemas/`，再同步到 Web 类型和鸿蒙模型。

### ClipboardItem

```python
class ClipboardItemResponse(BaseModel):
    id: str                    # uuid
    user_id: str               # uuid
    title: str                 # 标题；用户未填时服务端生成 "demo · 10-03 12:55"
    content_type: ContentType  # text | image | file
    content: str               # 文字内容或文件 URL
    preview: Optional[str]     # 预览文本
    metadata: Optional[dict]   # {"mime": "text/plain", "size": 1024, ...}
    created_at: datetime
    updated_at: datetime
```

### 关键约定

- 时间统一用 ISO 8601 UTC，格式 `2026-09-27T10:00:00Z`
- `content_hash` **不对外暴露**，仅服务端用于去重
- `title` 由用户填写；**留空时服务端生成** `<用户名> · <月-日 时:分>`（如 `demo · 10-03 12:55`）
- 去重规则：同一用户提交相同 `content`，更新时间戳并广播 `clipboard.updated`，不创建新记录；
  **去重时不覆盖已有标题**（除非本次请求显式传了 `title`）
- 搜索同时匹配 `title` 与 `content`
- 分页参数：`page` 从 1 开始，`size` 默认 20，最大 100

---

## 5. API 契约（目标设计）

完整定义的事实来源是 `server/app/schemas/`（Pydantic Schema）；
在线文档 <http://localhost:8000/docs>，契约存档 [`docs/api.md`](docs/api.md)（含导出脚本）。摘要：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册 |
| POST | `/api/v1/auth/login` | 登录 |
| GET | `/api/v1/auth/me` | 当前用户 |
| POST | `/api/v1/clipboard/items` | 创建（可按 `title` 命名，留空自动生成） |
| GET | `/api/v1/clipboard/items` | 列表（分页/筛选/按标题或内容搜索） |
| GET | `/api/v1/clipboard/items/{id}` | 详情 |
| DELETE | `/api/v1/clipboard/items/{id}` | 删除 |
| DELETE | `/api/v1/clipboard/items` | 清空 |
| POST | `/api/v1/dev/reset` | 重置种子数据（**仅 `ENABLE_DEV_ROUTES=true` 时注册**） |
| WS | `/api/v1/clipboard/ws?token=xxx` | 实时同步 |
| GET | `/health` | 健康检查 |

**改接口时必须做的事**：
1. 更新 Pydantic Schema
2. 重启 FastAPI，确认 `/openapi.json` 更新
3. 重新生成 Web 类型：`npx openapi-typescript http://localhost:8000/openapi.json -o web/src/types/api.d.ts`
4. 同步更新鸿蒙端 `models/ClipboardItem.ets`
5. 刷新 `docs/api.md` 的契约存档（导出脚本见该文件开头）

---

## 6. WebSocket 协议（目标设计）

**连接**：`ws://localhost:8000/api/v1/clipboard/ws?token=<JWT>`

**服务端推送事件**：

| event | data |
|-------|------|
| `clipboard.created` | ClipboardItem |
| `clipboard.updated` | ClipboardItem |
| `clipboard.deleted` | `{ "id": "uuid" }` |
| `clipboard.cleared` | `{}` |
| `pong` | `{}` |

**客户端发送**：`{ "action": "ping" }`

**约定**：
- 心跳间隔 30 秒
- 重连策略：指数退避，首次 1 秒，最大 30 秒
- 重连成功后必须调用 `GET /clipboard/items` 拉取最新列表

---

## 7. 当前进度

> **详细进度、验收记录、已知问题与技术债见 [`docs/roadmap.md`](docs/roadmap.md)。**
> 本文件只维护稳定约定；凡是每完成一步就要改一遍的内容（勾选框、实测记录、版本号），
> 一律写进 roadmap，避免两处不同步。

**当前**：第 1 步（后端骨架 + 数据契约）✅、第 2 步（Web 骨架 + 单端闭环）✅ → **下一步：第 3 步（接入数据库）**。

开工前请先看 `docs/roadmap.md` 的「已知问题」与「环境前置条件」：
那里记录了必须先修的高危项（`DEBUG` 默认值、测试清库风险）和本机实测状态
（Docker 守护进程未运行、5432 端口已被本机 PostgreSQL 18 占用、Redis 未启动）。

---

## 8. 开发规范

### 代码风格

**后端（Python）**：
- 遵循 PEP 8
- 类型注解必须完整
- 使用 `async def` 处理 I/O
- 路由层只做参数校验和调用，业务逻辑放 `services/` 或 `crud/`
- 数据库操作统一走 `crud/`，路由不直接写 SQL

**Web 端（TypeScript）**：
- 使用函数式组件 + Hooks
- 状态管理用 Zustand，避免 prop drilling
- 剪贴板 API 封装在 `utils/clipboard.ts`，组件不直接调 `navigator.clipboard`
- 类型从 `types/api.d.ts` 导入，不手写重复类型

**鸿蒙端（ArkTS）**：
- 剪贴板监听逻辑隔离在 `services/clipboardMonitor.ets`
- 网络请求统一封装在 `services/api.ets`
- 模型字段与后端 Schema 严格对齐

### 提交规范

遵循 Conventional Commits：

```
feat: 新增 WebSocket 广播
fix: 修复去重时未广播的问题
docs: 更新 API 文档
refactor: 抽取 crud 层
test: 补充剪贴板 CRUD 测试
chore: 更新依赖
```

### 分支策略

- `main`：稳定分支
- `feature/*`：功能分支
- `hotfix/*`：紧急修复

---

## 9. 关键约束（必须遵守）

### 安全

- **绝不**在代码中硬编码密钥，使用 `.env`
- `.env` 必须加入 `.gitignore`
- 生产环境必须用 HTTPS / WSS
- JWT 密钥生产环境必须更换

### 剪贴板 API

- 浏览器剪贴板 API **仅在 HTTPS 或 localhost 可用**
- 读取剪贴板**必须由用户手势触发**（点击、Ctrl+V），不能后台自动读
- 写入剪贴板时需设置标志位，避免触发自身监听导致死循环
- 鸿蒙 API 12+ 读取剪贴板需 `READ_PASTEBOARD` 权限；监听用 `on('update')` 无需权限

### 数据一致性

- 任何接口字段变更，必须同步更新三端
- 去重分支也必须广播 WebSocket 消息（易漏）
- 分页默认值：`page=1`，`size=20`

### 性能

- 图片、文件不要 base64 存数据库（阶段二）
- 列表查询必须带分页
- WebSocket 广播按用户隔离，不群发

---

## 10. 开发顺序（严格按此推进）

**原则：契约优先，后端先行，Web 验证，鸿蒙接入。**

### 第 1 步：FastAPI 骨架 + 数据契约

1. 创建 `server/` 目录结构和虚拟环境
2. 安装 `fastapi`、`uvicorn[standard]`
3. 编写 Pydantic Schema（`schemas/clipboard.py`、`schemas/user.py`）
4. 编写假数据路由（`routers/clipboard.py`、`routers/auth.py`）
5. 编写入口 `main.py`，注册路由和 CORS
6. 启动服务，验证 `/docs` 可用
7. 用 Swagger UI 测试假数据 CRUD

**完成标准**：`/docs` 可访问，所有接口返回假数据正常。

### 第 2 步：Web 端骨架 + 单端闭环

1. `web/` 初始化 Vite + React + TS
2. 用 `openapi-typescript` 生成类型
3. 封装 API 客户端（axios）
4. 封装剪贴板读写工具
5. 实现列表页 + 同步按钮
6. 用假数据后端跑通「读取剪贴板 → 上传 → 列表展示 → 点击复制」

**完成标准**：Web 端单端闭环可用（数据存内存即可）。

### 第 3 步：接入数据库

1. 创建 `docker-compose.yml`（PostgreSQL + Redis）
2. 安装 `sqlalchemy[asyncio]`、`asyncpg`、`alembic`
3. 配置 `db/session.py`、`db/base.py`
4. 定义 SQLAlchemy 模型
5. 初始化 Alembic，生成并执行迁移
6. 实现 `crud/` 层
7. 替换路由中的假数据为真实 CRUD
8. 验证重启后数据不丢失

**完成标准**：数据持久化，`/docs` 接口全部正常。

### 第 4 步：JWT 认证

1. `core/security.py` 实现密码哈希、JWT 签发/校验
2. 实现真实的注册、登录接口
3. 编写认证依赖 `get_current_user`
4. 给剪贴板路由加认证保护
5. Web 端加登录页，token 存 localStorage

**完成标准**：未带 token 请求返回 401，带 token 正常。

### 第 5 步：WebSocket 实时同步

1. `services/ws_manager.py` 实现连接管理
2. `routers/ws.py` 实现端点（token 校验）
3. 创建剪贴板项时广播
4. Web 端接入 WebSocket，实时更新列表
5. 验证多标签页同步

**完成标准**：标签 A 上传，标签 B 秒级收到。

### 第 6 步：内容去重

1. 创建时计算 `content_hash`
2. 相同内容更新时间戳，不创建新记录
3. 去重分支也广播 `clipboard.updated`
4. Web 端处理 `updated` 事件

**完成标准**：连续复制相同内容只产生一条记录。

### 第 7 步：鸿蒙 App

1. DevEco 创建项目
2. 配置网络权限
3. 封装 HTTP 客户端和 WebSocket
4. 实现剪贴板读写
5. 实现剪贴板变化监听
6. 列表页展示 + 手动同步
7. 接入 WebSocket

**完成标准**：鸿蒙与 Web 双向实时同步。

### 第 8 步：联调与测试

1. 三端同时运行，验证双向同步
2. 补充后端单元测试
3. 修复边界问题

---

## 11. 常见任务操作指引

### 启动后端（待创建后）

```bash
cd server
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

访问 `http://localhost:8000/docs` 验证。

### 添加新接口

1. 在 `app/schemas/` 定义请求/响应模型
2. 在 `app/routers/` 添加路由函数
3. 在 `app/main.py` 注册路由（如新模块）
4. 启动服务，确认 `/docs` 出现新接口
5. 刷新 `docs/api.md` 的契约存档（导出脚本见该文件开头）
6. 通知前端重新生成类型

### 添加数据库模型

1. 在 `app/db/models/` 定义 SQLAlchemy 模型
2. 在 `app/db/base.py` 的 metadata 中导入（确保 Alembic 能发现）
3. 生成迁移：`alembic revision --autogenerate -m "描述"`
4. 检查生成的迁移文件，确认无误
5. 执行：`alembic upgrade head`

### 生成 Web 端类型

```bash
cd web
npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.d.ts
```

### 调试 WebSocket

用 `wscat` 或浏览器控制台：

```bash
npx wscat -c "ws://localhost:8000/api/v1/clipboard/ws?token=<JWT>"
```

发送 `{"action":"ping"}`，应收到 `{"event":"pong"}`。

---

## 12. 已知风险与注意事项

| 风险 | 说明 | 应对 |
|------|------|------|
| 浏览器剪贴板 API 兼容性 | 部分浏览器不支持 `read()` | 封装降级逻辑，优先 `paste` 事件 |
| 鸿蒙剪贴板 API 12+ 权限管控 | 读取需 `READ_PASTEBOARD` | 监听用 `on('update')` 无需权限，读取需申请 |
| 浏览器剪贴板需 HTTPS | 生产必须配置 | 部署时处理 |
| WebSocket 循环同步 | 写回剪贴板触发监听 | 设标志位区分本地/远端写入 |
| 多实例广播不一致 | 后期多副本部署 | 引入 Redis Pub/Sub |
| 端到端加密与搜索冲突 | 服务端无法搜明文 | 搜索仅在客户端本地做 |

---

## 13. 下一步任务（现在就开始）

**当前应该做：第 3 步 —— 接入数据库**

具体操作：

1. 决定数据库方案：复用本机 PostgreSQL 18（5432 已被占用），或启动 Docker Desktop 后用容器
2. 安装 `sqlalchemy[asyncio]`、`asyncpg`、`alembic`
3. 配置 `app/db/session.py`、`app/db/base.py`
4. 定义 SQLAlchemy 模型（`db/models/user.py`、`db/models/clipboard.py`）
5. 初始化 Alembic，生成并执行迁移
6. 实现 `crud/` 层，替换路由中的内存假数据
7. 验证重启后数据不丢失

**开工前必须先处理**（详见 `docs/roadmap.md`）：

- **P1**：`DEBUG` 默认值已改为 `false`，开发路由改用 `ENABLE_DEV_ROUTES`；
  接库时需把 `dev/reset` 从"重置内存"改为"清空测试库"，并确认生产环境不会注册
- **P2**：`web/tests/e2e.test.ts` 会清库，必须先隔离到独立的测试数据库

**完成标准**：数据持久化，`/docs` 接口全部正常，重启服务后数据不丢失。

---

## 14. 参考文档

- `README.md` —— 项目说明与快速开始
- `docs/api.md` —— API 契约存档（含导出脚本，契约来源是 `server/app/schemas/`）
- `docs/ws-protocol.md` —— WebSocket 协议
- `docs/roadmap.md` —— **项目进度、验收记录、已知问题与技术债**

---

**最后更新**：2026-10-03（文档整理：进度迁至 `docs/roadmap.md`）  
**维护者**：云剪贴板项目组  
**给 AI 助手的提示**：
- **进度看 `docs/roadmap.md`**，不要往本文件里加勾选框；本文件只维护稳定约定。
- 已完成：第 1 步（后端骨架 + 契约）、第 2 步（Web 骨架 + 单端闭环）。下一步：第 3 步（接入数据库）。
- 第 3 步开工前先处理 `docs/roadmap.md` 里的 P1、P2 两个高危项。
- 请严格按照第 10 节的开发顺序推进，不要跳步。
- 每次修改代码前，先确认改动是否影响接口契约。如影响，按第 5 节流程同步三端。
- 每完成一个步骤，主动更新第 7 节「当前进度」的勾选状态。
