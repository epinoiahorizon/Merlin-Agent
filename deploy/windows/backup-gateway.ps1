# backup-gateway.ps1 — a real copy of the ledger, not a file copy of an open database.
#
# Runs daily at 03:00 from the MerlinGatewayBackup task. The ledger is SQLite; copying the file while the gateway
# is writing can capture a torn page, so the copy is made with sqlite3's own backup API and then verified with
# PRAGMA integrity_check. Fourteen snapshots are kept, rotated oldest-first.
#
# The backup folder holds credentials (gateway.env), so it is locked to the current user after every run.
param(
    [string]$DataDir = "$env:LOCALAPPDATA\merlin\gateway",
    [int]$Keep = 14
)

$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$root = Join-Path $DataDir 'backups'
$dest = Join-Path $root $stamp
New-Item -ItemType Directory -Force -Path $dest | Out-Null

$logPath = Join-Path $DataDir 'logs\backup.log'
function Write-Log([string]$m) {
    Add-Content -Path $logPath -Value ("{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m)
}

$py = "$env:LOCALAPPDATA\merlin\merlin-agent\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = 'python' }

$ledger = Join-Path $DataDir 'ledger.db'
if (Test-Path $ledger) {
    $copy = Join-Path $dest 'ledger.db'
    & $py -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()" $ledger $copy
    if ($LASTEXITCODE -ne 0) { throw "sqlite backup failed for $ledger" }
    $checker = Join-Path $env:TEMP 'merlin-ledger-check.py'
    @'
import sqlite3, sys
db = sqlite3.connect(sys.argv[1])
print(db.execute("pragma integrity_check").fetchone()[0])
row = db.execute("select name from sqlite_master where type='table' and name='usage_events'").fetchone()
print(db.execute("select count(*) from usage_events").fetchone()[0] if row else 0)
'@ | Set-Content -Path $checker -Encoding UTF8
    $check = & $py $checker $copy
    Write-Log ("ledger  {0}  integrity={1}  rows={2}" -f $copy, $check[0], $check[1])
    if ($check[0] -ne 'ok') { throw "integrity_check on the copy said: $($check[0])" }
} else {
    Write-Log "ledger  no ledger.db at $ledger (skipped)"
}

foreach ($name in @('proxy_upstreams.json', 'cloudflared-config.yml', 'gateway.env')) {
    $source = Join-Path $DataDir $name
    if (Test-Path $source) {
        Copy-Item -Path $source -Destination $dest -Force
        Write-Log ("copied  {0}" -f $name)
    }
}

# Only this account may read the snapshots: gateway.env carries keys.
& icacls $dest /inheritance:r /grant:r "$($env:USERNAME):(OI)(CI)F" | Out-Null

$snapshots = @(Get-ChildItem -Path $root -Directory | Sort-Object Name)
while ($snapshots.Count -gt $Keep) {
    Remove-Item -Path $snapshots[0].FullName -Recurse -Force
    Write-Log ("rotated out {0}" -f $snapshots[0].Name)
    $snapshots = @(Get-ChildItem -Path $root -Directory | Sort-Object Name)
}

Write-Log ("done  {0} snapshot(s) kept, newest {1}" -f $snapshots.Count, (Split-Path -Leaf $dest))
