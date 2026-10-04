# server —— 云剪贴板后端

FastAPI + uvicorn。当前处于 **第 1 步：骨架 + 数据契约**，接口返回内存假数据。

## 快速开始（Windows）

```powershell
cd server

# 1. 虚拟环境（已创建可跳过）
python -m venv venv

# 2. 安装依赖
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. 环境变量
Copy-Item .env.example .env

# 4. 启动服务
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

访问 <http://127.0.0.1:8000/docs> 查看 Swagger UI。

## 目录结构

```
server/
├── app/
│   ├── main.py              # 应用入口：注册路由、CORS、OpenAPI 元信息
│   ├── core/
│   │   └── config.py        # 环境变量（pydantic-settings）
│   ├── schemas/             # ✅ 数据契约（唯一事实来源）
│   │   ├── common.py        # ContentType / SortOrder / SortBy
│   │   ├── user.py
│   │   └── clipboard.py
│   ├── crud/                # 数据访问层（当前为内存假数据）
│   │   ├── store.py         # 内存存储 + 种子数据
│   │   ├── user.py          # 演示用户
│   │   └── clipboard.py     # 增删查改 + 去重
│   ├── routers/
│   │   ├── auth.py          # 注册 / 登录 / 当前用户
│   │   └── clipboard.py     # 剪贴板 CRUD
│   ├── services/            # 业务服务（第 5 步：ws_manager.py）
│   └── db/                  # 数据库层（第 3 步填充）
├── tests/
├── alembic/                 # 迁移（第 3 步填充）
├── requirements.txt
└── .env.example
```

## 已实现接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册（假数据） |
| POST | `/api/v1/auth/login` | 登录，返回假 token |
| GET | `/api/v1/auth/me` | 当前用户 |
| POST | `/api/v1/clipboard/items` | 创建（含内容去重） |
| GET | `/api/v1/clipboard/items` | 列表（分页/筛选/搜索/排序） |
| GET | `/api/v1/clipboard/items/{id}` | 详情 |
| DELETE | `/api/v1/clipboard/items/{id}` | 删除单条 |
| DELETE | `/api/v1/clipboard/items` | 清空 |

## 演示数据

首次启动时会写入 4 条内存种子数据（`app/crud/store.py` 的 `seed_demo_items()`）。
所有数据保存在进程内存中，**重启即丢失**——这是第 1 步的预期行为，第 3 步接入 PostgreSQL 后消除。

## 契约改动流程

改字段必须先改 `app/schemas/`，然后：

1. 重启服务，确认 `/openapi.json` 已更新
2. `npx openapi-typescript http://127.0.0.1:8000/openapi.json -o web/src/types/api.d.ts`
3. 同步 `harmony/entry/src/main/ets/models/ClipboardItem.ets`
4. 更新 `docs/api.yaml`
