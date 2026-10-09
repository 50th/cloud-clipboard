/**
 * 顶部提示（notice）的显示与自动消失。
 *
 * 抽成 composable 是为了能直接测：提示必须有生命周期，否则
 * 「登出后停在登录页、没有任何操作能覆盖提示」的场景会让它永久残留。
 */

import { ref } from 'vue'

export type NoticeKind = 'ok' | 'err'
export type Notice = { kind: NoticeKind; text: string } | null

/** 成功提示展示时长 */
export const NOTICE_TIMEOUT_OK_MS = 3000
/** 错误提示展示时长：给用户时间读完，闪一下就没等于没提示 */
export const NOTICE_TIMEOUT_ERR_MS = 8000

export function useNotice() {
  const notice = ref<Notice>(null)
  /** 待执行的自动消失计时器 */
  let timer: ReturnType<typeof setTimeout> | undefined

  /** 取消待执行的计时器（不清空当前提示） */
  function cancelTimer() {
    if (timer !== undefined) {
      clearTimeout(timer)
      timer = undefined
    }
  }

  /**
   * 显示提示并安排自动消失。
   *
   * 重复调用会重置计时（新提示覆盖旧提示，旧计时器必须取消），
   * 否则旧的计时器会把新提示提前清掉。
   */
  function showNotice(next: { kind: NoticeKind; text: string }) {
    cancelTimer()
    notice.value = next
    const timeout = next.kind === 'ok' ? NOTICE_TIMEOUT_OK_MS : NOTICE_TIMEOUT_ERR_MS
    timer = setTimeout(() => {
      notice.value = null
      timer = undefined
    }, timeout)
  }

  /** 立即收起提示并取消待执行的计时器。 */
  function clearNotice() {
    cancelTimer()
    notice.value = null
  }

  return { notice, showNotice, clearNotice }
}
