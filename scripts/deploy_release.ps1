<#
云剪贴板 · 上传发布包并在服务器部署（方案 B）

用法（仓库根目录）：
    .\scripts\deploy_release.ps1 -Tag "1.0.0"

前置：
    - 已运行 build_release.ps1
    - 服务器已存在 /opt/cloud-clipboard/deploy/.env
    - 本机可免密 SSH 登录服务器

流程：
    上传镜像包与源码包 → 解压源码 → 更新 IMAGE_TAG → docker load
    → 备份数据库 → alembic upgrade head → up -d → 健康检查
#>
[CmdletBinding()]
param(
    [string]$Tag = '1.0.0',
    [string]$Server = 'ubuntu@43.134.121.173',
    [string]$ReleaseDir = 'dist',
    [string]$HealthUrl = 'https://43.134.121.173:8443/health'
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$release = Join-Path $repoRoot (Join-Path $ReleaseDir "release-$Tag.tar.gz")
$source = Join-Path $repoRoot (Join-Path $ReleaseDir "source-$Tag.tar.gz")

foreach ($file in @($release, $source)) {
    if (-not (Test-Path $file)) { throw "缺少发布文件：$file" }
}

function Invoke-ScpWithRetry([string]$src, [string]$dst) {
    for ($i = 1; $i -le 3; $i++) {
        & scp -o ConnectTimeout=30 $src $dst
        if ($LASTEXITCODE -eq 0) { return }
        if ($i -lt 3) {
            Write-Host "[deploy] scp 失败，重试（$i/2）…" -ForegroundColor Yellow
            Start-Sleep -Seconds 8
        }
    }
    throw "scp 失败：$src → $dst"
}

Write-Host "[deploy] 上传发布包…" -ForegroundColor Cyan
Invoke-ScpWithRetry $release "${Server}:/tmp/release-$Tag.tar.gz"
Invoke-ScpWithRetry $source "${Server}:/tmp/source-$Tag.tar.gz"

# ⚠️ 用 __TAG__ 占位符，避免 Replace('TAG') 误伤 IMAGE_TAG 等单词
$remote = @'
set -euo pipefail
cd /opt/cloud-clipboard
export IMAGE_TAG=__TAG__

tar -xzf /tmp/source-__TAG__.tar.gz -C /opt/cloud-clipboard
rm -f /tmp/source-__TAG__.tar.gz

sed -i '/^IMAGE_TAG=/d' deploy/.env
printf 'IMAGE_TAG=__TAG__\n' >> deploy/.env
chmod 600 deploy/.env
grep -q '^IMAGE_TAG=__TAG__$' deploy/.env

gunzip -c /tmp/release-__TAG__.tar.gz | sudo docker load
rm -f /tmp/release-__TAG__.tar.gz

sudo env IMAGE_TAG="$IMAGE_TAG" docker compose -f deploy/docker-compose.prod.yml config --quiet

mkdir -p backups
sudo env IMAGE_TAG="$IMAGE_TAG" docker compose -f deploy/docker-compose.prod.yml exec -T db pg_dump -U clipboard clipboard \
  | gzip > "backups/backup-$(date +%Y%m%d-%H%M%S).sql.gz"

sudo env IMAGE_TAG="$IMAGE_TAG" docker compose -f deploy/docker-compose.prod.yml run --rm api alembic upgrade head
sudo env IMAGE_TAG="$IMAGE_TAG" docker compose -f deploy/docker-compose.prod.yml up -d

sleep 5
curl -sk https://127.0.0.1:8443/health
echo
'@

$remote = $remote.Replace('__TAG__', $Tag)
$remoteScript = Join-Path $env:TEMP "cc-deploy-$Tag.sh"
[IO.File]::WriteAllText(
    $remoteScript,
    $remote.Replace("`r`n", "`n"),
    [Text.UTF8Encoding]::new($false)
)

Write-Host "[deploy] 上传部署脚本…" -ForegroundColor Cyan
Invoke-ScpWithRetry $remoteScript "${Server}:/tmp/cc-deploy.sh"

$exit = 255
for ($i = 1; $i -le 3; $i++) {
    Write-Host "[deploy] 执行远程部署（第 $i 次）…" -ForegroundColor Cyan
    & ssh -o ConnectTimeout=30 $Server 'bash /tmp/cc-deploy.sh'
    $exit = $LASTEXITCODE
    if ($exit -ne 255) { break }
    if ($i -lt 3) {
        Write-Host "[deploy] SSH 连接失败，重试…" -ForegroundColor Yellow
        Start-Sleep -Seconds 10
    }
}
Remove-Item $remoteScript -ErrorAction SilentlyContinue
if ($exit -ne 0) { throw "远程部署失败（exit $exit）" }

Write-Host "[deploy] 外部健康检查：$HealthUrl" -ForegroundColor Cyan
$response = Invoke-WebRequest -SkipCertificateCheck -SkipHttpErrorCheck -Uri $HealthUrl -TimeoutSec 20
Write-Host "[deploy] HTTP $($response.StatusCode) $($response.Content)"
if ($response.StatusCode -ne 200) { throw '外部健康检查失败' }

Write-Host '[deploy] 完成' -ForegroundColor Green
