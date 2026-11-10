# AGENTS.md

> 本文件为 AI 编码助手（Claude Code / Cursor / Copilot / Gemini CLI / Codex 等）提供**稳定约定**：
> 项目范围、事实源、不可违反的约束、代码规范与文档入口。
> **进度、验收记录、踩坑、技术债一律看 [`docs/roadmap.md`](docs/roadmap.md)。**

---

## 1. 项目与范围

**云剪贴板（Cloud Clipboard）**：多设备间文字剪贴板内容实时同步。

- 当前交付：**Web 端**（桌面两栏 / `≤900px` 单栏页签），用户手动粘贴/输入后保存。
- 同一构建产物包含 **`/admin` 后台管理**（管理员专用）：用户 / 剪贴板 / 邀请码 / 审计；
  权限由后端 `is_admin` 校验，前端判断只用于展示。
- 范围：阶段一只做文字；图片、文件剪贴板属后续阶段。
- Web 端**不读取系统剪贴板**，也不做后台监听。
- 移动端复用同一个 SPA；本期只做响应式，不做 PWA 或平板专项。
- 鸿蒙 App 代码保留、**暂停上架**；恢复时见 [`harmony/README.md`](harmony/README.md)。
- 开发原则：**契约优先，后端先行，Web 验证**。

---

## 2. 事实源与技术栈

- **数据契约**：`server/app/schemas/`；摘要 [`docs/api.md`](docs/api.md)，在线 `/docs`。
- **WebSocket 协议**：[`docs/ws-protocol.md`](docs/ws-protocol.md)。
- **依赖版本**：`server/requirements.txt`、`web/package.json`，本文件不重复。
- 后端：FastAPI + PostgreSQL + SQLAlchemy 2.x（async）+ Alembic + JWT。
- Web：Vue 3 + TypeScript + Vite + Pinia（setup store）+ Axios。
- 广播：进程内 `ConnectionManager`；Redis 本阶段不引入。

---

## 3. 目录职责

```
cloud-clipboard/
├── server/   # FastAPI：路由、schemas、crud、services、模型/迁移、pytest
├── web/      # Vue SPA：用户端 + /admin 管理端、store、composables、测试
├── harmony/  # 鸿蒙 App（暂停上架，代码保留）
├── docs/     # api.md / ws-protocol.md / admin.md / roadmap.md / deployment.md
├── infra/    # PostgreSQL 容器
└── scripts/  # 连通性、局域网启动、Web 隔离测试
```

具体文件用 `ls` 查看；启动、迁移、排错分别见 `server/README.md` 与 `web/README.md`。

---

## 4. 不可违反的约束

### 4.1 数据契约

- 时间统一 ISO 8601 UTC，数据库列用 `timestamptz`；标题时区只影响展示文本。
- `content_hash` 不对外暴露。
- 同一用户提交相同 `content`：只刷新 `updated_at`、不新建记录，且**不覆盖已有标题**
  （除非显式传 `title`）；去重分支**也必须广播** `clipboard.updated`。
- 搜索同时匹配 `title` 与 `content`；分页 `page` 从 1 开始，`size` 默认 20、最大 100。
- 列表排序：后端 `sort_by` 默认是 `created_at`，**Web 端必须显式传 `updated_at`**。
- 图片、文件不要 base64 存数据库（阶段二）；列表查询必须带分页。

**改接口顺序**：先改 `server/app/schemas/` → 涉及表结构则生成迁移并逐行检查 →
`pnpm run gen:api` → 刷新 `docs/api.md`。

### 4.2 API 与 WebSocket

- 路径与参数见 [`docs/api.md`](docs/api.md) / `/docs`；开发路由仅在 `ENABLE_DEV_ROUTES=true` 时注册。
- ⚠️ WS token 走 query string 会被 uvicorn 访问日志明文记录，必须脱敏；
  **不能用 `logging.Filter` 改写 `record.args`**（`AccessFormatter` 要求恰好 5 个字段）。
- ⚠️ 广播是进程内实现，**必须单 worker**；守卫必须包含**固定端口独占**——
  uvicorn 的 CLI `--workers N` 不写进环境变量，只查 `WEB_CONCURRENCY` 会漏掉常见手误。
- 广播**按用户隔离，不群发**。

### 4.3 安全

- **绝不**硬编码密钥，一律走 `.env`；`.env` 必须被 `.gitignore` 忽略，迁移配置不写连接串。
- 生产必须 HTTPS / WSS；JWT 密钥生产必须更换。
- **后台管理端只允许内网 / VPN / IP 白名单访问**（`/admin` 与 `/api/v1/admin/` 同时限制），
  管理员令牌使用 `ADMIN_JWT_EXPIRE_MINUTES`（默认 12 小时）；普通用户访问管理接口返回 403。
- 会删数据的开发辅助接口必须由**独立开关**控制，不要复用 `DEBUG`。

### 4.4 测试隔离

- **测试库名必须含 `test`**：名字不含 `test` 的库不允许执行破坏性用例。
- **每套测试各用一个库**，开发库不得用于破坏性测试。
- 具体库名、隔离脚本与运行方式见 `web/README.md`、`server/README.md`。

---

## 5. 代码规范

**后端（Python）**

- 遵循 PEP 8；类型注解完整；I/O 一律 `async def`。
- 路由层只做参数校验与调用，业务逻辑放 `services/` 或 `crud/`；**路由不直接写 SQL**。

**Web 端（Vue 3 + TypeScript）**

- 组件一律 `<script setup lang="ts">`；状态管理用 Pinia setup store，避免 prop drilling。
- 可复用逻辑放 `src/composables/`，命名 `useXxx`。
- 剪贴板 API 封装在 `utils/clipboard.ts`，组件不直接调 `navigator.clipboard`。
- 组件不直接调 axios，统一经 `api/client.ts`；类型从 `types/api.d.ts` 导入。
- 响应式优先 `ref`；不用 `v-html` 渲染剪贴板内容。
- **布局统一，不拆移动端工程**：桌面两栏、`≤900px` 单栏 + 顶部「历史 / 输入」页签；
  两个面板始终挂载，页签只切显示；移动端默认「历史记录」，保存后不自动跳页。
  设备差异只允许放在视图层（`App.vue` + `styles.css`），store / composables / api 不感知设备。

**测试相关**

- `tests/*.test.ts` 直接跑源码：`.vue` / `main.ts` 用 `@/*`；
  **store / composables / api / utils 必须用 `#src/*.ts`**，否则 Node 报模块找不到。
- 改完跑 `pnpm test`，不要只跑 `typecheck`。
- 测试文件并行执行：多个套件共用账号会互相干扰，需各用独立账号。

**鸿蒙端（ArkTS）**

- 暂停上架；恢复维护时按 [`harmony/README.md`](harmony/README.md) 执行。

**提交与分支**

- Conventional Commits：`feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:`。
- `master` 稳定；功能分支 `feature/*`，紧急修复 `hotfix/*`。

---

## 6. 验证

- 后端：`python -m pytest`（独立测试库）。
- Web：`.\scripts\run_web_tests.ps1`（隔离库，推荐）或 `pnpm test`；
  `pnpm typecheck` / `pnpm build`。
- 命令细节、迁移步骤、端口与排错见 `server/README.md`、`web/README.md`。

---

## 7. 文档地图

| 文档 | 内容 |
|------|------|
| [`docs/roadmap.md`](docs/roadmap.md) | **进度、踩坑、技术债、环境前置条件、下一步行动** |
| [`docs/api.md`](docs/api.md) | API 契约摘要（含 OpenAPI 导出脚本） |
| [`docs/ws-protocol.md`](docs/ws-protocol.md) | WebSocket 协议 |
| [`docs/admin.md`](docs/admin.md) | 后台管理设计与实现（用户/剪贴板/邀请码/审计） |
| [`docs/deployment.md`](docs/deployment.md) | 生产部署方案（Docker Compose + Nginx） |
| [`docs/deploy-image-transfer.md`](docs/deploy-image-transfer.md) | 方案 B：本地出包、制品传输与回滚 |
| [`server/README.md`](server/README.md) | 后端启动、迁移、数据库结构、排错 |
| [`web/README.md`](web/README.md) | Web 端启动、桌面/移动布局、验证步骤 |
| [`harmony/README.md`](harmony/README.md) | 鸿蒙 App（暂停上架）构建与签名 |
| [`README.md`](README.md) | 项目介绍与快速开始 |

---

## 8. 给 AI 助手

- 本文件只维护**稳定约定**：进度、勾选框、实测记录、版本流水一律写 `docs/roadmap.md`。
- 契约字段与路径枚举不在本文展开，指向 `docs/api.md` 与 `/docs`。
- **源码注释不要引用 roadmap 的 P 编号或本文节号**；指向稳定载体：
  `app/schemas/`、`.env.example`、`docs/api.md`、`docs/ws-protocol.md`。
- 改动涉及**改名、路径、命令、依赖版本**时，改完 grep 旧关键词确认引用已同步。
