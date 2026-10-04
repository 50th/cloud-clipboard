/**
 * 复制文本到剪贴板的 hook（带「已复制」提示状态）。
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { getErrorMessage } from '@/api/client'
import { writeText } from '@/utils/clipboard'

interface UseCopyResult {
  copied: boolean
  error: string | null
  copy: (text: string) => Promise<boolean>
}

export function useCopy(resetDelay = 1500): UseCopyResult {
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => {
    return () => {
      if (timer.current !== undefined) {
        window.clearTimeout(timer.current)
      }
    }
  }, [])

  const copy = useCallback(
    async (text: string): Promise<boolean> => {
      try {
        await writeText(text)
        setError(null)
        setCopied(true)
        if (timer.current !== undefined) {
          window.clearTimeout(timer.current)
        }
        timer.current = window.setTimeout(() => setCopied(false), resetDelay)
        return true
      } catch (err) {
        setError(getErrorMessage(err))
        return false
      }
    },
    [resetDelay],
  )

  return { copied, error, copy }
}
