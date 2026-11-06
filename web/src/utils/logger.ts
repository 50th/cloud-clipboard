/**
 * 前端统一日志出口。
 *
 * 规范：组件、store、composables 不直接调 `console.*`，一律走本模块，
 * 由这里统一控制**级别阈值**与输出前缀（见 AGENTS.md 的「开发规范」）。
 *
 * 级别策略：
 * - 开发（Vite `DEV` / `NODE_ENV !== 'production'`）默认 `debug`，便于排查；
 * - 生产默认 `warn`：`debug` / `info` 会暴露内部接口路径，也容易刷屏；
 * - 可用 `VITE_LOG_LEVEL=debug|info|warn|error` 覆盖。
 *
 * ⚠️ 绝不把令牌、剪贴板正文等敏感内容写进日志：浏览器控制台与用户反馈里的
 * 日志片段都可能被截图带走。
 */

export type LogLevel = 'debug' | 'info' | 'warn' | 'error'

const LEVEL_WEIGHT: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
}

const PREFIX = '[cloud-clipboard]'

function readEnv(key: string): string | undefined {
  const fromProcess = (
    globalThis as { process?: { env?: Record<string, string | undefined> } }
  ).process?.env?.[key]
  if (fromProcess) {
    return fromProcess
  }
  return ((import.meta.env ?? {}) as Record<string, string | undefined>)[key]
}

/** 是否开发/测试环境（Node 下没有 `import.meta.env.DEV`，退回 `NODE_ENV`）。 */
function isDev(): boolean {
  const viteDev = ((import.meta.env ?? {}) as Record<string, unknown>).DEV
  if (typeof viteDev === 'boolean') {
    return viteDev
  }
  return readEnv('NODE_ENV') !== 'production'
}

function resolveLevel(): LogLevel {
  const explicit = readEnv('VITE_LOG_LEVEL')?.trim().toLowerCase()
  if (explicit && explicit in LEVEL_WEIGHT) {
    return explicit as LogLevel
  }
  return isDev() ? 'debug' : 'warn'
}

let minLevel: LogLevel = resolveLevel()

/** 当前生效的最低输出级别。 */
export function getLogLevel(): LogLevel {
  return minLevel
}

/** 覆盖最低输出级别（测试或运行时排查用）。 */
export function setLogLevel(level: LogLevel): void {
  minLevel = level
}

function emit(level: LogLevel, message: string, details: unknown[]): void {
  if (LEVEL_WEIGHT[level] < LEVEL_WEIGHT[minLevel]) {
    return
  }
  const line = `${PREFIX} ${message}`
  if (details.length > 0) {
    console[level](line, ...details)
  } else {
    console[level](line)
  }
}

export const logger = {
  debug(message: string, ...details: unknown[]): void {
    emit('debug', message, details)
  },
  info(message: string, ...details: unknown[]): void {
    emit('info', message, details)
  },
  warn(message: string, ...details: unknown[]): void {
    emit('warn', message, details)
  },
  error(message: string, ...details: unknown[]): void {
    emit('error', message, details)
  },
}
