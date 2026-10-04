/** 通用小工具。 */

/** 截断文本，超过 `max` 个字符时追加省略号。 */
export function truncate(text: string, max = 120): string {
  const collapsed = text.replace(/\s+/g, ' ').trim()
  return collapsed.length > max ? `${collapsed.slice(0, max)}…` : collapsed
}

/** 把 ISO 8601 时间格式化为本地易读文本。 */
export function formatDateTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return iso
  }
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** 相对时间（刚刚 / N 分钟前 / N 小时前 / 日期）。 */
export function formatRelative(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return iso
  }
  const diffSeconds = Math.round((Date.now() - date.getTime()) / 1000)
  if (diffSeconds < 0) {
    return formatDateTime(iso)
  }
  if (diffSeconds < 60) {
    return '刚刚'
  }
  if (diffSeconds < 3600) {
    return `${Math.floor(diffSeconds / 60)} 分钟前`
  }
  if (diffSeconds < 86_400) {
    return `${Math.floor(diffSeconds / 3600)} 小时前`
  }
  if (diffSeconds < 7 * 86_400) {
    return `${Math.floor(diffSeconds / 86_400)} 天前`
  }
  return formatDateTime(iso)
}

/** 估算文本大小（UTF-8 字节数）。 */
export function byteSize(text: string): number {
  return new TextEncoder().encode(text).length
}

/** 人类可读的大小。 */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
