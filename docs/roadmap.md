# 项目路线图与进度

> **本文件记录动态进度。** AGENTS.md 只保存稳定约定（技术栈、契约、规范、开发顺序），
> 凡是"每完成一步就要改一遍"的内容都放这里。

**最后更新**：2026-10-09
**当前进度**：第 1、2、3、4 步已完成 → **下一步：第 5 步（WebSocket 实时同步）**

---

## 阶段划分（AGENTS.md 第 1 节）

| 阶段 | 内容 | 状态 |
|------|------|------|
| 阶段一 | 文字剪贴板 MVP：上传/查询/删除 + 实时同步 + JWT + 去重 | 🚧 进行中 |
| 阶段二 | 图片剪贴板 + 对象存储 | 📋 计划中 |
| 阶段三 | 文件剪贴板 + 体验优化 | 📋 计划中 |
| 阶段四 | 端到端加密 + 生产部署 | 📋 计划中 |

---

## 开发步骤进度（AGENTS.md 第 10 节）

- ✅ **第 1 步（FastAPI 骨架 + 数据契约）已完成**，验收记录见 git log `89a03e9`
- ✅ **第 2 步（Web 端骨架 + 单端闭环）已完成**，验收记录见 git log `2aa5e49`
- ✅ **第 3 步（接入数据库）已完成**，验收记录见 git log `7f055ed`、`b5cc62d`
- ✅ **第 4 步（JWT 认证）已完成**，见下方「第 4 步踩坑记录」

### 🚧 第 3 步踩坑记录（永久保留，勿删）

1. Windows 上 `alembic.ini` 若含非 ASCII 字符会被 configparser 按 GBK 读取而崩，
   故该文件**保持纯 ASCII**；运行 Alembic 建议带 `$env:PYTHONUTF8='1'`
2. autogenerate 会把开发库里**手工建过的测试表**当成"已删除的表"写进迁移
   （生成了 `op.drop_table('rt')` / `op.drop_table('probe')`），在干净库上必然失败，已手工剔除。
   **流程要求：生成迁移后必须逐行检查内容**

### 🚧 第 3 步遗留（并入第 8 步）

- [ ] `tests/conftest.py` 已写好，但 **pytest / pytest-asyncio 未安装**，尚无后端测试用例
  （`httpx` 已在第 4 步装上，见下方 P5 处理记录）
- [ ] 迁移的 `upgrade`/`downgrade` 往返验证（downgrade 后重新 upgrade）

### ✅ 第 4 步：JWT 认证已完成

- ✅ `core/security.py`：bcrypt 密码哈希（`pwdlib`）、JWT 签发/校验（`PyJWT`）
- ✅ 真实的注册、登录接口（注册落库 + 唯一性校验，登录支持用户名或邮箱）
- ✅ 认证依赖 `get_current_user`（解析 `Authorization: Bearer`，失败 401 + `WWW-Authenticate`）
- ✅ 剪贴板路由加认证保护（本步骤前它就已经依赖 `CurrentUser`，只差真实实现）
- ✅ Web 端登录/注册页（`components/LoginPanel.vue`）、token 存 localStorage、
  401 自动登出回到登录页

**完成标准**：未带 token 请求返回 401，带 token 正常。**已达成**——后端进程内验收覆盖
401/200/409/422，Web e2e 20/20 通过（含 4 个新增认证用例）。

#### 🚧 第 4 步踩坑记录（永久保留，勿删）

1. **P5 的真实根因不是 bcrypt 版本冲突，而是 Python 3.13 移除了 `crypt` 模块**
   （PEP 594 的 19 个 dead batteries 之一）。`passlib` 依赖 `crypt`，import 阶段就
   `ModuleNotFoundError`。**所以 document 里"pin bcrypt==4.0.1"这条建议是死路**——
   根本走不到调用 bcrypt 那一步。已改用为 Python 3.13+ 而生的 `pwdlib`。
2. **`pwdlib` 的 `PasswordHash.recommended()` 只返回 Argon2**，本项目装的是
   `pwdlib[bcrypt]`，调它会抛 `HasherNotAvailable`。必须显式
   `PasswordHash((BcryptHasher(rounds=12),))`。
3. **bcrypt 限制的是 72 字节，不是 72 字符**。Schema 里原先只写 `max_length=72`（字符），
   24 个汉字（=72 字节）刚好卡线、25 个汉字就会在哈希阶段抛错变成 500。
   已加按 UTF-8 字节数的 `field_validator`，请求侧直接 422。
4. **`AuthResponse` 是扁平结构**：用户对象在 `token.user` 上。Web 端 `userStore` 原先
   把整个 `result` 赋给了 `user`，登录后界面会拿不到用户名。
5. **401 拦截器要排除 `/auth/login` 与 `/auth/register` 自身**，
   否则用户在登录页输错一次密码就会触发"全局登出"。
6. 默认 `JWT_SECRET` 若短于 32 字节，PyJWT 会发 `InsecureKeyLengthWarning`
   （RFC 7518 3.2 建议 HS256 密钥不短于 32 字节），故开发默认值也保持 32 字节以上。
7. **顶部提示必须有生命周期**（用户实测发现：登出后"已退出登录"一直不消失）。
   根因是提示**只在被下一条提示覆盖时才变**，而登出后界面停在登录页、
   没有任何后续操作能覆盖它。同类缺陷也影响错误提示（同步失败会永久挂着）。
   已抽成 `web/src/composables/useNotice.ts`：成功提示 3s、错误 8s 自动消失，
   并在登录成功时主动清除，配 `web/tests/notice.test.ts` 4 个回归用例。

### ⬜ 第 5 步：WebSocket 实时同步

- [ ] `services/ws_manager.py` 连接管理
- [ ] `routers/ws.py` 端点（token 校验）
- [ ] 创建剪贴板项时广播
- [ ] Web 端接入，实时更新列表
- [ ] 验证多标签页同步

**完成标准**：标签 A 上传，标签 B 秒级收到。
**开工前置**：必须先决定单 worker 还是引入 Redis Pub/Sub，见 P3；token 日志脱敏见 P6。

### ⬜ 第 6 步：内容去重

- [ ] 创建时计算 `content_hash`（内存版已实现，需迁移到数据库层）
- [ ] 相同内容更新时间戳，不创建新记录（**已实现**）
- [ ] 去重分支也广播 `clipboard.updated`（待第 5 步）
- [ ] Web 端处理 `updated` 事件

**完成标准**：连续复制相同内容只产生一条记录。**该标准目前已在数据库层成立（有 e2e 用例覆盖）。**

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
- [ ] **人工验证**浏览器侧「读取剪贴板 → 上传 → 列表展示 → 点击复制」（剪贴板 API 依赖用户手势，无法自动化）
- [ ] 修复边界问题

---

## 已知问题与技术债

**P1 / P4 / P7 / P8 已解决**（`DEBUG` 与开发路由解耦、文档文件名统一、`.gitignore` 补 `dist/`、README 路由表口径），过程见 git log。

### 🟡 P2 · 测试清库风险（守卫已就位，隔离待做）

`web/tests/e2e.test.ts` 的破坏性用例（清空全部、`dev/reset`）会清空数据。
**第 3 步接入数据库后，这已经是真实的删库操作。**

**已处理**：

- 新增 `E2E_ALLOW_DESTRUCTIVE=1` 显式开关：**不设置就跳过清空用例**（默认安全）
- 收尾自动恢复：优先调 `dev/reset`，该路由不可用时自动补回 4 条种子数据
- `dev/reset` 已明确标注"**会删除数据**"，且仅 `ENABLE_DEV_ROUTES=true` 时注册
- 新增 `GET /api/v1/dev/db`，可随时确认后端连的是哪个库
- 测试库 `clipboard_test` 已建好并跑通迁移

**仍需做**（第 8 步）：

- **Web e2e 目前打的仍是开发库**（后端 `DATABASE_URL` 指向 `clipboard`），
  跑测试会重置开发库数据。需加一个指向测试库的测试后端实例，
  或把 e2e 也纳入 pytest 夹具统一管理
- 后端 `tests/conftest.py` 已按"默认打 `clipboard_test`"写好（通过 `TEST_DATABASE_URL`），
  安装 pytest 后即可用

### 🟠 P3 · 多 worker 会打破 WebSocket 广播

**第 3 步没有改变这个约束**：数据现在共享（同一数据库），但第 5 步的 `ConnectionManager` 仍是**进程内结构**。

- uvicorn `--workers > 1` 时：数据一致（都在数据库），但**推送送不到另一个 worker**
- 处理：第 5 步要么强制 `--workers 1` 并禁止扩容，要么同时引入 Redis Pub/Sub
- **第 3 步后 AGENTS.md 第 6 节已明确记录该约束（不再藏在"后期风险"里）**，
  完整协议约定见 [`ws-protocol.md`](ws-protocol.md)

### ✅ P5 · 第 4 步认证依赖（已解决）

AGENTS.md 第 2 节原先指定 `python-jose + passlib[bcrypt]`。**该组合在本机根本装不起来**：

- 表面症状：`passlib 1.7.4` 与 `bcrypt 4.x` 的版本探测冲突
- **真实根因**：Python 3.13 按 PEP 594 移除了标准库 **`crypt`** 模块，而 `passlib` 依赖它，
  `import passlib` 阶段即 `ModuleNotFoundError`
- ⚠️ **所以"pin `bcrypt==4.0.1`"是死路**：根本走不到调用 bcrypt 那一步
- **处理**：改用为 Python 3.13+ 而生的 `pwdlib[bcrypt]==0.3.1` + `PyJWT==2.15.1`
  （只用 HS256 对称签名，不需要 `python-jose` 的算法矩阵）
- 顺带装上 `httpx`（第 8 步后端测试也要用），已用于第 4 步的进程内验收

### 🟡 P6 · WS token 走 query string 会被日志记录

`ws?token=<JWT>` 会被 uvicorn 访问日志明文记录。第 5 步需对 `token` 脱敏。

---

## 本地基础设施

**决策：本地开发与生产统一使用 Docker 容器跑 `postgres:16`**，
本机原生的 PostgreSQL 18 保留不动（避免影响其他项目），容器走宿主 **5433** 端口错开。

| 项目 | 值 |
|------|-----|
| 配置文件 | `infra/docker-compose.yml` |
| 镜像 | `postgres:16`（**本地已有**；`16-alpine` 需联网拉取，当前 Docker Hub 不可达） |
| 容器名 | `cloud-clipboard-postgres` |
| 端口 | 宿主 `5433` → 容器 `5432` |
| 数据卷 | `cloud-clipboard-postgres-data`（命名卷，`down` 不丢，`down -v` 才删） |
| 连接串 | `postgresql+asyncpg://clipboard:clipboard@127.0.0.1:5433/clipboard` |
| 验证脚本 | `scripts/verify_postgres.py`（宿主侧运行） |

启动、停止、看日志与连通性验证的完整命令见 `infra/docker-compose.yml` 顶部注释。

**注意事项**：

- Docker Hub 当前**不可达**（TLS handshake timeout），因此 compose 里用本地已有的
  `postgres:16` 而非 `16-alpine`。启动时若需强制离线：`up -d --pull never`
- Docker CLI 需访问命名管道 `//./pipe/docker_engine`，**在受限沙箱下会被拒绝**
  （`Access is denied`），因此所有 docker 命令都需要完全权限
- 版本漂移对策：本地与规划中的生产**均为 16**，避免跨大版本 `pg_dump/pg_restore` 不兼容

---

## 环境前置条件（实测）

| 组件 | 状态 | 说明 |
|------|------|------|
| Python 3.13.7 | ✅ | `server/venv` 已建，含 asyncpg 0.31.0 |
| Node 24.11.1 + pnpm 11.7.0 | ✅ | `web/node_modules` 已装 |
| Docker Desktop | ✅ 守护进程 29.8.1 运行中 | 但 CLI 需完全权限才能访问命名管道 |
| Docker Hub 拉取 | ❌ 网络不可达 | TLS handshake timeout，只能用本地已有镜像 |
| 本机 PostgreSQL 18 | ✅ Running，`5432` | **保留不动**，与容器（5433）并存 |
| 容器 PostgreSQL 16 | ✅ `cloud-clipboard-postgres` healthy | 本地开发主用 |
| Redis | ⬜ 6379 空闲 | 未安装，第 5 步启用 |
| MinIO | ⚠️ 9000 被 Windows 保留段占用 | 阶段二需另选端口（如 9010） |

### Windows 保留端口段（重要）

```
1034-1133, 4881-4980, 5141-5240, 8903-9002, 50000-50059
```

- **5141-5240** 覆盖了原定的 Vite 5173 → 已改用 **5273**
- **8903-9002** 覆盖了 MinIO 常用的 9000 → 阶段二需换端口
- 排查命令：`netsh int ipv4 show excludedportrange protocol=tcp`

---

## 下一步行动

1. **第 5 步（WebSocket 实时同步）**：开工前必须先决定**单 worker 还是 Redis Pub/Sub**（P3），
   并处理 `ws?token=` 的**日志脱敏**（P6）。协议见 [`ws-protocol.md`](ws-protocol.md)。
2. **P2 剩余项**：给 Web e2e 加一个指向 `clipboard_test` 的测试后端实例，
   让测试不再重置开发库
3. **第 8 步预留**：安装 `pytest`、`pytest-asyncio`（`httpx` 已在第 4 步装上），
   为 `tests/conftest.py` 补测试用例
