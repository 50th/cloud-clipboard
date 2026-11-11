/**
 * 修改密码单元测试：接口请求契约 + 用户端/管理端 store 的会话清理。
 *
 * 通过替换 axios adapter 模拟后端，不依赖运行中的服务。
 */

import assert from 'node:assert/strict'
import { afterEach, beforeEach, describe, it } from 'node:test'

import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { createPinia, setActivePinia } from 'pinia'

import { authApi, http } from '#src/api/client.ts'
import type { User } from '#src/api/client.ts'
import {
  adminChangePassword,
  adminHttp,
  getAdminToken,
  setAdminToken,
} from '#src/admin/api/client.ts'
import { useAdminStore } from '#src/admin/stores/adminStore.ts'
import { useUserStore } from '#src/stores/userStore.ts'

const originalHttpAdapter = http.defaults.adapter
const originalAdminAdapter = adminHttp.defaults.adapter

const USER: User = {
  id: 'user-1',
  username: 'demo',
  email: 'demo@example.com',
  nickname: null,
  avatar_url: null,
  is_admin: false,
  created_at: '2026-01-01T00:00:00Z',
}

const ADMIN: User = {
  ...USER,
  id: 'admin-1',
  username: 'admin',
  email: 'admin@example.com',
  is_admin: true,
}

/** 让下一次请求返回成功响应。 */
function respondWith(data: unknown) {
  return async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => ({
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config,
  })
}

/** 让下一次请求抛错（模拟后端 400）。 */
function rejectWith(error: Error) {
  return async (): Promise<AxiosResponse> => {
    throw error
  }
}

afterEach(() => {
  http.defaults.adapter = originalHttpAdapter
  adminHttp.defaults.adapter = originalAdminAdapter
})

describe('修改密码接口契约', () => {
  it('用户端提交 old_password / new_password', async () => {
    let captured: InternalAxiosRequestConfig | undefined
    http.defaults.adapter = async (config) => {
      captured = config
      return {
        data: { success: true, message: 'ok' },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }

    await authApi.changePassword('OldPass2026', 'NewPass2026')

    assert.equal(captured?.url, '/auth/change-password')
    assert.equal(captured?.method, 'post')
    assert.deepEqual(JSON.parse(String(captured?.data)), {
      old_password: 'OldPass2026',
      new_password: 'NewPass2026',
    })
  })

  it('管理端复用同一接口并携带管理端令牌', async () => {
    setAdminToken('admin-token')
    let captured: InternalAxiosRequestConfig | undefined
    adminHttp.defaults.adapter = async (config) => {
      captured = config
      return {
        data: { success: true, message: 'ok' },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }

    await adminChangePassword('OldPass2026', 'NewPass2026')

    assert.equal(captured?.url, '/auth/change-password')
    assert.equal(captured?.headers.Authorization, 'Bearer admin-token')
    assert.deepEqual(JSON.parse(String(captured?.data)), {
      old_password: 'OldPass2026',
      new_password: 'NewPass2026',
    })
  })
})

describe('用户端修改密码后的会话处理', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('成功后清空登录态', async () => {
    http.defaults.adapter = respondWith({ success: true, message: 'ok' })
    const store = useUserStore()
    store.user = { ...USER }

    await store.changePassword('OldPass2026', 'NewPass2026')

    assert.equal(store.user, null)
    assert.equal(store.isAuthenticated, false)
  })

  it('失败时保留登录态并抛出错误', async () => {
    http.defaults.adapter = rejectWith(new Error('当前密码错误'))
    const store = useUserStore()
    store.user = { ...USER }

    await assert.rejects(
      () => store.changePassword('wrong-password', 'NewPass2026'),
      /当前密码错误/,
    )
    assert.equal(store.user?.username, 'demo')
    assert.equal(store.isAuthenticated, true)
  })
})

describe('管理端修改密码后的会话处理', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    setAdminToken(null)
  })

  it('成功后清空管理端令牌与用户', async () => {
    adminHttp.defaults.adapter = respondWith({ success: true, message: 'ok' })
    setAdminToken('admin-token')
    const store = useAdminStore()
    store.user = { ...ADMIN }

    await store.changePassword('OldPass2026', 'NewPass2026')

    assert.equal(store.user, null)
    assert.equal(store.isAuthenticated, false)
    assert.equal(getAdminToken(), null)
  })

  it('失败时保留管理端登录态并抛出错误', async () => {
    adminHttp.defaults.adapter = rejectWith(new Error('当前密码错误'))
    setAdminToken('admin-token')
    const store = useAdminStore()
    store.user = { ...ADMIN }

    await assert.rejects(
      () => store.changePassword('wrong-password', 'NewPass2026'),
      /当前密码错误/,
    )
    assert.equal(store.user?.username, 'admin')
    assert.equal(getAdminToken(), 'admin-token')
  })
})
