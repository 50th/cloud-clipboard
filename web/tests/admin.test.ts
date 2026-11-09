/** 管理端纯逻辑测试（不依赖运行中的后端）。 */

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { getAdminToken, setAdminToken } from '#src/admin/api/client.ts'
import { isAdminPath } from '#src/admin/path.ts'

test('isAdminPath 只匹配 /admin 前缀', () => {
  assert.equal(isAdminPath('/admin'), true)
  assert.equal(isAdminPath('/admin/'), true)
  assert.equal(isAdminPath('/admin/users'), true)

  assert.equal(isAdminPath('/'), false)
  assert.equal(isAdminPath('/administrator'), false)
  assert.equal(isAdminPath('/adminx'), false)
})

test('管理端 token 在无 sessionStorage 环境下使用内存兜底', () => {
  // Node 测试环境没有 sessionStorage：读写都不应抛错，并回退到内存。
  setAdminToken('test-token')
  assert.equal(getAdminToken(), 'test-token')
  setAdminToken(null)
  assert.equal(getAdminToken(), null)
})
