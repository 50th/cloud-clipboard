/**
 * 自动保存 composable。
 *
 * 用户停止输入 `delay` 毫秒后自动保存一次。
 * 关闭再打开时通过 `markSaved` 记录已保存内容，避免重复上传。
 */

import { ref, watch, type Ref } from 'vue'

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
  /** 标记某段内容为「已保存」，用于手动上传后避免重复自动保存 */
  markSaved: (text: string) => void
}

const DEFAULT_DELAY = 1500

export function useAutoSave(options: UseAutoSaveOptions): UseAutoSaveResult {
  const { text, extra, enabled, onSave, delay = DEFAULT_DELAY } = options

  const lastSaved = ref<number | null>(null)
  const saving = ref(false)
  const error = ref<string | null>(null)

  /** 已保存内容的签名（text + extra，与 watch 的判定保持一致） */
  let savedSignature = ''
  let timer: ReturnType<typeof setTimeout> | undefined
  let running = false

  function signature(value: string): string {
    return `${value}\u0000${extra?.value ?? ''}`.trim()
  }

  function markSaved(value: string): void {
    savedSignature = signature(value)
    lastSaved.value = Date.now()
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

  watch(
    () => signature(text.value),
    (current) => {
      if (timer !== undefined) {
        clearTimeout(timer)
        timer = undefined
      }
      if (!enabled.value || !current || !text.value.trim() || current === savedSignature) {
        return
      }
      timer = setTimeout(() => {
        // 定时器触发时再判断一次：期间可能已保存或被关闭
        if (enabled.value && signature(text.value) !== savedSignature) {
          void save()
        }
      }, delay)
    },
  )

  return { lastSaved, saving, error, markSaved }
}
