<#
.SYNOPSIS
    在本机网络环境下推送仓库：临时把 Clash 切到全局模式，push 完成后立刻还原。

.DESCRIPTION
    本机 Clash 采用「规则模式」时，github.com 被判定为直连，TLS 会被重置，
    git push 报 `Recv failure: Connection was reset`。
    直连端口本身是通的（代理能 CONNECT 成功），只是缺一条 github 走代理的规则。

    这个脚本的做法：
      1. 从 Windows 系统代理读出 Clash 的 http 端口（也可用 -ProxyPort 指定）；
      2. 探测 Clash 的外部控制器（默认 33212，失败则试 9090/9091/9097/6170）；
      3. 读当前 mode → 临时改成 global → git push → 无论成败都改回原来的 mode。

.PARAMETER Remote
    远端名，默认 origin。

.PARAMETER Branch
    分支名，默认 main。

.PARAMETER ProxyPort
    Clash 的 http 代理端口，默认自动从系统代理推断（如 127.0.0.1:33210 → 33210）。

.PARAMETER ApiPort
    Clash 外部控制器端口，默认自动探测。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\push.ps1
    powershell -ExecutionPolicy Bypass -File scripts\push.ps1 -Remote origin -Branch feat/interview
#>
[CmdletBinding()]
param(
    [string]$Remote = "origin",
    [string]$Branch = "main",
    [int]$ProxyPort = 0,
    [int]$ApiPort = 0
)

$ErrorActionPreference = "Stop"
# 让中文提示在 PS 5.1 的控制台里不乱码
try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch { }

# ---------- 1. 代理端口：默认取 Windows 系统代理 ----------
if ($ProxyPort -eq 0) {
    $ie = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue
    if ($ie -and $ie.ProxyServer) {
        $raw = $ie.ProxyServer                       # 形如 127.0.0.1:33210 或 http=127.0.0.1:33210;https=...
        if ($raw -match '(\d+)\s*$') { $ProxyPort = [int]$matches[1] }
        elseif ($raw -match '=.*:(\d+)') { $ProxyPort = [int]$matches[1] }
    }
}
if ($ProxyPort -eq 0) {
    Write-Host "[push] 未检测到系统代理，直接尝试推送（若失败请加 -ProxyPort）" -ForegroundColor Yellow
}

# ---------- 2. Clash 控制器 ----------
if ($ApiPort -eq 0) {
    foreach ($p in 33212, 9090, 9091, 9097, 6170) {
        try {
            $cfg = Invoke-RestMethod -Uri "http://127.0.0.1:$p/configs" -TimeoutSec 3
            if ($null -ne $cfg.mode) { $ApiPort = $p; break }
        } catch { }
    }
}

$proxyArgs = @()
if ($ProxyPort -ne 0) {
    $proxyArgs = @("-c", "http.proxy=http://127.0.0.1:$ProxyPort", "-c", "https.proxy=http://127.0.0.1:$ProxyPort")
}

$origMode = $null
if ($ApiPort -ne 0) {
    try {
        $origMode = (Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/configs" -TimeoutSec 5).mode
        Write-Host "[push] Clash 控制器 127.0.0.1:$ApiPort，当前 mode=$origMode" -ForegroundColor Cyan
    } catch { $origMode = $null }
}

$exitCode = 1
try {
    if ($origMode -eq "rule") {
        Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/configs" -Method Patch `
            -Body '{"mode":"global"}' -ContentType 'application/json' -TimeoutSec 5 | Out-Null
        Write-Host "[push] mode → global" -ForegroundColor Cyan
        Start-Sleep -Milliseconds 400
    }

    Write-Host "[push] git @($proxyArgs) push -u $Remote $Branch" -ForegroundColor Cyan
    & git @proxyArgs push -u $Remote $Branch
    $exitCode = $LASTEXITCODE
} finally {
    if ($origMode -and $origMode -ne "global") {
        try {
            Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/configs" -Method Patch `
                -Body ('{"mode":"' + $origMode + '"}') -ContentType 'application/json' -TimeoutSec 5 | Out-Null
            Write-Host "[push] mode 还原 → $origMode" -ForegroundColor Cyan
        } catch {
            Write-Host "[push] 警告：mode 还原失败，请手动把 Clash 切回 $origMode" -ForegroundColor Red
        }
    }
}

if ($exitCode -eq 0) { Write-Host "[push] 成功" -ForegroundColor Green }
else { Write-Host "[push] 失败，exit=$exitCode" -ForegroundColor Red }
exit $exitCode
