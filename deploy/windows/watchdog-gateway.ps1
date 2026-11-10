# watchdog-gateway.ps1 — keep api.withmerlin.online answering.
#
# Run every five minutes by the MerlinGatewayWatchdog task. It checks the public health endpoint, not just the
# local port: a gateway that is up while its tunnel is dead answers nothing for a customer. Depending on what is
# broken it starts the missing pieces through start-gateway.ps1 (which is idempotent) or only the tunnel.
#
# Every decision is appended to gateway\logs\watchdog.log, and the log keeps its last 2000 lines.
param(
    [string]$PublicUrl = 'https://api.withmerlin.online/health',
    [int]$GatewayPort = 8645,
    [int]$DashboardPort = 8680,
    [string]$DataDir = "$env:LOCALAPPDATA\merlin\gateway",
    [string]$StartScript = "$env:LOCALAPPDATA\merlin\scratch\proxy-metering\deploy\windows\start-gateway.ps1",
    # Report what it would do and stop. Used to exercise the detection half without touching live processes.
    [switch]$DetectOnly
)

$ErrorActionPreference = 'Continue'
$logDir = Join-Path $DataDir 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$logPath = Join-Path $logDir 'watchdog.log'

function Write-Log([string]$message) {
    Add-Content -Path $logPath -Value ("{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $message)
    $lines = @(Get-Content -Path $logPath -ErrorAction SilentlyContinue)
    if ($lines.Count -gt 2000) {
        $lines[-2000..-1] | Set-Content -Path $logPath
    }
}

function Test-PortOpen([int]$Port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try { $client.Connect('127.0.0.1', $Port); return $client.Connected }
    catch { return $false }
    finally { $client.Dispose() }
}

function Test-Public {
    try {
        $r = Invoke-WebRequest -Uri $PublicUrl -TimeoutSec 20 -UseBasicParsing
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

$tunnelConfig = Join-Path $DataDir 'cloudflared-config.yml'
$cloudflared = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'

function Get-OurTunnels {
    @(Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*$tunnelConfig*" })
}

function Start-Tunnel {
    Start-Process -FilePath $cloudflared `
        -ArgumentList @('--config', ('"' + $tunnelConfig + '"'), 'tunnel', 'run') -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDir 'tunnel.log') `
        -RedirectStandardError (Join-Path $logDir 'tunnel.log.err') | Out-Null
}

$localUp = (Test-PortOpen $GatewayPort) -and (Test-PortOpen $DashboardPort)
$publicUp = Test-Public

if ($localUp -and $publicUp) {
    Write-Log 'ok  gateway local + public healthy'
    exit 0
}

if ($DetectOnly) {
    Write-Log ("detect-only  local={0} public={1}" -f $localUp, $publicUp)
    Write-Output ("local={0} public={1}" -f $localUp, $publicUp)
    exit 0
}

if (-not $localUp) {
    Write-Log ("down  local stack not listening (8645={0} 8680={1}); starting it" -f (Test-PortOpen $GatewayPort), (Test-PortOpen $DashboardPort))
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StartScript *>> $logPath
    Start-Sleep -Seconds 10
}

if (-not (Test-Public)) {
    $ours = Get-OurTunnels
    if ($ours.Count -gt 0) {
        Write-Log ("down  public endpoint unreachable with {0} tunnel(s) running; restarting the tunnel" -f $ours.Count)
        $ours | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 3
    } else {
        Write-Log 'down  public endpoint unreachable and no tunnel running; starting one'
    }
    if ((Test-Path $tunnelConfig) -and (Test-Path $cloudflared)) {
        Start-Tunnel
        Start-Sleep -Seconds 12
    } else {
        Write-Log 'fatal  cloudflared or tunnel config missing; cannot start the tunnel'
        exit 1
    }
}

if (Test-Public) {
    Write-Log 'recovered  public endpoint answering again'
    exit 0
}

Write-Log 'failed  public endpoint still unreachable after restart'
exit 1
