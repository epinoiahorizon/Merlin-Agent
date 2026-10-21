<p align="center">
  <img src="assets/banner.png" alt="Merlin Agent" width="100%">
</p>

# Merlin Agent ☤
<p align="center">
  <a href="https://merlin-agent.epinoiahorizon.com/">Merlin Agent</a> | <a href="https://merlin-agent.epinoiahorizon.com/">Merlin Desktop</a>
</p>
<p align="center">
  <a href="https://merlin-agent.epinoiahorizon.com/docs/"><img src="https://img.shields.io/badge/Docs-merlin--agent.epinoiahorizon.com-FFD700?style=for-the-badge" alt="Documentation"></a>
  <a href="https://discord.gg/merlin-agent"><img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://github.com/epinoiahorizon/Merlin-Agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://epinoiahorizon.com"><img src="https://img.shields.io/badge/Built%20by-Epinoia%20Horizon-blueviolet?style=for-the-badge" alt="Built by Epinoia Horizon"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/Lang-中文-red?style=for-the-badge" alt="中文"></a>
  <a href="README.ur-pk.md"><img src="https://img.shields.io/badge/Lang-اردو-green?style=for-the-badge" alt="اردو"></a>
  <a href="README.es.md"><img src="https://img.shields.io/badge/Lang-Español-orange?style=for-the-badge" alt="Español"></a>
</p>

> **Provenance, up front.** Merlin Agent is a rebranded distribution of [Hermes Agent](https://github.com/NousResearch/hermes-agent) (MIT, © 2025 Nous Research). The agent core, tools, gateway, skills engine, scheduler, desktop shell and TUI are upstream code — we did not write them and do not claim to. What we changed is listed in [NOTICE](NOTICE), licensing in [LICENSE](LICENSE). Nous Research does not endorse this fork. If you want the upstream project itself, go there: it is further ahead than we are, and we port its fixes rather than the other way round.
>
> Git history in this repository starts at the fork import (2026-09-30); upstream's history is not mirrored here.

**Merlin Agent is the self-improving AI agent made and supported by [Epinoia Horizon](https://epinoiahorizon.com)** — a packaged distribution built on the open-source Hermes Agent core (MIT, © 2025 Nous Research, credited above). It creates skills from experience, improves them during use, searches its own past conversations and keeps a deepening model of who you are across sessions. Merlin is the distribution around that core: an installer and an app window that need no terminal, [Atlas Portal](https://portal.epinoiahorizon.com) for people who would rather not collect five API keys, a Windows-focused support path that ends at us, and our own fixes on top.

Use any model you want — Atlas Portal, OpenRouter, OpenAI, your own endpoint, and [many others](https://merlin-agent.epinoiahorizon.com/docs/integrations/providers). Switch with `merlin model` — no code changes, no lock-in.

<table>
<tr><td><b>A real terminal interface</b></td><td>Full TUI with multiline editing, slash-command autocomplete, conversation history, interrupt-and-redirect, and streaming tool output.</td></tr>
<tr><td><b>Lives where you do</b></td><td>Telegram, Discord, Slack, WhatsApp, Signal, and CLI — all from a single gateway process. Voice memo transcription, cross-platform conversation continuity.</td></tr>
<tr><td><b>A closed learning loop</b></td><td>Agent-curated memory with periodic nudges. Autonomous skill creation after complex tasks. Skills self-improve during use. FTS5 session search with LLM summarization for cross-session recall. <a href="https://github.com/plastic-labs/honcho">Honcho</a> dialectic user modeling. Compatible with the <a href="https://agentskills.io">agentskills.io</a> open standard.</td></tr>
<tr><td><b>Scheduled automations</b></td><td>Built-in cron scheduler with delivery to any platform. Daily reports, nightly backups, weekly audits — all in natural language, running unattended.</td></tr>
<tr><td><b>Delegates and parallelizes</b></td><td>Spawn isolated subagents for parallel workstreams. Write Python scripts that call tools via RPC, collapsing multi-step pipelines into zero-context-cost turns.</td></tr>
<tr><td><b>Runs anywhere, not just your laptop</b></td><td>Seven terminal backends — local, Docker, SSH, Singularity, Modal, Daytona, and Vercel Sandbox. Daytona and Modal offer serverless persistence: the environment hibernates when idle and wakes on demand.</td></tr>
<tr><td><b>Research-ready</b></td><td>Batch trajectory generation, trajectory compression for training the next generation of tool-calling models.</td></tr>
</table>

---

## What we changed, and what we did not

We do not maintain a competing agent core. Merlin tracks upstream and ports its fixes; expect this repository to lag the upstream project, sometimes by weeks.

Changed in this distribution:

- **Brand and packaging** — name, icon, palette, docs site and domain, README copy, installer and store metadata.
- **Atlas Portal** — a hosted model and tool gateway wired into setup (`merlin setup --portal`), with its own transport and rate guard (`agent/atlas_wire.py`, `agent/atlas_rate_guard.py`). Entirely ours, independent of upstream.
- **Desktop runtime hardening** — backend discovery and exit recovery, host attach and spawn gating, pool limits and reclamation in the Electron app.
- **Policy seal** — memory and skills stay dormant unless you invoke them explicitly; the seal lives in `agent/prompt_builder.py`.
- **Our defaults, our support** — a curated default config, this issue tracker, and the Windows support path.

Not changed: the agent loop, tool implementations, skills engine, gateway, scheduler, cron, TUI, and the great majority of the desktop app. Those are upstream's, under the MIT licence, and they stay credited in [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

## What this repository is not

- Not a from-scratch agent, and it does not claim to be.
- Not endorsed by, affiliated with, or sponsored by Nous Research.
- Not ahead of upstream on features: if a capability exists in both projects, upstream had it first.
- Not a fork of anyone's brand assets — the name, wizard-hat icon and palette are ours, which is what keeps this clear of upstream trademarks.

---

## Quick Install

### Linux, macOS, WSL2

```bash
curl -fsSL https://merlin-agent.epinoiahorizon.com/install.sh | bash
```

### Windows (native, PowerShell)

> **Heads up:** Native Windows runs Merlin without WSL — CLI, gateway, TUI, and tools all work natively. If you'd rather use WSL2, the Linux/macOS one-liner above works there too. Found a bug? Please [file issues](https://github.com/epinoiahorizon/Merlin-Agent/issues).

Run this in PowerShell:

```powershell
iex (irm https://merlin-agent.epinoiahorizon.com/install.ps1)
```

The source installer delegates Python 3.14, Node.js, npm, ripgrep, FFmpeg,
and Python dependencies to PM. If Git is absent, it stages the verified Git
for Windows archive in Merlin' tool store. It does not replace your system Git.
See [installation methods](https://merlin-agent.epinoiahorizon.com/docs/getting-started/installation)
for the separate MSIX/App Installer package and its update ownership.

> **Android / Termux:** A signed APT repository is available for aarch64 devices, with a `stable` channel (tagged releases) and a prerelease `canary` channel. The package includes Python, Node.js, and the TUI. Use the [Termux guide](https://merlin-agent.epinoiahorizon.com/docs/getting-started/termux), not the desktop/server installer script.
>
> **Windows:** Native Windows is fully supported — the PowerShell one-liner above installs everything. If you'd rather use WSL2, the Linux command works there too. Native Windows install lives under `%LOCALAPPDATA%\merlin`; WSL2 installs under `~/.merlin` as on Linux.

After installation:

```bash
source ~/.bashrc    # reload shell (or: source ~/.zshrc)
merlin              # start chatting!
```

### Troubleshooting

#### Windows Defender or antivirus flags `uv.exe` as malware

If your antivirus (Bitdefender, Windows Defender, etc.) quarantines `uv.exe` from the Merlin `bin` folder (`%LOCALAPPDATA%\merlin\bin\uv.exe`), this is a **false positive**. The file is Astral's `uv` — the Rust Python package manager Merlin bundles to manage its Python environment. ML-based antivirus engines commonly flag unsigned Rust binaries that download and install packages.

**To verify your copy is authentic:**

```powershell
# Install GitHub CLI if needed
winget install --id GitHub.cli

# Login to GitHub
gh auth login

# Run verification
$uv = "$env:LOCALAPPDATA\merlin\bin\uv.exe"
$ver = (& $uv --version).Split(' ')[1]
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$zip = "$env:TEMP\uv.zip"
Invoke-WebRequest "https://github.com/astral-sh/uv/releases/download/$ver/uv-x86_64-pc-windows-msvc.zip" -OutFile $zip -UseBasicParsing
gh attestation verify $zip --repo astral-sh/uv
Expand-Archive $zip "$env:TEMP\uv_x" -Force
(Get-FileHash "$env:TEMP\uv_x\uv.exe").Hash -eq (Get-FileHash $uv).Hash
```

If attestation says "Verification succeeded" and the last line prints `True`, you're good.

**To whitelist Merlin:**
- **Windows Defender:** Run PowerShell as Admin → `Add-MpPreference -ExclusionPath "$env:LOCALAPPDATA\merlin\bin"`
- **Bitdefender:** Add an exception in the Bitdefender console (Protection > Antivirus > Settings > Manage Exceptions)
- Whitelist the **folder**, not the file hash — Merlin updates `uv` and the hash changes every version

For more context, see the upstream Astral reports: [astral-sh/uv#13553](https://github.com/astral-sh/uv/issues/13553), [astral-sh/uv#15011](https://github.com/astral-sh/uv/issues/15011), [astral-sh/uv#10079](https://github.com/astral-sh/uv/issues/10079).

---

## Getting Started

```bash
merlin              # Interactive CLI — start a conversation
merlin model        # Choose your LLM provider and model
merlin tools        # Configure which tools are enabled
merlin config set   # Set individual config values
merlin config get   # Print individual config values
merlin gateway      # Start the messaging gateway (Telegram, Discord, etc.)
merlin setup        # Run the full setup wizard (configures everything at once)
merlin claw migrate # Migrate from OpenClaw (if coming from OpenClaw)
merlin update       # Update to the latest version
merlin doctor       # Diagnose any issues
```

📖 **[Full documentation →](https://merlin-agent.epinoiahorizon.com/docs/)**

---

## Skip the API-key collection — Atlas Portal

Merlin works with whatever provider you want — that's not changing. But if you'd rather not collect five separate API keys for the model, web search, image generation, TTS, and a cloud browser, **[Atlas Portal](https://portal.epinoiahorizon.com)** covers all of them under one subscription:

- **300+ models** — pick any of them with `/model <name>`
- **Tool Gateway** — web search, image generation (FAL), text-to-speech (OpenAI), cloud browser (Browser Use), all routed through your sub. No extra accounts.

One command from a fresh install:

```bash
merlin setup --portal
```

That logs you in via OAuth, sets Atlas as your provider, and turns on the Tool Gateway. Check what's wired up any time with `merlin portal info`. Full details on the [Tool Gateway docs page](https://merlin-agent.epinoiahorizon.com/docs/user-guide/features/tool-gateway).

You can still bring your own keys per-tool whenever you want — the gateway is per-backend, not all-or-nothing.

---

## CLI vs Messaging Quick Reference

Merlin has two entry points: start the terminal UI with `merlin`, or run the gateway and talk to it from Telegram, Discord, Slack, WhatsApp, Signal, or Email. Once you're in a conversation, many slash commands are shared across both interfaces.

| Action                         | CLI                                           | Messaging platforms                                                              |
| ------------------------------ | --------------------------------------------- | -------------------------------------------------------------------------------- |
| Start chatting                 | `merlin`                                      | Run `merlin gateway setup` + `merlin gateway start`, then send the bot a message |
| Start fresh conversation       | `/new` or `/reset`                            | `/new` or `/reset`                                                               |
| Change model                   | `/model [provider:model]`                     | `/model [provider:model]`                                                        |
| Set a personality              | `/personality [name]`                         | `/personality [name]`                                                            |
| Retry or undo the last turn    | `/retry`, `/undo`                             | `/retry`, `/undo`                                                                |
| Compress context / check usage | `/compress`, `/usage`, `/insights [--days N]` | `/compress`, `/usage`, `/insights [days]`                                        |
| Browse skills                  | `/skills` or `/<skill-name>`                  | `/<skill-name>`                                                                  |
| Interrupt current work         | `Ctrl+C` or send a new message                | `/stop` or send a new message                                                    |
| Platform-specific status       | `/platforms`                                  | `/status`, `/sethome`                                                            |

For the full command lists, see the [CLI guide](https://merlin-agent.epinoiahorizon.com/docs/user-guide/cli) and the [Messaging Gateway guide](https://merlin-agent.epinoiahorizon.com/docs/user-guide/messaging).

---

## Documentation

All documentation lives at **[merlin-agent.epinoiahorizon.com/docs](https://merlin-agent.epinoiahorizon.com/docs/)**:

| Section                                                                                             | What's Covered                                             |
| --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| [Quickstart](https://merlin-agent.epinoiahorizon.com/docs/getting-started/quickstart)                 | Install → setup → first conversation in 2 minutes          |
| [CLI Usage](https://merlin-agent.epinoiahorizon.com/docs/user-guide/cli)                              | Commands, keybindings, personalities, sessions             |
| [Configuration](https://merlin-agent.epinoiahorizon.com/docs/user-guide/configuration)                | Config file, providers, models, all options                |
| [Messaging Gateway](https://merlin-agent.epinoiahorizon.com/docs/user-guide/messaging)                | Telegram, Discord, Slack, WhatsApp, Signal, Home Assistant |
| [Security](https://merlin-agent.epinoiahorizon.com/docs/user-guide/security)                          | Command approval, DM pairing, container isolation          |
| [Tools & Toolsets](https://merlin-agent.epinoiahorizon.com/docs/user-guide/features/tools)            | 40+ tools, toolset system, terminal backends               |
| [Skills System](https://merlin-agent.epinoiahorizon.com/docs/user-guide/features/skills)              | Procedural memory, Skills Hub, creating skills             |
| [Memory](https://merlin-agent.epinoiahorizon.com/docs/user-guide/features/memory)                     | Persistent memory, user profiles, best practices           |
| [MCP Integration](https://merlin-agent.epinoiahorizon.com/docs/user-guide/features/mcp)               | Connect any MCP server for extended capabilities           |
| [Cron Scheduling](https://merlin-agent.epinoiahorizon.com/docs/user-guide/features/cron)              | Scheduled tasks with platform delivery                     |
| [Context Files](https://merlin-agent.epinoiahorizon.com/docs/user-guide/features/context-files)       | Project context that shapes every conversation             |
| [Architecture](https://merlin-agent.epinoiahorizon.com/docs/developer-guide/architecture)             | Project structure, agent loop, key classes                 |
| [Contributing](https://merlin-agent.epinoiahorizon.com/docs/developer-guide/contributing)             | Development setup, PR process, code style                  |
| [CLI Reference](https://merlin-agent.epinoiahorizon.com/docs/reference/cli-commands)                  | All commands and flags                                     |
| [Environment Variables](https://merlin-agent.epinoiahorizon.com/docs/reference/environment-variables) | Complete env var reference                                 |

---

## Migrating from OpenClaw

If you're coming from OpenClaw, Merlin can automatically import your settings, memories, skills, and API keys.

**During first-time setup:** The setup wizard (`merlin setup`) automatically detects `~/.openclaw` and offers to migrate before configuration begins.

**Anytime after install:**

```bash
merlin claw migrate              # Interactive migration (full preset)
merlin claw migrate --dry-run    # Preview what would be migrated
merlin claw migrate --preset user-data   # Migrate without secrets
merlin claw migrate --overwrite  # Overwrite existing conflicts
```

What gets imported:

- **SOUL.md** — persona file
- **Memories** — MEMORY.md and USER.md entries
- **Skills** — user-created skills → `~/.merlin/skills/openclaw-imports/`
- **Command allowlist** — approval patterns
- **Messaging settings** — platform configs, allowed users, working directory
- **API keys** — allowlisted secrets (Telegram, OpenRouter, OpenAI, Anthropic, ElevenLabs)
- **TTS assets** — workspace audio files
- **Workspace instructions** — AGENTS.md (with `--workspace-target`)

See `merlin claw migrate --help` for all options, or use the `openclaw-migration` skill for an interactive agent-guided migration with dry-run previews.

---

## Contributing

We welcome contributions! See the [Contributing Guide](https://merlin-agent.epinoiahorizon.com/docs/developer-guide/contributing) for development setup, code style, and PR process.

Start with the [PM developer workflow](website/docs/reference/package-management.md#developer-workflow)
for activation, daily use, dependency changes, and leaving the environment.
[Development Setup](CONTRIBUTING.md#development-setup) covers the separate test environment and verification commands.

---

## Community

- 💬 [Discord](https://discord.gg/merlin-agent)
- 📚 [Skills Hub](https://agentskills.io)
- 🐛 [Issues](https://github.com/epinoiahorizon/Merlin-Agent/issues)
- 🔌 [computer-use-linux](https://github.com/avifenesh/computer-use-linux) — Linux desktop-control MCP server for Merlin and other MCP hosts, with AT-SPI accessibility trees, Wayland/X11 input, screenshots, and compositor window targeting.
- 🔌 [MerlinClaw](https://github.com/AaronWong1999/merlinclaw) — Community WeChat bridge: Run Merlin Agent and OpenClaw on the same WeChat account.

---

## License

MIT — see [LICENSE](LICENSE).

Merlin Agent is a modified fork of [hermes-agent](https://github.com/NousResearch/hermes-agent)
by Nous Research, used under the MIT License. The original copyright notice is
retained in [LICENSE](LICENSE) and the list of changes is in [NOTICE](NOTICE).
Nous Research does not endorse this fork.

Built by Epinoia Horizon.
