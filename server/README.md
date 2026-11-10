# server —— 云剪贴板后端

FastAPI + PostgreSQL（async SQLAlchemy 2.0）+ Alembic + WebSocket。

启动步骤见仓库根 [`README.md`](../README.md)；契约与规范见 [`../AGENTS.md`](../AGENTS.md)。

## 目录结构

```
server/
├── app/
│   ├── main.py              # 应用入口：路由、CORS、lifespan（启动守卫 + 探测数据库）
│   ├── core/
│   │   ├── config.py        # 环境变量（pydantic-settings）
│   │   ├── security.py      # bcrypt 密码哈希 + JWT 签发/校验
│   │   ├── single_worker.py # 单 worker 守卫（多 worker 会让广播丢事件）
│   │   └── logging_utils.py # token 日志脱敏
│   ├── db/
│   │   ├── base.py          # 声明式 Base + 约束命名约定
│   │   ├── session.py       # 异步引擎 / session 工厂 / get_db 依赖 / ping
│   │   └── models/          # User、ClipboardItem、InviteCode、AdminAuditLog
│   ├── schemas/             # 数据契约（唯一事实来源，含 admin.py）
│   ├── crud/                # 数据访问层（路由不写 SQL；admin.py / audit.py 供后台）
│   ├── routers/
│   │   ├── auth.py          # 注册 / 登录 / 当前用户 / 管理员依赖
│   │   ├── clipboard.py     # 剪贴板 CRUD + 广播
│   │   ├── admin.py         # 后台管理：用户 / 剪贴板 / 邀请码 / 统计 / 审计
│   │   ├── ws.py            # WebSocket 端点
│   │   └── dev.py           # 仅 ENABLE_DEV_ROUTES=true 时注册
│   └── services/
│       ├── ws_manager.py    # 按用户隔离的连接管理与广播
│       └── events.py        # 事件序列化（与 REST 共用）
├── alembic/                 # 迁移（env.py 走异步引擎）
├── scripts/init_db.py       # 建表 + 演示账号 + 种子数据
├── scripts/invite_code.py   # 邀请码 CLI（create / list / revoke）
├── scripts/set_admin.py     # 设置 / 撤销后台管理员
├── scripts/ensure_database.py  # 按需建库（测试用，幂等）
├── tests/                   # pytest（打 clipboard_test 库）
├── alembic.ini              # ⚠️ 保持纯 ASCII
└── requirements.txt / .env.example
```

## 数据库

| 项 | 值 |
|----|-----|
| 容器 | `cloud-clipboard-postgres`（`postgres:16`），宿主 `5433` |
| 开发库 | `clipboard` —— 日常使用 |
| 后端测试库 | `clipboard_test` —— pytest（每用例 `drop_all` 重建表） |
| Web 测试库 | `clipboard_web_test` —— `scripts/run_web_tests.ps1` 用（按需自动创建） |
| 演示账号 | `demo` / `demo1234`（口令由 `DEMO_PASSWORD` 配） |

> 两个测试库分开是必要的：pytest 会反复删表，与 Web 测试共用库时并行会互相干扰。
> 三个库都可连 `127.0.0.1:5433`。

**表**

- `users`：id / username / email / password_hash / nickname / avatar_url /
  `is_admin` / `is_active` / `token_version` / `last_login_at` / `invite_code_id`(FK) / created_at
- `clipboard_items`：id / user_id(FK) / title / content_type / content / preview /
  metadata(JSONB) / `content_hash` / created_at / updated_at
- `invite_codes`：id / `code_hash`（SHA-256）/ `code_hint` / label / max_uses /
  used_count / expires_at / revoked_at / last_used_at / created_at
- `admin_audit_logs`：id / admin_id(FK, 删管理员后置空) / admin_username / action /
  target_type / target_id / detail(JSONB) / created_at

**迁移**

| revision | 内容 |
|----------|------|
| `0001_initial` | users + clipboard_items |
| `0002_invite_codes` | invite_codes |
| `0003_admin_users_and_audit_logs` | 用户管理列 + admin_audit_logs |
| `0004_user_invite_code` | users.invite_code_id（邀请码使用详情） |

**去重**：`UNIQUE(user_id, content_hash)` —— 同一用户提交相同 `content` 命中同一行，
只刷新 `updated_at`、不新建记录；`content_hash` **不对外暴露**。

## 已实现接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册（先校验邀请码，再落库 + 唯一性校验，**直接返回令牌**；邀请码无效 403，重名/重邮箱 409） |
| POST | `/api/v1/auth/login` | 登录（`username` 支持用户名或邮箱，错误统一 401） |
| GET | `/api/v1/auth/me` | 当前用户（需 `Authorization: Bearer <token>`） |
| POST | `/api/v1/clipboard/items` | 创建（含内容去重） |
| GET | `/api/v1/clipboard/items` | 列表（分页/筛选/搜索/排序） |
| GET | `/api/v1/clipboard/items/{id}` | 详情 |
| PATCH | `/api/v1/clipboard/items/{id}` | 更新（只改传入字段） |
| DELETE | `/api/v1/clipboard/items/{id}` | 删除单条 |
| DELETE | `/api/v1/clipboard/items` | 清空 |
| POST | `/api/v1/dev/reset` | ⚠️ 删数据重建种子（仅 dev 路由开启时） |
| GET | `/api/v1/dev/db` | 探测当前连的是哪个库（仅 dev 路由开启时） |
| GET/PATCH/DELETE | `/api/v1/admin/*` | 后台管理：用户 / 剪贴板 / 邀请码 / 统计 / 审计（需 `is_admin`，普通用户 403；详见 [`../docs/admin.md`](../docs/admin.md)） |
| WS | `/api/v1/clipboard/ws?token=<JWT>` | 实时同步（协议见 [`../docs/ws-protocol.md`](../docs/ws-protocol.md)） |
| GET | `/health` | 健康检查 |

> `/api/v1/clipboard/*` **全部需要认证**，不带令牌返回 `401`。
> 生产开启 `REGISTRATION_REQUIRE_INVITE` 后，注册必须携带 `invite_codes` 表中的有效邀请码
> （生成与撤销见 [`../docs/deployment.md`](../docs/deployment.md) 的「邀请码管理」）。
> ⚠️ 必须**单 worker** 启动：广播是进程内实现，多 worker 会"数据一致但推送丢事件"。
> 启动守卫会自动检测并拒绝（`WEB_CONCURRENCY` + 固定回环端口独占）。

## 常用命令

```powershell
$env:PYTHONUTF8 = '1'   # Windows 上跑 Alembic 必需（否则 configparser 按 GBK 读配置报错）

# 迁移
.\venv\Scripts\python.exe -m alembic revision --autogenerate -m "描述"
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m alembic current
# 对测试库单独跑
.\venv\Scripts\python.exe -m alembic -x db_url=postgresql+asyncpg://clipboard:clipboard@127.0.0.1:5433/clipboard_test upgrade head

# 数据初始化
.\venv\Scripts\python.exe -m scripts.init_db            # 建表 + 演示账号 + 种子数据
.\venv\Scripts\python.exe -m scripts.init_db --no-seed  # 只建表
# --drop 会清库；目标库名不含 test 时需显式 ALLOW_DROP_DEV=1

# 注册邀请码（也可以直接用后台 /admin 的「邀请码」页管理）
.\venv\Scripts\python.exe -m scripts.invite_code create --days 7 --max-uses 1 --label "alice"
.\venv\Scripts\python.exe -m scripts.invite_code list
.\venv\Scripts\python.exe -m scripts.invite_code revoke --hint ABCD1234

# 后台管理员：创建并授权 / 仅授权 / 撤销（设计与步骤见 ../docs/admin.md）
.\venv\Scripts\python.exe -m scripts.set_admin --username <用户名> --email <邮箱> --create
.\venv\Scripts\python.exe -m scripts.set_admin --username <用户名>
.\venv\Scripts\python.exe -m scripts.set_admin --username <用户名> --revoke
# 非交互：'密码' | ... --username <用户名> --email <邮箱> --create --password-stdin
```

改契约的完整流程见 [`../AGENTS.md`](../AGENTS.md) 的「数据契约」。

## 日志

默认写入**文件**（`RotatingFileHandler`），不依赖终端回滚缓冲：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL`（非法值按 `INFO`） |
| `LOG_FILE` | `logs/app.log` | 相对路径按 `server/` 解析；**置空**则只输出到终端 |
| `LOG_MAX_BYTES` | `10485760` | 单文件上限（字节）；`0` 表示不轮转 |
| `LOG_BACKUP_COUNT` | `5` | 保留份数（`app.log.1`、`app.log.2`…） |
| `LOG_CONSOLE` | `false` | 设为 `true` 时**额外**输出到终端 |

- 行格式带**毫秒与时区偏移**的时间戳、请求 id 与 logger 名，例如
  `2026-11-04 22:30:01.123+08:00 INFO     [3f9a1c2d7e4b] app.routers.ws ws connected: user=… client=… connections=1`
- `request_id` 由 `core/request_context.py` 生成：同一个 HTTP / WebSocket 请求的
  访问日志、写审计、广播日志都带同一个 id，并回写到响应头 `X-Request-ID`；
  不在请求上下文里的日志（启动、脚本）显示 `-`
- uvicorn 的访问日志/错误日志也追加进**同一个文件**；WS 的 `token` 与列表搜索的
  `search` 在落盘前已脱敏（`token=***` / `search=***`），**root 与 uvicorn 的所有
  handler 都覆盖**（含 `LOG_FILE` 为空的纯终端模式）
- 排查顺序：先看 `server/logs/app.log`，再看终端里 uvicorn 自己的启动输出。
- 文件打不开（目录无权限 / 磁盘满）时**自动退回终端**并记一条 warning，不会阻断启动。
- ⚠️ `RotatingFileHandler` **不能多进程写同一文件**（轮转时互相抢）。本项目强制单
  worker，故安全；并行起独立实例时（如 `run_web_tests.ps1` 的 8001 端口）要用
  `LOG_FILE` 指向别的文件——脚本已自动指到 `%TEMP%`。

## 注意事项

- **autogenerate 会把开发库里手工建过的测试表当成"已删除的表"**写进迁移
  （生成 `op.drop_table('xxx')`），在干净库上必然失败。生成后务必逐行检查并删掉噪声语句。
- **`metadata` 是 SQLAlchemy 保留名**：模型里属性叫 `meta`，列名才是 `metadata`。
- 连接池开了 `pool_pre_ping`，数据库重启后会自动剔除坏连接。
