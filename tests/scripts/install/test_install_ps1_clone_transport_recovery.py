"""A clone that only a proxy or IPv4 pin can reach is retried with it, and kept.

Live failure class (2026-10-20, Malaysia user behind a proxied/blocked network):
prerequisites download fine through .NET -- which follows the Windows proxy --
and then every `git clone` dies with

    fatal: unable to access 'https://github.com/epinoiahorizon/Merlin-Agent.git/':
        Failed to connect to github.com port 443 after 21xxx ms

because git's libcurl reads neither the WinINET proxy nor an IPv4 fallback.
The installer used to repeat that identical command three times and then a
fourth (the deferred checkout), so the user got a dead end with no cause.

`Stage-Repository` now probes the repo host after two identical failures and
retries with the proxy the PC already uses and/or an IPv4 pin, then writes the
setting that worked into the checkout so `merlin update` inherits it. This
drives that ladder with the network boundary stubbed (a `git` function is
defined, so PowerShell resolves it before PATH): the first two clones fail the
way the reported network fails, the proxy candidate answers on a real listening
socket, and the third clone must carry `-c http.proxy=`.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
INSTALL_PS1 = ROOT / "scripts" / "install.ps1"
POWERSHELL = next(
    (candidate for candidate in ("pwsh", "powershell") if shutil.which(candidate)),
    None,
)

HARNESS = r"""
param([string]$RepoRoot, [string]$WorkDir)
$ErrorActionPreference = 'Stop'
. (Join-Path $RepoRoot 'scripts\install.ps1')

# --- stub git: the first $cloneFailures clones die the way a blocked network
# dies (no connect at all), then a clone succeeds like a remedied one does. ---
$script:cloneFailures = 2
$script:clones = New-Object System.Collections.ArrayList
$script:configWrites = New-Object System.Collections.ArrayList

function global:git {
    $argv = @($args)
    $rest = @()
    $configs = @()
    $index = 0
    while ($index -lt $argv.Count) {
        if ($argv[$index] -eq '-c' -and ($index + 1) -lt $argv.Count) {
            $configs += [string]$argv[$index + 1]
            $index += 2
            continue
        }
        $rest += [string]$argv[$index]
        $index++
    }
    $location = $null
    if ($rest.Count -ge 2 -and $rest[0] -eq '-C') {
        $location = $rest[1]
        $rest = @($rest | Select-Object -Skip 2)
    }
    if (-not $rest.Count) { $global:LASTEXITCODE = 0; return }
    switch ($rest[0]) {
        'config' {
            if ($rest -contains '--get') { $global:LASTEXITCODE = 1; return }
            $key = if ($rest.Count -ge 2) { $rest[1] } else { '' }
            $value = if ($rest.Count -ge 3) { $rest[2] } else { '' }
            [void]$script:configWrites.Add(@{ key = $key; value = $value })
            $global:LASTEXITCODE = 0
            return
        }
        'clone' {
            [void]$script:clones.Add(@{ args = $rest; configs = $configs })
            if ($script:clones.Count -le $script:cloneFailures) {
                [Console]::Error.WriteLine("Cloning into '$($rest[-1])'...")
                [Console]::Error.WriteLine("fatal: unable to access 'https://github.com/epinoiahorizon/Merlin-Agent.git/': Failed to connect to github.com port 443 after 21067 ms: Could not connect to server")
                $global:LASTEXITCODE = 128
                return
            }
            $target = $rest[-1]
            New-Item -ItemType Directory -Force -Path $target | Out-Null
            New-Item -ItemType Directory -Force -Path (Join-Path $target '.git') | Out-Null
            Set-Content -Path (Join-Path $target '.git\config') -Value "[core]`n`trepositoryformatversion = 0`n"
            $global:LASTEXITCODE = 0
            return
        }
        default { $global:LASTEXITCODE = 0; return }
    }
}

function Ensure-Git { return $true }

$Branch = 'main'
$MerlinHome = Join-Path $WorkDir 'home'
$InstallDir = Join-Path $WorkDir 'install'
$RepoUrl = 'https://github.com/epinoiahorizon/Merlin-Agent.git'

try {
    Stage-Repository
} catch {
    Write-Output ("HARNESS ERROR: " + $_.Exception.Message)
    exit 2
}

$result = @{
    clones = @($script:clones | ForEach-Object { , @{ args = $_.args; configs = $_.configs } })
    config_writes = @($script:configWrites)
    transport_config = @($script:CloneTransportConfig)
    installed = (Test-Path (Join-Path $InstallDir '.git\config'))
}
$result | ConvertTo-Json -Depth 6 -Compress
"""


@pytest.mark.skipif(POWERSHELL is None, reason="needs PowerShell")
def test_proxy_retry_is_applied_and_kept(tmp_path):
    # A real listening socket stands in for the local proxy client the probe
    # has to refuse to ignore.
    sock = __import__("socket").socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(8)
    proxy_port = sock.getsockname()[1]
    try:
        harness = tmp_path / "harness.ps1"
        harness.write_text(HARNESS, encoding="utf-8")
        env = dict(
            __import__("os").environ,
            HTTPS_PROXY=f"http://127.0.0.1:{proxy_port}",
            MERLIN_INSTALL_VERBOSE="1",
        )
        env.pop("NO_PROXY", None)
        result = subprocess.run(
            [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness),
             "-RepoRoot", str(ROOT), "-WorkDir", str(tmp_path)],
            env=env, capture_output=True, text=True, timeout=180,
        )
    finally:
        sock.close()

    output = result.stdout + result.stderr
    assert "HARNESS ERROR" not in output, output
    line = next((text for text in reversed(result.stdout.splitlines()) if text.strip().startswith("{")), None)
    assert line, f"no JSON from the harness:\n{output}"
    report = json.loads(line)

    clones = report["clones"]
    # Two identical attempts, then the diagnosed variant -- never a third
    # blind repeat.
    assert len(clones) == 3, clones
    assert clones[0]["configs"] == [] and clones[1]["configs"] == []
    assert f"http.proxy=http://127.0.0.1:{proxy_port}" in clones[2]["configs"], clones[2]
    assert f"https.proxy=http://127.0.0.1:{proxy_port}" in clones[2]["configs"], clones[2]
    assert "--filter=tree:0" in " ".join(clones[2]["args"])

    # The setting that reached the remote is written into the checkout, so the
    # next `merlin update` fetch does not fail the same way.
    written = {(entry["key"], entry["value"]) for entry in report["config_writes"]}
    assert ("http.proxy", f"http://127.0.0.1:{proxy_port}") in written, written
    assert ("https.proxy", f"http://127.0.0.1:{proxy_port}") in written, written
    assert report["installed"] is True
    assert f"http.proxy=http://127.0.0.1:{proxy_port}" in report["transport_config"]

    # The user sees what the probe found, not just a repeated timeout.
    assert "using the proxy this PC already uses" in output, output


@pytest.mark.skipif(POWERSHELL is None, reason="needs PowerShell")
def test_healthy_network_never_probes(tmp_path):
    """A clone that works first time must not pay for a probe or a variant."""
    sock = __import__("socket").socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(8)
    proxy_port = sock.getsockname()[1]
    try:
        harness = tmp_path / "harness.ps1"
        # Same harness, but nothing fails.
        harness.write_text(HARNESS.replace("$script:cloneFailures = 2", "$script:cloneFailures = 0"), encoding="utf-8")
        env = dict(
            __import__("os").environ,
            HTTPS_PROXY=f"http://127.0.0.1:{proxy_port}",
            MERLIN_INSTALL_VERBOSE="1",
        )
        result = subprocess.run(
            [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness),
             "-RepoRoot", str(ROOT), "-WorkDir", str(tmp_path)],
            env=env, capture_output=True, text=True, timeout=180,
        )
    finally:
        sock.close()

    line = next((text for text in reversed(result.stdout.splitlines()) if text.strip().startswith("{")), None)
    assert line, result.stdout + result.stderr
    report = json.loads(line)
    assert len(report["clones"]) == 1, report["clones"]
    assert report["clones"][0]["configs"] == []
    assert report["config_writes"] == []
    assert "using the proxy this PC already uses" not in (result.stdout + result.stderr)
