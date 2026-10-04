/** 用户状态（Pinia setup store）。第 4 步接入真实登录后完善。 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

import { authApi, setToken } from '#src/api/client.ts'
import type { User } from '#src/api/client.ts'

export const useUserStore = defineStore('user', () => {
  const user = ref<User | null>(null)
  const loading = ref(false)

  /** 拉取当前用户：后端第 3 步仍固定返回演示用户 */
  async function loadCurrentUser() {
    loading.value = true
    try {
      user.value = await authApi.me()
    } catch {
      user.value = null
    } finally {
      loading.value = false
    }
  }

  async function login(username: string, password: string): Promise<User> {
    const result = await authApi.login(username, password)
    setToken(result.token.access_token)
    user.value = result
    return result
  }

  function logout() {
    setToken(null)
    user.value = null
  }

  return { user, loading, loadCurrentUser, login, logout }
})
