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

Write-Host "1/3 Memasang cloudflared sebagai service..." -ForegroundColor Cyan
# Matikan proses tunnel yang berjalan manual supaya tidak dobel koneksi.
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

& $cloudflared --config $configPath service uninstall 2>$null | Out-Null
& $cloudflared --config $configPath service install
if ($LASTEXITCODE -ne 0) { throw "cloudflared service install gagal (exit $LASTEXITCODE)." }
Set-Service -Name cloudflared -StartupType Automatic
Restart-Service -Name cloudflared -Force
Start-Sleep -Seconds 3
$svc = Get-Service cloudflared
Write-Host ("   cloudflared: {0} / {1}" -f $svc.Status, $svc.StartType) -ForegroundColor Green

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
# Hentikan instance yang mungkin masih jalan manual, supaya tugas tidak mati karena port terpakai.
foreach ($port in @($GatewayPort, $DashboardPort)) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 2
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 12

foreach ($check in @(
        @{ Name = 'tunnel'; Url = 'http://127.0.0.1:8645/health' },
        @{ Name = 'dashboard'; Url = 'http://127.0.0.1:8680/api/status' })) {
    try {
        $r = Invoke-WebRequest -Uri $check.Url -TimeoutSec 10
        Write-Host ("   {0}: HTTP {1}" -f $check.Name, $r.StatusCode) -ForegroundColor Green
    } catch {
        Write-Warning ("   {0}: belum merespons — cek {1}\logs" -f $check.Name, $DataDir)
    }
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
