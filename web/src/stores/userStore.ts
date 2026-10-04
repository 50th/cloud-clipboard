/** 用户状态（第 4 步接入真实登录后完善）。 */

import { create } from 'zustand'

import { authApi, setToken } from '@/api/client'
import type { User } from '@/api/client'

interface UserState {
  user: User | null
  loading: boolean
  /** 拉取当前用户：后端第 1 步固定返回演示用户 */
  loadCurrentUser: () => Promise<void>
  login: (username: string, password: string) => Promise<User>
  logout: () => void
}

export const useUserStore = create<UserState>((set) => ({
  user: null,
  loading: false,

  loadCurrentUser: async () => {
    set({ loading: true })
    try {
      const user = await authApi.me()
      set({ user, loading: false })
    } catch {
      set({ user: null, loading: false })
    }
  },

  login: async (username, password) => {
    const result = await authApi.login(username, password)
    setToken(result.token.access_token)
    set({ user: result })
    return result
  },

  logout: () => {
    setToken(null)
    set({ user: null })
  },
}))
