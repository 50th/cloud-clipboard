/**
 * 分享端到端测试（打真实后端）。
 *
 * 覆盖：快照/跟随、密码、撤销、次数用尽、删除原记录、跨账号、
 * 计数规则与访问记录。使用**独立测试账号**，避免与其它并行套件互相干扰。
 */

import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

// api/client.ts 在模块加载时会读 localStorage，Node 下先补一个最小实现
const memory = new Map<string, string>()
;(globalThis as unknown as { localStorage: Storage }).localStorage = {
  getItem: (key: string) => memory.get(key) ?? null,
  setItem: (key: string, value: string) => void memory.set(key, value),
  removeItem: (key: string) => void memory.delete(key),
  clear: () => memory.clear(),
  key: (index: number) => [...memory.keys()][index] ?? null,
  get length() {
    return memory.size
  },
} as Storage

const { authApi, clipboardApi, publicShareApi, shareApi, setToken } = await import(
  '#src/api/client.ts'
)

const PASSWORD = 'share-e2e-pw1'
const TAG = `[share-e2e-${Date.now()}]`

async function registerUser(suffix: string): Promise<string> {
  const username = `share-${suffix}-${Date.now()}`
  const result = await authApi.register(
    username,
    `${username}@example.com`,
    PASSWORD,
  )
  return result.token.access_token
}

async function loginAs(token: string): Promise<void> {
  setToken(token)
}

async function createItem(
  content = `${TAG} 正文`,
  title?: string,
): Promise<{ id: string; title: string }> {
  return clipboardApi.create({ content, content_type: 'text', title })
}

async function statusOf(promise: Promise<unknown>): Promise<number | undefined> {
  try {
    await promise
    return undefined
  } catch (error) {
    return (error as { response?: { status?: number } }).response?.status
  }
}

describe('分享端到端（真实后端）', () => {
  it('快照分享不随原记录编辑变化', async () => {
    const token = await registerUser('snapshot')
    await loginAs(token)
    const item = await createItem(`${TAG} 快照原始`)
    const share = await shareApi.create(item.id, {
      mode: 'snapshot',
      expires_in: '7d',
    })

    await clipboardApi.update(item.id, { content: `${TAG} 快照改过` })
    const content = await publicShareApi.access(share.token)
    assert.equal(content.content, `${TAG} 快照原始`)

    await clipboardApi.remove(item.id).catch(() => undefined)
  })

  it('跟随分享读取原记录最新内容', async () => {
    const token = await registerUser('live')
    await loginAs(token)
    const item = await createItem(`${TAG} 跟随第一版`)
    const share = await shareApi.create(item.id, {
      mode: 'live',
      expires_in: '7d',
    })

    await clipboardApi.update(item.id, { content: `${TAG} 跟随第二版` })
    const content = await publicShareApi.access(share.token)
    assert.equal(content.content, `${TAG} 跟随第二版`)

    await clipboardApi.remove(item.id).catch(() => undefined)
  })

  it('密码分享：错误 403，正确后可读', async () => {
    const token = await registerUser('password')
    await loginAs(token)
    const item = await createItem(`${TAG} 受保护`)
    const share = await shareApi.create(item.id, {
      mode: 'snapshot',
      expires_in: '1d',
      password: '1234',
    })

    const meta = await publicShareApi.meta(share.token)
    assert.equal(meta.password_required, true)
    assert.equal(meta.title, null)

    assert.equal(await statusOf(publicShareApi.access(share.token, '9999')), 403)
    const content = await publicShareApi.access(share.token, '1234')
    assert.equal(content.content, `${TAG} 受保护`)

    await clipboardApi.remove(item.id).catch(() => undefined)
  })

  it('撤销后公开访问 410', async () => {
    const token = await registerUser('revoke')
    await loginAs(token)
    const item = await createItem()
    const share = await shareApi.create(item.id, { mode: 'snapshot', expires_in: '7d' })

    await shareApi.revoke(share.id)
    assert.equal(await statusOf(publicShareApi.meta(share.token)), 410)

    await clipboardApi.remove(item.id).catch(() => undefined)
  })

  it('max_views=1：第二次访问 410', async () => {
    const token = await registerUser('views')
    await loginAs(token)
    const item = await createItem()
    const share = await shareApi.create(item.id, {
      mode: 'snapshot',
      expires_in: '7d',
      max_views: 1,
    })

    const first = await publicShareApi.access(share.token)
    assert.equal(first.remaining_views, 0)
    assert.equal(await statusOf(publicShareApi.access(share.token)), 410)

    await clipboardApi.remove(item.id).catch(() => undefined)
  })

  it('删除原记录后公开访问 404', async () => {
    const token = await registerUser('cascade')
    await loginAs(token)
    const item = await createItem()
    const share = await shareApi.create(item.id, { mode: 'snapshot', expires_in: '7d' })

    await clipboardApi.remove(item.id)
    assert.equal(await statusOf(publicShareApi.meta(share.token)), 404)
  })

  it('跨账号撤销他人分享返回 404', async () => {
    const ownerToken = await registerUser('cross-owner')
    await loginAs(ownerToken)
    const item = await createItem()
    const share = await shareApi.create(item.id, { mode: 'snapshot', expires_in: '7d' })

    await loginAs(await registerUser('cross-other'))
    assert.equal(await statusOf(shareApi.revoke(share.id)), 404)

    await loginAs(ownerToken)
    await clipboardApi.remove(item.id).catch(() => undefined)
  })

  it('打开分享页只调 meta 不计数，主动 access 才计数', async () => {
    const token = await registerUser('counting')
    await loginAs(token)
    const item = await createItem()
    const share = await shareApi.create(item.id, { mode: 'snapshot', expires_in: '7d' })

    await publicShareApi.meta(share.token)
    await publicShareApi.meta(share.token)

    let listed = await shareApi.list({ item_id: item.id, status: 'active', size: 1 })
    assert.equal(listed.items[0].view_count, 0)

    await publicShareApi.access(share.token)

    listed = await shareApi.list({ item_id: item.id, status: 'active', size: 1 })
    assert.equal(listed.items[0].view_count, 1)

    await clipboardApi.remove(item.id).catch(() => undefined)
  })

  it('我的分享支持状态筛选与标题/内容搜索', async () => {
    const token = await registerUser('filters')
    await loginAs(token)

    const itemA = await createItem(`${TAG} 内容 needle-body`, '筛选标题甲')
    const itemB = await createItem(`${TAG} 普通内容`, '筛选标题乙')
    const shareA = await shareApi.create(itemA.id, {
      mode: 'snapshot',
      expires_in: '7d',
    })
    const shareB = await shareApi.create(itemB.id, {
      mode: 'snapshot',
      expires_in: '7d',
    })
    await shareApi.revoke(shareB.id)

    const active = await shareApi.list({ status: 'active', size: 50 })
    assert.equal(active.total, 1)
    assert.equal(active.items[0].id, shareA.id)

    const revoked = await shareApi.list({ status: 'revoked', size: 50 })
    assert.equal(revoked.total, 1)
    assert.equal(revoked.items[0].id, shareB.id)

    const byTitle = await shareApi.list({ search: '筛选标题乙', size: 50 })
    assert.equal(byTitle.total, 1)
    assert.equal(byTitle.items[0].id, shareB.id)

    const byContent = await shareApi.list({ search: 'needle-body', size: 50 })
    assert.equal(byContent.total, 1)
    assert.equal(byContent.items[0].id, shareA.id)

    await clipboardApi.remove(itemA.id).catch(() => undefined)
    await clipboardApi.remove(itemB.id).catch(() => undefined)
  })

  it('成功访问后「访问记录」新增一条', async () => {
    const token = await registerUser('logs')
    await loginAs(token)
    const item = await createItem()
    const share = await shareApi.create(item.id, { mode: 'snapshot', expires_in: '7d' })

    await publicShareApi.access(share.token)
    const logs = await shareApi.accessLogs(share.id)
    assert.equal(logs.total, 1)
    assert.equal(logs.items[0].result, 'success')

    await clipboardApi.remove(item.id).catch(() => undefined)
  })
})
