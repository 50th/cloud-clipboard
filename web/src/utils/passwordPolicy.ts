/**
 * 密码策略（与后端 `server/app/schemas/user.py` 保持一致）。
 *
 * 至少 8 个字符、同时包含字母和数字、不能包含用户名（不区分大小写）。
 * 前端只做即时提示，最终以服务端校验为准。
 */

export const MIN_PASSWORD_LENGTH = 8

const HAS_LETTER = /[A-Za-z]/
const HAS_DIGIT = /[0-9]/

/** 返回第一条不满足的规则；全部满足时返回空字符串。 */
export function validatePassword(password: string, username?: string): string {
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `密码至少 ${MIN_PASSWORD_LENGTH} 个字符`
  }
  if (!HAS_LETTER.test(password)) {
    return '密码必须包含字母'
  }
  if (!HAS_DIGIT.test(password)) {
    return '密码必须包含数字'
  }
  const normalized = (username ?? '').trim().toLowerCase()
  if (normalized && password.toLowerCase().includes(normalized)) {
    return '密码不能包含用户名'
  }
  return ''
}
