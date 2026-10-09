# 云剪贴板（Cloud Clipboard）

一个跨平台的云剪贴板服务，实现多设备间剪贴板内容的实时同步。支持 **鸿蒙 App**、**Web 端** 两种客户端，后端基于 **FastAPI + PostgreSQL**。第一阶段聚焦文字剪贴板，后续扩展图片、文件等类型。

---

## ✨ 特性

- 🔄 **实时同步**：基于 WebSocket，多设备剪贴板内容秒级同步（第 5 步实现）
- 📱 **跨平台**：鸿蒙 App + Web 端，覆盖手机与桌面场景
- 📋 **多类型内容**：文字（已支持）、图片、文件（阶段二 / 阶段三）
- 🔍 **历史管理**：查看、搜索、筛选、删除历史剪贴板记录
- 🔐 **安全认证**：JWT 认证（第 4 步），规划中的端到端加密
- 🎯 **去重优化**：相同内容不重复存储，自动更新时间戳（已在数据库层生效）
- 💾 **数据持久化**：PostgreSQL 存储，重启不丢数据

---

## 🏗️ 架构概览

```
┌──────────────┐        ┌──────────────┐
│  鸿蒙 App    │        │   Web 端     │
│  (ArkTS)     │        │ (Vue 3 + TS) │
│   ⬜ 未创建    │        │    ✅ 已跑通  │
└──────┬───────┘        └──────┬───────┘
       │                       │
       │   HTTPS / WSS         │
       └───────────┬───────────┘
                   │
           ┌───────▼────────┐
           │  FastAPI 后端  │
           │  + WebSocket   │   ← WebSocket 第 5 步
           └───────┬────────┘
                   │
        ┌──────────┼ ─ ─ ─ ─ ─ ┐
        │          │           │
   ┌────▼───┐ ┌───▼────┐ ┌ ─ ─▼─ ─ ┐
   │Postgres│ │ Redis  │ │  MinIO  │
   │  数据  │ │ 广播   │ │ 对象存储 │
   │ ✅ 启用│ │⬜ 第5步│ │⬜ 阶段二│
   └────────┘ └────────┘ └ ─ ─ ─ ─ ┘
    宿主 5433              （阶段二启用）
```

> 实线框 = 阶段一在用；虚线框 = 阶段二 / 第 5 步才启用。
> 端口说明：Postgres 走后端宿主 **5433**（本机原生 PostgreSQL 占用 5432）；Redis 6379 当前空闲但**未安装**；MinIO 常用 9000 落在 Windows 保留端口段内，阶段二需另选端口。

---

## 📁 项目结构

```
cloud-clipboard/
├── AGENTS.md        # AI 编码助手的项目约定（技术栈、契约、规范、开发顺序）
├── README.md        # 本文件
├── server/          # 后端 FastAPI + PostgreSQL
├── web/             # Web 端 (Vue 3 + TS + Vite)
├── harmony/         # ⬜ 鸿蒙 App (ArkTS)，尚未创建
├── infra/           # 本地基础设施（docker-compose.yml）
├── scripts/         # 数据库连通性与往返验证脚本
└── docs/            # roadmap.md / api.md / ws-protocol.md
```

各子项目的详细结构见对应目录下的 `README.md`（[`server/README.md`](server/README.md)、[`web/README.md`](web/README.md)）。

---

## 🚀 快速开始

> 以下步骤只覆盖**当前可跑通**的部分：PostgreSQL 容器 + 后端 + Web 端。
> Redis 与 MinIO 属阶段二 / 第 5 步，现在**不需要安装**，见文末「阶段二准备」。

### 环境要求（阶段一）

| 组件 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.10+（实测 3.13.7） | 后端 |
| Node.js | 18+（实测 24.11.1） | Web 端 |
| **pnpm** | 11.x（实测 11.7.0） | **本项目统一使用 pnpm，不要用 npm** |
| Docker | 20+ | 跑 PostgreSQL 容器 |
| PostgreSQL | 16（走容器，宿主端口 5433） | 不需要本机原生安装 |
| DevEco Studio | 4.0+ | 仅鸿蒙开发需要（鸿蒙端尚未创建） |

> 📌 **包管理器约定**：仓库里只有 `web/pnpm-lock.yaml`，**没有 `package-lock.json`**。
> 项目级设置写在 `web/pnpm-workspace.yaml`（`allowBuilds` 放行 `esbuild` 与 `vue-demi`，
> 不授权会在安装时报 `ERR_PNPM_IGNORED_BUILDS`）。请一律用 `pnpm`，不要混用 `npm`。

### 1. 克隆仓库

```bash
git clone https://github.com/your-org/cloud-clipboard.git
cd cloud-clipboard
```

### 2. 启动本地数据库（PostgreSQL 16 容器）

```powershell
# 仓库根目录执行
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml ps        # 等 healthcheck 变成 healthy

# 连通性验证（可选）
server\venv\Scripts\python.exe scripts\verify_postgres.py
```

> Docker Hub 当前可能不可达，compose 里用的是本地已有的 `postgres:16` 镜像。
> 需要强制离线启动时加 `--pull never`。

### 3. 启动后端

```powershell
cd server

# 复制环境变量模板（Windows PowerShell）
Copy-Item .env.example .env

# 创建虚拟环境并安装依赖
python -m venv venv
.\venv\Scripts\Activate.ps1          # bash: source venv/bin/activate
pip install -r requirements.txt

# 数据库迁移 + 建表 + 演示用户 + 种子数据
$env:PYTHONUTF8='1'                  # Windows 上跑 Alembic 建议设置（见 AGENTS.md 第 11 节）
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m scripts.init_db

# 启动服务
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

访问 <http://127.0.0.1:8000/docs> 查看 API 文档。

> ⚠️ **`init_db` 不能跳过**：它负责播种演示账号 `demo`（口令由 `DEMO_PASSWORD` 控制）。
> 真实登录已接入，演示用户不再享有"免登录"特权——不播种就没有可用的本地账号，
> 需要自己走 `/api/v1/auth/register` 注册。
> 该脚本末尾带 `if __name__ == "__main__":`，并在内部把 `server/` 加进 `sys.path`，
> 所以 `-m scripts.init_db` 这种模块方式可以直接用；等价的直接运行方式是
> `.\venv\Scripts\python.exe scripts\init_db.py`（同样在 `server/` 目录下执行）。
> 常用参数：`--no-seed`（不写种子数据）、`--drop`（⚠️ 先删表）、
> `--database <URL>`（覆盖 `DATABASE_URL`，例如指向 `clipboard_test` 库）。
> ⚠️ `--drop` 只对**目标库名含 `test`** 的库放行；确要清空开发库需先设 `ALLOW_DROP_DEV=1`，
> 否则脚本会拒绝执行并以 `exit 2` 退出。
> ⚠️ 用 `127.0.0.1` 而不是 `localhost` 访问——浏览器剪贴板 API 只在 HTTPS 或 localhost 下可用。

### 4. 启动 Web 端

```powershell
cd web

# 复制环境变量模板
Copy-Item .env.example .env

# 安装依赖（必须用 pnpm）
pnpm install

# 启动开发服务器
pnpm dev
```

访问 <http://127.0.0.1:5273> 打开 Web 端。

> ⚠️ 端口固定 **5273**（`vite.config.ts` 里 `strictPort: true`）。
> 不要改回 5173——它落在 Windows 保留端口段 `5141-5240` 内，会报 `EACCES / WinError 10013`。

### 5. 启动鸿蒙 App

⬜ **鸿蒙端尚未创建**，`harmony/` 目录目前为空。届时步骤为：

1. 打开 **DevEco Studio**
2. 选择 `File > Open`，打开 `harmony/` 目录
3. 等待依赖同步完成
4. 选择模拟器或真机，点击运行

---

## 🔧 配置说明

### 后端环境变量（`server/.env`）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `APP_NAME` | 服务名 | `Cloud Clipboard` |
| `APP_ENV` | 运行环境标识 | `development` |
| `DEBUG` | 是否暴露错误详情（**生产必须 false**） | `false` |
| `ENABLE_DEV_ROUTES` | 开发/测试辅助路由（`/api/v1/dev/*`）开关。与 `DEBUG` 解耦：**`dev/reset` 会删数据**，生产必须 false | `false` |
| `API_V1_PREFIX` | API 前缀 | `/api/v1` |
| `DATABASE_URL` | PostgreSQL 连接串（容器宿主端口 5433） | `postgresql+asyncpg://clipboard:clipboard@127.0.0.1:5433/clipboard` |
| `DB_ECHO` | 是否把每条 SQL 打进日志（排查用） | `false` |
| `DEMO_USER_ID` | 演示用户 UUID（本地开发/测试用，不再是"免登录"身份） | 见 `.env.example` |
| `DEMO_USERNAME` | 演示用户名 | `demo` |
| `DEMO_EMAIL` | 演示用户邮箱 | `demo@cloud-clipboard.dev` |
| `DEMO_PASSWORD` | 演示账号登录口令（由 `init_db` / `dev/reset` 播种） | `demo1234` |
| `CORS_ORIGINS` | 允许跨域的来源（JSON 数组或逗号分隔） | `["http://localhost:5273", ...]` |
| `REDIS_URL` | Redis 连接串（第 5 步启用，当前注释掉） | - |
| `JWT_SECRET` | JWT 密钥。**生产必须替换**：`APP_ENV=production` 时若仍是默认值或短于 32 字符，后端会拒绝启动 | `dev-only-...`（开发用） |
| `JWT_ALGORITHM` | JWT 算法 | `HS256` |
| `JWT_EXPIRE_MINUTES` | Token 有效期（分钟） | `10080`（7 天） |
| `TEST_DATABASE_URL` | 后端 pytest 用的独立测试库（第 8 步启用） | `...5433/clipboard_test` |

> ⚠️ 本地要跑 `web` 的端到端测试（会调用 `dev/reset` 恢复种子数据）时，
> 需在 `server/.env` 里设 `ENABLE_DEV_ROUTES=true`。**该接口是清库操作，生产环境永远不要开。**
> 另：e2e 目前打的仍是开发库，重置会清掉开发库数据（见 [`docs/roadmap.md`](docs/roadmap.md) 的 P2）。

### Web 端环境变量（`web/.env`）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VITE_API_BASE_URL` | 后端 API 地址 | `http://127.0.0.1:8000` |
| `VITE_WS_URL` | WebSocket 地址（第 5 步启用） | `ws://127.0.0.1:8000` |
| `VITE_AUTH_TOKEN` | 认证令牌覆盖值（一般留空，令牌由登录后写入 localStorage；仅自动化测试需要预置） | 空 |

> 只有 `VITE_` 前缀的变量会被注入前端代码。

---

## 📖 核心使用流程

### Web 端同步剪贴板

1. 打开 Web 端（第 4 步后需先登录）
2. 点击「同步剪贴板」按钮，或直接在页面 `Ctrl+V`
3. 内容自动上传到云端
4. 其他设备（鸿蒙 App、其他浏览器标签）实时收到更新（第 5 步 WebSocket）

### 鸿蒙 App 同步剪贴板（尚未实现）

1. 登录鸿蒙 App
2. 在任意应用复制内容
3. App 自动捕获并上传（需开启同步开关）
4. 其他设备实时收到更新

### 写回剪贴板

- **Web 端**：点击历史记录的「复制」按钮
- **鸿蒙 App**：点击历史记录，自动写入系统剪贴板

---

## 🔌 API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/auth/register` | 用户注册（落库 + 唯一性校验，**直接返回令牌**） |
| `POST` | `/api/v1/auth/login` | 用户登录（`username` 支持用户名或邮箱，错误统一 401） |
| `GET` | `/api/v1/auth/me` | 当前用户 |
| `POST` | `/api/v1/clipboard/items` | 创建剪贴板项（`title` 留空时自动生成，按 `timezone` 显示本地时间） |
| `PATCH` | `/api/v1/clipboard/items/{id}` | 更新（自动保存复用草稿，避免中间态产生多行） |
| `GET` | `/api/v1/clipboard/items` | 获取列表（分页/筛选/按标题或内容搜索/排序） |
| `GET` | `/api/v1/clipboard/items/{id}` | 获取详情 |
| `DELETE` | `/api/v1/clipboard/items/{id}` | 删除单条 |
| `DELETE` | `/api/v1/clipboard/items` | 清空 |
| `POST` | `/api/v1/dev/reset` | ⚠️ 删数据并重建种子（仅 `ENABLE_DEV_ROUTES=true` 时注册） |
| `GET` | `/api/v1/dev/db` | 探测当前连接的数据库（仅 dev 路由开启时） |
| `GET` | `/` | 服务信息 |
| `GET` | `/health` | 健康检查 |
| `WS` | `/api/v1/clipboard/ws` | ⬜ 实时同步（**第 5 步**，当前未实现） |
| `POST` | `/api/v1/clipboard/upload` | ⬜ 上传图片/文件（**阶段二**，当前未实现） |

交互式文档见 <http://127.0.0.1:8000/docs>；契约存档见 [`docs/api.md`](docs/api.md)，WebSocket 协议见 [`docs/ws-protocol.md`](docs/ws-protocol.md)。

---

## 🗺️ 路线图

阶段划分与 [`docs/roadmap.md`](docs/roadmap.md) 一致：

| 阶段 | 内容 | 状态 |
|------|------|------|
| 阶段一 | 文字剪贴板 MVP：上传/查询/删除 + 实时同步 + JWT + 去重 | 🚧 进行中 |
| 阶段二 | 图片剪贴板 + 对象存储 | 📋 计划中 |
| 阶段三 | 文件剪贴板 + 体验优化 | 📋 计划中 |
| 阶段四 | 端到端加密 + 生产部署 | 📋 计划中 |

阶段一拆成 8 个开发步骤（顺序定义见 [`AGENTS.md`](AGENTS.md) 第 10 节）。
**具体步骤进度、验收记录、已知问题与技术债见 [`docs/roadmap.md`](docs/roadmap.md)。**

---

## 🧪 测试

### 后端测试（尚未建立）

```powershell
cd server
.\venv\Scripts\python.exe -m pytest                          # 运行所有测试
.\venv\Scripts\python.exe -m pytest --cov=app tests/         # 带覆盖率
```

> `tests/conftest.py` 已就绪（默认打 `clipboard_test` 库），但 pytest 依赖尚未安装。

### Web 端

```powershell
cd web
pnpm test           # 端到端测试（Node 类型擦除直接跑源码 + 真实后端/数据库）
pnpm typecheck      # vue-tsc --noEmit
pnpm build          # 类型检查 + 构建
```

> Web 端**没有**配置 lint 脚本，别照搬其他项目的 lint 命令。
> 注意：`pnpm test` 里的破坏性用例需在 `server/.env` 设 `ENABLE_DEV_ROUTES=true`，
> 否则会被跳过（`E2E_ALLOW_DESTRUCTIVE=1` 控制是否执行清空用例）。

### 鸿蒙 App（尚未实现）

在 DevEco Studio 中使用内置测试框架运行 `entry/src/ohosTest/` 下的用例。

---

## 🐳 部署

> ⬜ **阶段四**：`infra/docker-compose.prod.yml` 与 `infra/README.md` 尚未创建。
> 下面的命令是目标形态，当前不可执行。

```bash
cd infra
docker compose -f docker-compose.prod.yml up -d
```

### 生产环境要求

- 使用 HTTPS / WSS（剪贴板 API 依赖安全上下文）
- 修改默认 `JWT_SECRET`（第 4 步引入）
- 保持 `DEBUG=false` 与 `ENABLE_DEV_ROUTES=false`（后者是清库接口的开关）
- 对象存储生命周期策略（阶段二，配合 MinIO 等）
- 数据库定期备份

---

## 🤝 贡献指南

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交变更：`git commit -m "feat: add your feature"`
4. 推送分支：`git push origin feature/your-feature`
5. 提交 Pull Request

### 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

- `feat:` 新功能
- `fix:` 修复
- `docs:` 文档
- `refactor:` 重构
- `test:` 测试
- `chore:` 杂项

### 代码审查

所有 PR 需至少 1 人 review 通过后方可合并。

---

## 📚 相关文档

- [`AGENTS.md`](AGENTS.md) —— 项目约定：技术栈、目录结构、数据契约、开发规范与顺序
- [`docs/roadmap.md`](docs/roadmap.md) —— **当前进度、验收记录、已知问题与技术债**
- [`docs/api.md`](docs/api.md) —— API 契约存档（含导出脚本）
- [`docs/ws-protocol.md`](docs/ws-protocol.md) —— WebSocket 协议
- [`server/README.md`](server/README.md) —— 后端启动与目录说明
- [`web/README.md`](web/README.md) —— Web 端启动、界面结构与验证步骤

---

## ⚠️ 注意事项

- **HTTPS 要求**：浏览器剪贴板 API 仅在 HTTPS 或 localhost 下可用
- **用户手势**：读取剪贴板必须由用户主动触发，无法后台自动读取
- **循环同步**：写回剪贴板时需过滤自身触发的变更，避免死循环
- **Windows 保留端口段**：`5141-5240`（吃掉 5173）、`8903-9002`（吃掉 MinIO 9000）等区间无法绑定。
  排查命令：`netsh int ipv4 show excludedportrange protocol=tcp`
- **存储成本**：图片/文件建议配置对象存储生命周期策略，避免成本失控（阶段二）

---

## 🧱 阶段二准备（当前不需要）

以下组件属**阶段二 / 第 5 步**，阶段一不要安装：

| 组件 | 现状 | 启用时机与注意 |
|------|------|----------------|
| Redis | ⬜ **未安装**（6379 端口空闲） | 第 5 步 WebSocket 广播需要时引入；`infra/docker-compose.yml` 届时补服务，`server/.env.example` 里有注释掉的 `REDIS_URL` |
| MinIO | ⚠️ **端口冲突** | 常用 9000 落在 Windows 保留段 `8903-9002` 内，阶段二需另选端口（如 9010） |
| `infra/docker-compose.prod.yml` | ⬜ 未创建 | 阶段四生产部署 |
| `.github/`（CI） | ⬜ 未创建 | roadmap 未排期，暂不在结构图中 |

---

## 📄 许可证

⬜ **待补**：`LICENSE` 文件尚未加入仓库。

---

## 📮 联系方式

- 问题反馈：[GitHub Issues](https://github.com/your-org/cloud-clipboard/issues)
- 邮箱：your-email@example.com

---

**⭐ 如果这个项目对你有帮助，欢迎 Star！**
