/**
 * 管理端 HTTP 客户端。
 *
 * 与用户端完全隔离：
 * - token 只写 `sessionStorage`，关闭标签页即失效
 * - 401 只清管理端 token，不影响用户端登录态
 * - **不提供“记住密码”**，不把密码写入任何浏览器存储
 */

import axios from 'axios'

import { API_BASE_URL, API_PREFIX } from '#src/api/client.ts'
import type { components } from '#src/types/api.ts'

export type User = components['schemas']['UserResponse']
export type AuthResponse = components['schemas']['AuthResponse']
export type AdminUser = components['schemas']['AdminUserResponse']
export type AdminUserList = components['schemas']['AdminUserList']
export type AdminUserUpdate = components['schemas']['AdminUserUpdate']
export type AdminClipboardItem = components['schemas']['AdminClipboardItemResponse']
export type AdminClipboardItemList = components['schemas']['AdminClipboardItemList']
export type AdminStats = components['schemas']['AdminStatsResponse']
export type AdminAuditLog = components['schemas']['AdminAuditLogResponse']
export type AdminAuditLogList = components['schemas']['AdminAuditLogList']
export type MessageResponse = components['schemas']['MessageResponse']

const TOKEN_KEY = 'cloud-clipboard.admin.token'

/** 内存兜底：隐私模式下 sessionStorage 可能不可用，当前标签页仍可正常使用。 */
let memoryToken: string | null = null

/** 读取管理端 JWT。 */
export function getAdminToken(): string | null {
  try {
    const stored = sessionStorage.getItem(TOKEN_KEY)
    if (stored) {
      return stored
    }
  } catch {
    /* 隐私模式或 Node 测试环境可能不可用 */
  }
  return memoryToken
}

/** 保存 / 清除管理端 JWT。 */
export function setAdminToken(token: string | null): void {
  memoryToken = token
  try {
    if (token) {
      sessionStorage.setItem(TOKEN_KEY, token)
    } else {
      sessionStorage.removeItem(TOKEN_KEY)
    }
  } catch {
    /* 隐私模式或 Node 测试环境可能不可用，忽略即可 */
  }
}

export const adminHttp = axios.create({
  baseURL: `${API_BASE_URL}${API_PREFIX}`,
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
})

adminHttp.interceptors.request.use((config) => {
  const token = getAdminToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

type UnauthorizedHandler = () => void
let onUnauthorized: UnauthorizedHandler | null = null

/** 注册管理端“令牌失效”回调（由 admin/main.ts 在 Pinia 就绪后注册）。 */
export function setAdminUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler
}

adminHttp.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const url = error.config?.url ?? ''
      const isLoginEntry = url.includes('/auth/login') || url.includes('/auth/register')
      if (!isLoginEntry) {
        setAdminToken(null)
        onUnauthorized?.()
      }
    }
    return Promise.reject(error)
  },
)

/** 管理员登录：复用 `/auth/login`，由调用方校验 `is_admin`。 */
export async function adminLogin(
  username: string,
  password: string,
): Promise<AuthResponse> {
  const { data } = await adminHttp.post<AuthResponse>('/auth/login', {
    username,
    password,
  })
  return data
}

/** 获取当前管理员信息（令牌失效会触发 401 处理）。 */
export async function adminMe(): Promise<User> {
  const { data } = await adminHttp.get<User>('/auth/me')
  return data
}
