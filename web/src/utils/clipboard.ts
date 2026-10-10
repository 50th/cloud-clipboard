/**
 * 剪贴板读写工具。
 *
 * 规范（见 AGENTS.md 的「开发规范」与「关键约束」）：
 * - 组件不直接调用 `navigator.clipboard`，一律走本模块；
 * - 浏览器剪贴板 API 仅在 HTTPS 或 localhost 下可用；
 * - 读取必须由用户手势触发；
 * - 写回时设置标志位，避免触发自身监听导致死循环。
 */

/** 剪贴板操作失败时抛出，`code` 便于 UI 分支处理。 */
export class ClipboardError extends Error {
  constructor(
    message: string,
    readonly code: 'unsupported' | 'denied' | 'empty' | 'failed' = 'failed',
  ) {
    super(message)
    this.name = 'ClipboardError'
  }
}

/** 当前是否由本应用主动写入剪贴板（用于第 5 步过滤自身事件，避免循环同步）。 */
let selfWrite = false

/** 本次写入的标志位保持多久（毫秒）。 */
const SELF_WRITE_TTL = 800

/** 是否处于「自身写入」窗口内。第 5 步的监听逻辑据此忽略自己触发的变化。 */
export function isSelfWrite(): boolean {
  return selfWrite
}

function markSelfWrite(): void {
  selfWrite = true
  window.setTimeout(() => {
    selfWrite = false
  }, SELF_WRITE_TTL)
}

/** 运行环境是否支持异步剪贴板 API（需 HTTPS 或 localhost）。 */
export function isClipboardSupported(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    typeof navigator.clipboard !== 'undefined' &&
    typeof navigator.clipboard.readText === 'function'
  )
}

/**
 * 读取剪贴板文本。
 * ⚠️ 必须在用户手势（点击 / paste 事件）中调用，否则浏览器会拒绝。
 */
export async function readText(): Promise<string> {
  if (!isClipboardSupported()) {
    throw new ClipboardError(
      '当前环境不支持读取剪贴板：请使用 https 或 localhost 打开页面（建议 Chrome / Edge）',
      'unsupported',
    )
  }
  try {
    const text = await navigator.clipboard.readText()
    if (!text) {
      throw new ClipboardError('剪贴板是空的，先在别处复制点内容吧', 'empty')
    }
    return text
  } catch (error) {
    if (error instanceof ClipboardError) {
      throw error
    }
    throw new ClipboardError(
      '读取剪贴板被拒绝：请确认页面处于前台，并允许剪贴板权限（读取必须由点击触发）',
      'denied',
    )
  }
}

/** 写入剪贴板文本（带自身写入标志与 execCommand 降级）。 */
export async function writeText(text: string): Promise<void> {
  markSelfWrite()

  if (isClipboardSupported() && typeof navigator.clipboard.writeText === 'function') {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch {
      /* 降级到 execCommand */
    }
  }

  // 降级方案：适用于不支持 navigator.clipboard.writeText 的旧浏览器
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.top = '-1000px'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  document.body.removeChild(textarea)

  if (!copied) {
    throw new ClipboardError('复制失败：浏览器拒绝了剪贴板写入', 'failed')
  }
}
