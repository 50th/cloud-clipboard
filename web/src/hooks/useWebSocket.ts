/**
 * WebSocket 实时同步（第 5 步实现）。
 *
 * 协议见 AGENT.md 第 6 节：
 * - 连接：`ws://localhost:8000/api/v1/clipboard/ws?token=<JWT>`
 * - 事件：clipboard.created / updated / deleted / cleared / pong
 * - 心跳 30 秒；指数退避重连（首次 1s，上限 30s）；重连成功后拉取最新列表
 *
 * 本文件为第 2 步占位实现：不建立连接，只暴露配置与事件名，
 * 让 UI 层可以提前引用而不产生副作用。
 */

export type WsEventName =
  | 'clipboard.created'
  | 'clipboard.updated'
  | 'clipboard.deleted'
  | 'clipboard.cleared'
  | 'pong'

export interface WsEnvelope<T = unknown> {
  event: WsEventName
  data: T
}

export interface UseWebSocketOptions {
  /** 是否启用连接（第 5 步接入时传入 true） */
  enabled?: boolean
  /** JWT，作为 query 参数传给后端 */
  token?: string
  /** 重连成功后触发，用于拉取最新列表 */
  onReconnect?: () => void
}

export const WS_HEARTBEAT_MS = 30_000
export const WS_BACKOFF_MAX_MS = 30_000

const DEFAULT_WS_URL = 'ws://127.0.0.1:8000'

/** WebSocket 端点地址。 */
export function getWebSocketUrl(token?: string): string {
  const fromProcess = (
    globalThis as { process?: { env?: Record<string, string | undefined> } }
  ).process?.env?.VITE_WS_URL
  const base =
    ((import.meta.env ?? {}) as Record<string, string | undefined>).VITE_WS_URL ??
    fromProcess ??
    DEFAULT_WS_URL

  const url = `${base}/api/v1/clipboard/ws`
  return token ? `${url}?token=${encodeURIComponent(token)}` : url
}

/**
 * 占位 hook：`enabled` 为 false 时什么都不做。
 * 第 5 步在此实现连接、心跳、指数退避与事件分发。
 */
export function useWebSocket(options: UseWebSocketOptions = {}): {
  connected: boolean
  lastEvent: WsEnvelope | null
} {
  // 第 2 步：只做单端闭环，实时同步留到第 5 步
  void options
  return { connected: false, lastEvent: null }
}
