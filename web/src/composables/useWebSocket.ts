/**
 * WebSocket 实时同步。
 *
 * 协议见 `docs/ws-protocol.md`：
 * - 连接：`ws://localhost:8000/api/v1/clipboard/ws?token=<JWT>`
 * - 事件：clipboard.created / updated / deleted / cleared / pong
 * - 心跳 30 秒；指数退避重连（首次 1s，上限 30s）；重连成功后拉取最新列表
 *
 * ⚠️ **浏览器无法自定义 WebSocket 请求头**，令牌只能走 query string；
 * 服务端已对访问日志脱敏（见 `server/app/core/logging_utils.py`）。
 */

import { onScopeDispose, ref } from 'vue'
import type { Ref } from 'vue'

import { API_BASE_URL, getToken } from '#src/api/client.ts'

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
  /** 是否启用连接（未登录时应传 false） */
  enabled?: boolean
  /** JWT，作为 query 参数传给后端；不传时从 localStorage 读取 */
  token?: string
  /** 收到任意剪贴板事件时触发（用于刷新列表） */
  onEvent?: (envelope: WsEnvelope) => void
  /** 重连成功后触发，用于拉取最新列表（断线期间可能漏事件） */
  onReconnect?: () => void
}

export const WS_HEARTBEAT_MS = 30_000
export const WS_BACKOFF_MAX_MS = 30_000
export const WS_BACKOFF_FIRST_MS = 1_000

/** 服务端约定：令牌无效时以此关闭码断开（见 docs/ws-protocol.md） */
export const WS_CLOSE_UNAUTHORIZED = 4401

const DEFAULT_WS_URL = 'ws://127.0.0.1:8000'

/** 读取环境变量：浏览器走 import.meta.env，Node（测试）走 process.env。 */
function readWsUrl(): string | undefined {
  const fromProcess = (
    globalThis as { process?: { env?: Record<string, string | undefined> } }
  ).process?.env?.VITE_WS_URL
  if (fromProcess) {
    return fromProcess
  }
  return ((import.meta.env ?? {}) as Record<string, string | undefined>).VITE_WS_URL
}

/**
 * 解析 WebSocket 基址。
 *
 * 优先 `VITE_WS_URL`（WS 与 API 不在同一主机时用，例如走反向代理）；
 * **未配置时从 API 基址推导**（`http→ws`）。
 *
 * ⚠️ 推导这个兜底很重要：否则只改 `VITE_API_BASE_URL` 时，
 * 请求会打新后端、WebSocket 却仍连默认的 8000，**两端指向不同后端**，
 * 表现为"数据写进去了但收不到实时事件"（隔离测试时就踩到过）。
 */
function resolveWsBase(): string {
  const explicit = readWsUrl()
  if (explicit) {
    return explicit
  }
  const derived = API_BASE_URL.replace(/^http/, 'ws')
  return derived.length > 0 ? derived : DEFAULT_WS_URL
}

/** WebSocket 端点地址。 */
export function getWebSocketUrl(token?: string): string {
  const url = `${resolveWsBase()}/api/v1/clipboard/ws`
  return token ? `${url}?token=${encodeURIComponent(token)}` : url
}

/**
 * 第 `attempt` 次重连前的等待时长（指数退避，上限 30 秒）。
 *
 * `attempt` 从 0 开始：1s、2s、4s、8s、16s、30s、30s…
 */
export function backoffDelay(attempt: number): number {
  return Math.min(WS_BACKOFF_FIRST_MS * 2 ** attempt, WS_BACKOFF_MAX_MS)
}

export interface UseWebSocketReturn {
  /** 是否已连接（ref，便于模板与 computed 直接使用） */
  connected: Ref<boolean>
  /** 已连续失败的重连次数（0 表示连接正常） */
  retryCount: Ref<number>
  /** 最近收到的一条事件 */
  lastEvent: Ref<WsEnvelope | null>
  /** 建连/断连记录，便于排查 */
  log: Ref<string[]>
  connect: () => void
  disconnect: () => void
}

/**
 * 建立并维持与后端的 WebSocket 连接。
 *
 * 返回的 `connected` 可用于界面提示。
 */
export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const connected = ref(false)
  const retryCount = ref(0)
  const lastEvent = ref<WsEnvelope | null>(null)
  const log = ref<string[]>([])

  let socket: WebSocket | null = null
  let heartbeatTimer: ReturnType<typeof setInterval> | undefined
  let retryTimer: ReturnType<typeof setTimeout> | undefined
  /** 主动断开时置 true，避免把正常关闭误判为断线而去重连 */
  let closedByUs = false

  function appendLog(message: string) {
    log.value = [...log.value.slice(-19), `${new Date().toLocaleTimeString()} ${message}`]
  }

  function clearTimers() {
    if (heartbeatTimer !== undefined) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = undefined
    }
    if (retryTimer !== undefined) {
      clearTimeout(retryTimer)
      retryTimer = undefined
    }
  }

  function disconnect() {
    closedByUs = true
    clearTimers()
    if (socket) {
      // 先把回调摘掉，避免 close() 触发 onclose 再排一次重连
      socket.onopen = null
      socket.onmessage = null
      socket.onerror = null
      socket.onclose = null
      try {
        socket.close()
      } catch {
        /* 已经关闭就忽略 */
      }
      socket = null
    }
    connected.value = false
  }

  function scheduleReconnect() {
    if (closedByUs) {
      return
    }
    const delay = backoffDelay(retryCount.value)
    retryCount.value += 1
    appendLog(`将在 ${Math.round(delay / 1000)}s 后重连（第 ${retryCount.value} 次）`)
    retryTimer = setTimeout(() => {
      retryTimer = undefined
      connect()
    }, delay)
  }

  function startHeartbeat() {
    if (heartbeatTimer !== undefined) {
      clearInterval(heartbeatTimer)
    }
    // 后端只认 {"action":"ping"}，回 {"event":"pong","data":{}}
    heartbeatTimer = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ action: 'ping' }))
      }
    }, WS_HEARTBEAT_MS)
  }

  function connect() {
    if (options.enabled === false) {
      return
    }
    if (
      socket &&
      (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)
    ) {
      return
    }

    closedByUs = false
    const token = options.token ?? getToken() ?? undefined
    if (!token) {
      appendLog('缺少令牌，暂不连接')
      return
    }

    const wasReconnect = retryCount.value > 0
    const url = getWebSocketUrl(token)

    try {
      socket = new WebSocket(url)
    } catch (error) {
      appendLog(`建立连接失败: ${String(error)}`)
      scheduleReconnect()
      return
    }

    socket.onopen = () => {
      connected.value = true
      retryCount.value = 0
      appendLog('已连接')
      startHeartbeat()
      // 断线期间可能漏掉事件，重连成功后必须重新拉取列表
      if (wasReconnect) {
        options.onReconnect?.()
      }
    }

    socket.onmessage = (event: MessageEvent) => {
      let envelope: WsEnvelope
      try {
        envelope = JSON.parse(String(event.data)) as WsEnvelope
      } catch {
        appendLog('收到无法解析的消息，已忽略')
        return
      }
      lastEvent.value = envelope
      if (envelope.event !== 'pong') {
        options.onEvent?.(envelope)
      }
    }

    socket.onerror = () => {
      // 浏览器不提供错误细节，真正的处理在 onclose 里
      appendLog('连接出错')
    }

    socket.onclose = (event: CloseEvent) => {
      connected.value = false
      clearTimers()
      socket = null
      if (closedByUs) {
        appendLog('已断开')
        return
      }
      // 4401 = 服务端判定令牌无效：重连没有意义，直接放弃
      if (event.code === WS_CLOSE_UNAUTHORIZED) {
        appendLog('令牌无效或已过期，需重新登录')
        return
      }
      appendLog(`连接关闭（code=${event.code}）`)
      scheduleReconnect()
    }
  }

  // 作用域销毁（组件卸载）时必须断开，否则会留下后台重连定时器
  onScopeDispose(() => disconnect())

  return {
    connected,
    retryCount,
    lastEvent,
    log,
    connect,
    disconnect,
  }
}
