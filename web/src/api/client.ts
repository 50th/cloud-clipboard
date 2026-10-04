/**
 * HTTP 客户端统一封装（axios）。
 *
 * 规范：组件不直接调用 axios（AGENT.md 第 8 节），一律走 `src/api/`。
 */

import axios, { AxiosError } from 'axios'

import type { components } from '#src/types/api.ts'

export type ClipboardItem = components['schemas']['ClipboardItemResponse']
export type ClipboardItemList = components['schemas']['ClipboardItemList']
export type ClipboardItemCreate = components['schemas']['ClipboardItemCreate']
export type User = components['schemas']['UserResponse']
export type AuthResponse = components['schemas']['AuthResponse']
export type SortBy = components['schemas']['SortBy']
export type SortOrder = components['schemas']['SortOrder']
export type ContentType = components['schemas']['ContentType']

const DEFAULT_BASE_URL = 'http://127.0.0.1:8000'

/**
 * 读取环境变量。
 * 浏览器走 Vite 的 `import.meta.env`；Node（端到端测试）走 `process.env`。
 */
function readEnv(
  key: 'VITE_API_BASE_URL' | 'VITE_WS_URL' | 'VITE_AUTH_TOKEN',
): string | undefined {
  const fromProcess = (
    globalThis as { process?: { env?: Record<string, string | undefined> } }
  ).process?.env?.[key]
  if (fromProcess) {
    return fromProcess
  }
  const fromImportMeta = ((import.meta.env ?? {}) as Record<string, string | undefined>)[key]
  return fromImportMeta || undefined
}

/** 后端基址：优先取环境变量，默认与本机后端一致。 */
export const API_BASE_URL: string = readEnv('VITE_API_BASE_URL') ?? DEFAULT_BASE_URL

export const API_PREFIX = '/api/v1'

const TOKEN_KEY = 'cloud-clipboard.token'

/** 读取本地保存的 JWT（第 4 步接入登录后使用）。 */
export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

/** 保存 / 清除 JWT。 */
export function setToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token)
    } else {
      localStorage.removeItem(TOKEN_KEY)
    }
  } catch {
    /* 隐私模式下 localStorage 可能不可用，忽略即可 */
  }
}

export const http = axios.create({
  baseURL: `${API_BASE_URL}${API_PREFIX}`,
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
})

// 自动附加 Bearer token（未登录时后端按演示用户处理）
http.interceptors.request.use((config) => {
  const bearer = readEnv('VITE_AUTH_TOKEN') || getToken()
  if (bearer) {
    config.headers.Authorization = `Bearer ${bearer}`
  }
  return config
})

/** 从任意异常中提取对用户友好的错误文本。 */
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ detail?: string | { msg?: string }[] }>
    const detail = axiosError.response?.data?.detail

    if (typeof detail === 'string') {
      return detail
    }
    if (Array.isArray(detail) && detail.length > 0) {
      return detail
        .map((entry) => (typeof entry === 'string' ? entry : entry?.msg ?? ''))
        .filter(Boolean)
        .join('；')
    }
    if (axiosError.response) {
      return `请求失败（HTTP ${axiosError.response.status}）`
    }
    if (axiosError.code === 'ERR_NETWORK' || axiosError.code === 'ECONNREFUSED') {
      return `无法连接后端 ${API_BASE_URL}，请确认 FastAPI 已启动`
    }
    return axiosError.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return String(error)
}

/** 认证接口 */
export const authApi = {
  /** 获取当前用户（第 1 步后端固定返回演示用户） */
  me: async (): Promise<User> => {
    const { data } = await http.get<User>('/auth/me')
    return data
  },

  /** 登录（第 1 步后端返回假 token） */
  login: async (username: string, password: string): Promise<AuthResponse> => {
    const { data } = await http.post<AuthResponse>('/auth/login', { username, password })
    return data
  },

  /** 注册 */
  register: async (
    username: string,
    email: string,
    password: string,
  ): Promise<AuthResponse> => {
    const { data } = await http.post<AuthResponse>('/auth/register', {
      username,
      email,
      password,
    })
    return data
  },
}

/** 剪贴板接口 */
export const clipboardApi = {
  /** 列表：分页 / 筛选 / 搜索 / 排序 */
  list: async (
    params: {
      page?: number
      size?: number
      content_type?: ContentType
      search?: string
      sort_by?: SortBy
      order?: SortOrder
    } = {},
  ): Promise<ClipboardItemList> => {
    const { data } = await http.get<ClipboardItemList>('/clipboard/items', { params })
    return data
  },

  /** 详情 */
  detail: async (id: string): Promise<ClipboardItem> => {
    const { data } = await http.get<ClipboardItem>(`/clipboard/items/${id}`)
    return data
  },

  /**
   * 创建。
   * `title` 留空时由服务端自动生成；
   * 后端内置内容去重：相同 `content` 返回同一条记录并刷新 `updated_at`。
   */
  create: async (payload: ClipboardItemCreate): Promise<ClipboardItem> => {
    const { data } = await http.post<ClipboardItem>('/clipboard/items', payload)
    return data
  },

  /** 删除单条 */
  remove: async (id: string): Promise<void> => {
    await http.delete(`/clipboard/items/${id}`)
  },

  /** 清空 */
  clear: async (): Promise<void> => {
    await http.delete('/clipboard/items')
  },
}

/** 开发/测试辅助接口（仅后端 DEBUG=true 时可用） */
export const devApi = {
  /** 把后端内存数据重置为种子数据 */
  reset: async (): Promise<void> => {
    await http.post('/dev/reset')
  },
}
