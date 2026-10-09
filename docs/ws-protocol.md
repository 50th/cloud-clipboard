# WebSocket 协议

> 实时同步端点。**本文件是协议约定，任何字段变更需同步三端。**
> ✅ 已实现（服务端 `routers/ws.py` + `services/ws_manager.py`，Web 端 `composables/useWebSocket.ts`）。

## 连接

```
ws://localhost:8000/api/v1/clipboard/ws?token=<JWT>
```

- `token`：**必需**。校验失败时服务端**先 accept 再以关闭码 `4401` 关闭**——
  这样浏览器能拿到明确的关闭码，而不是笼统的 1006 握手失败
- 生产环境必须用 `wss://`（AGENTS.md 第 9 节）
- `127.0.0.1` 与 `localhost` 等价

> ⚠️ **token 走 query string 的日志脱敏已实现**（两层）：
> 1. 端点入口调 `scrub_scope_token()` 把 token 从 ASGI scope 里删掉，
>    访问日志只剩 `/api/v1/clipboard/ws`，**根本没有 token**；
> 2. `install_log_redaction()` 给 uvicorn 的 handler 套一层 formatter，兜住其他 logger。
>
> ⚠️ **不要用 `logging.Filter` 去改写 `record.args` 做脱敏**：uvicorn 的
> `AccessFormatter` 依赖 args 里的 5 个字段，清空 args 会让**每个请求**都抛
> `ValueError: not enough values to unpack`，直接搞坏全部访问日志（实测踩过）。

## 消息格式

所有消息均为 JSON 文本帧，信封结构：

```json
{ "event": "clipboard.created", "data": { } }
```

## 服务端推送事件

| event | data | 说明 |
|-------|------|------|
| `clipboard.created` | `ClipboardItem` | 新记录创建 |
| `clipboard.updated` | `ClipboardItem` | **去重命中**导致的时间戳刷新，或标题变更（易漏，必须广播） |
| `clipboard.deleted` | `{ "id": "uuid" }` | 单条删除 |
| `clipboard.cleared` | `{}` | 全部清空 |
| `pong` | `{}` | 心跳响应 |

`ClipboardItem` 的结构与 HTTP 接口完全一致，见 `api.md`。

## 客户端发送

| action | 说明 |
|--------|------|
| `{ "action": "ping" }` | 心跳，服务端应回 `{ "event": "pong", "data": {} }` |

## 约定

- **心跳间隔 30 秒**：`WS_HEARTBEAT_MS = 30_000`（已落地在
  `web/src/composables/useWebSocket.ts`）
- **重连策略**：指数退避，首次 1 秒、上限 30 秒（`WS_BACKOFF_FIRST_MS` /
  `WS_BACKOFF_MAX_MS`）；收到关闭码 `4401` 时**不再重连**（令牌无效，重试无意义）
- **重连成功后必须调用 `GET /api/v1/clipboard/items` 拉取最新列表**（断线期间可能漏事件）
- **广播按用户隔离，不群发**（AGENTS.md 第 9 节）；同一用户的多条连接（多标签/多设备）都会收到
- Web 端收到事件后的处理是**静默重新拉取当前页**，而不是把载荷合并进本地列表：
  排序、分页、搜索都会影响"该出现哪些记录"，本地合并容易与后端规则不一致

## 多实例问题（重要）

`ConnectionManager` 是**进程内**数据结构。uvicorn 一旦以 `--workers > 1` 运行：

- 用户 A 连在 worker 1、用户 B 连在 worker 2 → **事件永远送不到**
- 数据库层是共享的，所以数据一致，但**推送不一致**且现象隐蔽

**本阶段的选择：强制单 worker**（`--workers 1`），并在 Redis Pub/Sub 落地前禁止扩容。

实现上做了**两道运行时守卫**（`app/core/single_worker.py`）：

1. 检查环境变量 `WEB_CONCURRENCY > 1` → 直接拒绝
2. **独占一个固定回环端口**（`LOCK_PORT = 49137`）→ 第二个实例绑定时拿到
   `WSAEADDRINUSE (10048)`，据此判定"已有实例"

> ⚠️ **为什么必须有第 2 道**：uvicorn 的 CLI `--workers N` **不会**写进环境变量
> （实测 worker 进程里 `WEB_CONCURRENCY` 是 `None`），只查环境变量会漏掉最常见的手误。
>
> ⚠️ **锁端口必须是固定值，不能写成 `bind(('127.0.0.1', 0))` 去"找个空闲端口"。**
> 实测 `bind(0)` 每次都返回不同端口（连续三次得到 13099/13100/13101），
> "探测-释放-再绑定"的写法在并发下**永不相撞**，锁形同虚设。

实测行为：`--workers 2` 时 worker B 检测到锁被占用 → lifespan 失败 →
uvicorn supervisor **停止整个进程组**（退出码 1），多 worker 服务无法对外提供服务。

## 循环同步防护

写回本地剪贴板会触发剪贴板变化监听，可能造成死循环：

- Web 端：`web/src/utils/clipboard.ts` 的 `isSelfWrite()` 标志位（写入后 800ms 窗口内忽略）✅ 已实现
- 鸿蒙端：`harmony/entry/src/main/ets/services/clipboardMonitor.ets` 需实现同样的标志位 ⬜ 尚未创建

## 调试

```powershell
# token 必须是真实 JWT：
#   $body = @{ username='demo'; password='demo1234' } | ConvertTo-Json
#   (Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/auth/login -Method Post -Body $body -ContentType 'application/json').token.access_token
pnpm dlx wscat -c "ws://127.0.0.1:8000/api/v1/clipboard/ws?token=<JWT>"
```

发送 `{"action":"ping"}`，应收到 `{"event":"pong","data":{}}`。

**自动化验证**：`cd web && pnpm test` 里的 `tests/websocket.test.ts` 会驱动真实的
`useWebSocket` 建两条连接，验证「A 上传 → B 秒级收到」与 A 删除后 B 同步消失。

## 落地位置

| 约定 | 落地文件 | 状态 |
|------|---------|------|
| WS 端点 + token 校验 | `server/app/routers/ws.py` | ✅ 已实现 |
| 连接管理与按用户广播 | `server/app/services/ws_manager.py` | ✅ 已实现 |
| 事件序列化（与 REST 共用） | `server/app/services/events.py` | ✅ 已实现 |
| token 日志脱敏 | `server/app/core/logging_utils.py` | ✅ 已实现 |
| 单 worker 守卫 | `server/app/core/single_worker.py` | ✅ 已实现 |
| Web 端连接、心跳、退避、事件分发 | `web/src/composables/useWebSocket.ts` | ✅ 已实现 |
| 自身写入标志位 | `web/src/utils/clipboard.ts` | ✅ 已实现 |
| 鸿蒙端对应实现 | `harmony/entry/src/main/ets/services/clipboardMonitor.ets` | ⬜ 尚未创建 |
