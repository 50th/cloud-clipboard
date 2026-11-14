/** 分享路径判断单测（不依赖后端）。 */

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { isSharePath } from '#src/share/path.ts'

test('isSharePath 只匹配 /s 与 /s/ 前缀', () => {
  assert.equal(isSharePath('/s'), true)
  assert.equal(isSharePath('/s/'), true)
  assert.equal(isSharePath('/s/abc'), true)

  assert.equal(isSharePath('/'), false)
  assert.equal(isSharePath('/admin'), false)
  assert.equal(isSharePath('/sfoo'), false)
  assert.equal(isSharePath('/share/abc'), false)
})
