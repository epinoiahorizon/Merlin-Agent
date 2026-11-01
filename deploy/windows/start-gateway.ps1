# start-gateway.ps1 — jalankan gateway + dashboard DI MESIN INI.
#
#   powershell -ExecutionPolicy Bypass -File deploy\windows\start-gateway.ps1
#
# Tidak ada VPS, tidak ada port yang dibuka ke internet: nanti cloudflared yang menembus keluar.
# Token admin dibuat sekali lalu disimpan; JANGAN dibuat ulang tiap start (invoice lama jadi tak
# bisa dikonfirmasi dengan token baru).

[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$Python = "$env:LOCALAPPDATA\merlin\merlin-agent\.venv\Scripts\python.exe",
    [string]$DataDir = "$env:LOCALAPPDATA\merlin\gateway",
    [int]$GatewayPort = 8645,
    [int]$DashboardPort = 8680
)

$ErrorActionPreference = 'Stop'

# $PSScriptRoot tidak selalu terisi saat skrip dipanggil dengan -File (gejala nyata: RepoRoot jadi
# "C:\..\.." dan Python mati di import). Turunkan dari lokasi skrip yang sebenarnya, lalu validasi.
if (-not $RepoRoot) {
    $scriptPath = $MyInvocation.MyCommand.Path
    if (-not $scriptPath) { throw "Tidak bisa menentukan lokasi skrip (MyCommand.Path kosong)." }
    $RepoRoot = (Resolve-Path (Join-Path (Split-Path -Parent $scriptPath) '..\..')).Path
}
if (-not (Test-Path (Join-Path $RepoRoot 'merlin_cli\proxy\entry.py'))) {
    throw "RepoRoot salah: '$RepoRoot' tidak berisi merlin_cli\proxy\entry.py"
}

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
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    # [Convert]::ToHexString hanya ada di .NET 5+ / PowerShell 7; di Windows PowerShell 5.1 metode itu
    # tidak ada dan pembuatan token akan gagal. Format per-byte menjaga RNG kriptografis yang sama.
    $token = -join ($bytes | ForEach-Object { $_.ToString('x2') })
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

# Rahasia upstream (API key relay) hidup di gateway.env, bukan di proxy_upstreams.json.
$envFile = Join-Path $DataDir 'gateway.env'
if (-not (Test-Path $envFile)) {
    Set-Content -Path $envFile -Value "# THIRTYSTORE_API_KEY=..." -Encoding ascii
    Write-Warning "gateway.env belum berisi kunci upstream — upstream dengan api_key_env akan gagal (401)."
}

# Peluncuran TIDAK boleh bergantung pada environment warisan: Task Scheduler tidak meneruskan
# PYTHONPATH, dan proses anak mati dengan "No module named merlin_cli.proxy.entry". Wrapper ini
# menyisipkan RepoRoot ke sys.path sendiri, lalu semua path diteruskan sebagai argumen.
$launcher = Join-Path $DataDir 'launch_proxy.py'
$launcherBody = @(
    'import sys',
    ('sys.path.insert(0, r"' + $RepoRoot + '")'),
    'from merlin_cli.proxy.entry import main',
    'raise SystemExit(main(sys.argv[1:]))'
) -join "`r`n"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($launcher, $launcherBody, $utf8NoBom)

# Start-Process tidak mengutip argumen; setiap path yang mengandung spasi harus dibungkus sendiri.
function Q([string]$value) { return '"' + $value + '"' }

$ledgerPath = Join-Path $DataDir 'ledger.db'

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
    (Q $launcher), 'serve', '--provider', 'generic', '--host', '127.0.0.1', '--port', "$GatewayPort",
    '--upstreams', (Q $configPath), '--ledger', (Q $ledgerPath), '--env-file', (Q $envFile)
)
$dashboard = Start-LocalService -Name 'dashboard' -Log (Join-Path $logDir 'dashboard.log') -Arguments @(
    (Q $launcher), 'dashboard', '--host', '127.0.0.1', '--port', "$DashboardPort",
    '--qris', (Q $qrisPath), '--ledger', (Q $ledgerPath), '--probes', (Q $ledgerPath),
    '--admin-token', $env:MERLIN_PROXY_ADMIN_TOKEN, '--env-file', (Q $envFile)
)

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
