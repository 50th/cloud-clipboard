# WebSocket 协议

> 实时同步端点。**本文件是协议约定**（连接、事件、心跳），任何字段变更需同步三端。
> 实现细节与踩坑见 [`roadmap.md`](roadmap.md)。

## 连接

```
ws://localhost:8000/api/v1/clipboard/ws?token=<JWT>
```

- `token`：**必需**。校验失败时服务端**先 accept 再以关闭码 `4401` 关闭**——
  这样浏览器能拿到明确的关闭码，而不是笼统的 1006 握手失败
- 生产环境必须用 `wss://`（见 AGENTS.md 的「关键约束」）；`127.0.0.1` 与 `localhost` 等价
- ⚠️ 令牌走 query string 是**浏览器的硬限制**（WebSocket API 不允许自定义请求头），
  因此服务端必须对访问日志脱敏，不得记录 token 值

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

`ClipboardItem` 的结构与 HTTP 接口完全一致，见 [`api.md`](api.md)。

## 客户端发送

| action | 说明 |
|--------|------|
| `{ "action": "ping" }` | 心跳，服务端应回 `{ "event": "pong", "data": {} }` |

## 约定

- **心跳间隔 30 秒**（`WS_HEARTBEAT_MS`）
- **重连策略**：指数退避，首次 1 秒、上限 30 秒（`WS_BACKOFF_FIRST_MS` / `WS_BACKOFF_MAX_MS`）；
  收到 `4401` 时**不再重连**（令牌无效，重试无意义）
- **重连成功后必须重新拉取列表**（`GET /api/v1/clipboard/items`），断线期间可能漏事件
- **广播按用户隔离，不群发**（见 AGENTS.md 的「关键约束」）；同一用户的多条连接（多标签/多设备）都会收到
- Web 端收到事件后**静默重新拉取当前页**，而不是把载荷合并进本地列表：
  排序、分页、搜索都会影响"该出现哪些记录"，本地合并容易与后端规则不一致

## 多实例约束（重要）

连接表是**进程内**结构：`--workers > 1` 时 A 连 worker 1、B 连 worker 2，
**事件永远送不到**；而数据库是共享的，所以**数据一致、推送不一致**，现象隐蔽。

**本阶段决策：强制单 worker**（`--workers 1`），Redis Pub/Sub 落地前禁止扩容。
启动守卫会在多 worker 时拒绝服务（机制见 [`roadmap.md`](roadmap.md) 第 5 步踩坑 1）。

## 循环同步防护

写回本地剪贴板会触发剪贴板变化监听，可能造成死循环：

- Web 端：`web/src/utils/clipboard.ts` 的 `isSelfWrite()` 标志位（写入后 800ms 窗口内忽略）
- 鸿蒙端：需实现同样的标志位（见 `harmony/.../services/clipboardMonitor.ets`）

## 调试

```powershell
# token 必须是真实 JWT：
#   $body = @{ username='demo'; password='demo1234' } | ConvertTo-Json
#   (Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/auth/login -Method Post -Body $body -ContentType 'application/json').token.access_token
pnpm dlx wscat -c "ws://127.0.0.1:8000/api/v1/clipboard/ws?token=<JWT>"
```

发送 `{"action":"ping"}`，应收到 `{"event":"pong","data":{}}`。

**自动化验证**：`cd web && pnpm test` 的 `tests/websocket.test.ts` 会驱动真实的
`useWebSocket` 开两条连接，验证「A 上传 → B 秒级收到」与「A 删除 → B 同步消失」。
