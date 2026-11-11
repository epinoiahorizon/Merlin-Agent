# Rebuilds the gateway task instead of patching it. Set-ScheduledTask on the existing definition rejected a
# one-minute restart interval because the stored XML carries its own repetition blocks; registering from scratch
# with fresh settings is both simpler and verifiable.
#
# Run as Administrator. Everything is re-derived from the existing task, so the command line it starts is unchanged.
$ErrorActionPreference = 'Stop'
$taskName = if ($env:PROBE_TASK) { $env:PROBE_TASK } else { 'MerlinGateway' }
$me = "$env:USERDOMAIN\$env:USERNAME"

if (-not (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)) {
    throw "Task $taskName not found. Nothing to rebuild."
}

$old = Get-ScheduledTask -TaskName $taskName
Write-Output ("action : {0} {1}" -f $old.Actions[0].Execute, $old.Actions[0].Arguments)
Write-Output ("principal: {0} / {1}" -f $old.Principal.UserId, $old.Principal.LogonType)

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

$triggers = @(New-ScheduledTaskTrigger -AtLogOn -User $me)

Register-ScheduledTask -TaskName $taskName `
    -Action $old.Actions -Trigger $triggers -Principal $old.Principal -Settings $settings -Force | Out-Null

$new = Get-ScheduledTask -TaskName $taskName
Write-Output ("registered: triggers={0} restart={1} interval={2} startwhenavailable={3}" -f `
    (($new.Triggers | ForEach-Object { $_.CimClass.CimClassName }) -join ','), `
    $new.Settings.RestartCount, $new.Settings.RestartInterval, $new.Settings.StartWhenAvailable)

Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 6
$state = (Get-ScheduledTask -TaskName $taskName).State
Write-Output "state after start: $state"
