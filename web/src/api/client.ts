/**
 * HTTP 客户端统一封装（axios）。
 *
 * 规范：组件不直接调用 axios（见 AGENTS.md 的「开发规范」），一律走 `src/api/`。
 */

import axios, { AxiosError } from 'axios'

import type { components } from '#src/types/api.ts'

export type ClipboardItem = components['schemas']['ClipboardItemResponse']
export type ClipboardItemList = components['schemas']['ClipboardItemList']
export type ClipboardItemCreate = components['schemas']['ClipboardItemCreate']
export type ClipboardItemUpdate = components['schemas']['ClipboardItemUpdate']
export type User = components['schemas']['UserResponse']
export type AuthResponse = components['schemas']['AuthResponse']
export type SortBy = components['schemas']['SortBy']
export type SortOrder = components['schemas']['SortOrder']
export type ContentType = components['schemas']['ContentType']

/**
 * 浏览器所在时区（IANA 名，如 Asia/Shanghai）。
 *
 * **只用于自动生成标题时展示时间**：数据库统一存 UTC，
 * 由服务端用它把 UTC 转成用户本地时间，避免标题显示成 UTC。
 */
export const LOCAL_TIMEZONE: string | undefined = (() => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined
  } catch {
    return undefined
  }
})()

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

// 自动附加 Bearer token。第 4 步起剪贴板接口必须带令牌，缺失会被后端 401。
http.interceptors.request.use((config) => {
  const bearer = readEnv('VITE_AUTH_TOKEN') || getToken()
  if (bearer) {
    config.headers.Authorization = `Bearer ${bearer}`
  }
  return config
})

/**
 * 401 处理器。
 *
 * 用回调注册而不是在这里直接 import userStore：store 会 import 本模块，
 * 反向依赖会形成循环。由 `main.ts` 在 Pinia 就绪后注册。
 */
type UnauthorizedHandler = () => void
let onUnauthorized: UnauthorizedHandler | null = null

/** 注册"令牌失效"回调（401 时触发，用于清状态并回到登录页）。 */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler
}

http.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    // 登录/注册本身返回 401 属于"凭证错误"，交给调用方展示，
    // 不能触发全局登出（否则用户在登录页输错密码会被反复重置）。
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const url = error.config?.url ?? ''
      const isAuthEntry = url.includes('/auth/login') || url.includes('/auth/register')
      if (!isAuthEntry) {
        setToken(null)
        onUnauthorized?.()
      }
    }
    return Promise.reject(error)
  },
)

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
  /** 获取当前用户（需已登录，否则 401） */
  me: async (): Promise<User> => {
    const { data } = await http.get<User>('/auth/me')
    return data
  },

  /** 登录：`username` 支持用户名或邮箱，返回 JWT 与用户信息 */
  login: async (username: string, password: string): Promise<AuthResponse> => {
    const { data } = await http.post<AuthResponse>('/auth/login', { username, password })
    return data
  },

  /** 注册：成功即返回令牌，无需再登录一次 */
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

  /**
   * 更新已有记录（只更新传入字段）。
   * 自动保存用它复用同一条草稿，避免打字中间态产生多行。
   */
  update: async (id: string, payload: ClipboardItemUpdate): Promise<ClipboardItem> => {
    const { data } = await http.patch<ClipboardItem>(`/clipboard/items/${id}`, payload)
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

/** 数据库探测结果（`GET /dev/db`）。 */
export interface DevDatabaseInfo {
  database: string
  version: string
}

/** 开发/测试辅助接口（仅后端 ENABLE_DEV_ROUTES=true 时注册，见 `docs/api.md` 的「接口摘要」） */
export const devApi = {
  /** ⚠️ 删除当前用户的剪贴板项并重建种子数据（仅开发路由开启时可用） */
  reset: async (): Promise<void> => {
    await http.post('/dev/reset')
  },

  /**
   * 探测后端当前连接的数据库。
   *
   * **测试用它做安全守卫**：只有确认目标是测试库时，才允许执行破坏性操作
   * （`dev/reset`、清空全部），避免误跑一次测试就把开发库数据清掉。
   *
   * 开发路由未开启时返回 404，调用方需要处理。
   */
  db: async (): Promise<DevDatabaseInfo> => {
    const { data } = await http.get<DevDatabaseInfo>('/dev/db')
    return data
  },
}
