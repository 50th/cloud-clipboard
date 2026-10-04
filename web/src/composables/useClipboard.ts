/**
 * 剪贴板读写 + 上传的编排 composable。
 *
 * 组件只调用本 composable，不直接碰 `navigator.clipboard` 或 axios。
 */

import { ref } from 'vue'

import { getErrorMessage } from '#src/api/client.ts'
import { useClipboardStore } from '#src/stores/clipboardStore.ts'
import { ClipboardError, isClipboardSupported, readText } from '#src/utils/clipboard.ts'
import { truncate } from '#src/utils/format.ts'

interface UploadOutcome {
  ok: boolean
  /** 需要用户手动粘贴时置为 true（浏览器不支持或权限被拒） */
  needsManualInput?: boolean
  message: string
}

export function useClipboard() {
  const store = useClipboardStore()
  const busy = ref(false)
  const error = ref<string | null>(null)
  const needsManualInput = ref(false)

  /** 上传一段文本（内部使用，统一处理 busy/error）。 */
  async function upload(
    text: string,
    source: 'clipboard' | 'manual',
    title?: string,
  ): Promise<UploadOutcome> {
    const content = text.trim()
    if (!content) {
      return { ok: false, message: '内容为空，没有可同步的文本' }
    }

    busy.value = true
    error.value = null
    try {
      const { item, deduped } = await store.uploadText(content, title)
      const prefix = source === 'clipboard' ? '已同步剪贴板' : '已上传'
      const detail = deduped
        ? '（内容已存在，已刷新时间戳）'
        : `（新记录 ${item.id.slice(0, 8)}）`
      return { ok: true, message: `${prefix}${detail}：${truncate(content, 40)}` }
    } catch (err) {
      const message = getErrorMessage(err)
      error.value = message
      return { ok: false, message }
    } finally {
      busy.value = false
    }
  }

  /**
   * 读取系统剪贴板并上传。
   * ⚠️ 必须由用户手势触发（点击事件），浏览器才允许读取。
   * 调用方从返回值的 `needsManualInput` 判断是否要引导用户手动粘贴。
   */
  async function syncFromClipboard(): Promise<UploadOutcome> {
    let text: string
    try {
      text = await readText()
    } catch (err) {
      const code = err instanceof ClipboardError ? err.code : 'failed'
      const message = err instanceof Error ? err.message : '读取剪贴板失败'
      error.value = message
      // 空剪贴板不算能力问题，其余情况都引导用户手动粘贴
      const needsManual = code !== 'empty'
      needsManualInput.value = needsManual
      return { ok: false, needsManualInput: needsManual, message }
    }
    return upload(text, 'clipboard')
  }

  /** 手动输入内容上传（用于输入面板的「上传」按钮）。 */
  async function uploadManual(text: string, title?: string): Promise<UploadOutcome> {
    const result = await upload(text, 'manual', title)
    if (result.ok) {
      needsManualInput.value = false
    }
    return result
  }

  return {
    busy,
    error,
    needsManualInput,
    supported: isClipboardSupported(),
    syncFromClipboard,
    uploadManual,
  }
}
