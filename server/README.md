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
│   │   └── models/          # User、ClipboardItem
│   ├── schemas/             # 数据契约（唯一事实来源）
│   ├── crud/                # 数据访问层（异步，路由不写 SQL）
│   ├── routers/
│   │   ├── auth.py          # 注册 / 登录 / 当前用户
│   │   ├── clipboard.py     # 剪贴板 CRUD + 广播
│   │   ├── ws.py            # WebSocket 端点
│   │   └── dev.py           # 仅 ENABLE_DEV_ROUTES=true 时注册
│   └── services/
│       ├── ws_manager.py    # 按用户隔离的连接管理与广播
│       └── events.py        # 事件序列化（与 REST 共用）
├── alembic/                 # 迁移（env.py 走异步引擎）
├── scripts/init_db.py       # 建表 + 演示账号 + 种子数据
├── tests/conftest.py        # ⬜ 夹具已写好（打 clipboard_test 库），用例待补
├── alembic.ini              # ⚠️ 保持纯 ASCII
└── requirements.txt / .env.example
```

## 数据库

| 项 | 值 |
|----|-----|
| 容器 | `cloud-clipboard-postgres`（`postgres:16`），宿主 `5433` |
| 开发库 / 测试库 | `clipboard` / `clipboard_test` @ `127.0.0.1:5433` |
| 演示账号 | `demo` / `demo1234`（口令由 `DEMO_PASSWORD` 配） |

**表**

- `users`：id / username / email / password_hash / nickname / avatar_url / created_at
- `clipboard_items`：id / user_id(FK) / title / content_type / content / preview /
  metadata(JSONB) / `content_hash` / created_at / updated_at

**去重**：`UNIQUE(user_id, content_hash)` —— 同一用户提交相同 `content` 命中同一行，
只刷新 `updated_at`、不新建记录；`content_hash` **不对外暴露**。

## 已实现接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册（落库 + 唯一性校验，**直接返回令牌**；重名/重邮箱 409） |
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
| WS | `/api/v1/clipboard/ws?token=<JWT>` | 实时同步（协议见 [`../docs/ws-protocol.md`](../docs/ws-protocol.md)） |
| GET | `/health` | 健康检查 |

> `/api/v1/clipboard/*` **全部需要认证**，不带令牌返回 `401`。
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
```

改契约的完整流程见 [`../AGENTS.md`](../AGENTS.md) 的「数据契约」。

## 注意事项

- **autogenerate 会把开发库里手工建过的测试表当成"已删除的表"**写进迁移
  （生成 `op.drop_table('xxx')`），在干净库上必然失败。生成后务必逐行检查并删掉噪声语句。
- **`metadata` 是 SQLAlchemy 保留名**：模型里属性叫 `meta`，列名才是 `metadata`。
- 连接池开了 `pool_pre_ping`，数据库重启后会自动剔除坏连接。
