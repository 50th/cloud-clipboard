/** 分享链接生成单测（不依赖后端）。 */

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { buildShareUrl } from '#src/share/url.ts'

test('buildShareUrl 使用传入的 origin 拼接分享页地址', () => {
  assert.equal(
    buildShareUrl('abc123', 'https://example.com:8443'),
    'https://example.com:8443/s/abc123',
  )
  assert.equal(
    buildShareUrl('abc123', 'http://127.0.0.1:5273/'),
    'http://127.0.0.1:5273/s/abc123',
  )
})
