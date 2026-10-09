/**
 * 顶部提示（notice）生命周期的回归测试。
 *
 * 背景：登出后界面停在登录页，**没有任何后续操作能覆盖提示**，
 * 所以"提示只会被下一条提示覆盖"这个假设不成立——提示必须自己消失。
 * 这里用真实计时器驱动，确保修复真的生效。
 *
 * 运行：pnpm test
 */

import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  NOTICE_TIMEOUT_ERR_MS,
  NOTICE_TIMEOUT_OK_MS,
  useNotice,
} from '#src/composables/useNotice.ts'

/** 等待真实计时器推进 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

describe('提示自动消失（登出提示残留的回归测试）', () => {
  it('登出类成功提示会在超时后自动消失', async () => {
    const { notice, showNotice } = useNotice()
    showNotice({ kind: 'ok', text: '已退出登录' })
    assert.equal(notice.value?.text, '已退出登录', '刚显示时应可见')

    await sleep(NOTICE_TIMEOUT_OK_MS + 150)
    assert.equal(notice.value, null, '超时后必须自动消失，不能永久残留')
  })

  it('错误提示同样会自动消失，且展示时间比成功提示长', async () => {
    const { notice, showNotice } = useNotice()
    showNotice({ kind: 'err', text: '同步失败' })

    // 成功提示的时长过去后，错误提示仍应可见
    await sleep(NOTICE_TIMEOUT_OK_MS + 150)
    assert.equal(notice.value?.text, '同步失败', '错误提示应比成功提示停留更久')

    await sleep(NOTICE_TIMEOUT_ERR_MS - NOTICE_TIMEOUT_OK_MS + 150)
    assert.equal(notice.value, null, '错误提示最终也要消失')
  })

  it('新提示会取消上一条的计时器，不会被提前清掉', async () => {
    const { notice, showNotice } = useNotice()
    showNotice({ kind: 'ok', text: '第一条' })

    // 在第一条到期前换成错误提示（更长的时长）
    await sleep(NOTICE_TIMEOUT_OK_MS - 500)
    showNotice({ kind: 'err', text: '第二条' })

    // 如果旧计时器没被取消，它会在第一条的到期时刻把"第二条"清掉
    await sleep(1000)
    assert.equal(notice.value?.text, '第二条', '旧计时器不应提前清掉新提示')
  })

  it('clearNotice 立即收起提示（登录时清掉"已退出登录"）', async () => {
    const { notice, showNotice, clearNotice } = useNotice()
    showNotice({ kind: 'ok', text: '已退出登录' })
    clearNotice()
    assert.equal(notice.value, null, 'clearNotice 应立即清空')

    // 计时器已被取消：不应在超时后出现"迟到的清空"影响后续提示
    showNotice({ kind: 'ok', text: '重新登录' })
    await sleep(NOTICE_TIMEOUT_OK_MS + 150)
    assert.equal(notice.value, null)
  })
})
