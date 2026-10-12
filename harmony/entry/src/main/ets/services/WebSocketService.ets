/**
 * WebSocket 实时同步客户端。
 *
 * 协议见 `docs/ws-protocol.md`：
 * - 连接：`ws://<host>/api/v1/clipboard/ws?token=<JWT>`
 * - 事件：`clipboard.created` / `updated` / `deleted` / `cleared` / `pong`
 * - 心跳 30 秒；指数退避重连（首次 1s，上限 30s）；重连成功后必须重新拉列表
 * - 服务端以关闭码 **4401** 表示令牌无效，此时**不要重连**（重试无意义）
 *
 * ⚠️ 令牌只能走 query string——WebSocket 握手无法带自定义请求头。
 *    服务端已对访问日志脱敏（见 `server/app/core/logging_utils.py`）。
 */
import { webSocket } from '@kit.NetworkKit';
import { BusinessError } from '@kit.BasicServicesKit';

import { API_PREFIX, WS_BACKOFF_MAX_MS, WS_HEARTBEAT_MS } from '../common/Config';
import { WsEnvelope, WS_CLOSE_UNAUTHORIZED } from '../models/Types';

/** 连接状态变化回调。 */
export type ConnectionListener = (connected: boolean) => void;
/** 收到剪贴板事件时的回调（`pong` 不会触发）。 */
export type EventListener = (envelope: WsEnvelope) => void;

/** 计算第 `attempt` 次重连的等待时长（1s、2s、4s…上限 30s）。 */
export function backoffDelay(attempt: number): number {
  return Math.min(1000 * Math.pow(2, attempt), WS_BACKOFF_MAX_MS);
}

export class WebSocketService {
  private baseUrl: string;
  private token: string;

  private socket: webSocket.WebSocket | null = null;
  private heartbeatTimer: number = -1;
  private retryTimer: number = -1;
  private retryAttempt: number = 0;
  /** 主动断开时置 true，避免把正常关闭当成断线去重连 */
  private closedByUs: boolean = false;

  private onConnection: ConnectionListener | null = null;
  private onEvent: EventListener | null = null;
  private onReconnect: (() => void) | null = null;

  constructor(baseUrl: string, token: string) {
    this.baseUrl = baseUrl;
    this.token = token;
  }

  /** 更新令牌（重新登录后调用）。 */
  updateToken(token: string): void {
    this.token = token;
  }

  /** 构造带令牌的连接地址。 */
  buildUrl(): string {
    const wsBase = this.baseUrl.replace(/^http/, 'ws');
    return `${wsBase}${API_PREFIX}/clipboard/ws?token=${encodeURIComponent(this.token)}`;
  }

  /**
   * 建立连接并自动维持。
   *
   * `onReconnect` 会在**重连成功后**触发——断线期间可能漏事件，必须重新拉列表。
   */
  connect(
    onConnection: ConnectionListener,
    onEvent: EventListener,
    onReconnect: () => void,
  ): void {
    this.onConnection = onConnection;
    this.onEvent = onEvent;
    this.onReconnect = onReconnect;
    this.open();
  }

  private open(): void {
    if (this.token.length === 0) {
      this.notifyConnection(false);
      return;
    }

    this.closedByUs = false;
    const isRetry = this.retryAttempt > 0;
    const socket = webSocket.createWebSocket();
    this.socket = socket;

    socket.on('open', () => {
      this.retryAttempt = 0;
      this.notifyConnection(true);
      this.startHeartbeat();
      if (isRetry) {
        // 重连成功：断线期间可能漏了事件
        if (this.onReconnect !== null) {
          this.onReconnect();
        }
      }
    });

    socket.on('message', (err: BusinessError, data: string | ArrayBuffer) => {
      if (typeof data !== 'string') {
        return;
      }
      this.handleMessage(data);
    });

    socket.on('close', (err: BusinessError, result: webSocket.CloseResult) => {
      this.stopHeartbeat();
      this.socket = null;
      this.notifyConnection(false);

      if (this.closedByUs) {
        return;
      }
      // 4401 = 令牌无效，重连没有意义
      if (result.code === WS_CLOSE_UNAUTHORIZED) {
        return;
      }
      this.scheduleReconnect();
    });

    socket.on('error', (err: BusinessError) => {
      // 错误之后通常还会收到 close，重连逻辑统一放在 close 里
      this.stopHeartbeat();
    });

    socket.connect(this.buildUrl()).catch((error: BusinessError) => {
      this.notifyConnection(false);
      this.scheduleReconnect();
    });
  }

  private handleMessage(raw: string): void {
    let envelope: WsEnvelope;
    try {
      envelope = JSON.parse(raw) as WsEnvelope;
    } catch (error) {
      // 解析不了的消息直接忽略，不要因此断开连接
      return;
    }
    if (envelope.event === 'pong') {
      return;
    }
    if (this.onEvent !== null) {
      this.onEvent(envelope);
    }
  }

  private scheduleReconnect(): void {
    if (this.closedByUs) {
      return;
    }
    if (this.retryTimer !== -1) {
      clearTimeout(this.retryTimer);
    }
    const delay = backoffDelay(this.retryAttempt);
    this.retryAttempt += 1;
    this.retryTimer = setTimeout(() => {
      this.retryTimer = -1;
      this.open();
    }, delay);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.socket !== null) {
        this.socket.send(JSON.stringify({ action: 'ping' })).catch(() => {
          // 发送失败交给 close 事件处理重连
        });
      }
    }, WS_HEARTBEAT_MS);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer !== -1) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = -1;
    }
  }

  private notifyConnection(connected: boolean): void {
    if (this.onConnection !== null) {
      this.onConnection(connected);
    }
  }

  /** 主动断开（退出登录或页面销毁时必须调用，否则会持续后台重连）。 */
  disconnect(): void {
    this.closedByUs = true;
    this.stopHeartbeat();
    if (this.retryTimer !== -1) {
      clearTimeout(this.retryTimer);
      this.retryTimer = -1;
    }
    this.retryAttempt = 0;
    const socket = this.socket;
    this.socket = null;
    if (socket !== null) {
      socket.close().catch(() => {
        // 已经关闭就忽略
      });
    }
    this.onConnection = null;
    this.onEvent = null;
    this.onReconnect = null;
  }
}
