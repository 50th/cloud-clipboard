# server —— 云剪贴板后端

FastAPI + PostgreSQL（async SQLAlchemy 2.0）+ Alembic。当前处于 **第 3 步：接入数据库**。

## 快速开始（Windows）

前置：PostgreSQL 容器已启动（见 `../infra/docker-compose.yml`）。

```powershell
# 0. 启动数据库容器（仓库根目录）
docker compose -f infra/docker-compose.yml up -d

cd server

# 1. 虚拟环境（已创建可跳过）
python -m venv venv

# 2. 安装依赖
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. 环境变量
Copy-Item .env.example .env

# 4. 建表（二选一）
.\venv\Scripts\python.exe -m alembic upgrade head      # 推荐：走迁移
.\venv\Scripts\python.exe -m scripts.init_db           # 本地快速铺开（create_all + 种子数据）

# 5. 启动服务（⚠️ 必须单 worker）
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

> ⚠️ **不要用 `--workers > 1`**：WebSocket 广播是进程内实现，多 worker 会让
> 事件送不到另一个 worker（数据一致、推送不一致，很难排查）。启动守卫会直接拒绝。
> 注意 `--reload` 与 `--workers` 互斥，本地热重载就用上面的命令。

访问 <http://127.0.0.1:8000/docs> 查看 Swagger UI。

> ⚠️ **Windows 上必须带 `PYTHONUTF8=1`**，否则 Alembic 读取配置会因 GBK 编码报错：
> `$env:PYTHONUTF8 = '1'`（`pytest.ini` / `alembic.ini` 已刻意保持纯 ASCII 以降低风险）

## 目录结构

```
server/
├── app/
│   ├── main.py              # 应用入口：路由、CORS、lifespan（启动探测数据库）
│   ├── core/
│   │   └── config.py        # 环境变量（pydantic-settings）
│   ├── db/                  # ✅ 数据库层
│   │   ├── base.py          #   声明式 Base + 约束命名约定
│   │   ├── session.py       #   异步引擎 / session 工厂 / get_db 依赖 / ping
│   │   └── models/          #   ✅ User、ClipboardItem
│   ├── schemas/             # ✅ 数据契约（唯一事实来源）
│   ├── crud/                # ✅ 数据访问层（异步，路由不写 SQL）
│   │   ├── user.py
│   │   └── clipboard.py
│   ├── routers/
│   │   ├── auth.py          # 注册 / 登录 / 当前用户
│   │   ├── clipboard.py     # 剪贴板 CRUD
│   │   └── dev.py           # 仅 ENABLE_DEV_ROUTES=true 时注册
│   └── services/            # 第 5 步：ws_manager.py
├── alembic/                 # ✅ 迁移
│   ├── env.py               #   异步引擎；连接串从 settings 读取
│   └── versions/            #   0001_initial
├── scripts/
│   └── init_db.py           # ✅ 建表 + 演示用户 + 种子数据
├── tests/
│   └── conftest.py          # ⬜ 测试夹具（打 clipboard_test 库，第 8 步扩充）
├── alembic.ini              # ⚠️ 保持纯 ASCII
├── requirements.txt
└── .env.example
```

## 数据库

| 项 | 值 |
|----|-----|
| 容器 | `cloud-clipboard-postgres`（`postgres:16`） |
| 开发库 | `clipboard` @ `127.0.0.1:5433` |
| 测试库 | `clipboard_test` @ `127.0.0.1:5433` |
| 演示用户 | `demo` / `3f1a9c62-7d4b-4e18-9f2a-6b0c5d8e1a34` |

**表**：

- `users`：id(UUID) / username / email / password_hash / nickname / avatar_url / created_at
- `clipboard_items`：id(UUID) / user_id(FK) / title / content_type / content / preview /
  metadata(JSONB) / `content_hash` / created_at / updated_at

**去重**：`UNIQUE(user_id, content_hash)`。同一用户提交相同 `content` 时命中同一行，
只刷新 `updated_at`，不新建记录。`content_hash` **不对外暴露**。

## 常用命令

```powershell
$env:PYTHONUTF8 = '1'

# 迁移
.\venv\Scripts\python.exe -m alembic revision --autogenerate -m "描述"
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m alembic downgrade -1
.\venv\Scripts\python.exe -m alembic current
# 对测试库单独跑迁移
.\venv\Scripts\python.exe -m alembic -x db_url=postgresql+asyncpg://clipboard:clipboard@127.0.0.1:5433/clipboard_test upgrade head

# 数据初始化
.\venv\Scripts\python.exe -m scripts.init_db            # 建表 + 演示用户 + 种子数据
.\venv\Scripts\python.exe -m scripts.init_db --no-seed  # 只建表
# --drop 会清库；目标库名不含 test 时需显式 ALLOW_DROP_DEV=1

# 连通性验证（仓库根目录）
.\venv\Scripts\python.exe ..\scripts\verify_postgres.py
```

## 已实现接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册（落库 + 唯一性校验，**直接返回令牌**；重名/重邮箱 409） |
| POST | `/api/v1/auth/login` | 登录（`username` 支持用户名或邮箱，错误统一 401） |
| GET | `/api/v1/auth/me` | 当前用户（需 `Authorization: Bearer <token>`） |
| POST | `/api/v1/clipboard/items` | 创建（含内容去重） |
| GET | `/api/v1/clipboard/items` | 列表（分页/筛选/按标题或内容搜索/排序） |
| GET | `/api/v1/clipboard/items/{id}` | 详情 |
| PATCH | `/api/v1/clipboard/items/{id}` | 更新（只改传入字段） |
| DELETE | `/api/v1/clipboard/items/{id}` | 删除单条 |
| DELETE | `/api/v1/clipboard/items` | 清空 |
| POST | `/api/v1/dev/reset` | ⚠️ 删数据重建种子（仅 dev 路由开启时） |
| GET | `/api/v1/dev/db` | 数据库连通性探测（确认连的是哪个库） |
| WS | `/api/v1/clipboard/ws?token=<JWT>` | 实时同步（事件表见 [`../docs/ws-protocol.md`](../docs/ws-protocol.md)） |
| GET | `/health` | 健康检查 |

> **`/api/v1/clipboard/*` 全部需要认证**：不带令牌返回 `401`。
> 本地可用演示账号登录：`demo` / `demo1234`（口令由 `DEMO_PASSWORD` 配置，
> 由 `scripts/init_db` 与 `dev/reset` 播种）。

> ⚠️ **必须用单 worker 启动**（`--workers 1`）。WebSocket 广播是进程内实现，
> 多 worker 会导致"数据一致但推送丢事件"。启动时会自动检测并拒绝：
> 既检查 `WEB_CONCURRENCY`，也独占一个固定回环端口（`core/single_worker.py`）。
> 详见 [`../docs/ws-protocol.md`](../docs/ws-protocol.md) 的「多实例问题」。

## 契约改动流程

改字段必须先改 `app/schemas/`，然后：

1. 生成迁移：`alembic revision --autogenerate -m "描述"`，**检查生成的文件**（见注意事项）
2. `alembic upgrade head`，重启服务确认 `/openapi.json` 已更新
3. `cd web && pnpm run gen:api` 重新生成前端类型
4. 同步 `harmony/entry/src/main/ets/models/ClipboardItem.ets`
5. 刷新 `docs/api.md` 的契约存档

## 注意事项

- **autogenerate 会记录数据库里的"多余表"**：如果开发库中手工建过测试表，
  生成的迁移会包含 `op.drop_table('xxx')`，在干净库（如 CI / 测试库）上执行会失败。
  生成后务必检查并删掉这类噪声语句。
- **`metadata` 是 SQLAlchemy 保留名**，模型里属性叫 `meta`、列名才是 `metadata`。
- 连接池开了 `pool_pre_ping`，数据库重启后会自动剔除坏连接。
