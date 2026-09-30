# Merlin CLI Reference

Live sources when anything looks stale: `merlin --help`, `merlin <command> --help`,
https://merlin-agent.epinoiahorizon.com/docs/reference/cli-commands

### Global Flags

```
merlin [flags] [command]        (no subcommand = interactive chat)

  --version, -V             Show version
  -z, --oneshot PROMPT      One-shot: print ONLY the final response (for scripts/pipes)
  -m MODEL  --provider P    Model/provider override for this invocation
  -t, --toolsets LIST       Comma-separated toolsets for this invocation
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --tui / --cli             Force the Ink TUI / classic REPL
  --ignore-rules            Skip AGENTS.md/SOUL.md/memory/skill injection
  --safe-mode               Disable ALL customizations (troubleshooting)
  --pass-session-id         Include session ID in system prompt
```

### Chat

```
merlin chat [flags]
  -q, --query TEXT          Single query, non-interactive
  --image PATH              Attach a local image to a single query
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --max-turns N             Cap tool-calling iterations
  --source TAG              Session source tag (default: cli)
```
(plus the global flags above)

### Configuration

```
merlin setup [section]      Wizard (model|tts|terminal|gateway|tools|agent)
merlin model                Interactive model/provider picker
merlin fallback [add|remove|list]  Fallback provider chain
merlin config [show|edit|get|set|unset|path|env-path|check|migrate]
merlin login / logout       OAuth sign-in / clear stored auth
merlin doctor [--fix]       Check dependencies and config
merlin status [--all]       Component status
```

### Tools & Skills

```
merlin tools [list|enable NAME|disable NAME]   Per-platform toolsets (curses UI with no args)

merlin skills list|browse|search QUERY|inspect ID
merlin skills install ID    Hub identifier OR a direct https://…/SKILL.md URL
merlin skills config        Enable/disable skills per platform
merlin skills check|update|uninstall|publish PATH
merlin skills tap add REPO  Add a GitHub repo as a skill source
merlin bundles              Skill bundles (one /<name> alias loads several skills)
```

### MCP Servers

```
merlin mcp add NAME (--url or --command) | remove | list | test NAME
merlin mcp catalog | install NAME     Curated catalog install
merlin mcp configure NAME             Toggle tool selection
merlin mcp serve                      Run Merlin as an MCP server
```
Details (transport, tool discovery, catalog): `references/native-mcp.md`.

### Gateway (Messaging Platforms)

```
merlin gateway run|install|start|stop|restart|status|setup
```

20+ platforms: Telegram, Discord, Slack, WhatsApp (Baileys + Business Cloud API), iMessage (Photon — `merlin photon setup`), Signal, Email, SMS, Matrix, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin, API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`.
Docs: https://merlin-agent.epinoiahorizon.com/docs/user-guide/messaging/

### Sessions

```
merlin sessions list|browse|rename ID TITLE|delete ID|export OUT|prune|stats
```

### Cron / Webhooks

```
merlin cron list|create SCHED|edit ID|pause|resume|run ID|remove|status
    Schedules: '30m', 'every 2h', '0 9 * * *', ISO timestamp
merlin webhook subscribe NAME|list|remove NAME|test NAME
```
Webhook payloads/routes: `references/webhooks.md`.

### Profiles

```
merlin profile list|create NAME (--clone|--clone-all|--clone-from)|use|show|delete
merlin profile rename A B | alias NAME | export NAME | import FILE
merlin profile migrate-identity A B   Retry a completed rename's session/routing identity migration
```

### Credentials & Pools

```
merlin auth                 Interactive credential manager
merlin auth add [PROVIDER]  Add OAuth or API-key credential (atlas, openai-codex, qwen-oauth, …)
merlin auth list|remove P IDX|reset PROVIDER|status
```
Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
merlin desktop / gui        Native desktop app
merlin dashboard            Web admin panel + embedded chat (--stop / --status)
merlin proxy                OpenAI-compatible local proxy backed by an OAuth provider
merlin portal               Quick setup / sign in via Atlas Portal
merlin kanban <verb>        Multi-agent work-queue board
merlin project              Named multi-folder workspaces
merlin skin list|use|set    Switch/tweak skins (see references/themes.md)
merlin pets <verb>          Pet mascots (see references/petdex.md)
merlin memory setup|status|off|reset   Memory provider
merlin secrets bitwarden|onepassword   External secret stores
merlin moa                  Mixture-of-Agents slots
merlin hooks / security / backup / import / checkpoints / console
merlin logs [-f] [errors]   View agent/error logs
merlin send                 One-off message through a gateway platform
merlin pairing / plugins / insights / journey / computer-use
merlin acp                  ACP server (IDE integration)
merlin completion bash|zsh|fish
merlin update / uninstall / claw migrate
```

Plugin- and provider-supplied subcommands (e.g. `merlin photon setup`) only appear once their plugin is installed/active.

### Where to Find Things

| Looking for... | Location |
|---|---|
| Config options | `merlin config edit` · [Configuration docs](https://merlin-agent.epinoiahorizon.com/docs/user-guide/configuration) |
| Tools / toolsets | `merlin tools list` · [Tools reference](https://merlin-agent.epinoiahorizon.com/docs/reference/tools-reference) |
| Skills catalog | `merlin skills browse` · [Skills catalog](https://merlin-agent.epinoiahorizon.com/docs/reference/skills-catalog) |
| Provider setup | `merlin model` · [Providers guide](https://merlin-agent.epinoiahorizon.com/docs/integrations/providers) |
| Env variables | `merlin config env-path` · [Env vars reference](https://merlin-agent.epinoiahorizon.com/docs/reference/environment-variables) |
| Gateway logs | `~/.merlin/logs/gateway.log` (or `merlin logs`) |
| Sessions | `merlin sessions browse` (reads state.db) |
