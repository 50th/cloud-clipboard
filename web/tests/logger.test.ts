/**
 * 前端统一日志出口（`utils/logger.ts`）的单元测试。
 *
 * 目的：确保**级别阈值**真的生效——生产环境不该把 debug/info 打到用户控制台，
 * 而排查问题时又能临时调低。日志本身不影响业务，出错的代价是"排查时没有线索"，
 * 所以这里直接验证输出行为。
 *
 * 运行：pnpm test
 */

import assert from 'node:assert/strict'
import { afterEach, beforeEach, describe, it } from 'node:test'

import { getLogLevel, logger, setLogLevel } from '#src/utils/logger.ts'
import type { LogLevel } from '#src/utils/logger.ts'

type ConsoleMethod = 'debug' | 'info' | 'warn' | 'error'

const METHODS: ConsoleMethod[] = ['debug', 'info', 'warn', 'error']

interface Call {
  level: ConsoleMethod
  args: unknown[]
}

let calls: Call[] = []
let originals: Record<ConsoleMethod, (...args: unknown[]) => void>
let initialLevel: LogLevel

beforeEach(() => {
  calls = []
  initialLevel = getLogLevel()
  originals = {
    debug: console.debug,
    info: console.info,
    warn: console.warn,
    error: console.error,
  }
  for (const method of METHODS) {
    console[method] = (...args: unknown[]) => {
      calls.push({ level: method, args })
    }
  }
})

afterEach(() => {
  for (const method of METHODS) {
    console[method] = originals[method]
  }
  setLogLevel(initialLevel)
})

describe('logger 级别过滤', () => {
  it('阈值以下的日志不输出', () => {
    setLogLevel('warn')

    logger.debug('debug 不该出现')
    logger.info('info 不该出现')
    logger.warn('warn 应该出现')
    logger.error('error 应该出现')

    assert.deepEqual(
      calls.map((call) => call.level),
      ['warn', 'error'],
    )
  })

  it('阈值以上的日志全部输出', () => {
    setLogLevel('debug')

    logger.debug('d')
    logger.info('i')
    logger.warn('w')
    logger.error('e')

    assert.equal(calls.length, 4)
  })

  it('输出带统一前缀', () => {
    setLogLevel('debug')
    logger.info('已连接')

    assert.equal(calls[0]?.args[0], '[cloud-clipboard] 已连接')
  })

  it('附加参数原样透传（便于在控制台展开异常对象）', () => {
    setLogLevel('debug')
    const error = new Error('boom')
    logger.error('清空失败', error)

    assert.deepEqual(calls[0]?.args, ['[cloud-clipboard] 清空失败', error])
  })

  it('setLogLevel 会改变 getLogLevel', () => {
    setLogLevel('error')
    assert.equal(getLogLevel(), 'error')
  })
})
