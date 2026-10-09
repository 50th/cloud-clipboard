/** 用户状态（Pinia setup store）。第 4 步接入真实 JWT 登录。 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { authApi, getToken, setToken } from '#src/api/client.ts'
import type { User } from '#src/api/client.ts'

export const useUserStore = defineStore('user', () => {
  const user = ref<User | null>(null)
  /** 首屏用本地 token 恢复会话时为 true，避免界面闪一下登录页 */
  const restoring = ref(false)
  const loading = ref(false)

  const isAuthenticated = computed(() => user.value !== null)

  /**
   * 首屏恢复会话。
   *
   * localStorage 里有 token 时才调 `/auth/me` 验证它是否仍然有效
   * （可能已过期或密钥已轮换）。验证失败就清掉，避免一直发无效请求。
   */
  async function restoreSession(): Promise<void> {
    if (!getToken()) {
      user.value = null
      return
    }
    restoring.value = true
    try {
      user.value = await authApi.me()
    } catch {
      setToken(null)
      user.value = null
    } finally {
      restoring.value = false
    }
  }

  async function login(username: string, password: string): Promise<User> {
    loading.value = true
    try {
      const result = await authApi.login(username, password)
      // ⚠️ AuthResponse 是"用户信息 + token"的扁平结构，
      // 用户对象在 `token.user` 上，不能整个赋给 user。
      setToken(result.token.access_token)
      user.value = result.token.user
      return result.token.user
    } finally {
      loading.value = false
    }
  }

  async function register(username: string, email: string, password: string): Promise<User> {
    loading.value = true
    try {
      const result = await authApi.register(username, email, password)
      setToken(result.token.access_token)
      user.value = result.token.user
      return result.token.user
    } finally {
      loading.value = false
    }
  }

  function logout() {
    setToken(null)
    user.value = null
  }

  return {
    user,
    loading,
    restoring,
    isAuthenticated,
    restoreSession,
    login,
    register,
    logout,
  }
})
