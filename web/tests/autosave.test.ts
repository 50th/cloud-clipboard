/**
 * 自动保存倒计时的单元测试。
 *
 * 纯 composable，不需要后端。用真实计时器 + 较宽松的等待余量，
 * 避免在慢机器上抖动（倒计时本身就是时间逻辑，用假计时器测不出真实行为）。
 */

import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { nextTick, ref, type Ref } from 'vue'

import { useAutoSave } from '#src/composables/useAutoSave.ts'

const sleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms))

/** 防抖延迟。取 400ms，配 250ms 的等待余量，慢机器上也不易抖动 */
const DELAY = 400
const SETTLE = 250

interface Harness {
  text: Ref<string>
  enabled: Ref<boolean>
  /** 成功保存的次数（getter，读取时才取值） */
  readonly saves: number
  failNext: boolean
  api: ReturnType<typeof useAutoSave>
}

function setup(): Harness {
  const text = ref('')
  const enabled = ref(true)
  let saves = 0

  const harness = {
    text,
    enabled,
    get saves() {
      return saves
    },
    failNext: false,
    api: undefined as unknown as ReturnType<typeof useAutoSave>,
  }

  harness.api = useAutoSave({
    text,
    enabled,
    delay: DELAY,
    onSave: async () => {
      if (harness.failNext) {
        throw new Error('boom')
      }
      saves += 1
    },
  })

  return harness
}

describe('自动保存倒计时', () => {
  it('有未保存改动时进入倒计时，且剩余时间真实递减', async () => {
    const h = setup()
    assert.equal(h.api.pending.value, false, '初始不应处于待保存状态')
    assert.equal(h.api.remainingMs.value, 0)
    assert.equal(h.api.progress.value, 0)

    h.text.value = 'hello'
    await nextTick()

    assert.equal(h.api.pending.value, true, '有改动时应进入倒计时')
    assert.equal(h.api.progress.value, 1, '刚进入倒计时时进度应为 1')
    const first = h.api.remainingMs.value
    assert.ok(first > 0, '剩余时间应大于 0')

    await sleep(SETTLE)
    assert.ok(
      h.api.remainingMs.value < first,
      `剩余时间应递减（前 ${first}，后 ${h.api.remainingMs.value}）`,
    )
    assert.ok(h.api.progress.value < 1, '进度应小于 1')
  })

  it('倒计时归零后自动保存一次，并复位状态', async () => {
    const h = setup()
    h.text.value = 'hi'
    await nextTick()

    await sleep(DELAY + SETTLE)

    assert.equal(h.saves, 1, '应恰好保存一次')
    assert.equal(h.api.pending.value, false, '保存后应退出待保存状态')
    assert.equal(h.api.remainingMs.value, 0)
    assert.ok(h.api.lastSaved.value !== null, '应记录保存时间')
  })

  it('保存后继续编辑会重新进入倒计时（回归：不能用 lastSaved === null 判断）', async () => {
    const h = setup()

    h.text.value = 'a'
    await nextTick()
    await sleep(DELAY + SETTLE)
    assert.equal(h.saves, 1)
    assert.equal(h.api.pending.value, false)

    // 旧实现用 `lastSaved.value === null` 判断 pending，
    // 保存过一次之后就永远为 false，界面会一直显示旧的「已自动保存」时间
    h.text.value = 'ab'
    await nextTick()
    assert.equal(h.api.pending.value, true, '已保存过一次后再编辑，仍应显示待保存')

    await sleep(DELAY + SETTLE)
    assert.equal(h.saves, 2, '改动应再次触发保存')
  })

  it('继续输入会重置倒计时（防抖）', async () => {
    const h = setup()

    h.text.value = 'a'
    await nextTick()
    await sleep(SETTLE)

    h.text.value = 'ab'
    await nextTick()
    await sleep(SETTLE)

    assert.equal(h.saves, 0, '持续输入期间不应保存')

    await sleep(DELAY)
    assert.equal(h.saves, 1, '停止输入后应保存一次')
  })

  it('markSaved 会取消倒计时，不再重复保存', async () => {
    const h = setup()

    h.text.value = 'x'
    await nextTick()
    assert.equal(h.api.pending.value, true)

    h.api.markSaved('x')
    assert.equal(h.api.pending.value, false, '标记已保存后应退出倒计时')
    assert.equal(h.api.remainingMs.value, 0)

    await sleep(DELAY + SETTLE)
    assert.equal(h.saves, 0, '已标记保存的内容不应再自动保存')
  })

  it('saveNow 跳过剩余等待立即保存，且不会保存第二次', async () => {
    const h = setup()

    h.text.value = 'now'
    await nextTick()
    assert.equal(h.api.pending.value, true)

    await h.api.saveNow()
    assert.equal(h.saves, 1, '应立即保存')
    assert.equal(h.api.pending.value, false)

    await sleep(DELAY + SETTLE)
    assert.equal(h.saves, 1, '倒计时已取消，不应再保存一次')
  })

  it('关闭开关会停止倒计时，且关闭后不会补一次保存', async () => {
    const h = setup()

    h.text.value = 'z'
    await nextTick()
    assert.equal(h.api.pending.value, true)

    h.enabled.value = false
    await nextTick()
    assert.equal(h.api.pending.value, false, '关闭后应停止倒计时')

    await sleep(DELAY + SETTLE)
    assert.equal(h.saves, 0, '关闭自动保存后不应保存')
  })

  it('空白内容不触发倒计时', async () => {
    const h = setup()

    h.text.value = '   '
    await nextTick()
    assert.equal(h.api.pending.value, false, '纯空白不应触发保存')

    await sleep(DELAY + SETTLE)
    assert.equal(h.saves, 0)
  })

  it('保存失败会记录 error，且不写入 lastSaved', async () => {
    const h = setup()
    h.failNext = true

    h.text.value = 'bad'
    await nextTick()
    await sleep(DELAY + SETTLE)

    assert.ok(h.api.error.value?.includes('boom'), '应记录失败原因')
    assert.equal(h.api.lastSaved.value, null, '失败时不应记录保存时间')
    assert.equal(h.saves, 0, '失败的保存不应计入成功次数')
    assert.equal(h.api.pending.value, false, '失败后也应退出倒计时')
  })

  it('载入已保存内容后不应触发保存（回归：hasUnsaved 曾把签名又包了一层）', async () => {
    const h = setup()

    // 模拟「点历史记录载入编辑」：先赋值，紧接着 markSaved 建立基线
    // （组件的 watch 回调在下一个 tick 才跑，那时基线已经设好）
    h.text.value = '载入的内容'
    h.api.markSaved('载入的内容')
    await nextTick()

    assert.equal(h.api.pending.value, false, '内容与基线一致，不应进入倒计时')

    await sleep(DELAY + SETTLE)
    assert.equal(h.saves, 0, '没有改动就绝不能自动保存')
  })

  it('载入后只改标题也算改动，应触发保存', async () => {
    const title = ref('原标题')
    const text = ref('内容')
    let saves = 0
    const api = useAutoSave({
      text,
      extra: title,
      enabled: ref(true),
      delay: DELAY,
      onSave: async () => {
        saves += 1
      },
    })
    api.markSaved('内容')

    title.value = '新标题'
    await nextTick()
    assert.equal(api.pending.value, true, '标题变了就是未保存改动')

    await sleep(DELAY + SETTLE)
    assert.equal(saves, 1)
  })
})
