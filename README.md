# 云剪贴板（Cloud Clipboard）

一个跨平台的云剪贴板服务，实现多设备间剪贴板内容的实时同步。支持 **鸿蒙 App**、**Web 端** 两种客户端，后端基于 **FastAPI**。第一阶段聚焦文字剪贴板，后续扩展图片、文件等类型。

---

## ✨ 特性

- 🔄 **实时同步**：基于 WebSocket，多设备剪贴板内容秒级同步
- 📱 **跨平台**：鸿蒙 App + Web 端，覆盖手机与桌面场景
- 📋 **多类型内容**：文字（已支持）、图片、文件（规划中）
- 🔍 **历史管理**：查看、搜索、筛选、删除历史剪贴板记录
- 🔐 **安全认证**：JWT 认证，规划中的端到端加密
- 🎯 **去重优化**：相同内容不重复存储，自动更新时间戳

---

## 🏗️ 架构概览

```
┌──────────────┐        ┌──────────────┐
│  鸿蒙 App    │        │   Web 端     │
│  (ArkTS)     │        │ (React + TS) │
└──────┬───────┘        └──────┬───────┘
       │                       │
       │   HTTPS / WSS         │
       └───────────┬───────────┘
                   │
           ┌───────▼────────┐
           │  FastAPI 后端  │
           │  + WebSocket   │
           └───────┬────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
   ┌────▼───┐ ┌───▼────┐ ┌───▼────┐
   │Postgres│ │ Redis  │ │ MinIO  │
   │  数据  │ │ 广播   │ │ 对象存储│
   └────────┘ └────────┘ └────────┘
```

---

## 📁 项目结构

```
cloud-clipboard/
├── server/          # 后端 FastAPI
├── web/             # Web 端 (React + TS + Vite)
├── harmony/         # 鸿蒙 App (ArkTS)
├── infra/           # 部署与运维
├── docs/            # 项目文档
└── .github/         # CI 配置
```

各子项目的详细结构见对应目录下的 `README.md`。

---

## 🚀 快速开始

### 环境要求

| 组件 | 版本要求 |
|------|---------|
| Python | 3.10+ |
| Node.js | 18+ |
| PostgreSQL | 14+ |
| Redis | 6+ |
| Docker | 20+（推荐，用于本地基础设施） |
| DevEco Studio | 4.0+（鸿蒙开发） |

### 1. 克隆仓库

```bash
git clone https://github.com/your-org/cloud-clipboard.git
cd cloud-clipboard
```

### 2. 启动后端

```bash
cd server

# 复制环境变量模板
cp .env.example .env

# 启动本地依赖（Postgres + Redis + MinIO）
docker-compose up -d

# 创建虚拟环境
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 数据库迁移
alembic upgrade head

# 启动服务
uvicorn app.main:app --reload --port 8000
```

访问 <http://localhost:8000/docs> 查看 API 文档。

### 3. 启动 Web 端

```bash
cd web

# 复制环境变量模板
cp .env.example .env

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 <http://localhost:5273> 打开 Web 端。

### 4. 启动鸿蒙 App

1. 打开 **DevEco Studio**
2. 选择 `File > Open`，打开 `harmony/` 目录
3. 等待依赖同步完成
4. 选择模拟器或真机，点击运行

---

## 🔧 配置说明

### 后端环境变量（`server/.env`）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `APP_ENV` | 运行环境标识 | `development` |
| `DEBUG` | 是否暴露错误详情（**生产必须 false**） | `false` |
| `ENABLE_DEV_ROUTES` | 开发/测试辅助路由（`/api/v1/dev/*`）开关。与 `DEBUG` 解耦：**接库后该路由会清库**，生产必须 false | `false` |
| `CORS_ORIGINS` | 允许跨域的来源（JSON 数组或逗号分隔） | `["http://localhost:5273", ...]` |
| `DATABASE_URL` | PostgreSQL 连接串（第 3 步启用） | - |
| `REDIS_URL` | Redis 连接串（第 5 步启用） | - |
| `JWT_SECRET` | JWT 密钥（第 4 步启用，生产必须修改） | - |
| `JWT_EXPIRE_MINUTES` | Token 有效期（分钟，第 4 步启用） | `10080`（7 天） |

> ⚠️ 本地要跑 `web` 的端到端测试（会调用 `dev/reset` 恢复种子数据）时，
> 需在 `server/.env` 里设 `ENABLE_DEV_ROUTES=true`。**该接口接入数据库后会变成清库操作，生产环境永远不要开。**

### Web 端环境变量（`web/.env`）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VITE_API_BASE_URL` | 后端 API 地址 | `http://localhost:8000` |
| `VITE_WS_URL` | WebSocket 地址 | `ws://localhost:8000` |

---

## 📖 核心使用流程

### Web 端同步剪贴板

1. 登录 Web 端
2. 点击「同步剪贴板」按钮，或直接在页面 `Ctrl+V`
3. 内容自动上传到云端
4. 其他设备（鸿蒙 App、其他浏览器标签）实时收到更新

### 鸿蒙 App 同步剪贴板

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
| `POST` | `/api/v1/auth/register` | 用户注册 |
| `POST` | `/api/v1/auth/login` | 用户登录 |
| `GET` | `/api/v1/auth/me` | 当前用户 |
| `POST` | `/api/v1/clipboard/items` | 创建剪贴板项（`title` 留空时服务端自动生成） |
| `GET` | `/api/v1/clipboard/items` | 获取列表（分页/筛选/按标题或内容搜索/排序） |
| `GET` | `/api/v1/clipboard/items/{id}` | 获取详情 |
| `DELETE` | `/api/v1/clipboard/items/{id}` | 删除单条 |
| `DELETE` | `/api/v1/clipboard/items` | 清空 |
| `POST` | `/api/v1/dev/reset` | ⚠️ 删数据并重建种子（仅 `ENABLE_DEV_ROUTES=true` 时注册） |
| `GET` | `/api/v1/dev/db` | 探测当前连接的数据库（仅 dev 路由开启时） |
| `GET` | `/health` | 健康检查 |
| `WS` | `/api/v1/clipboard/ws` | 实时同步（第 5 步） |
| `POST` | `/api/v1/clipboard/upload` | 上传图片/文件（**阶段二**，当前未实现） |

交互式文档见 <http://localhost:8000/docs>；契约存档见 [`docs/api.md`](docs/api.md)，WebSocket 协议见 [`docs/ws-protocol.md`](docs/ws-protocol.md)。

---

## 🗺️ 路线图

| 阶段 | 内容 | 状态 |
|------|------|------|
| 阶段 0 | 项目初始化，三端骨架跑通 | 🚧 进行中 |
| 阶段 1 | 文字剪贴板 MVP，实时同步 | 📋 计划中 |
| 阶段 2 | 图片剪贴板，对象存储 | 📋 计划中 |
| 阶段 3 | 文件剪贴板，体验优化 | 📋 计划中 |
| 阶段 4 | 端到端加密，生产部署 | 📋 计划中 |

详细计划见 `docs/roadmap.md`。

---

## 🧪 测试

### 后端

```bash
cd server
pytest                          # 运行所有测试
pytest --cov=app tests/         # 带覆盖率
```

### Web 端

```bash
cd web
npm run test                    # 单元测试
npm run lint                    # 代码检查
```

### 鸿蒙 App

在 DevEco Studio 中使用内置测试框架运行 `entry/src/ohosTest/` 下的用例。

---

## 🐳 部署

### Docker Compose 一键部署

```bash
cd infra
docker-compose -f docker-compose.prod.yml up -d
```

### 生产环境要求

- 使用 HTTPS / WSS（剪贴板 API 依赖安全上下文）
- 修改默认 `JWT_SECRET`
- 配置对象存储生命周期策略
- 设置数据库定期备份

详细部署文档见 `infra/README.md`。

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

- [`AGENT.md`](AGENT.md) —— 项目约定：技术栈、目录结构、数据契约、开发规范与顺序
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
- **存储成本**：图片/文件建议配置对象存储生命周期策略，避免成本失控

---

## 📄 许可证

本项目采用 [MIT License](LICENSE)。

---

## 📮 联系方式

- 问题反馈：[GitHub Issues](https://github.com/your-org/cloud-clipboard/issues)
- 邮箱：your-email@example.com

---

**⭐ 如果这个项目对你有帮助，欢迎 Star！**
