/**
 * 自动保存 hook。
 *
 * 用户停止输入 `delay` 毫秒后自动保存一次。
 * 关闭再打开时通过 `markSaved` 记录已保存内容，避免重复上传。
 */

import { useCallback, useEffect, useRef, useState } from 'react'

export interface UseAutoSaveOptions {
  /** 要保存的文本（通常是输入框内容） */
  text: string
  /** 参与变化检测的附加内容（例如标题）；改变它也会触发重新保存 */
  extra?: string
  /** 是否启用自动保存 */
  enabled: boolean
  /** 实际执行保存的逻辑，抛异常表示失败 */
  onSave: () => Promise<void>
  /** 防抖延迟（毫秒） */
  delay?: number
}

export interface UseAutoSaveResult {
  /** 最近一次保存成功的时间戳（毫秒），未保存过为 null */
  lastSaved: number | null
  /** 是否正在保存 */
  saving: boolean
  /** 最近一次失败原因 */
  error: string | null
  /** 标记某段内容为「已保存」，用于手动上传后避免重复自动保存 */
  markSaved: (text: string) => void
}

const DEFAULT_DELAY = 1500

export function useAutoSave({
  text,
  extra = '',
  enabled,
  onSave,
  delay = DEFAULT_DELAY,
}: UseAutoSaveOptions): UseAutoSaveResult {
  const [lastSaved, setLastSaved] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const savedTextRef = useRef('')
  const onSaveRef = useRef(onSave)
  const runningRef = useRef(false)
  onSaveRef.current = onSave

  const markSaved = useCallback((value: string) => {
    savedTextRef.current = value.trim()
    setLastSaved(Date.now())
  }, [])

  const signature = `${text}\u0000${extra}`.trim()

  useEffect(() => {
    if (!enabled) {
      return
    }
    if (!signature || text.trim() === '' || signature === savedTextRef.current) {
      return
    }

    const timer = window.setTimeout(() => {
      if (runningRef.current) {
        return
      }
      runningRef.current = true
      setSaving(true)
      setError(null)

      void onSaveRef
        .current()
        .then(() => {
          savedTextRef.current = signature
          setLastSaved(Date.now())
        })
        .catch((err: unknown) => {
          setError(err instanceof Error ? err.message : String(err))
        })
        .finally(() => {
          runningRef.current = false
          setSaving(false)
        })
    }, delay)

    return () => window.clearTimeout(timer)
  }, [signature, text, enabled, delay])

  return { lastSaved, saving, error, markSaved }
}
