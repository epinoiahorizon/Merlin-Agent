import { existsSync, readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

import type { SkinBranding, SkinColors } from '@merlin/shared/skin'

/**
 * Local skin resolver for the standalone console demo.
 *
 * The real TUI receives its skin from the gateway over JSON-RPC; this demo
 * runs without a gateway, so it reads the same source of truth the Python
 * skin engine uses: `$MERLIN_HOME/config.yaml` (display.skin) → the skin
 * YAML in `$MERLIN_HOME/skins/<name>.yaml`. Built-in skins (`default`,
 * `charizard`, …) have no YAML file here, so they resolve to null and the
 * demo keeps its static Arcane palette.
 */

export interface LoadedSkin {
  name: string
  colors: SkinColors
  branding: SkinBranding
  toolPrefix?: string
}

// `  token: '#1a2b3c'` — quoted or bare hex values, full-line only (so the
// banner_logo markup block never matches).
const COLOR_LINE = /^\s+(\w+):\s*['"]?#([0-9a-fA-F]{6})['"]?\s*$/

const BRANDING_LINE = /^\s+(agent_name|prompt_symbol|welcome|goodbye|help_header):\s*['"]?(.*?)['"]?\s*$/

const TOOL_PREFIX_LINE = /^tool_prefix:\s*['"]?(.*?)['"]?\s*$/

// Mirrors merlin_constants._get_platform_default_merlin_home(): win32 uses
// %LOCALAPPDATA%\merlin, everything else uses ~/.merlin.
function defaultMerlinHome(): string {
  if (process.platform === 'win32') {
    const localAppData = process.env.LOCALAPPDATA?.trim()

    return join(localAppData || join(homedir(), 'AppData', 'Local'), 'merlin')
  }

  return join(homedir(), '.merlin')
}

export function loadActiveSkin(): LoadedSkin | null {
  const home = process.env.MERLIN_HOME ?? defaultMerlinHome()

  try {
    const configPath = join(home, 'config.yaml')

    if (!existsSync(configPath)) {
      return null
    }

    const config = readFileSync(configPath, 'utf8')
    const name = /^display:[\s\S]*?\n\s+skin:\s*([^\s#]+)/m.exec(config)?.[1]

    if (!name || name === 'default') {
      return null
    }

    const skinPath = join(home, 'skins', `${name}.yaml`)

    if (!existsSync(skinPath)) {
      return null
    }

    const raw = readFileSync(skinPath, 'utf8')
    const colors: SkinColors = {}
    const branding: SkinBranding = {}
    let toolPrefix: string | undefined

    for (const line of raw.split(/\r?\n/)) {
      const colorMatch = COLOR_LINE.exec(line)

      if (colorMatch) {
        colors[colorMatch[1]] = `#${colorMatch[2]}`

        continue
      }

      const brandMatch = BRANDING_LINE.exec(line)

      if (brandMatch) {
        branding[brandMatch[1]] = brandMatch[2]

        continue
      }

      const toolMatch = TOOL_PREFIX_LINE.exec(line)

      if (toolMatch) {
        toolPrefix = toolMatch[1]
      }
    }

    if (Object.keys(colors).length === 0) {
      return null
    }

    return { name, colors, branding, toolPrefix }
  } catch {
    return null
  }
}
