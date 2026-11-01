# 云剪贴板（Cloud Clipboard）

跨平台云剪贴板：多设备间剪贴板内容实时同步。当前客户端为 **Web 端**
（桌面 + 移动自适应，✅ 可用）；鸿蒙 App 代码保留、**暂停上架**。
后端为 **FastAPI + PostgreSQL + WebSocket**。

## 项目进度

**v1.0.0 只包含文字剪贴板同步**；图片与文件剪贴板安排在下一版本（v1.1）。

| 阶段 | 内容 | 版本 | 状态 |
|------|------|------|------|
| 阶段一 | 文字：保存 / 查询 / 删除 + 实时同步 + 登录 + 去重 | **v1.0.0** | ✅ 功能完成，发版中 |
| 阶段二 | 图片 + 对象存储 | **v1.1（下一版本）** | 📋 计划中 |
| 阶段三 | 文件 + 体验优化 | **v1.1（下一版本）** | 📋 计划中 |
| 阶段四 | 端到端加密 + 生产加固 | 后续 | 📋 计划中 |

| 客户端 | 状态 |
|--------|------|
| Web 端 | ✅ 桌面 + 移动自适应；登录、手动粘贴/输入、保存、历史、复制、多设备实时同步 |
| 鸿蒙 App | ⏸️ 暂停上架；代码保留且编译通过，安装运行仍需签名，见 [`harmony/README.md`](harmony/README.md) |

细节（含踩坑记录与技术债）见 [`docs/roadmap.md`](docs/roadmap.md)。

---

## 架构

```
┌──────────────┐
│   Web 端     │
│ 桌面 + 移动   │
└──────┬───────┘
       │ HTTPS / WSS
┌──────▼────────┐
│  FastAPI 后端  │
│  + WebSocket   │
└──────┬────────┘
       │
┌──────▼──────┐
│  PostgreSQL │  ← 宿主 5433（5432 被本机原生 PostgreSQL 占用）
└─────────────┘
```

鸿蒙 App 已暂停上架，代码保留在 [`harmony/`](harmony/README.md)，不在当前交付架构内。
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

> ⚠️ 用 `127.0.0.1` 而不是 `localhost` 访问——历史记录的「复制」使用浏览器剪贴板 API，
> 它只在 HTTPS 或 localhost 下可用。端口不能改回 5173（Windows 保留段）。
> 详见 [`web/README.md`](web/README.md)。

### 4. 登录

**真实登录已接入**，首次使用需登录：演示账号 `demo` / `demo1234`
（口令由 `server/.env` 的 `DEMO_PASSWORD` 控制，由 `init_db` 播种）。

---

## 使用流程

### Web 端

1. 打开 <http://127.0.0.1:5273> 并登录
2. 在输入框里直接输入或 `Ctrl+V` 粘贴内容，点「保存」
3. 停止输入 2 秒后自动保存（右下角有倒计时）；其他标签页/设备**实时收到**（WebSocket）
4. 点历史记录的「复制」写回系统剪贴板
5. 点历史记录可载入输入区编辑，保存后仍是同一条；点「＋ 新建剪贴板」才会另起一条

> Web 端不读取系统剪贴板，直接手动粘贴/输入即可；未带令牌访问接口一律返回 `401`。
> 移动端使用顶部「历史记录 / 剪贴板输入」页签，详情见 [`web/README.md`](web/README.md)。

---

## 测试

```powershell
# 后端：163 项（纯函数 + 接口集成，打独立测试库 clipboard_test）
cd server
$env:PYTHONUTF8='1'
.\venv\Scripts\python.exe -m pytest

# Web 端隔离模式（推荐，55 项）：自动起一个指向测试库的独立后端，跑完自动停
.\scripts\run_web_tests.ps1

# Web 端安全模式：打当前后端，不删除任何既有数据
cd web
pnpm test
pnpm typecheck
```

- 两套测试**各用一个独立的库**（`clipboard_test` / `clipboard_web_test`），
  可任意并行；开发库 `clipboard` 完全不受影响
- Web 端有安全守卫：目标库名不含 `test` 时，破坏性操作一律跳过

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [`AGENTS.md`](AGENTS.md) | 项目约定：技术栈、数据契约、开发规范与顺序 |
| [`docs/roadmap.md`](docs/roadmap.md) | **当前进度、踩坑记录、技术债、下一步行动** |
| [`docs/api.md`](docs/api.md) | API 契约摘要 |
| [`docs/ws-protocol.md`](docs/ws-protocol.md) | WebSocket 协议 |
| [`server/README.md`](server/README.md) | 后端启动、迁移、数据库结构、环境变量 |
| [`web/README.md`](web/README.md) | Web 端启动、桌面/移动布局、配置与验证步骤 |
| [`harmony/README.md`](harmony/README.md) | 鸿蒙 App（暂停上架）的构建与签名说明 |

完整环境变量见 `server/.env.example` 与 `web/.env.example`。

---

## 注意事项

- **HTTPS / WSS**：浏览器剪贴板的「复制写回」仅在安全上下文可用；生产必须 HTTPS
- **手动粘贴**：Web 端不读取系统剪贴板，用户自己粘贴/输入后保存
- **单 worker**：WebSocket 广播是进程内实现，多 worker 会导致"数据一致但推送丢事件"
- **Windows 保留端口段**：`5141-5240`（吃掉 5173）、`8903-9002`（吃掉 MinIO 9000）
  等区间无法绑定。排查：`netsh int ipv4 show excludedportrange protocol=tcp`
