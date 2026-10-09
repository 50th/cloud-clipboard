/**
 * 端到端闭环测试（第 2 步验收资产，第 3 步起打真实 PostgreSQL）。
 *
 * 直接驱动真实的 Pinia store + axios 客户端打到真实后端，
 * 覆盖「上传 → 标题 → 列表展示 → 去重 → 搜索 → 排序 → 删除 → 清空」这条链路。
 * 剪贴板读写本身依赖浏览器 API，由浏览器手工验证（见 web/README.md）。
 *
 * 运行（需先启动后端）：
 *   pnpm test
 */

import assert from 'node:assert/strict'
import { after, describe, it } from 'node:test'

import { createPinia, setActivePinia } from 'pinia'

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

// Pinia 需要一个激活实例，才能在组件外使用 store
setActivePinia(createPinia())

const { API_BASE_URL, authApi, clipboardApi, devApi, setToken } = await import(
  '#src/api/client.ts'
)
const { useClipboardStore, PAGE_SIZE } = await import('#src/stores/clipboardStore.ts')

/**
 * 先登录拿 JWT：第 4 步起剪贴板接口全部受保护，不带令牌一律 401。
 *
 * 用演示账号（由 `scripts/init_db` 或 `dev/reset` 按 DEMO_PASSWORD 播种），
 * 这样测试数据仍归属 demo 用户，与手工验证看到的一致。
 * 可用 VITE_E2E_USERNAME / VITE_E2E_PASSWORD 覆盖。
 */
const E2E_USERNAME = process.env.VITE_E2E_USERNAME ?? 'demo'
const E2E_PASSWORD = process.env.VITE_E2E_PASSWORD ?? 'demo1234'

const loginResult = await authApi.login(E2E_USERNAME, E2E_PASSWORD)
setToken(loginResult.token.access_token)

const store = useClipboardStore()
const state = () => useClipboardStore()

/** 本次测试创建的内容前缀，便于收尾时清理 */
const TAG = `[e2e-${Date.now()}]`

/**
 * 是否允许执行破坏性用例（清空全部 / dev/reset）。
 *
 * ⚠️ 第 3 步接入数据库后，这两个操作会清空**真实数据**。
 * 因此必须显式设置 `E2E_ALLOW_DESTRUCTIVE=1` 才执行（仅对测试库使用）：
 *
 *   $env:E2E_ALLOW_DESTRUCTIVE = '1'; pnpm test
 *
 * 默认关闭，避免误跑一次测试就把库清空（见 docs/roadmap.md 的 P2）。
 */
const ALLOW_DESTRUCTIVE = process.env.E2E_ALLOW_DESTRUCTIVE === '1'

/** 破坏性用例之间共用的标记：会话开始时列表本就是空的 */
let sawEmptyList = false

/** 种子数据内容，用于 dev/reset 不可用时手工兜底恢复 */
const SEED_CONTENTS = [
  'https://fastapi.tiangolo.com/tutorial/',
  'pip install fastapi uvicorn[standard]',
  '云剪贴板 MVP 范围：文字内容的上传、查询、删除 + WebSocket 实时同步 + JWT 认证 + 内容去重。',
  'git commit -m "feat: 新增 WebSocket 广播"',
]

/** 清空全部（仅在允许破坏性操作时执行） */
async function clearAllGuarded(): Promise<void> {
  if (!ALLOW_DESTRUCTIVE) {
    return
  }
  await state().clearAll()
  sawEmptyList = true
}

/** 恢复初始状态：优先调 dev/reset，失败则手工补回种子数据 */
async function restoreSeedData(): Promise<void> {
  try {
    await devApi.reset()
    return
  } catch {
    /* dev 路由未开启（ENABLE_DEV_ROUTES=false），走兜底 */
  }
  if (!sawEmptyList) {
    return
  }
  for (const content of SEED_CONTENTS) {
    await state()
      .uploadText(content)
      .catch(() => undefined)
  }
}

async function upload(text: string, title?: string) {
  return state().uploadText(text, title)
}

describe('Web 端单端闭环（真实后端）', () => {
  after(async () => {
    const leftovers = state().items.filter((item) => item.content.startsWith(TAG))
    for (const item of leftovers) {
      await clipboardApi.remove(item.id).catch(() => undefined)
    }
    // 破坏性用例会清空数据，收尾时恢复，方便接着手工验证
    await restoreSeedData()
  })

  it('后端可达（/health）', async () => {
    const response = await fetch(`${API_BASE_URL}/health`)
    assert.equal(response.status, 200)
    assert.deepEqual(await response.json(), { status: 'ok' })
  })

  it('认证已启用：不带令牌访问剪贴板返回 401', async () => {
    // 刻意绕过 http 拦截器，直接发裸请求验证后端确实在保护接口
    const response = await fetch(`${API_BASE_URL}/api/v1/clipboard/items`)
    assert.equal(response.status, 401, '未带令牌必须 401，而不是回退到演示用户')
  })

  it('登录返回可用令牌，且 /auth/me 能解析出用户', async () => {
    assert.ok(loginResult.token.access_token.length > 0, '应拿到非空 JWT')
    assert.equal(loginResult.token.token_type, 'bearer')
    assert.ok(loginResult.token.expires_in > 0)

    const me = await authApi.me()
    assert.equal(me.username, E2E_USERNAME, '/auth/me 应返回登录用户')
    assert.ok(!('password_hash' in me), '响应绝不能带 password_hash')
  })

  it('错误密码登录返回 401', async () => {
    await assert.rejects(
      () => authApi.login(E2E_USERNAME, 'definitely-not-the-password'),
      (error: unknown) => {
        const status = (error as { response?: { status?: number } }).response?.status
        assert.equal(status, 401)
        return true
      },
    )
  })

  it('首屏拉取列表：返回分页元信息，且每条都有标题', async () => {
    await store.fetchItems()
    const current = state()
    assert.equal(current.error, null)
    assert.equal(current.loading, false)
    assert.equal(current.page, 1)
    assert.ok(current.total >= 0)
    assert.ok(current.items.length <= PAGE_SIZE)
    assert.equal(current.pages, current.total > 0 ? Math.ceil(current.total / PAGE_SIZE) : 0)
    for (const item of current.items) {
      assert.ok(item.title.length > 0, '每条记录都应有非空标题')
    }
  })

  it('上传新内容：total +1，新记录出现在列表首位', async () => {
    const before = state().total
    const content = `${TAG} 新内容`
    const { item, deduped } = await upload(content)

    assert.equal(deduped, false, '首次上传不应判定为去重')
    assert.equal(item.content, content)
    assert.equal(item.content_type, 'text')

    const current = state()
    assert.equal(current.total, before + 1)
    assert.equal(current.items[0].id, item.id, '最新记录应排在列表首位')
  })

  it('标题时间按传入时区展示，而不是 UTC', async () => {
    // 北京 = UTC+8。用本地时间算出期望值，避免依赖测试机时区
    const parts = new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).formatToParts(new Date())
    const get = (type: string) => parts.find((p) => p.type === type)?.value ?? ''
    const expected = `${get('month')}-${get('day')} ${get('hour')}:${get('minute')}`

    const viaBeijing = await clipboardApi.create({
      content: `${TAG} 时区验证`,
      content_type: 'text',
      timezone: 'Asia/Shanghai',
    })
    assert.equal(
      viaBeijing.title,
      `demo · ${expected}`,
      `标题应按 Asia/Shanghai 展示，实际为 ${viaBeijing.title}`,
    )

    const viaUtc = await clipboardApi.create({
      content: `${TAG} 时区验证 UTC`,
      content_type: 'text',
      timezone: 'UTC',
    })
    assert.match(viaUtc.title, /^demo · \d{2}-\d{2} \d{2}:\d{2}$/)
    assert.notEqual(viaUtc.title, viaBeijing.title, 'UTC 与北京时间的标题不应相同')

    await clipboardApi.remove(viaBeijing.id).catch(() => undefined)
    await clipboardApi.remove(viaUtc.id).catch(() => undefined)
  })

  it('自动保存草稿：反复保存只占一条记录，不会每个中间态新建一行', async () => {
    const first = await state().saveDraft(`${TAG} 草稿 v1`)
    const second = await state().saveDraft(`${TAG} 草稿 v2`)
    const third = await state().saveDraft(`${TAG} 草稿 v3`)

    assert.equal(second.item.id, first.item.id, '第二次保存应复用同一条草稿')
    assert.equal(third.item.id, first.item.id, '第三次保存应复用同一条草稿')
    assert.equal(third.item.content, `${TAG} 草稿 v3`, '草稿内容应更新为最新值')

    const found = await clipboardApi.list({ search: `${TAG} 草稿`, size: 100 })
    assert.equal(found.total, 1, `草稿应只占 1 行，实际 ${found.total} 行`)

    assert.ok(found.items[0].updated_at >= found.items[0].created_at, 'updated_at 不应早于 created_at')
    await clipboardApi.remove(first.item.id).catch(() => undefined)
  })

  it('草稿被删除后再保存：自动新建一条而不是报错', async () => {
    const first = await state().saveDraft(`${TAG} 会被删掉的草稿`)
    await clipboardApi.remove(first.item.id)

    const again = await state().saveDraft(`${TAG} 会被删掉的草稿 2`)
    assert.notEqual(again.item.id, first.item.id, '草稿已删除，应新建一条')
    assert.equal(again.item.content, `${TAG} 会被删掉的草稿 2`)

    await clipboardApi.remove(again.item.id).catch(() => undefined)
  })

  it('清空输入不新开记录：后续编辑仍更新同一条', async () => {
    const first = await state().saveDraft(`${TAG} 清空测试 A`)
    const totalAfterFirst = (await clipboardApi.list({ search: TAG, size: 100 })).total

    // 模拟用户点「清空输入」：界面清空，但**不解除草稿关联**
    // （组件里 clearInput 只调 markSaved('')，不调 startNewDraft）
    const second = await state().saveDraft(`${TAG} 清空测试 B`)

    assert.equal(second.item.id, first.item.id, '清空输入后继续编辑，应仍复用同一行')
    const after = await clipboardApi.list({ search: TAG, size: 100 })
    assert.equal(after.total, totalAfterFirst, '清空输入不应新增记录')

    await clipboardApi.remove(first.item.id).catch(() => undefined)
  })

  it('点「新建剪贴板」后才新开一条记录', async () => {
    const first = await state().saveDraft(`${TAG} 新建前`)
    const totalBefore = (await clipboardApi.list({ search: `${TAG} 新建`, size: 100 })).total

    state().startNewDraft() // 等价于点「＋ 新建剪贴板」
    const second = await state().saveDraft(`${TAG} 新建后`)

    assert.notEqual(second.item.id, first.item.id, '新建剪贴板后应另起一条记录')
    assert.equal(second.item.content, `${TAG} 新建后`)

    const totalAfter = (await clipboardApi.list({ search: `${TAG} 新建`, size: 100 })).total
    assert.equal(totalAfter, totalBefore + 1, '新建剪贴板后应恰好新增 1 条')

    await clipboardApi.remove(first.item.id).catch(() => undefined)
    await clipboardApi.remove(second.item.id).catch(() => undefined)
  })
  it('不传标题：服务端自动生成 `<用户名> · <月-日 时:分>`', async () => {
    const { item } = await upload(`${TAG} 自动标题`)
    assert.match(item.title, /^demo · \d{2}-\d{2} \d{2}:\d{2}$/, `自动标题格式不符：${item.title}`)
  })

  it('传标题：原样保存并展示', async () => {
    const { item } = await upload(`${TAG} 自定义标题`, '我的会议记录')
    assert.equal(item.title, '我的会议记录')
    assert.equal(state().items[0].title, '我的会议记录')
  })

  it('同一内容再次上传：服务端去重，不新增记录且被识别为 deduped', async () => {
    const content = `${TAG} 去重内容`
    const first = await upload(content)
    const totalAfterFirst = state().total

    const second = await upload(content)

    assert.equal(second.item.id, first.item.id, '去重应返回同一条记录')
    assert.equal(second.deduped, true, '第二次上传必须被识别为去重')
    assert.equal(state().total, totalAfterFirst, '去重不应增加总条数')
  })

  it('搜索过滤：可命中标题与正文，结果全部匹配，清空后恢复', async () => {
    await upload(`${TAG} 搜索目标`, '搜索命中标题样例')
    await state().setSearch('搜索命中标题样例')
    const byTitle = state()
    assert.equal(byTitle.search, '搜索命中标题样例')
    assert.ok(byTitle.total >= 1, '按标题应能搜到')
    assert.ok(byTitle.items.every((item) => item.title.includes('搜索命中标题样例')))

    await state().setSearch('fastapi')
    const byContent = state()
    assert.ok(
      byContent.items.every(
        (item) =>
          item.content.toLowerCase().includes('fastapi') ||
          item.title.toLowerCase().includes('fastapi'),
      ),
    )

    await state().setSearch('')
    assert.ok(state().total >= byContent.total)
  })

  it('排序切换：asc 与 desc 首条记录不同', async () => {
    const all = await clipboardApi.list({ size: 100 })
    if (all.total < 2) {
      return
    }
    await state().setOrder('asc')
    const ascFirst = state().items[0]?.id
    await state().setOrder('desc')
    const descFirst = state().items[0]?.id
    assert.notEqual(ascFirst, descFirst, '升序与降序首条应不同')
  })

  it('删除单条：total -1 且该记录不再出现在列表', async () => {
    const { item } = await upload(`${TAG} 待删除`)
    const before = state().total

    await state().removeItem(item.id)

    const current = state()
    assert.equal(current.total, before - 1)
    assert.ok(!current.items.some((entry) => entry.id === item.id))
  })

  it('清空全部：按 E2E_ALLOW_DESTRUCTIVE 决定是否执行，随后可继续上传', async () => {
    await clearAllGuarded()
    if (ALLOW_DESTRUCTIVE) {
      assert.equal(state().total, 0)
      assert.equal(state().items.length, 0)
    }

    const { item } = await upload(`${TAG} 清空后重新上传`)
    assert.ok(item.id)
    assert.ok(state().total >= 1)
  })

  it('破坏性开关状态可被观察（便于排查为何跳过了清空用例）', () => {
    console.log(
      `  [e2e] E2E_ALLOW_DESTRUCTIVE=${ALLOW_DESTRUCTIVE ? '1（会执行清空用例）' : '未设置（已跳过清空用例）'}`,
    )
    assert.equal(typeof ALLOW_DESTRUCTIVE, 'boolean')
  })

  it('后端不可达时给出可读错误，而不是抛异常', async () => {
    const { getErrorMessage } = await import('#src/api/client.ts')
    const failure = await fetch('http://127.0.0.1:1/health').catch((error: unknown) => error)
    const message = getErrorMessage(failure)
    assert.ok(typeof message === 'string' && message.length > 0, '应返回非空错误文本')
  })
})
