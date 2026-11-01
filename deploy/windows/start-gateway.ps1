# start-gateway.ps1 — jalankan gateway + dashboard DI MESIN INI.
#
#   powershell -ExecutionPolicy Bypass -File deploy\windows\start-gateway.ps1
#
# Tidak ada VPS, tidak ada port yang dibuka ke internet: nanti cloudflared yang menembus keluar.
# Token admin dibuat sekali lalu disimpan; JANGAN dibuat ulang tiap start (invoice lama jadi tak
# bisa dikonfirmasi dengan token baru).

[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path,
    [string]$Python = "$env:LOCALAPPDATA\merlin\merlin-agent\.venv\Scripts\python.exe",
    [string]$DataDir = "$env:LOCALAPPDATA\merlin\gateway",
    [int]$GatewayPort = 8645,
    [int]$DashboardPort = 8680
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $Python)) {
    throw "Python Merlin tidak ditemukan di $Python. Jalankan dari venv Merlin yang benar."
}
if (-not (Test-Path $DataDir)) { New-Item -ItemType Directory -Path $DataDir | Out-Null }

$configPath = Join-Path $DataDir 'proxy_upstreams.json'
if (-not (Test-Path $configPath)) {
    Write-Warning "Belum ada upstream: $configPath"
    Write-Warning "Buat dulu (lihat deploy/windows/README.md), lalu jalankan ulang."
}

$qrisPath = Join-Path $DataDir 'qris.txt'
if (-not (Test-Path $qrisPath)) {
    Write-Warning "Belum ada payload QRIS: $qrisPath (dashboard akan menolak start)."
}

$tokenPath = Join-Path $DataDir 'admin_token.txt'
if (-not (Test-Path $tokenPath)) {
    $token = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
    Set-Content -Path $tokenPath -Value $token -NoNewline -Encoding ascii
    Write-Host "Token admin dibuat: $tokenPath"
}

$env:PYTHONPATH = $RepoRoot
$env:MERLIN_PROXY_METERING = '1'
$env:MERLIN_PROXY_LEDGER = Join-Path $DataDir 'ledger.db'
$env:MERLIN_PROXY_PROBES = Join-Path $DataDir 'ledger.db'
$env:MERLIN_PROXY_UPSTREAMS = $configPath
$env:MERLIN_PROXY_QRIS_FILE = $qrisPath
$env:MERLIN_PROXY_ADMIN_TOKEN = (Get-Content $tokenPath -Raw).Trim()
$env:PYTHONUNBUFFERED = '1'

$logDir = Join-Path $DataDir 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

function Start-LocalService {
    param([string]$Name, [string[]]$Arguments, [string]$Log)
    $proc = Start-Process -FilePath $Python -ArgumentList $Arguments -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $Log -RedirectStandardError "$Log.err"
    Write-Host ("{0}: pid {1}  log {2}" -f $Name, $proc.Id, $Log)
    return $proc
}

$gateway = Start-LocalService -Name 'gateway' -Log (Join-Path $logDir 'gateway.log') -Arguments @(
    '-m', 'merlin_cli.proxy.entry', 'serve',
    '--provider', 'generic', '--host', '127.0.0.1', '--port', "$GatewayPort"
)
$dashboard = Start-LocalService -Name 'dashboard' -Log (Join-Path $logDir 'dashboard.log') -Arguments @(
    '-m', 'merlin_cli.proxy.entry', 'dashboard',
    '--host', '127.0.0.1', '--port', "$DashboardPort"
)
# Catatan: jalur QRIS TIDAK dikirim lewat argumen. Start-Process tidak mengutip path yang mengandung
# spasi (mis. "C:\Users\JM Project\..."), sehingga argumen pecah dan dashboard gagal start. Nilainya
# sudah ada di MERLIN_PROXY_QRIS_FILE di atas.

Start-Sleep -Seconds 4
foreach ($pair in @(@{ Name = 'gateway'; Port = $GatewayPort; Path = '/health' },
                    @{ Name = 'dashboard'; Port = $DashboardPort; Path = '/api/status' })) {
    try {
        $r = Invoke-WebRequest -Uri ("http://127.0.0.1:{0}{1}" -f $pair.Port, $pair.Path) -TimeoutSec 8
        Write-Host ("{0}: OK HTTP {1}" -f $pair.Name, $r.StatusCode)
    } catch {
        Write-Warning ("{0}: belum merespons — cek {1}" -f $pair.Name, (Join-Path $logDir ($pair.Name + '.log.err')))
    }
}

Write-Host ""
Write-Host "Gateway  : http://127.0.0.1:$GatewayPort/v1"
Write-Host "Dashboard: http://127.0.0.1:$DashboardPort"
Write-Host "Token    : $tokenPath"
Write-Host ""
Write-Host "Berikutnya: cloudflared tunnel --config deploy\windows\cloudflared-config.yml run"
