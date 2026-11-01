<#
.SYNOPSIS
    Pasang auto-start permanen untuk Merlin Gateway (tunnel + gateway + dashboard).

.DESCRIPTION
    Dua hal dipasang sekaligus, karena satu tanpa yang lain tidak berguna:

    1. cloudflared  -> Windows service (jalan saat boot, sebelum login).
    2. gateway+dashboard -> Scheduled Task saat logon, sebagai user Anda (proses Python perlu
       profil user untuk membaca %LOCALAPPDATA%\merlin\gateway dan venv Merlin).

    Skrip ini WAJIB dijalankan sebagai Administrator (service install memerlukan hak itu).
    Jalankan ulang kapan saja — idempoten.

.EXAMPLE
    # dari PowerShell biasa, ini memunculkan prompt UAC:
    Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',"$PWD\install-autostart.ps1"
#>
[CmdletBinding()]
param(
    [string]$DataDir = "$env:LOCALAPPDATA\merlin\gateway",
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path,
    [string]$TaskName = 'MerlinGateway',
    [int]$GatewayPort = 8645,
    [int]$DashboardPort = 8680
)

$ErrorActionPreference = 'Stop'
$cloudflared = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
$configPath = Join-Path $DataDir 'cloudflared-config.yml'
$startScript = Join-Path $PSScriptRoot 'start-gateway.ps1'

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Skrip ini harus dijalankan sebagai Administrator. Buka PowerShell as Admin lalu jalankan ulang."
    }
}

Assert-Admin

foreach ($required in @($cloudflared, $configPath, $startScript)) {
    if (-not (Test-Path $required)) { throw "Tidak ditemukan: $required" }
}

Write-Host "1/3 Melepas service cloudflared (tunnel kini dijalankan oleh task)..." -ForegroundColor Cyan
# Matikan proses tunnel yang berjalan manual supaya tidak dobel koneksi.
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# cloudflared menulis log ke stderr. Dengan $ErrorActionPreference='Stop', Windows PowerShell 5.1
# memperlakukan stderr program native sebagai error fatal dan skrip berhenti
# (kejadian nyata: uninstall sukses tapi skrip abort, tunnel tertinggal mati).
function Invoke-Cloudflared {
    param([string[]]$Arguments)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & $cloudflared @Arguments 2>&1
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    return @{ Output = $output; Code = $code }
}

# Service cloudflared 2025.8.1 memasang dirinya TANPA --config, dan sebagai LocalSystem ia membaca
# config dari profil SYSTEM — hasilnya "Running" tapi tidak tersambung (Cloudflare 530). Tunnel
# sekarang dijalankan sebagai proses biasa oleh Scheduled Task, jadi service lama dilepas agar tidak
# berebut tunnel yang sama.
if (Get-Service cloudflared -ErrorAction SilentlyContinue) {
    $uninstall = Invoke-Cloudflared -Arguments @('--config', $configPath, 'service', 'uninstall')
    Write-Host ("   uninstall service: exit {0}" -f $uninstall.Code) -ForegroundColor DarkGray
    for ($i = 0; $i -lt 10; $i++) {
        if (-not (Get-Service cloudflared -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Seconds 1
    }
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    if (Get-Service cloudflared -ErrorAction SilentlyContinue) {
        Write-Warning "   service masih terdaftar; jalankan 'sc.exe delete cloudflared' sekali, lalu ulangi."
    } else {
        Write-Host "   service cloudflared dilepas" -ForegroundColor Green
    }
} else {
    Write-Host "   tidak ada service cloudflared — bagus, tunnel akan jalan dari task" -ForegroundColor Green
}

Write-Host "2/3 Memasang Scheduled Task untuk gateway + dashboard (saat logon)..." -ForegroundColor Cyan
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument ("-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"{0}`"" -f $startScript)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 0)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Force | Out-Null
Write-Host "   task '$TaskName' terdaftar (trigger: logon $env:USERNAME)" -ForegroundColor Green

Write-Host "3/3 Menjalankan sekarang..." -ForegroundColor Cyan
# Hentikan instance yang mungkin masih jalan manual, supaya tugas tidak mati karena port terpakai
# dan tunnel tidak dobel koneksi.
foreach ($port in @($GatewayPort, $DashboardPort)) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 15

foreach ($check in @(
        @{ Name = 'gateway(local)'; Url = 'http://127.0.0.1:8645/health' },
        @{ Name = 'dashboard(local)'; Url = 'http://127.0.0.1:8680/api/status' })) {
    try {
        # -UseBasicParsing: tanpa itu Windows PowerShell memunculkan prompt "Script Execution Risk"
        # dan menunggu jawaban, bukan memeriksa apa pun.
        $r = Invoke-WebRequest -Uri $check.Url -TimeoutSec 10 -UseBasicParsing
        Write-Host ("   {0}: HTTP {1}" -f $check.Name, $r.StatusCode) -ForegroundColor Green
    } catch {
        Write-Warning ("   {0}: belum merespons — cek {1}\logs" -f $check.Name, $DataDir)
    }
}

# Verifikasi PUBLIK, bukan localhost: tunnel bisa mati sementara gateway lokal tetap 200 (persis
# kasus yang menyesatkan sebelumnya: "tunnel: HTTP 200" padahal Cloudflare menjawab 530).
if (Test-Path $tunnelConfig) {
    $hostnames = (Get-Content $tunnelConfig | Select-String -Pattern '^\s*-\s*hostname:\s*(\S+)').Matches |
        ForEach-Object { $_.Groups[1].Value }
    foreach ($hostname in $hostnames) {
        $url = "https://$hostname/health"
        if ($hostname -notmatch '^api\.') { $url = "https://$hostname/" }
        for ($attempt = 1; $attempt -le 5; $attempt++) {
            try {
                $r = Invoke-WebRequest -Uri $url -TimeoutSec 12 -UseBasicParsing
                Write-Host ("   publik {0}: HTTP {1}" -f $hostname, $r.StatusCode) -ForegroundColor Green
                break
            } catch {
                if ($attempt -eq 5) {
                    Write-Warning ("   publik {0}: gagal — cek {1}" -f $hostname, (Join-Path $logDir 'tunnel.log.err'))
                } else {
                    Start-Sleep -Seconds 3
                }
            }
        }
    }
}

if ((Get-Service cloudflared -ErrorAction SilentlyContinue).Status -eq 'Running') {
    Write-Warning "service cloudflared masih jalan — ia akan berebut tunnel dengan proses di atas; uninstall service-nya."
}

$public = (Get-Content $configPath | Select-String -Pattern 'hostname:\s*(\S+)' -AllMatches).Matches.Value
Write-Host ""
Write-Host "Selesai. Yang sekarang otomatis saat PC menyala:" -ForegroundColor Cyan
Write-Host "  - cloudflared service (boot, sebelum login)"
Write-Host "  - gateway :$GatewayPort + dashboard :$DashboardPort (saat login $env:USERNAME)"
Write-Host ""
Write-Host "Cek kapan saja:" -ForegroundColor Cyan
Write-Host "  Get-Service cloudflared; Get-ScheduledTask $TaskName"
Write-Host "  curl.exe -s https://api.withmerlin.online/health"
