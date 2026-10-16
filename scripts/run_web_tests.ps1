<#
云剪贴板 · Web 端端到端测试（隔离模式）

作用：为 Web 端测试单独起一个**指向测试库**的后端实例，跑完自动停掉。
这样测试（含破坏性用例）不会碰到开发库数据。

用法（在任意目录）：
    .\scripts\run_web_tests.ps1                    # 跑完自动停后端
    .\scripts\run_web_tests.ps1 -KeepServer        # 跑完保留后端（方便手工验证）
    .\scripts\run_web_tests.ps1 -SkipPrepare       # 跳过"准备测试库"（库已就绪时更快）

为什么需要它：
- 开发后端监听 8000 且连的是开发库 `clipboard`
- 直接 `pnpm test` 打开发库时，破坏性操作会清掉真实数据
- 本脚本起第二个实例（端口 8001、库 `clipboard_web_test`、独立锁端口），与开发实例互不干扰

⚠️ 为什么单独用一个库而不是 `clipboard_test`：
   后端 pytest 打 `clipboard_test`，且**每个用例都会 `drop_all` 重建表**。
   两者共用一个库时，同时跑就会互相删表（实测：并行跑时 Web 测试因表被删而失败）。
   各自一个库后，两套测试可以随意并行。

⚠️ 库名**必须含 `test`**：安全守卫以此判定"这是可丢弃的测试库"，
   名字不含 `test` 的库一律不允许跑破坏性用例（本脚本自己也会二次确认）。
   所以这里用 `clipboard_web_test` 而不是 `clipboard_e2e`。

⚠️ 锁端口：后端的单实例守卫会独占一个固定端口（默认 49137）。
   测试实例用 `CLIPBOARD_LOCK_PORT=49138` 与开发实例错开——
   这不是绕过守卫，同一实例内的多 worker 仍会被拦下。
#>
[CmdletBinding()]
param(
    [int]$Port = 8001,
    [int]$LockPort = 49138,
    [string]$TestDatabaseUrl = 'postgresql+asyncpg://clipboard:clipboard@127.0.0.1:5433/clipboard_web_test',
    [switch]$KeepServer,
    [switch]$SkipPrepare,
    [string]$PnpmPath,
    [string]$NodePath
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$serverDir = Join-Path $repoRoot 'server'
$webDir = Join-Path $repoRoot 'web'
$python = Join-Path $serverDir 'venv\Scripts\python.exe'

foreach ($p in @($python, $webDir)) {
    if (-not (Test-Path $p)) {
        Write-Error "未找到 $p。请先按 README 完成环境准备。"
    }
}

# ---- 解析 pnpm：优先 PATH，其次允许显式指定 ----
$pnpm = $null
if ($PnpmPath) {
    if (-not (Test-Path $PnpmPath)) { Write-Error "指定的 -PnpmPath 不存在: $PnpmPath" }
    $pnpm = $PnpmPath
} else {
    $cmd = Get-Command pnpm -ErrorAction SilentlyContinue
    if ($cmd) { $pnpm = $cmd.Source }
}
if (-not $pnpm) {
    Write-Error @"
未找到 pnpm。请任选其一：
  1) 把 pnpm 加入 PATH
  2) 用 -PnpmPath 指定：.\scripts\run_web_tests.ps1 -PnpmPath <pnpm 可执行文件或 .mjs>
     若指定的是 .mjs，还需要 -NodePath <node 可执行文件>
"@
}

$env:PYTHONUTF8 = '1'

# ---- 1. 准备测试库（建库 + 建表 + 演示账号）----
if (-not $SkipPrepare) {
    Write-Host "[test] 准备测试库 $($TestDatabaseUrl.Split('/')[-1]) …" -ForegroundColor Cyan
    Push-Location $serverDir
    try {
        # 1a. 库不存在则创建（首次运行需要）
        & $python -m scripts.ensure_database --database-url $TestDatabaseUrl 2>&1 |
            ForEach-Object { "      $_" }
        if ($LASTEXITCODE -ne 0) { Write-Error "创建测试库失败（exit $LASTEXITCODE）" }

        # 1b. 建表 + 演示账号（幂等）
        & $python -m scripts.init_db --database $TestDatabaseUrl 2>&1 | ForEach-Object { "      $_" }
        if ($LASTEXITCODE -ne 0) { Write-Error "测试库准备失败（exit $LASTEXITCODE）" }
    } finally {
        Pop-Location
    }
}

# ---- 2. 启动隔离后端 ----
Write-Host "[test] 启动隔离后端：http://127.0.0.1:$Port（库 $($TestDatabaseUrl.Split('/')[-1])，锁端口 $LockPort）" -ForegroundColor Cyan

$envVars = @{
    'DATABASE_URL'          = $TestDatabaseUrl
    'ENABLE_DEV_ROUTES'     = 'true'
    'CLIPBOARD_LOCK_PORT'   = "$LockPort"
    'APP_ENV'               = 'development'
    'PYTHONUTF8'            = '1'
}
# 逐个注入到子进程环境（Start-Process 不继承本次调用内临时设的 $env:，故显式传入）
foreach ($kv in $envVars.GetEnumerator()) {
    Set-Item -Path "env:$($kv.Key)" -Value $kv.Value
}

$outLog = Join-Path $env:TEMP 'cloud-clipboard-test-server.out.log'
$errLog = Join-Path $env:TEMP 'cloud-clipboard-test-server.err.log'
Remove-Item $outLog, $errLog -ErrorAction SilentlyContinue

$server = Start-Process -FilePath $python `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--port', "$Port" `
    -WorkingDirectory $serverDir -PassThru -NoNewWindow `
    -RedirectStandardOutput $outLog -RedirectStandardError $errLog

$exitCode = 1
$base = "http://127.0.0.1:$Port"
try {
    # ---- 3. 等健康检查 ----
    $ready = $false
    $deadline = (Get-Date).AddSeconds(40)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 600
        try {
            if ((Invoke-WebRequest -Uri "$base/health" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch { }
        if ($server.HasExited) { break }
    }

    if (-not $ready) {
        Write-Host "[test] 隔离后端未能就绪。" -ForegroundColor Red
        Write-Host "--- 启动输出（末尾）---" -ForegroundColor Yellow
        Get-Content $errLog -ErrorAction SilentlyContinue | Select-Object -Last 25 | ForEach-Object { "      $_" }
        throw "隔离后端启动失败"
    }

    # ---- 4. 双重确认：这个后端真的连的是测试库 ----
    $dbInfo = (Invoke-WebRequest -Uri "$base/api/v1/dev/db" -UseBasicParsing -TimeoutSec 5).Content | ConvertFrom-Json
    Write-Host "[test] 后端实际连接的库：$($dbInfo.database)（$($dbInfo.version)）" -ForegroundColor Cyan
    if ($dbInfo.database -notmatch 'test') {
        Write-Error "隔离后端连的不是测试库（$($dbInfo.database)），已中止以免清掉真实数据。"
    }

    # ---- 5. 跑测试 ----
    $env:VITE_API_BASE_URL = $base
    # 目标是测试库，可以放行破坏性用例（守卫仍要求库名含 test）
    $env:E2E_ALLOW_DESTRUCTIVE = '1'

    Write-Host "[test] 运行 pnpm test（E2E_ALLOW_DESTRUCTIVE=1）" -ForegroundColor Cyan
    Push-Location $webDir
    try {
        if ($pnpm -like '*.mjs') {
            # pnpm 的 .mjs 入口需要显式指定 node
            $nodeExe = $NodePath
            if (-not $nodeExe) {
                $found = Get-Command node -ErrorAction SilentlyContinue
                if ($found) { $nodeExe = $found.Source }
            }
            if (-not $nodeExe) {
                Write-Error "以 .mjs 方式调用 pnpm 时需要在 PATH 中有 node，或用 -NodePath 指定。"
            }
            & $nodeExe $pnpm test
        } else {
            & $pnpm test
        }
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
} catch {
    Write-Host "[test] $($_.Exception.Message)" -ForegroundColor Red
    $exitCode = 1
} finally {
    if ($KeepServer) {
        Write-Host "[test] 已保留隔离后端（PID $($server.Id)）：$base" -ForegroundColor Yellow
        Write-Host "[test] 手工验证完请自行停止：Stop-Process -Id $($server.Id)" -ForegroundColor Yellow
    } else {
        Write-Host '[test] 停止隔离后端…' -ForegroundColor Cyan
        Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
    }
}

if ($exitCode -eq 0) {
    Write-Host '[test] 全部通过 ✅' -ForegroundColor Green
} else {
    Write-Host "[test] 测试失败（退出码 $exitCode）" -ForegroundColor Red
}
exit $exitCode
