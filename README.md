<p align="center">
  <img src="assets/banner.png" alt="Merlin Agent" width="100%">
</p>

# Merlin Agent ☤
<p align="center">
  <a href="https://withmerlin.online/">Merlin Agent</a> | <a href="https://withmerlin.online/">Merlin Desktop</a>
</p>
<p align="center">
  <a href="https://docs.withmerlin.online/docs/"><img src="https://img.shields.io/badge/Docs-merlin--agent.epinoiahorizon.com-FFD700?style=for-the-badge" alt="Documentation"></a>
  <a href="https://discord.gg/merlin-agent"><img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://github.com/epinoiahorizon/Merlin-Agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://epinoiahorizon.com"><img src="https://img.shields.io/badge/Built%20by-Epinoia%20Horizon-blueviolet?style=for-the-badge" alt="Built by Epinoia Horizon"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/Lang-中文-red?style=for-the-badge" alt="中文"></a>
  <a href="README.ur-pk.md"><img src="https://img.shields.io/badge/Lang-اردو-green?style=for-the-badge" alt="اردو"></a>
  <a href="README.es.md"><img src="https://img.shields.io/badge/Lang-Español-orange?style=for-the-badge" alt="Español"></a>
</p>

**Merlin Agent is the self-improving AI agent made and supported by [Epinoia Horizon](https://epinoiahorizon.com)** — not a chat wrapper. It creates skills from experience, improves them during use, searches its own past conversations, and keeps a deepening model of who you are across sessions. One installer, one app window, no terminal required — with a Windows-native support path that ends at us.

Use any model you want — OpenRouter, OpenAI, your own endpoint, and [many others](https://docs.withmerlin.online/docs/integrations/providers). Switch with `merlin model` — no code changes, no lock-in.

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

## What makes Merlin Merlin

Everything distinctive about the product ships from Epinoia Horizon:

- **Policy seal** — an optional governance mode that keeps memory and skills dormant unless you invoke them explicitly (`agent/prompt_builder.py`).
- **`@merlin/ui`** — our own vendored design system behind the desktop app and TUI skins (arcane default).
- **Desktop runtime hardening** — backend discovery and exit recovery, host attach and spawn gating, pool limits and reclamation in the Electron app.
- **Windows-native, end to end** — a PowerShell one-liner installer, PM-managed toolchain, MSIX packaging, and a support path that ends at us.
- **Merlin PM** — declarative Python environment and dependency management with a 14-day release quarantine.

The full provenance record — origin of every component, what is and is not claimed — is kept in [`NOTICE`](NOTICE); licensing in [`LICENSE`](LICENSE). Merlin is maintained and released by Epinoia Horizon as an independent product, and its roadmap is ours (`INDEPENDENCE-ROADMAP.md`).

---

## Quick Install

### Linux, macOS, WSL2

```bash
curl -fsSL https://epinoiahorizon.com/install.sh | bash
```

### Windows (native, PowerShell)

> **Heads up:** Native Windows runs Merlin without WSL — CLI, gateway, TUI, and tools all work natively. If you'd rather use WSL2, the Linux/macOS one-liner above works there too. Found a bug? Please [file issues](https://github.com/epinoiahorizon/Merlin-Agent/issues).

Run this in PowerShell:

```powershell
iex (irm https://epinoiahorizon.com/install.ps1)
```

The source installer delegates Python 3.14, Node.js, npm, ripgrep, FFmpeg,
and Python dependencies to PM. If Git is absent, it stages the verified Git
for Windows archive in Merlin' tool store. It does not replace your system Git.
See [installation methods](https://docs.withmerlin.online/docs/getting-started/installation)
for the separate MSIX/App Installer package and its update ownership.

> **Android / Termux:** A signed APT repository is available for aarch64 devices, with a `stable` channel (tagged releases) and a prerelease `canary` channel. The package includes Python, Node.js, and the TUI. Use the [Termux guide](https://docs.withmerlin.online/docs/getting-started/termux), not the desktop/server installer script.
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

📖 **[Full documentation →](https://docs.withmerlin.online/docs/)**

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

For the full command lists, see the [CLI guide](https://docs.withmerlin.online/docs/user-guide/cli) and the [Messaging Gateway guide](https://docs.withmerlin.online/docs/user-guide/messaging).

---

## Documentation

All documentation lives at **[docs.withmerlin.online/docs](https://docs.withmerlin.online/docs/)**:

| Section                                                                                             | What's Covered                                             |
| --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| [Quickstart](https://docs.withmerlin.online/docs/getting-started/quickstart)                 | Install → setup → first conversation in 2 minutes          |
| [CLI Usage](https://docs.withmerlin.online/docs/user-guide/cli)                              | Commands, keybindings, personalities, sessions             |
| [Configuration](https://docs.withmerlin.online/docs/user-guide/configuration)                | Config file, providers, models, all options                |
| [Messaging Gateway](https://docs.withmerlin.online/docs/user-guide/messaging)                | Telegram, Discord, Slack, WhatsApp, Signal, Home Assistant |
| [Security](https://docs.withmerlin.online/docs/user-guide/security)                          | Command approval, DM pairing, container isolation          |
| [Tools & Toolsets](https://docs.withmerlin.online/docs/user-guide/features/tools)            | 40+ tools, toolset system, terminal backends               |
| [Skills System](https://docs.withmerlin.online/docs/user-guide/features/skills)              | Procedural memory, Skills Hub, creating skills             |
| [Memory](https://docs.withmerlin.online/docs/user-guide/features/memory)                     | Persistent memory, user profiles, best practices           |
| [MCP Integration](https://docs.withmerlin.online/docs/user-guide/features/mcp)               | Connect any MCP server for extended capabilities           |
| [Cron Scheduling](https://docs.withmerlin.online/docs/user-guide/features/cron)              | Scheduled tasks with platform delivery                     |
| [Context Files](https://docs.withmerlin.online/docs/user-guide/features/context-files)       | Project context that shapes every conversation             |
| [Architecture](https://docs.withmerlin.online/docs/developer-guide/architecture)             | Project structure, agent loop, key classes                 |
| [Contributing](https://docs.withmerlin.online/docs/developer-guide/contributing)             | Development setup, PR process, code style                  |
| [CLI Reference](https://docs.withmerlin.online/docs/reference/cli-commands)                  | All commands and flags                                     |
| [Environment Variables](https://docs.withmerlin.online/docs/reference/environment-variables) | Complete env var reference                                 |

---

## Migrating from OpenClaw

If you're coming from OpenClaw, Merlin can automatically import your settings, memories, skills, and API keys.

**During first-time setup:** The setup wizard (`merlin setup`) automatically detects `~/.openclaw` and offers to migrate before configuration begins.

**Anytime after install:**

```bash
merlin claw migrate                        # Interactive migration (full preset)
merlin claw migrate --dry-run              # Preview what would be migrated
merlin claw migrate --overwrite            # Replace existing files and skills instead of refusing
merlin claw migrate --migrate-secrets      # Also import bot tokens and provider API keys
merlin claw migrate --preset user-data     # Import user data only (never secrets)
```

Behavior worth knowing before you run it:

- **Secrets are always opt-in.** No preset imports `TELEGRAM_BOT_TOKEN`, `DISCORD_BOT_TOKEN`, `SLACK_BOT_TOKEN`/`SLACK_APP_TOKEN`, or provider API keys — pass `--migrate-secrets` to include them. Withheld tokens are reported, never silently dropped.
- **A stock `SOUL.md` is replaced silently** (an auto-seeded template carries no user intent). A persona you edited yourself is a conflict, so add `--overwrite` for that case.
- **`--overwrite` also settles skill-name conflicts.** Use `--skill-conflict rename` instead to keep both copies side by side.
- **`~/.agents/skills` is not imported by default.** That directory is your own cross-project skill library, not OpenClaw state; add `--include-personal-skills` if you want it copied into `~/.merlin/skills/openclaw-imports/`.

What gets imported:

- **SOUL.md** — persona file
- **Memories** — MEMORY.md and USER.md entries, merged into what you already have
- **Skills** — user-created skills → `~/.merlin/skills/openclaw-imports/`
- **Command allowlist** — approval patterns
- **Messaging settings** — platform configs, allowed users, working directory
- **API keys** — allowlisted secrets (Telegram, Discord, Slack, OpenRouter, OpenAI, Anthropic, ElevenLabs), only with `--migrate-secrets`
- **TTS assets** — workspace audio files
- **Workspace instructions** — AGENTS.md (with `--workspace-target`)

See `merlin claw migrate --help` for all options, or use the `openclaw-migration` skill for an interactive agent-guided migration with dry-run previews.

---

## Contributing

We welcome contributions! See the [Contributing Guide](https://docs.withmerlin.online/docs/developer-guide/contributing) for development setup, code style, and PR process.

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

## License & Provenance

MIT — see [LICENSE](LICENSE).

Merlin Agent is maintained and released by Epinoia Horizon as an independent
product. The agent core was originally derived from [hermes-agent](https://github.com/NousResearch/hermes-agent)
by Nous Research, used under the MIT License: the original copyright notice is
retained in [LICENSE](LICENSE), and the factual record of origin — which
components come from where, and what Epinoia Horizon changed — is kept in
[NOTICE](NOTICE). Repository git history begins at the 2026-09-30 import.
No endorsement by Nous Research is claimed or implied. Merlin's brand assets
— name, wizard-hat icon, rune palette — are entirely Epinoia Horizon's own.

Built by Epinoia Horizon.
