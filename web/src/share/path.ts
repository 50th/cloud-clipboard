/** 分享公开页路径判断（纯函数，便于测试）。 */

export function isSharePath(pathname: string): boolean {
  return pathname === '/s' || pathname.startsWith('/s/')
}
