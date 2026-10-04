# WebSocket 协议

> 实时同步端点，第 5 步实现。**本文件是协议约定，任何字段变更需同步三端。**

## 连接

```
ws://localhost:8000/api/v1/clipboard/ws?token=<JWT>
```

- `token`：**必需**（第 4 步接入 JWT 后），服务端校验失败应关闭连接（关闭码 `4401`）
- 生产环境必须用 `wss://`（AGENT.md 第 9 节）
- `127.0.0.1` 与 `localhost` 等价

> ⚠️ **实现注意**：token 走 query string 会被 uvicorn 的访问日志明文记录。
> 实现时需对 `token` 参数脱敏（自定义 log filter 或改用 `Sec-WebSocket-Protocol` 头传令牌）。

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

- **心跳间隔 30 秒**（`WS_HEARTBEAT_MS = 30_000`，已定义于 `web/src/hooks/useWebSocket.ts`）
- **重连策略**：指数退避，首次 1 秒、上限 30 秒（`WS_BACKOFF_MAX_MS = 30_000`）
- **重连成功后必须调用 `GET /api/v1/clipboard/items` 拉取最新列表**（断线期间可能漏事件）
- **广播按用户隔离，不群发**（AGENT.md 第 9 节）

## 循环同步防护

写回本地剪贴板会触发剪贴板变化监听，可能造成死循环：

- Web 端：`web/src/utils/clipboard.ts` 的 `isSelfWrite()` 标志位（写入后 800ms 窗口内忽略）
- 鸿蒙端：`harmony/entry/src/main/ets/services/clipboardMonitor.ets` 需实现同样的标志位

## 多实例问题（重要）

第 5 步的 `ConnectionManager` 是**进程内**数据结构。uvicorn 一旦以 `--workers > 1` 运行：

- 用户 A 连在 worker 1、用户 B 连在 worker 2 → **事件永远送不到**
- 数据库层是共享的，所以数据一致，但**推送不一致**且现象隐蔽

因此顺序上只有两种选择，不能拖：

1. **第 5 步强制单 worker**（`--workers 1`），并在 Redis Pub/Sub 落地前禁止扩容；或
2. **第 5 步同时引入 Redis Pub/Sub**，让广播跨进程

**该约束已写入 AGENT.md 第 6 节**：不能拖到"多副本部署"阶段再处理。

## 调试

```powershell
# 需先取到 token（第 4 步前可随便填）
npx wscat -c "ws://127.0.0.1:8000/api/v1/clipboard/ws?token=<JWT>"
```

发送 `{"action":"ping"}`，应收到 `{"event":"pong","data":{}}`。
