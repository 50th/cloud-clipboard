/**
 * WebSocket 实时同步的端到端测试（第 5 步验收资产）。
 *
 * 与 `e2e.test.ts` 的区别：这里驱动**真实的** `useWebSocket` composable，
 * 用 Node 内置的全局 `WebSocket` 连到真实后端，验证「标签 A 上传 → 标签 B 秒级收到」。
 *
 * 运行（需先启动后端）：pnpm test
 */

import assert from 'node:assert/strict'
import { after, describe, it } from 'node:test'

import { createPinia, setActivePinia } from 'pinia'
import { effectScope } from 'vue'

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

setActivePinia(createPinia())

const { authApi, setToken } = await import('#src/api/client.ts')
const { useClipboardStore } = await import('#src/stores/clipboardStore.ts')
const { backoffDelay, getWebSocketUrl, useWebSocket, WS_BACKOFF_MAX_MS } = await import(
  '#src/composables/useWebSocket.ts'
)

const TAG = `[ws-${Date.now()}]`

/**
 * 本套件**注册并使用自己的账号**，不复用 `e2e.test.ts` 的 demo。
 *
 * 原因：Node 测试运行器会**并行**跑多个测试文件，而两个套件都在增删剪贴板记录。
 * 共用 demo 会让 `e2e.test.ts` 里"total 应 +1"这类断言随机失败
 * （实测过：e2e 期望 5 实际 6）。各自一个账号后互不干扰。
 */
const WS_USERNAME = `ws_e2e_${Date.now()}`
const WS_PASSWORD = 'ws-e2e-password'

const registered = await authApi.register(WS_USERNAME, `${WS_USERNAME}@example.com`, WS_PASSWORD)
const TOKEN = registered.token.access_token
setToken(TOKEN)

/** 等待条件成立，超时则返回 false */
async function waitFor(predicate: () => boolean, timeoutMs = 8000): Promise<boolean> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (predicate()) {
      return true
    }
    await new Promise((resolve) => setTimeout(resolve, 50))
  }
  return predicate()
}

/**
 * 建一个"标签页"：自己的 Pinia store + 自己的 WebSocket 连接。
 *
 * `useWebSocket` 内部用了 `onScopeDispose`，所以必须跑在 `effectScope` 里，
 * 否则会警告且无法卸载。
 */
function openTab() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useClipboardStore(pinia)

  const scope = effectScope()
  const ws = scope.run(() =>
    useWebSocket({
      token: TOKEN,
      onEvent: (envelope) => void store.applyRealtimeEvent(envelope),
    }),
  )
  assert.ok(ws, 'useWebSocket 应在 effectScope 内返回实例')

  const tab = {
    store,
    ws,
    get connected() {
      return ws.connected.value
    },
    close() {
      ws.disconnect()
      scope.stop()
    },
  }
  ws.connect()
  return tab
}

describe('WebSocket 实时同步（真实后端）', () => {
  const tabs: Array<ReturnType<typeof openTab>> = []

  after(async () => {
    // 清理本次产生的记录
    for (const tab of tabs) {
      for (const item of tab.store.items) {
        if (item.content.startsWith(TAG)) {
          await tab.store.removeItem(item.id).catch(() => undefined)
        }
      }
      tab.close()
    }
    // 说明：本套件注册的 ws_e2e_* 账号会留在库里（每个只占一行）。
    // 它每次运行的用户名都带时间戳，所以不会互相干扰；如需清理可执行
    //   DELETE FROM users WHERE username LIKE 'ws_e2e_%';
  })

  it('纯函数：端点地址与指数退避符合协议约定', () => {
    assert.match(
      getWebSocketUrl('abc'),
      /\/api\/v1\/clipboard\/ws\?token=abc$/,
      '端点路径应与 docs/ws-protocol.md 一致',
    )
    assert.match(getWebSocketUrl(), /\/api\/v1\/clipboard\/ws$/, '无令牌时不应带查询串')
    assert.match(
      getWebSocketUrl('a b&c'),
      /token=a%20b%26c$/,
      '令牌必须被 URL 编码，避免 & 破坏查询串',
    )

    // 首次 1s，之后翻倍，上限 30s（协议约定）
    assert.equal(backoffDelay(0), 1000)
    assert.equal(backoffDelay(1), 2000)
    assert.equal(backoffDelay(2), 4000)
    assert.equal(backoffDelay(3), 8000)
    assert.equal(backoffDelay(4), 16000)
    assert.equal(backoffDelay(5), WS_BACKOFF_MAX_MS, '第 5 次应达上限 30s')
    assert.equal(backoffDelay(50), WS_BACKOFF_MAX_MS, '不得超过上限')
  })

  it('两个"标签页"都能建立连接', async () => {
    const tabA = openTab()
    const tabB = openTab()
    tabs.push(tabA, tabB)

    assert.ok(await waitFor(() => tabA.connected), '标签 A 应连接成功')
    assert.ok(await waitFor(() => tabB.connected), '标签 B 应连接成功')
  })

  it('标签 A 上传：标签 B 秒级收到并出现在列表里', async () => {
    const tabA = tabs[0]
    const tabB = tabs[1]
    const content = `${TAG} 跨标签同步`

    await tabA.store.fetchItems()
    await tabB.store.fetchItems()
    const before = tabB.store.total

    // A 上传（走 HTTP，与真实界面一致）
    await tabA.store.uploadText(content)

    // B 应通过 WebSocket 事件自动刷新出这条记录，而不是自己发 HTTP
    const seen = await waitFor(() =>
      tabB.store.items.some((item) => item.content === content),
    )
    assert.ok(seen, `标签 B 应在超时内收到并展示新记录（当前 ${tabB.store.total} 条）`)
    assert.equal(tabB.store.total, before + 1, '标签 B 的总数应 +1')

    await tabA.store.removeItem(tabA.store.items.find((i) => i.content === content)!.id)
  })

  it('标签 A 删除：标签 B 也会同步消失', async () => {
    const tabA = tabs[0]
    const tabB = tabs[1]
    const content = `${TAG} 删除同步`

    const { item } = await tabA.store.uploadText(content)
    assert.ok(
      await waitFor(() => tabB.store.items.some((entry) => entry.id === item.id)),
      'B 应先看到这条记录',
    )

    await tabA.store.removeItem(item.id)

    const gone = await waitFor(
      () => !tabB.store.items.some((entry) => entry.id === item.id),
    )
    assert.ok(gone, 'B 中的该记录应随广播消失')
  })

  it('令牌无效时被服务端以 4401 关闭，且不会无限重连', async () => {
    const scope = effectScope()
    const ws = scope.run(() => useWebSocket({ token: 'garbage.token.value' }))
    assert.ok(ws)
    ws.connect()

    const closed = await waitFor(() => ws.log.value.some((line) => line.includes('令牌无效')), 8000)
    assert.ok(closed, `应记录令牌无效（日志：${ws.log.value.join(' | ')}）`)
    assert.equal(ws.connected.value, false, '不应处于已连接状态')
    assert.equal(ws.retryCount.value, 0, '4401 不应触发重连计数')
    scope.stop()
  })
})
