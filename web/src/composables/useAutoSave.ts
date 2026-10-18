/**
 * 自动保存 composable（带**可见倒计时**）。
 *
 * 用户停止输入 `delay` 毫秒后自动保存一次。倒计时期间暴露剩余毫秒与进度，
 * 让界面能真实递减地显示「N 秒后自动保存」——**静态文案会让用户以为卡住了**。
 *
 * 关闭再打开时通过 `markSaved` 记录已保存内容，避免重复上传。
 */

import { getCurrentScope, onScopeDispose, ref, watch, type Ref } from 'vue'

export interface UseAutoSaveOptions {
  /** 要保存的文本（通常是输入框内容） */
  text: Ref<string>
  /** 参与变化检测的附加内容（例如标题）；改变它也会触发重新保存 */
  extra?: Ref<string>
  /** 是否启用自动保存 */
  enabled: Ref<boolean>
  /** 实际执行保存的逻辑，抛异常表示失败 */
  onSave: () => Promise<void>
  /** 防抖延迟（毫秒） */
  delay?: number
}

export interface UseAutoSaveResult {
  /** 最近一次保存成功的时间戳（毫秒），未保存过为 null */
  lastSaved: Ref<number | null>
  /** 是否正在保存 */
  saving: Ref<boolean>
  /** 最近一次失败原因 */
  error: Ref<string | null>
  /**
   * 是否有**未保存的改动**（倒计时进行中）。
   *
   * ⚠️ 不能简单用 `lastSaved === null` 判断：那样首次保存成功后，
   * 用户继续编辑也永远显示"已保存"，状态是错的。
   */
  pending: Ref<boolean>
  /** 距自动保存还剩多少毫秒；未在计时则为 0 */
  remainingMs: Ref<number>
  /** 倒计时进度 0~1（1 = 刚开始计时，0 = 即将保存），便于画进度条 */
  progress: Ref<number>
  /** 标记某段内容为「已保存」，用于手动上传后避免重复自动保存 */
  markSaved: (text: string) => void
  /** 跳过剩余等待，立即保存 */
  saveNow: () => Promise<void>
}

const DEFAULT_DELAY = 1500
/** 倒计时刷新间隔：100ms 足够让秒数与进度条看起来连续，又不至于太耗 */
const TICK_MS = 100

export function useAutoSave(options: UseAutoSaveOptions): UseAutoSaveResult {
  const { text, extra, enabled, onSave, delay = DEFAULT_DELAY } = options

  const lastSaved = ref<number | null>(null)
  const saving = ref(false)
  const error = ref<string | null>(null)
  const pending = ref(false)
  const remainingMs = ref(0)
  const progress = ref(0)

  /** 已保存内容的签名（text + extra，与 watch 的判定保持一致） */
  let savedSignature = ''
  let ticker: ReturnType<typeof setInterval> | undefined
  let running = false

  function signature(value: string): string {
    return `${value}\u0000${extra?.value ?? ''}`.trim()
  }

  /** 停止倒计时并复位相关状态（不清 savedSignature） */
  function stopCountdown(): void {
    if (ticker !== undefined) {
      clearInterval(ticker)
      ticker = undefined
    }
    pending.value = false
    remainingMs.value = 0
    progress.value = 0
  }

  /**
   * 当前输入相对已保存内容是否有改动。
   *
   * ⚠️ **不接受参数**，直接用 `text.value` 计算签名。
   * 原先它收一个 `value` 参数，而 watcher 里把**已经是签名**的 `current` 传了进来，
   * 于是签名被套了两层（`内容\0标题\0标题`），与 `savedSignature` 永不相等——
   * 结果"永远有改动"：点开一条记录**不做任何修改**也会触发一次自动保存。
   */
  function hasUnsavedChanges(): boolean {
    if (text.value.trim() === '') {
      return false
    }
    return signature(text.value) !== savedSignature
  }

  function markSaved(value: string): void {
    savedSignature = signature(value)
    lastSaved.value = Date.now()
    stopCountdown()
  }

  async function save(): Promise<void> {
    if (running) {
      return
    }
    running = true
    saving.value = true
    error.value = null
    const current = signature(text.value)

    try {
      await onSave()
      savedSignature = current
      lastSaved.value = Date.now()
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      running = false
      saving.value = false
    }
  }

  /** 启动倒计时：`delay` 毫秒后保存。用单一 interval 驱动，避免两个计时器不同步。 */
  function startCountdown(): void {
    stopCountdown()
    if (delay <= 0) {
      void save()
      return
    }

    const deadline = Date.now() + delay
    pending.value = true
    remainingMs.value = delay
    progress.value = 1

    ticker = setInterval(() => {
      const left = deadline - Date.now()
      if (left > 0) {
        remainingMs.value = left
        progress.value = left / delay
        return
      }
      // 到点：先停表（pending 置 false），再保存
      stopCountdown()
      void save()
    }, TICK_MS)
  }

  /**
   * 跳过剩余等待立即保存。
   *
   * 无未保存改动或未启用时是空操作，调用方不必先判断。
   */
  async function saveNow(): Promise<void> {
    stopCountdown()
    if (!enabled.value || !hasUnsavedChanges()) {
      return
    }
    await save()
  }

  watch(
    () => signature(text.value),
    () => {
      stopCountdown()
      if (!enabled.value || !hasUnsavedChanges()) {
        return
      }
      startCountdown()
    },
  )

  // 关闭自动保存开关时，正在跑的倒计时必须停掉，否则会在关闭后仍然保存一次
  watch(enabled, (on) => {
    if (!on) {
      stopCountdown()
    }
  })

  // 组件卸载时清理计时器，避免回调打到已销毁的组件上
  if (getCurrentScope()) {
    onScopeDispose(stopCountdown)
  }

  return {
    lastSaved,
    saving,
    error,
    pending,
    remainingMs,
    progress,
    markSaved,
    saveNow,
  }
}
