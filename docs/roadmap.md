# 项目路线图与进度

> **本文件只记录动态进度与踩坑。** AGENTS.md 只保存稳定约定（技术栈、契约、规范、开发顺序）。
> 踩坑记录只留**会导致错误发生的机制**；实现细节看代码，过程看 git log。

**最后更新**：2026-10-09
**当前进度**：第 1～6 步已完成（**阶段一 MVP 收尾**）→ 下一步见文末「下一步行动」

---

## 阶段划分

| 阶段 | 内容 | 状态 |
|------|------|------|
| 阶段一 | 文字剪贴板 MVP：上传/查询/删除 + 实时同步 + JWT + 去重 | ✅ 已完成 |
| 阶段二 | 图片剪贴板 + 对象存储 | 📋 计划中 |
| 阶段三 | 文件剪贴板 + 体验优化 | 📋 计划中 |
| 阶段四 | 端到端加密 + 生产部署 | 📋 计划中 |

## 开发步骤进度

| 步骤 | 状态 | 说明 |
|------|------|------|
| 1 FastAPI 骨架 + 数据契约 | ✅ | git log `89a03e9` |
| 2 Web 端骨架 + 单端闭环 | ✅ | git log `2aa5e49` |
| 3 接入数据库 | ✅ | git log `7f055ed`、`b5cc62d`；踩坑见下 |
| 4 JWT 认证 | ✅ | 踩坑见下 |
| 5 WebSocket 实时同步 | ✅ | 踩坑见下；**强制单 worker**（P3 已决策） |
| 6 内容去重 | ✅ | 代码在第 3／5 步已落地，本步骤补齐验收覆盖 |
| 7 鸿蒙 App | ⬜ | 需先确认 DevEco 环境 |
| 8 联调与测试 | ⬜ | 后端 pytest 用例仍为零，是当前最大盲区 |

---

## 踩坑记录（永久保留，勿删）

### 第 3 步

1. **`alembic.ini` 必须保持纯 ASCII**：Windows 上 configparser 按 locale（GBK）读取，
   中文注释会让 Alembic 直接崩溃。运行迁移建议带 `$env:PYTHONUTF8='1'`。
2. **autogenerate 会把开发库里手工建过的测试表当成"已删除的表"**写进迁移
   （曾生成 `op.drop_table('rt')`），在干净库上必然失败。
   **流程要求：生成迁移后逐行检查内容。**

### 第 4 步

1. **`passlib` 在 Python 3.13 上根本装不了**：PEP 594 移除了标准库 `crypt` 模块，
   而 passlib 依赖它，`import` 阶段即 `ModuleNotFoundError`。
   ⚠️ **pin 老版本 bcrypt 是死路**——根本走不到调用 bcrypt 那一步。
   改用 `pwdlib`；对应地 JWT 用 `PyJWT`（只需 HS256，不需要已停止维护的 `python-jose`）。
2. **`pwdlib` 的 `PasswordHash.recommended()` 只返回 Argon2**，本项目装的是
   `pwdlib[bcrypt]`，调它会抛 `HasherNotAvailable`。必须显式
   `PasswordHash((BcryptHasher(rounds=12),))`。
3. **bcrypt 限制的是 72 字节，不是 72 字符**。只写 `max_length=72`（字符）会让
   25 个汉字通过校验后在哈希阶段抛错变成 500。已按 UTF-8 字节数校验。
4. **`JWT_SECRET` 短于 32 字节会让 PyJWT 发 `InsecureKeyLengthWarning`**
   （RFC 7518 3.2），故开发默认值也保持 32 字节以上。
5. Web 端两个易错点：`AuthResponse` 是扁平结构（用户对象在 `token.user` 上，不是整个响应）；
   401 拦截器**必须排除 `/auth/login` 与 `/auth/register` 自身**，否则登录页输错一次密码
   就触发全局登出。
6. **顶部提示必须有生命周期**：它只在被下一条提示覆盖时才变，而登出后界面停在登录页、
   没有任何操作能覆盖它 —— 导致"已退出登录"永久残留（错误提示同理）。
   已抽成 `web/src/composables/useNotice.ts`。

### 第 5 步

1. **单 worker 守卫只查环境变量是无效的。** uvicorn 的 CLI `--workers N`
   **不会**写进环境变量（实测 worker 进程里 `WEB_CONCURRENCY` 是 `None`），
   只有 `WEB_CONCURRENCY=N` 这条路径才会 → 必须额外做"独占固定回环端口"检测。
   ⚠️ 锁端口**必须固定**：实测 `bind(('127.0.0.1', 0))` 每次都返回不同端口
   （连续三次 13099/13100/13101），"探测空闲端口再绑定"的写法在并发下**永不相撞**。
2. **日志脱敏不能用 `logging.Filter` 改写 `record.args`。** uvicorn 的 `AccessFormatter`
   要求 args 里恰好 5 个字段，清空后**每个 HTTP 请求**都抛 `ValueError`，
   访问日志整体报废。正确做法：`scrub_scope_token()` 从 ASGI scope 删掉 token
   （日志里根本没有它），再包一层 formatter 兜底。
   ⚠️ 不要把 `?token=***` 拼回 `scope["path"]`，会被百分号编码成 `%3Ftoken%3D...`。
3. **Node 测试运行器会并行跑多个测试文件**：两个套件共用同一账号时，
   一方的增删会让另一方的 `total` 断言随机失败（实测期望 5、实际 6）。
   各套件必须用**独立账号**。
4. **`pnpm test -- <file>` 不会只跑指定文件**：`--` 之后的参数被追加到已有 glob 之后。
   要单跑得直接调 node：`node --experimental-strip-types --test tests/websocket.test.ts`
5. 去重的两条易错契约（第 6 步）：命中时**只刷新 `updated_at`、不改 `created_at`**，
   且**未显式传 `title` 时不得覆盖原标题**。

---

## 已知问题与技术债

### 🟡 P2 · 测试清库风险（守卫已就位，隔离待做）

破坏性用例会清空数据。**已处理**：`E2E_ALLOW_DESTRUCTIVE=1` 显式开关（默认跳过）、
收尾自动恢复种子、`dev/reset` 仅 `ENABLE_DEV_ROUTES=true` 时注册、
`GET /api/v1/dev/db` 可确认连的是哪个库、测试库 `clipboard_test` 已建好。

**仍需做**：Web e2e 打的**仍是开发库**，跑测试会重置开发库数据。
需加一个指向测试库的测试后端实例，或把 e2e 纳入 pytest 夹具统一管理
（后端 `tests/conftest.py` 已按"默认打 `clipboard_test`"写好，装好 pytest 即可用）。

### ✅ 已关闭

- **P1 / P4 / P7 / P8**：`DEBUG` 与开发路由解耦、文档文件名统一、`.gitignore` 补 `dist/`、
  README 路由表口径 —— 过程见 git log
- **P3 多 worker 打破广播**：已决策**强制单 worker**并落地运行时守卫
  （见「第 5 步踩坑记录」1 与 [`ws-protocol.md`](ws-protocol.md)）。
  解除限制的前置条件是先引入 Redis Pub/Sub
- **P5 认证依赖兼容性**：见「第 4 步踩坑记录」1；顺带装了 `httpx`（第 8 步也要用）
- **P6 WS token 日志泄露**：见「第 5 步踩坑记录」2

---

## 本地基础设施

**Postgres 16 走 Docker 容器（宿主 5433）**；本机原生的 PostgreSQL 18 保留不动（占 5432）。
连接串、数据卷、健康检查等见 `infra/docker-compose.yml` 顶部注释与
`scripts/verify_postgres.py`。

- **Docker Hub 当前不可达**（TLS handshake timeout）→ compose 用本地已有的 `postgres:16`
  而非 `16-alpine`；离线启动加 `--pull never`
- Docker CLI 需访问命名管道，**受限沙箱下会被拒绝**，故 docker 命令都需完全权限
- 本地与规划中的生产**均为 16**，避免跨大版本 `pg_dump/pg_restore` 不兼容

## 环境前置条件

| 组件 | 状态 | 说明 |
|------|------|------|
| Python 3.13.7 | ✅ | `server/venv` 已建 |
| Node 24.11.1 + pnpm 11.7.0 | ✅ | `web/node_modules` 已装 |
| Docker Desktop | ✅ | CLI 需完全权限才能访问命名管道 |
| Docker Hub 拉取 | ❌ | 网络不可达，只能用本地已有镜像 |
| 本机 PostgreSQL 18 | ✅ `5432` | **保留不动**，与容器并存 |
| 容器 PostgreSQL 16 | ✅ healthy | 本地开发主用（宿主 5433） |
| Redis | ⬜ 空闲 | **本阶段不引入**（P3 走单 worker）；需跨进程广播时再启用 |
| MinIO | ⚠️ | 9000 被 Windows 保留段占用，阶段二需换端口 |

### Windows 保留端口段（重要）

```
1034-1133, 4881-4980, 5141-5240, 8903-9002, 50000-50059
```

**5141-5240** 覆盖了原定的 Vite 5173 → 已改用 **5273**；**8903-9002** 覆盖 MinIO 的 9000。
排查命令：`netsh int ipv4 show excludedportrange protocol=tcp`

---

## 下一步行动

阶段一已完成。建议顺序：

1. **补后端单元测试**（第 8 步的一部分，建议优先）：安装 `pytest`、`pytest-asyncio`
   （`httpx` 已装），为 `tests/conftest.py` 补用例。
   当前 34 个通过的测试全部来自 Web 端间接覆盖，后端自身的单元逻辑
   （时区回退、分页校验、哈希边界）**一条都没测**
2. **人工验证**浏览器侧「读取剪贴板 → 上传 → 列表展示 → 点击复制」
   （依赖用户手势，无法自动化）
3. **第 7 步鸿蒙 App**：需先确认 DevEco 环境
4. **P2 剩余项**：让 Web e2e 打测试库而非开发库
5. 清理测试账号（需要时）：`DELETE FROM users WHERE username LIKE 'ws_e2e_%';`
