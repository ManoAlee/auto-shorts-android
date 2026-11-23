<#
.SYNOPSIS
    AutoShorts Sentinel - Daemon de Alta Disponibilidade e Auto-Cura (Zero-Drop)
    Mantém conexão USB, portas ADB forward, túnel Cloudflare e serviços Termux sempre vivos.
#>

param(
    [int]$IntervalSec = 3,
    [string]$AdbPath = "C:\platform-tools\adb.exe",
    [string]$DesktopPath = [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop)
)

$ErrorActionPreference = "SilentlyContinue"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  AUTOSHORTS ZERO-DROP SENTINEL ATIVADO (SAMSUNG A55)" -ForegroundColor Green
Write-Host "  Monitorando ADB, Port Forwards, WebApp e Servicos 24/7" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

function Ensure-DesktopShortcut([string]$Name, [string]$Url) {
    if (-not (Test-Path $DesktopPath)) { return }
    $shortcutPath = Join-Path $DesktopPath "$Name.url"
    $content = "[InternetShortcut]`r`nURL=$Url`r`nIconIndex=0`r`n"
    if (-not (Test-Path $shortcutPath) -or (Get-Content $shortcutPath -Raw) -ne $content) {
        Set-Content -Path $shortcutPath -Value $content -Encoding UTF8 -Force
    }
}

function Test-WebStatus([string]$Url, [int]$TimeoutSec = 6) {
    try {
        $req = [System.Net.HttpWebRequest]::Create($Url)
        $req.Timeout = $TimeoutSec * 1000
        $req.Method = "GET"
        $res = $req.GetResponse()
        $ok = ($res.StatusCode -eq [System.Net.HttpStatusCode]::OK)
        $res.Close()
        return $ok
    } catch {
        return $false
    }
}

# Atalho fixo USB Local
Ensure-DesktopShortcut "AutoShorts Studio (USB Local)" "http://127.0.0.1:8787"
# Atalho fixo Tailscale
Ensure-DesktopShortcut "AutoShorts Studio (Tailscale)" "http://100.122.142.89:8787"

$lastTunnelUrl = ""
$consecutiveFails = 0

while ($true) {
    try {
        # 1. Verificar se o celular esta conectado via ADB
        $devices = & $AdbPath devices 2>$null | Out-String
        $isDeviceConnected = ($devices -match "(device\s*$|model:)")

        if ($isDeviceConnected) {
            # 2. Verificar e restaurar ADB Port Forwards imediatamente
            $forwards = & $AdbPath forward --list 2>$null | Out-String
            if ($forwards -notmatch "tcp:8787\s+tcp:8787") {
                & $AdbPath forward tcp:8787 tcp:8787 2>$null
                Write-Host "[$(Get-Date -Format 'HH:mm:ss')] [ADB] Porta 8787 (Web) re-encaminhada com sucesso." -ForegroundColor Yellow
            }
            if ($forwards -notmatch "tcp:8022\s+tcp:8022") {
                & $AdbPath forward tcp:8022 tcp:8022 2>$null
                Write-Host "[$(Get-Date -Format 'HH:mm:ss')] [ADB] Porta 8022 (SSH) re-encaminhada com sucesso." -ForegroundColor Yellow
            }

            # 3. Testar Saude da WebApp em 127.0.0.1:8787
            $webOk = Test-WebStatus "http://127.0.0.1:8787/api/status" 2
            if ($webOk) {
                if ($consecutiveFails -gt 0) {
                    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] [RECUPERADO] AutoShorts Studio respondendo 100%!" -ForegroundColor Green
                    $consecutiveFails = 0
                }
            } else {
                $consecutiveFails++
                if ($consecutiveFails -ge 2) {
                    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] [ALERTA] WebApp nao respondeu. Disparando despertar do Termux..." -ForegroundColor Red
                    & $AdbPath shell "am startservice -n com.termux/.app.TermuxService ; cmd package compile -m speed com.termux 2>/dev/null" 2>$null
                    & $AdbPath shell "settings put global stay_on_while_plugged_in 7" 2>$null
                    Start-Sleep -Seconds 2
                }
            }

            # 4. Sincronizar URL do Tunel Cloudflare para o Desktop
            $tunnelUrl = ""
            try {
                $tunnelUrl = (& ssh -p 8022 -o StrictHostKeyChecking=no -o ConnectTimeout=2 127.0.0.1 "cat ~/auto-shorts-android/output/tunnel_url.txt 2>/dev/null").Trim()
            } catch {}

            if ($tunnelUrl -and $tunnelUrl -match "^https://" -and $tunnelUrl -ne $lastTunnelUrl) {
                $lastTunnelUrl = $tunnelUrl
                Ensure-DesktopShortcut "AutoShorts Studio (Nuvem)" $tunnelUrl
                Write-Host "[$(Get-Date -Format 'HH:mm:ss')] [TUNNEL] Atalho Nuvem atualizado: $tunnelUrl" -ForegroundColor Cyan
            }
        }
    } catch {
        # Resiliencia contra interrupcoes
    }

    Start-Sleep -Seconds $IntervalSec
}
