# 云剪贴板 · API 契约

> **本文件是接口契约的速查摘要，不是事实来源，也不内嵌完整 OpenAPI。**
> 契约的事实来源始终是 `server/app/schemas/`（Pydantic Schema）；最新内容查运行中后端的 `/openapi.json`。
> 在线交互式文档：<http://127.0.0.1:8000/docs> · 机器可读：<http://127.0.0.1:8000/openapi.json>

## 导出方式

```powershell
# ── Windows（PowerShell）示例 ───────────────────────────────────────

# 方式一：从运行中的后端拉取（永远与实现一致）——需要【两个终端】
# 终端 1：在 server 目录下启动服务，并保持它一直运行
cd server
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000

# 终端 2：另开一个终端，在仓库根目录执行导出
Invoke-RestMethod http://127.0.0.1:8000/openapi.json | ConvertTo-Json -Depth 30 | Set-Content -Encoding utf8 docs\.openapi.json

# 方式二：不启动服务、不开第二个终端，直接导出（app.openapi() 是纯静态构建，不需要连数据库）
cd server
.\venv\Scripts\python.exe -c "import json;from app.main import app;print(json.dumps(app.openapi(),ensure_ascii=False,indent=2))" | Set-Content -Encoding utf8 ..\docs\.openapi.json
```

```bash
# ── bash / macOS / Linux 等价写法 ───────────────────────────────────

# 方式一：从运行中的后端拉取（同样需要【两个终端】）
cd server
./venv/bin/python -m uvicorn app.main:app --port 8000

# 终端 2：在仓库根目录执行导出
curl -s http://127.0.0.1:8000/openapi.json | python -m json.tool > docs/.openapi.json

# 方式二：不启动服务直接导出
cd server
./venv/bin/python -c "import json;from app.main import app;print(json.dumps(app.openapi(),ensure_ascii=False,indent=2))" > ../docs/.openapi.json
```

> ⚠️ 导出的是**裸 JSON 文件** `docs/.openapi.json`——**临时文件，用完请删掉，不要提交**
> （仓库 `.gitignore` 目前没有覆盖它，它会在 `git status` 里以未跟踪文件出现）。
> 逐字段定义请直接读它，或按下方「完整字段定义」的三条途径获取。
>
> 📌 **方式一需要两个终端**：终端 1 负责启动并**持续运行** uvicorn（关掉它，终端 2 的拉取就会连接失败）；
> 终端 2 只发一次 HTTP 请求把 JSON 拉下来。两条命令的当前目录不同，注释里已分别标出。

## 接口契约修改流程（AGENTS.md 第 4 节）

1. 改 `server/app/schemas/`（**契约唯一事实来源**）
2. 重启 FastAPI，确认 `/openapi.json` 已更新
3. 刷新本文件的「接口摘要」与「核心数据契约」（只更新与本次变更相关的行，不要重写全文）
4. 重新生成 Web 端类型：`cd web && pnpm run gen:api`
5. 同步鸿蒙端 `harmony/entry/src/main/ets/models/ClipboardItem.ets`（鸿蒙端创建后）

---

## 接口摘要

> 下表是**人读摘要**；逐字段的权威定义以运行中后端的 `/openapi.json` 为准（见文末「完整字段定义」）。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册：收 `username/email/password`，**不落库、不校验唯一性**，返回演示用户 + 假 token |
| POST | `/api/v1/auth/login` | 登录：**当前不接收请求体、不校验凭证**，直接返回演示用户 + 假 token（第 4 步接入真实校验） |
| GET | `/api/v1/auth/me` | 当前用户（当前固定返回演示用户） |
| POST | `/api/v1/clipboard/items` | 创建；`title` 留空时自动生成，按 `timezone` 显示本地时间 |
| GET | `/api/v1/clipboard/items` | 列表：分页 / 类型筛选 / 按标题或内容搜索 / 排序 |
| GET | `/api/v1/clipboard/items/{id}` | 详情 |
| PATCH | `/api/v1/clipboard/items/{id}` | 更新（只改显式传入的字段；自动保存复用同一条草稿，避免中间态多行） |
| DELETE | `/api/v1/clipboard/items/{id}` | 删除单条 |
| DELETE | `/api/v1/clipboard/items` | 清空 |
| POST | `/api/v1/dev/reset` | ⚠️ 删数据并重建种子（**仅开发路由开启时注册**） |
| GET | `/api/v1/dev/db` | 探测当前连接的数据库（仅开发路由开启时） |
| GET | `/health` | 健康检查 |
| GET | `/` | 服务信息 |
| WS | `/api/v1/clipboard/ws?token=xxx` | ⬜ 实时同步（**第 5 步**，尚未实现；协议见 [`ws-protocol.md`](ws-protocol.md)） |
| POST | `/api/v1/clipboard/upload` | ⬜ 图片/文件上传（**阶段二**，尚未实现） |

> 最后两个接口**不在 `/openapi.json` 里**——`ws` 与 `upload` 尚未实现，所以不会出现在在线文档中。
> 它们是已排期的约定目标，列在这里只为了避免下游以为漏掉。排期见 [`roadmap.md`](roadmap.md)。

## 核心数据契约

### ClipboardItemResponse

```python
class ClipboardItemResponse(BaseModel):
    id: str                    # uuid
    user_id: str               # uuid
    title: str                 # 用户填写；留空时服务端生成 "demo · 10-05 21:56"
    content_type: ContentType  # text | image | file
    content: str               # 文字内容或文件 URL
    preview: Optional[str]     # 预览文本
    metadata: Optional[dict]   # {"mime": "text/plain", "size": 1024, ...}
    created_at: datetime       # ISO 8601 UTC
    updated_at: datetime       # ISO 8601 UTC
```

列表响应 `ClipboardItemList` = `items: ClipboardItemResponse[]` + `page` / `size` / `total` / `pages`。

### 关键约定

- 时间统一 ISO 8601 UTC，形如 `2026-09-27T10:00:00Z`；数据库列用 `timestamptz`
- `content_hash` **不对外暴露**，仅服务端用于去重
- `title` 留空时服务端生成 `<用户名> · <月-日 时:分>`，时间按请求里的 `timezone`（IANA 名）展示；
  数据库**始终存 UTC**，时区只影响标题文本。未传或非法时回退 `DEFAULT_TIMEZONE`（默认 `Asia/Shanghai`）
- 去重：同一用户提交相同 `content` → 更新时间戳、不新建记录；**不覆盖已有标题**（除非本次显式传 `title`）
- 搜索同时匹配 `title` 与 `content`
- 分页：`page` 从 1 开始，`size` 默认 20、最大 100
- 阶段一仅支持 `content_type = text`；`image` / `file` 属阶段二、阶段三

---

## 完整字段定义

本文件不再内嵌完整 OpenAPI。需要逐字段定义时，按以下优先级获取：

1. 后端在跑：`curl http://127.0.0.1:8000/openapi.json`
2. 后端未跑：读 `server/app/schemas/`（契约唯一事实来源）
3. 交互式浏览：<http://127.0.0.1:8000/docs>

导出裸 JSON 到 `docs/.openapi.json` 的命令见本文顶部。
