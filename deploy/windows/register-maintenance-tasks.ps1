# Registers the two maintenance tasks for the gateway: a five-minute watchdog and a nightly backup.
# Both run as the current user, so no elevation is needed; both are idempotent and replace any earlier version.
$ErrorActionPreference = 'Stop'
$scripts = "$env:LOCALAPPDATA\merlin\scripts"
$me = "$env:USERDOMAIN\$env:USERNAME"

$watchdogAction = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f (Join-Path $scripts 'watchdog-gateway.ps1'))
$watchdogTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
$watchdogSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName 'MerlinGatewayWatchdog' -Action $watchdogAction -Trigger $watchdogTrigger `
    -Settings $watchdogSettings -User $me -Force | Out-Null

$backupAction = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f (Join-Path $scripts 'backup-gateway.ps1'))
$backupTrigger = New-ScheduledTaskTrigger -Daily -At '03:00'
$backupSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName 'MerlinGatewayBackup' -Action $backupAction -Trigger $backupTrigger `
    -Settings $backupSettings -User $me -Force | Out-Null

foreach ($name in 'MerlinGatewayWatchdog', 'MerlinGatewayBackup') {
    $t = Get-ScheduledTask -TaskName $name
    $trig = ($t.Triggers | ForEach-Object { $_.CimClass.CimClassName }) -join ','
    $rep = ($t.Triggers | ForEach-Object { $_.Repetition.Interval }) -join ','
    Write-Output ($name + ": state=" + $t.State + " trigger=" + $trig + " repetition=" + $rep)
}
