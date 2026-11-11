/** 密码策略单元测试：与后端 `validate_password_strength` / `validate_password_against_username` 对齐。 */

import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { validatePassword } from '#src/utils/passwordPolicy.ts'

describe('密码策略', () => {
  it('长度不足 8 个字符时拒绝', () => {
    assert.equal(validatePassword('Ab1'), '密码至少 8 个字符')
    assert.equal(validatePassword('Ab1defg'), '密码至少 8 个字符')
  })

  it('缺少字母时拒绝', () => {
    assert.equal(validatePassword('12345678'), '密码必须包含字母')
  })

  it('缺少数字时拒绝', () => {
    assert.equal(validatePassword('abcdefgh'), '密码必须包含数字')
  })

  it('包含用户名时拒绝（不区分大小写）', () => {
    assert.equal(validatePassword('Alice2026', 'alice'), '密码不能包含用户名')
    assert.equal(validatePassword('xxALICE2026', 'Alice'), '密码不能包含用户名')
  })

  it('合法密码通过', () => {
    assert.equal(validatePassword('GoodPass2026', 'alice'), '')
    assert.equal(validatePassword('a1!bcdef', 'alice'), '')
  })

  it('没有用户名上下文时只校验复杂度', () => {
    assert.equal(validatePassword('GoodPass2026'), '')
  })
})
