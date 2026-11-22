# Self-hosted runners

GitHub stopped starting workflows on this account while billing was in arrears ("The job was not started
because recent account payments have failed…"), which left 30 runs queued and every deploy frozen. These
runners exist so CI keeps working regardless of GitHub's billing state, and so a red board means broken code
rather than an unreachable machine.

## Where they run

| Runner | Host | Labels | Path | Kept alive by |
|---|---|---|---|---|
| `wsl-ma` | WSL2 Ubuntu on the developer PC | `self-hosted, Linux, X64` | `~/actions-runner-ma` | `systemctl --user gh-runner-ma` |
| `wsl-ma2` | same | `self-hosted, Linux, X64` | `~/actions-runner-ma2` | `systemctl --user gh-runner-ma2` |
| `win-ma` | the Windows side of the same PC | `self-hosted, Windows, X64` | `%USERPROFILE%\actions-runner-win` | `run.cmd` (console) |

`wsl-mb` belongs to another repository and is listed here only so it is not mistaken for a duplicate.

Two Linux runners give the queue parallelism; one runner serialises everything behind the slowest job.

## Why the PC

Self-hosted minutes are not billed, and the machine already has the toolchains (node 26, npm, git, ffmpeg).
The trade-off is honest: **when the PC sleeps, its runners go offline and queued jobs wait.** The VPS that
serves `api.withmerlin.online` has 2 vCPU and 8 GB shared with game servers, so heavy builds do not belong
there. Once GitHub billing is restored, the routine jobs should move back to GitHub-hosted runners — they are
free for a public repository — and these can be removed.

## Registration (once per machine)

```bash
# Linux
mkdir -p ~/actions-runner-ma && cd ~/actions-runner-ma
curl -sL -o runner.tar.gz https://github.com/actions/runner/releases/download/v<version>/actions-runner-linux-x64-<version>.tar.gz
tar xzf runner.tar.gz
TOKEN=$(gh api -X POST repos/epinoiahorizon/Merlin-Agent/actions/runners/registration-token --jq .token)
./config.sh --url https://github.com/epinoiahorizon/Merlin-Agent --token "$TOKEN" \
  --name wsl-ma --labels self-hosted,Linux,X64 --work _work --unattended --replace
```

```powershell
# Windows
Expand-Archive actions-runner-win-x64-<version>.zip -DestinationPath $env:USERPROFILE\actions-runner-win
$token = gh api -X POST repos/epinoiahorizon/Merlin-Agent/actions/runners/registration-token --jq .token
.\config.cmd --url https://github.com/epinoiahorizon/Merlin-Agent --token $token `
  --name win-ma --labels self-hosted,Windows,X64 --work _work --unattended --replace
```

## Keeping them alive

Linux runners are `systemd --user` units, so they survive a WSL restart:

```ini
[Service]
WorkingDirectory=/home/<user>/actions-runner-ma
Environment=PATH=/home/<user>/.merlin/tools/node-26.12.1-linux-x64/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/home/<user>/actions-runner-ma/run.sh
Restart=always
RestartSec=10
KillMode=process
```

`svc.sh install` needs sudo; a user unit does not.

## Removing one

```bash
# stop, unregister, delete
systemctl --user disable --now gh-runner-ma
TOKEN=$(gh api -X POST repos/epinoiahorizon/Merlin-Agent/actions/runners/remove-token --jq .token)
~/actions-runner-ma/config.sh remove --token "$TOKEN"
rm -rf ~/actions-runner-ma
```

Delete the stale entries in Settings → Actions → Runners as well: a registered runner that never comes online
does not just sit idle, it holds queued jobs for as long as it exists.

## Known gaps on this host

| Workflow | State | Reason |
|---|---|---|
| `ci-review-comment.yml` | disabled | re-runs CI for every comment, producing duplicates for one SHA |
| `codeql.yml` | disabled | CodeQL toolchain is not installed on these runners |
| `docker.yml` | disabled | no Docker daemon inside WSL |
| `desktop-bundled-release.yml` | manual | needs Windows + macOS runners, code-signing and Store credentials |

Re-enable with:

```bash
gh api -X PUT repos/epinoiahorizon/Merlin-Agent/actions/workflows/<id>/enable
```
