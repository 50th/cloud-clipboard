/**
 * 复制文本到剪贴板的 composable（带「已复制」提示状态）。
 */

import { onScopeDispose, ref, type Ref } from 'vue'

import { getErrorMessage } from '#src/api/client.ts'
import { writeText } from '#src/utils/clipboard.ts'

export interface UseCopyResult {
  copied: Ref<boolean>
  error: Ref<string | null>
  copy: (text: string) => Promise<boolean>
}

export function useCopy(resetDelay = 1500): UseCopyResult {
  const copied = ref(false)
  const error = ref<string | null>(null)
  let timer: ReturnType<typeof setTimeout> | undefined

  onScopeDispose(() => {
    if (timer !== undefined) {
      clearTimeout(timer)
    }
  })

  async function copy(text: string): Promise<boolean> {
    try {
      await writeText(text)
      error.value = null
      copied.value = true
      if (timer !== undefined) {
        clearTimeout(timer)
      }
      timer = setTimeout(() => {
        copied.value = false
      }, resetDelay)
      return true
    } catch (err) {
      error.value = getErrorMessage(err)
      return false
    }
  }

  return { copied, error, copy }
}
