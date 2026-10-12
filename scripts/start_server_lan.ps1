<#
云剪贴板 · 局域网联调后端启动脚本

用途：让后端监听 0.0.0.0，供同一局域网内的鸿蒙真机 / 模拟器访问。
（设备上的 127.0.0.1 指向设备自身，连不到你的电脑。）

用法（在任意目录）：
    .\scripts\start_server_lan.ps1
    .\scripts\start_server_lan.ps1 -Port 8000

⚠️ 必须单 worker：WebSocket 广播是进程内实现，多 worker 会"数据一致但推送丢事件"。
   本脚本不传 --workers，uvicorn 默认即单进程（与 app/core/single_worker.py 守卫一致）。
#>
[CmdletBinding()]
param(
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

# 仓库根目录 = 本脚本所在目录的上一级
$repoRoot = Split-Path -Parent $PSScriptRoot
$serverDir = Join-Path $repoRoot 'server'
$python = Join-Path $serverDir 'venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
    Write-Error "未找到 $python。请先在 server/ 下建好 venv 并安装依赖（见 server/README.md）。"
}

Write-Host '[lan] 本机 IPv4 地址（把其中之一填进鸿蒙端登录页的「后端地址」）：' -ForegroundColor Cyan
Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notmatch '^127\.' } |
    ForEach-Object { Write-Host ("      http://{0}:{1}" -f $_.IPAddress, $Port) }

Write-Host ("[lan] 启动后端：http://0.0.0.0:{0}（单 worker）" -f $Port) -ForegroundColor Cyan
Write-Host '[lan] 记得放行防火墙的该端口，否则设备连不上。' -ForegroundColor Yellow

Push-Location $serverDir
try {
    & $python -m uvicorn app.main:app --host 0.0.0.0 --port $Port
} finally {
    Pop-Location
}