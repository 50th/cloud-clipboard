/** 分享链接生成：分享页与主站同源，基址取当前页面 origin。 */

export function buildShareUrl(
  token: string,
  origin: string = window.location.origin,
): string {
  return `${origin.replace(/\/+$/, '')}/s/${token}`
}
