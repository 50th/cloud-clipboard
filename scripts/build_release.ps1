<#
云剪贴板 · 本地构建生产镜像并生成发布包（方案 B）

用法（仓库根目录）：
    .\scripts\build_release.ps1 -ApiBaseUrl "https://43.134.121.173:8443" -Tag "1.0.0"

输出到 dist/（已被 .gitignore 忽略）：
    release-<tag>.tar.gz   后端 + 前端镜像（gzip）
    source-<tag>.tar.gz   已提交源码（Compose / Nginx / 迁移）

⚠️ 必须使用干净工作区：镜像与源码包都应严格对应某个提交。
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ApiBaseUrl,
    [string]$Tag = '1.0.0',
    [string]$OutputDir = 'dist'
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$serverDir = Join-Path $repoRoot 'server'
$webDir = Join-Path $repoRoot 'web'
$outDir = Join-Path $repoRoot $OutputDir

Push-Location $repoRoot
try {
    $dirty = (& git status --porcelain) -join "`n"
    if ($dirty) {
        throw "工作区有未提交改动，请先提交后再出包：`n$dirty"
    }
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[build] api → cloud-clipboard-api:$Tag" -ForegroundColor Cyan
& docker build --platform linux/amd64 -t "cloud-clipboard-api:$Tag" $serverDir
if ($LASTEXITCODE -ne 0) { throw 'api 镜像构建失败' }

Write-Host "[build] web → cloud-clipboard-web:$Tag" -ForegroundColor Cyan
& docker build --platform linux/amd64 `
    --build-arg "VITE_API_BASE_URL=$ApiBaseUrl" `
    -t "cloud-clipboard-web:$Tag" $webDir
if ($LASTEXITCODE -ne 0) { throw 'web 镜像构建失败' }

# 源码包：只含已跟踪文件，不含 .env / certs
$sourceArchive = Join-Path $outDir "source-$Tag.tar.gz"
Push-Location $repoRoot
try {
    & git archive --format=tar.gz -o $sourceArchive HEAD
} finally {
    Pop-Location
}
if ($LASTEXITCODE -ne 0) { throw '源码打包失败' }

# 镜像包：docker save 先写 tar，再用 .NET gzip 压缩。
# ⚠️ PowerShell 管道会破坏二进制，不能 `docker save | gzip`。
$tarPath = Join-Path $outDir "release-$Tag.tar"
$tgzPath = Join-Path $outDir "release-$Tag.tar.gz"
& docker save -o $tarPath "cloud-clipboard-api:$Tag" "cloud-clipboard-web:$Tag"
if ($LASTEXITCODE -ne 0) { throw 'docker save 失败' }

$input = [IO.File]::OpenRead($tarPath)
$output = [IO.File]::Create($tgzPath)
$gzip = [IO.Compression.GZipStream]::new($output, [IO.Compression.CompressionMode]::Compress)
try {
    $input.CopyTo($gzip)
} finally {
    $gzip.Dispose()
    $input.Dispose()
    $output.Dispose()
}
Remove-Item $tarPath

foreach ($file in @($sourceArchive, $tgzPath)) {
    $item = Get-Item $file
    $hash = (Get-FileHash $file -Algorithm SHA256).Hash
    Write-Host ("[build] {0}  {1:N1} MB  sha256={2}" -f $item.Name, ($item.Length / 1MB), $hash)
}

Write-Host "[build] 完成：$outDir" -ForegroundColor Green
