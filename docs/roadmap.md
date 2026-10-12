# 项目路线图与进度

> **本文件只记录动态进度与踩坑。** AGENTS.md 只保存稳定约定（技术栈、契约、规范、开发顺序）。
> 踩坑记录只留**会导致错误发生的机制**；实现细节看代码，过程看 git log。

**最后更新**：2026-10-12
**当前进度**：阶段一（第 1～6 步）功能已完成；第 8 步的**后端测试已补**（150 项），
人工验证与三端联调仍待做 → 见文末「下一步行动」

---

## 阶段划分

| 阶段 | 内容 | 状态 |
|------|------|------|
| 阶段一 | 文字：上传 / 查询 / 删除 + 实时同步 + 登录 + 去重 | ✅ 已完成 |
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
| 7 鸿蒙 App | 🚧 | 代码完成、**编译通过**；已补手动上传/搜索/排序/二次确认与应用内改后端地址；待签名上机验证（踩坑见下） |
| 8 联调与测试 | 🚧 | 后端 150 项 + Web 34 项已就位；**人工验证与三端联调**待做 |

---

## 测试现状

| 套件 | 数量 | 说明 |
|------|------|------|
| 后端 pytest | **150** | 打独立库 `clipboard_test`，不碰开发库 |
| Web 端 e2e + WS + 提示 | **34** | 打**开发库**（P2 未解决，注意破坏性用例） |

后端覆盖：`crud/clipboard.py` 纯函数（时区回退、标题换算、哈希、预览截断）、
`core/security.py`（哈希、JWT 及伪造/篡改/alg=none 降级攻击）、
`core/single_worker.py` 与 `core/logging_utils.py`、
auth 与 clipboard 接口（含**跨用户越权隔离**、去重契约、分页校验）。

**鸿蒙端**：见 [`harmony/README.md`](../harmony/README.md) 的「已验证与未验证」。
编译与打包已验证；**安装运行、联调、`READ_PASTEBOARD` 授权均未验证**。

---

## 踩坑记录（永久保留，勿删）

### 第 7 步（鸿蒙 App）

1. **打包阶段报 `spawn java ENOENT`（错误码 00308018）不是签名问题，是缺 `JAVA_HOME`。**
   hvigor 的 `PackageHap` 需要 Java；报错文案指向"签名配置"极具误导性。
   指向 DevEco 自带 JBR 即可：`C:\Program Files\Huawei\DevEco Studio\jbr`。
   已封装进 `harmony/build.ps1`，它同时设置 `DEVECO_SDK_HOME` / `NODE_HOME` / `JAVA_HOME`。
2. **ArkTS 不允许无类型的对象字面量**（`arkts-no-untyped-obj-literals`）。
   给函数传 `{ username: x }` 这类匿名字面量**编译不过**，必须为每个请求体
   声明显式 `interface` 再传变量。空响应体的 `{}` 也一样，需要一个占位接口。
3. **`abilityAccessCtrl.checkAccessToken` 返回 `Promise`**，同步判断要用
   `checkAccessTokenSync`。用错会得到"类型无重叠"的编译错误。
4. **`.hvigor/` 不默认被忽略**：它是构建缓存与日志目录，每次构建都重写。
   已加入 `.gitignore`（连同 `oh_modules/`、`.idea/` 与 `*.p12`/`*.p7b`/`*.cer`）。
5. **设备上的 `127.0.0.1` 指向设备自身**，不是开发机。真机联调必须：
   改 `harmony/.../common/Config.ets` 的后端地址为电脑局域网 IP，
   并让后端 `--host 0.0.0.0` 启动（当前只监听 `127.0.0.1`，设备连不上）。

### 第 3 步

1. **`alembic.ini` 必须保持纯 ASCII**：Windows 上 configparser 按 locale（GBK）读取，
   中文注释会让 Alembic 直接崩溃。运行迁移建议带 `$env:PYTHONUTF8='1'`。
2. **autogenerate 会把开发库里手工建过的测试表当成"已删除的表"**写进迁移
   （曾生成 `op.drop_table('rt')`），在干净库上必然失败。
   **流程要求：生成迁移后逐行检查内容。**

### 第 8 步（补后端测试）

1. **`tests/conftest.py` 的 `engine` 夹具原本是 session 级，跑不起来。**
   pytest-asyncio 默认**每个测试用新的事件循环**，而引擎的连接池会把连接绑定在创建它的
   循环上 → 第二个测试起就报 `RuntimeError: got Future attached to a different loop`，
   表现为 `cannot rollback; the transaction is in error state`。
   已改为**函数级引擎**（每个测试建表一次，耗时约 28s / 150 项，可接受）。
   ⚠️ 不要"优化"回 session 级，除非同时把事件循环也提成 session 级。
2. **测单 worker 守卫时不能直接用 `LOCK_PORT`**：本地后端启动时会占着它，
   测试会被判成"已有实例"。夹具用 monkeypatch 换成临时空闲端口
   （为此 `lock_single_worker(port=None)` 改为在函数体内读模块常量，
   因为默认参数在定义时就求值，patch 不生效）。
3. **测试里不要用短密钥签 JWT**（如 `"attacker-secret"`）：会触发 PyJWT 的
   `InsecureKeyLengthWarning`，把测试输出搞脏。用 ≥32 字节的密钥。

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

阶段一功能已完成，后端测试已补齐。剩余：

1. **人工验证**浏览器侧「读取剪贴板 → 上传 → 列表展示 → 点击复制」
   （依赖用户手势，无法自动化）—— 这是第 8 步最后一块没被自动化覆盖的
2. **P2 剩余项**：让 Web e2e 打测试库而非开发库（后端测试已隔离，Web 端还没有）
3. **第 7 步鸿蒙 App**：代码与界面已就绪；剩下的是**签名 + 上机联调**（需华为开发者账号，
   在 DevEco 里配置签名）。联调清单见 [`harmony/README.md`](../harmony/README.md)，
   后端用 [`scripts/start_server_lan.ps1`](../scripts/start_server_lan.ps1) 以 `0.0.0.0` 启动
4. 之后可考虑：CI（`.github/workflows/`）、LICENSE、GitHub 默认分支设置
5. 清理测试账号（需要时）：`DELETE FROM users WHERE username LIKE 'ws_e2e_%';`
