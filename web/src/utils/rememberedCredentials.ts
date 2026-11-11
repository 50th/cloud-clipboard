/** 「记住密码」的本地存储（只存在本机浏览器，不上传服务端）。 */

export const REMEMBERED_CREDENTIALS_KEY = 'cloud-clipboard.remembered-credentials'

/** 清除本机保存的账号密码；localStorage 不可用时静默忽略。 */
export function clearRememberedCredentials(): void {
  try {
    localStorage.removeItem(REMEMBERED_CREDENTIALS_KEY)
  } catch {
    /* 隐私模式下 localStorage 可能不可用，忽略即可 */
  }
}
