/**
 * 从运行中的后端生成 TypeScript 类型。
 *
 * 用法（需先启动后端）：
 *   pnpm run gen:api
 *
 * 本脚本内部调用 devDependencies 里的 openapi-typescript；
 * 不要用 `npx openapi-typescript`（会绕过 pnpm 锁定的本地版本）。
 */

import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import openapiTS, { astToString } from 'openapi-typescript'

const here = dirname(fileURLToPath(import.meta.url))
const projectRoot = resolve(here, '..')

const baseUrl = (process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')
const specUrl = `${baseUrl}/openapi.json`
const outFile = resolve(projectRoot, 'src/types/api.d.ts')

async function main() {
  console.log(`[gen:api] 读取 ${specUrl}`)

  let spec
  try {
    const response = await fetch(specUrl)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    spec = await response.json()
  } catch (error) {
    console.error(`[gen:api] 无法读取 OpenAPI 契约：${error.message}`)
    console.error('[gen:api] 请先启动后端：cd server && .\\venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000')
    process.exit(1)
  }

  const ast = await openapiTS(spec)
  const output = astToString(ast)

  await mkdir(dirname(outFile), { recursive: true })
  await writeFile(outFile, output, 'utf8')

  const pathCount = Object.keys(spec.paths ?? {}).length
  console.log(`[gen:api] 已写入 ${outFile}`)
  console.log(`[gen:api] 契约版本 ${spec.info?.version} · ${pathCount} 个路径`)
}

await main()
