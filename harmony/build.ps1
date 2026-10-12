<#
云剪贴板 · 鸿蒙端构建脚本

用法（在仓库根目录或 harmony/ 下均可）：
    .\harmony\build.ps1              # 构建未签名 HAP（无需签名配置）
    .\harmony\build.ps1 -Clean       # 先清理再构建

为什么要用这个脚本：hvigor 依赖三个环境变量，缺一个就会以难以理解的错误失败。
- DEVECO_SDK_HOME  缺 → 找不到 SDK
- NODE_HOME        缺 → hvigor 起不来
- JAVA_HOME        ⚠️ 缺 → 打包阶段报 `spawn java ENOENT`，错误码 00308018
                     （这个错看起来像签名问题，其实是缺 Java）

产物：entry/build/default/outputs/default/entry-default-unsigned.hap

⚠️ 产物是**未签名**的，不能直接安装到设备。要安装请在 DevEco Studio 里配置签名
   （File → Project Structure → Signing Configs → 勾选 Automatically generate signature），
   或用 DevEco 直接 Run。签名细节见 harmony/README.md。
#>
[CmdletBinding()]
param(
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'

$DevEcoRoot = 'C:\Program Files\Huawei\DevEco Studio'
$SdkHome = Join-Path $DevEcoRoot 'sdk'
$NodeHome = Join-Path $DevEcoRoot 'tools\node'
$JavaHome = Join-Path $DevEcoRoot 'jbr'
$Hvigor = Join-Path $DevEcoRoot 'tools\hvigor\bin\hvigorw.bat'

foreach ($tool in @($Hvigor, (Join-Path $NodeHome 'node.exe'), (Join-Path $JavaHome 'bin\java.exe'))) {
    if (-not (Test-Path $tool)) {
        Write-Error "未找到 $tool。请确认 DevEco Studio 安装在 `"$DevEcoRoot`"，或修改本脚本顶部的路径。"
    }
}

# 切到 harmony 目录（脚本可能在仓库根目录被调用）
$harmonyDir = $PSScriptRoot
Push-Location $harmonyDir
try {
    $env:DEVECO_SDK_HOME = $SdkHome
    $env:NODE_HOME = $NodeHome
    $env:JAVA_HOME = $JavaHome
    $env:PATH = "$JavaHome\bin;$NodeHome;$env:PATH"

    if ($Clean) {
        Write-Host '[build] 清理构建产物…' -ForegroundColor Cyan
        & $Hvigor clean --no-daemon | Out-Null
    }

    Write-Host '[build] 开始构建 HAP…' -ForegroundColor Cyan
    & $Hvigor assembleHap --no-daemon
    $code = $LASTEXITCODE

    if ($code -ne 0) {
        Write-Host "[build] 构建失败（退出码 $code）" -ForegroundColor Red
        exit $code
    }

    $hap = Join-Path $harmonyDir 'entry\build\default\outputs\default\entry-default-unsigned.hap'
    if (Test-Path $hap) {
        $size = [math]::Round((Get-Item $hap).Length / 1KB)
        Write-Host "[build] 成功：$hap（$size KB，未签名）" -ForegroundColor Green
        Write-Host '[build] 提示：未签名 HAP 不能直接安装；请在 DevEco Studio 中配置签名后 Run。' -ForegroundColor Yellow
    } else {
        Write-Host '[build] 构建返回成功，但未找到 HAP 产物，请检查上方日志。' -ForegroundColor Yellow
        exit 1
    }
} finally {
    Pop-Location
}
