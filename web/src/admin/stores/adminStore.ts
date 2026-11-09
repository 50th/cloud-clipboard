/** 管理端状态（Pinia setup store）。 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  adminLogin,
  adminMe,
  getAdminToken,
  setAdminToken,
} from '@/admin/api/client.ts'
import type { User } from '@/admin/api/client.ts'
import { logger } from '#src/utils/logger.ts'

export type AdminView =
  | 'dashboard'
  | 'users'
  | 'userDetail'
  | 'clipboards'
  | 'inviteCodes'
  | 'audit'

export const useAdminStore = defineStore('admin', () => {
  const user = ref<User | null>(null)
  const restoring = ref(false)
  const loading = ref(false)
  const activeView = ref<AdminView>('dashboard')
  const selectedUserId = ref<string | null>(null)

  const isAuthenticated = computed(() => user.value !== null)
  const isAdmin = computed(() => user.value?.is_admin === true)

  /**
   * 首屏恢复管理会话。
   *
   * 只接受 `is_admin=true` 的账号；非管理员即使持有有效令牌也会被清除。
   */
  async function restoreSession(): Promise<void> {
    if (!getAdminToken()) {
      user.value = null
      return
    }
    restoring.value = true
    try {
      const me = await adminMe()
      if (!me.is_admin) {
        setAdminToken(null)
        user.value = null
        return
      }
      user.value = me
    } catch {
      logger.debug('恢复管理会话失败，已清除管理端令牌')
      setAdminToken(null)
      user.value = null
    } finally {
      restoring.value = false
    }
  }

  /** 管理员登录：先校验 `is_admin`，通过后才保存令牌。 */
  async function login(username: string, password: string): Promise<User> {
    loading.value = true
    try {
      const result = await adminLogin(username, password)
      if (!result.token.user.is_admin) {
        throw new Error('该账号没有管理权限')
      }
      setAdminToken(result.token.access_token)
      user.value = result.token.user
      activeView.value = 'dashboard'
      selectedUserId.value = null
      return result.token.user
    } finally {
      loading.value = false
    }
  }

  function logout(): void {
    setAdminToken(null)
    user.value = null
    activeView.value = 'dashboard'
    selectedUserId.value = null
  }

  function setView(view: AdminView): void {
    activeView.value = view
    if (view !== 'userDetail') {
      selectedUserId.value = null
    }
  }

  function openUser(userId: string): void {
    selectedUserId.value = userId
    activeView.value = 'userDetail'
  }

  return {
    user,
    restoring,
    loading,
    activeView,
    selectedUserId,
    isAuthenticated,
    isAdmin,
    restoreSession,
    login,
    logout,
    setView,
    openUser,
  }
})
