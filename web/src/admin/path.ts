/** 管理端路径判断（纯函数，便于测试）。 */

export function isAdminPath(pathname: string): boolean {
  return pathname === '/admin' || pathname.startsWith('/admin/')
}
