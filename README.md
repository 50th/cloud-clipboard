# 云剪贴板（Cloud Clipboard）

跨平台云剪贴板：多设备间剪贴板内容实时同步。客户端为 **Web 端**（已可正常使用）与
**鸿蒙 App**（已编译通过，待签名上机验证）；后端为 **FastAPI + PostgreSQL + WebSocket**。

## 项目进度

**阶段一功能已完成：目前支持文字的剪贴板同步。** 图片与文件属后续阶段。

| 阶段 | 内容 | 状态 |
|------|------|------|
| 阶段一 | 文字：上传 / 查询 / 删除 + 实时同步 + 登录 + 去重 | ✅ 已完成 |
| 阶段二 | 图片 + 对象存储 | 📋 计划中 |
| 阶段三 | 文件 + 体验优化 | 📋 计划中 |
| 阶段四 | 端到端加密 + 生产部署 | 📋 计划中 |

| 客户端 | 状态 |
|--------|------|
| Web 端 | ✅ 可正常使用（登录、粘贴、历史、复制、多标签实时同步） |
| 鸿蒙 App | 🚧 代码完成且**编译通过**；安装运行需先配置签名，见 [`harmony/README.md`](harmony/README.md) |

细节（含踩坑记录与技术债）见 [`docs/roadmap.md`](docs/roadmap.md)。

---

## 架构

```
┌──────────────┐        ┌──────────────┐
│  鸿蒙 App    │        │   Web 端     │
│ 🚧 已编译通过 │        │  ✅ 可正常用  │
└──────┬───────┘        └──────┬───────┘
       │   HTTPS / WSS         │
       └───────────┬───────────┘
           ┌───────▼────────┐
           │  FastAPI 后端  │
           │  + WebSocket   │
           └───────┬────────┘
                   │
            ┌──────▼──────┐
            │  PostgreSQL │  ← 宿主 5433（5432 被本机原生 PostgreSQL 占用）
            └─────────────┘
```

Redis 与 MinIO 属后续阶段，本阶段**不要安装**（见 [`docs/roadmap.md`](docs/roadmap.md)）。

---

## 快速开始

### 环境要求

Python 3.13、Node 24 + pnpm、Docker Desktop。实测版本见 [`docs/roadmap.md`](docs/roadmap.md)。

### 1. 启动数据库（PostgreSQL 16 容器）

```powershell
# 仓库根目录执行
docker compose -f infra/docker-compose.yml up -d

# 连通性验证（可选；需先完成第 2 步的 venv）
server\venv\Scripts\python.exe scripts\verify_postgres.py
```

完整命令与端口说明见 `infra/docker-compose.yml` 顶部注释。

### 2. 启动后端

```powershell
cd server
Copy-Item .env.example .env           # 首次需要
python -m venv venv                   # 首次需要
.\venv\Scripts\python.exe -m pip install -r requirements.txt

$env:PYTHONUTF8='1'                   # Windows 上跑 Alembic 需要
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m scripts.init_db     # 建演示账号 + 种子数据

# ⚠️ 必须单 worker：WebSocket 广播是进程内实现
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

交互式文档 <http://127.0.0.1:8000/docs>。启动、迁移与排错详见 [`server/README.md`](server/README.md)。

### 3. 启动 Web 端

```powershell
cd web
Copy-Item .env.example .env           # 首次需要
pnpm install
pnpm dev                              # http://127.0.0.1:5273
```

> ⚠️ 用 `127.0.0.1` 而不是 `localhost` 访问——浏览器剪贴板 API 只在 HTTPS 或 localhost 下可用。
> 端口不能改回 5173（Windows 保留段）。详见 [`web/README.md`](web/README.md)。

### 4. 登录

**真实登录已接入**，首次使用需登录：演示账号 `demo` / `demo1234`
（口令由 `server/.env` 的 `DEMO_PASSWORD` 控制，由 `init_db` 播种）。

### 5. 鸿蒙 App（可选）

```powershell
.\harmony\build.ps1              # 构建 HAP（验证代码可编译）
```

> ⚠️ 产出的是**未签名** HAP，**不能直接安装**。要在设备/模拟器上运行，
> 需先在 DevEco Studio 里配置签名。另需把后端地址改成电脑局域网 IP，
> 并让后端监听 `0.0.0.0`——设备上的 `127.0.0.1` 指向设备自身。
> 完整说明见 [`harmony/README.md`](harmony/README.md)。

---

## 使用流程

### Web 端

1. 打开 <http://127.0.0.1:5273> 并登录
2. 点「同步剪贴板」，或在页面里 `Ctrl+V`
3. 内容自动上传；其他标签页/设备**实时收到**（WebSocket）
4. 点历史记录的「复制」写回系统剪贴板

> 读取剪贴板必须由用户手势触发（浏览器限制，无法后台自动读）。
> 未带令牌访问接口一律返回 `401`。

### 鸿蒙端

1. 登录（演示账号同上）
2. 首次进入会申请剪贴板读取权限；同意后**复制任何内容都会自动同步**
3. 列表里可「复制」写回剪贴板、「删除」单条、「清空全部」
4. 顶部显示 WebSocket 实时连接状态

---

## 测试

```powershell
# 后端：150 项（纯函数 + 接口集成，打独立测试库 clipboard_test）
cd server
$env:PYTHONUTF8='1'
.\venv\Scripts\python.exe -m pytest

# Web 端：34 项（端到端 + 多标签页同步 + 提示回归，需后端在跑）
cd web
pnpm test
pnpm typecheck
```

- 后端测试**不会碰开发库**：`tests/conftest.py` 强制指向 `clipboard_test`
- ⚠️ Web 端的破坏性用例（清空全部）默认**跳过**，需显式 `$env:E2E_ALLOW_DESTRUCTIVE='1'`
  且 `server/.env` 里 `ENABLE_DEV_ROUTES=true`；**它会清空所连库的数据**

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [`AGENTS.md`](AGENTS.md) | 项目约定：技术栈、数据契约、开发规范与顺序 |
| [`docs/roadmap.md`](docs/roadmap.md) | **当前进度、踩坑记录、技术债、下一步行动** |
| [`docs/api.md`](docs/api.md) | API 契约摘要 |
| [`docs/ws-protocol.md`](docs/ws-protocol.md) | WebSocket 协议 |
| [`server/README.md`](server/README.md) | 后端启动、迁移、数据库结构、环境变量 |
| [`web/README.md`](web/README.md) | Web 端启动、界面结构、配置与验证步骤 |

完整环境变量见 `server/.env.example` 与 `web/.env.example`。

---

## 注意事项

- **HTTPS / WSS**：浏览器剪贴板 API 仅在安全上下文可用；生产必须 HTTPS
- **用户手势**：读剪贴板无法后台自动触发
- **循环同步**：写回剪贴板需过滤自身触发的变更，避免死循环
- **单 worker**：WebSocket 广播是进程内实现，多 worker 会导致"数据一致但推送丢事件"
- **Windows 保留端口段**：`5141-5240`（吃掉 5173）、`8903-9002`（吃掉 MinIO 9000）
  等区间无法绑定。排查：`netsh int ipv4 show excludedportrange protocol=tcp`
