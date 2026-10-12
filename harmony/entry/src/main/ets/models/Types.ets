/**
 * 数据模型 —— 与后端 Pydantic Schema **严格对齐**。
 *
 * 字段清单的唯一事实来源是 `server/app/schemas/`；改动必须同步本文件
 * （见 AGENTS.md 的「数据契约」）。
 */

/** 内容类型。阶段一只有 `text` 可用，`image` / `file` 属后续阶段。 */
export enum ContentType {
  TEXT = 'text',
  IMAGE = 'image',
  FILE = 'file',
}

/** 列表排序字段。 */
export enum SortBy {
  CREATED_AT = 'created_at',
  UPDATED_AT = 'updated_at',
}

/** 排序方向。 */
export enum SortOrder {
  DESC = 'desc',
  ASC = 'asc',
}

/**
 * 剪贴板项（对应 `ClipboardItemResponse`）。
 *
 * ⚠️ **没有 `content_hash`**：它仅服务端用于去重，任何响应都不包含。
 */
export interface ClipboardItem {
  id: string;
  user_id: string;
  title: string;
  content_type: string;
  content: string;
  preview?: string | null;
  metadata?: Record<string, string | number> | null;
  created_at: string;
  updated_at: string;
}

/** 列表响应（对应 `ClipboardItemList`）。 */
export interface ClipboardItemList {
  items: ClipboardItem[];
  page: number;
  size: number;
  total: number;
  pages: number;
}

/** 创建请求（对应 `ClipboardItemCreate`）。 */
export interface ClipboardItemCreate {
  content: string;
  title?: string;
  /** IANA 时区名，服务端用它生成标题里的时间文本 */
  timezone?: string;
  content_type?: string;
  preview?: string;
  metadata?: Record<string, string | number>;
}

/** 更新请求（对应 `ClipboardItemUpdate`，只传要改的字段）。 */
export interface ClipboardItemUpdate {
  content?: string;
  title?: string;
  timezone?: string;
  preview?: string;
  metadata?: Record<string, string | number>;
}

/** 用户公开信息（对应 `UserResponse`）。**绝不含密码哈希**。 */
export interface UserInfo {
  id: string;
  username: string;
  email: string;
  nickname?: string | null;
  avatar_url?: string | null;
  created_at: string;
}

/** 令牌信息（对应 `TokenResponse`）。 */
export interface TokenInfo {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserInfo;
}

/**
 * 注册/登录响应（对应 `AuthResponse`）。
 *
 * ⚠️ 这是**扁平结构**：用户信息在顶层，令牌在 `token` 里。
 * 别把整个响应当成用户对象（Web 端就踩过这个坑）。
 */
export interface AuthResponse {
  id: string;
  username: string;
  email: string;
  nickname?: string | null;
  avatar_url?: string | null;
  created_at: string;
  token: TokenInfo;
}

/** 通用消息响应（删除类接口）。 */
export interface MessageResponse {
  success: boolean;
  message: string;
}

/** WebSocket 事件名，与 `docs/ws-protocol.md` 一致。 */
export enum WsEventName {
  CREATED = 'clipboard.created',
  UPDATED = 'clipboard.updated',
  DELETED = 'clipboard.deleted',
  CLEARED = 'clipboard.cleared',
  PONG = 'pong',
}

/** WebSocket 消息信封。 */
export interface WsEnvelope {
  event: string;
  data: object;
}

/** 服务端令牌无效时的 WebSocket 关闭码。 */
export const WS_CLOSE_UNAUTHORIZED: number = 4401;
