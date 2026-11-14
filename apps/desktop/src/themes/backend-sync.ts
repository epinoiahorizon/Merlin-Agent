/**
 * Live skin sync from the Merlin backend.
 *
 * The backend resolves the active skin (built-in or `$MERLIN_HOME/skins/*.yaml`)
 * and announces it on `gateway.ready` / `skin.changed`, and answers `config.get
 * skin` with the same payload. `ingestBackendSkin` folds that into the desktop:
 *
 *   1. Registers the converted theme in `$backendThemes` so it appears wherever a
 *      built-in does — Appearance, Cmd-K, `/skin` — with no per-surface wiring
 *      (`listAllThemes` merges this store).
 *   2. When asked to apply (an explicit change), requests the switch via
 *      `$pendingSkinApply`, which the ThemeProvider drains through `setTheme`.
 *
 * `gateway.ready` seeds the baseline WITHOUT applying, so a fresh connect never
 * stomps the user's persisted desktop theme; only a genuine name change (Merlin
 * authoring/activating a skin from a prompt, or `/skin` elsewhere) repaints.
 */

import type { MerlinSkin } from '@merlin/shared/skin'
import { atom } from 'nanostores'

import { readJson, writeJson } from '@/lib/storage'

import { BUILTIN_THEMES, DEFAULT_SKIN_NAME } from './presets'
import { skinToDesktopTheme } from './skin'
import { type DesktopTheme, isValidTheme } from './types'

// Cached so the boot-time paint (which runs before the gateway connects) can
// resolve a persisted skin pick synchroatlasly, like a built-in or a user
// install. Without it the stored name failed `resolveTheme` on every launch
// and the app silently painted the default until the next `skin.changed`.
const BACKEND_THEMES_KEY = 'merlin-desktop-backend-themes-v1'

// Electron reads the active local `display.skin` before it creates the
// renderer. Seed it alongside the existing cache so an unreachable primary
// gateway cannot leave a first-time custom skin unknown to the theme registry.
const localSkinPayload = typeof window === 'undefined' ? null : (window.merlinDesktop?.localSkin ?? null)
const localSkin = localSkinPayload?.skin ?? null
export const localDisplaySkinName = (localSkin?.name ?? '').trim() || null
export const localDisplaySkinProfile = localDisplaySkinName
  ? (localSkinPayload?.profile ?? '').trim() || 'default'
  : null

const readCached = (): Record<string, DesktopTheme> =>
  Object.fromEntries(
    Object.entries(readJson<Record<string, unknown>>(BACKEND_THEMES_KEY) ?? {}).filter(
      (entry): entry is [string, DesktopTheme] => !BUILTIN_THEMES[entry[0]] && isValidTheme(entry[1])
    )
  )

/** Skins pushed by the backend, keyed by name. Merged by `listAllThemes`. */
export const $backendThemes = atom<Record<string, DesktopTheme>>(typeof window === 'undefined' ? {} : readCached())

$backendThemes.listen(themes => writeJson(BACKEND_THEMES_KEY, themes))

/** Custom CSS carried by a user skin whose name is `default` or a desktop
 *  built-in. The palette policy keeps built-in palettes (a user `mono.yaml`
 *  must not shadow the desktop's hand-tuned mono), but the user's CSS is still
 *  the skin file's truth — keyed by the name the desktop resolves the skin
 *  under (`default` → `atlas`). Merged into the active theme in context.tsx. */
export const $backendCustomCSS = atom<Record<string, string>>({})

/** One-shot skin name the ThemeProvider should switch to (it clears this). */
export const $pendingSkinApply = atom<string | null>(null)

// Last skin name synced from the backend + whether it was ever APPLIED (vs
// merely seeded at connect). Once applied, only a name change applies again —
// no re-apply on repeat events, no snap-back after a manual desktop switch.
// A `skin.changed` matching a seed-only baseline still applies: the seed
// records without painting, so if the activation event was missed (backend
// restart / disconnected), an explicit re-affirm must repaint, not no-op.
let lastSynced: { applied: boolean; name: string } | null = null

/** Test-only: reset the module's apply guard + registry between cases. */
export function __resetBackendSkinSync(): void {
  lastSynced = null
  $backendThemes.set({})
  $pendingSkinApply.set(null)
  $backendCustomCSS.set({})
}

/**
 * Fold a resolved skin into the desktop. `apply: false` (connect-time seed) only
 * records the baseline; `apply: true` (runtime change / poll) repaints on a name
 * change. Built-in names keep the desktop's own palette but can still be applied.
 */
export function ingestBackendSkin(skin: MerlinSkin | undefined | null, { apply }: { apply: boolean }): void {
  const name = (skin && typeof skin === 'object' ? (skin.name ?? '') : '').trim()

  if (!name) {
    return
  }

  // `default` is "no opinion" on the PALETTE — the desktop keeps its own default
  // (atlas), so we never register a converted theme under `default`. It is still a
  // valid apply TARGET though: a runtime switch back to `default` must repaint the
  // desktop to its own default (setTheme normalizes `default` → atlas). So we only
  // skip the registry step here and let it flow through the apply logic below.
  // Built-in names (mono/slate/…) already have a hand-tuned desktop palette — we
  // never shadow it, but the name is still a valid apply target.
  if (name !== 'default' && !BUILTIN_THEMES[name]) {
    const theme = skinToDesktopTheme(skin as MerlinSkin)

    if (!theme) {
      return
    }

    const current = $backendThemes.get()

    if (JSON.stringify(current[name]) !== JSON.stringify(theme)) {
      $backendThemes.set({ ...current, [name]: theme })
    }
  } else {
    // Built-in/default-named user skins never shadow the desktop palette, but
    // their customCSS still belongs to the user's skin file (user skins take
    // precedence over built-ins with the same name). Carry it separately so
    // applyTheme can inject it on top of the built-in palette; dropping the
    // field from the YAML clears the entry so stale rules don't linger.
    const css = skin?.customCSS?.trim() ?? ''
    const cssKey = name === 'default' ? DEFAULT_SKIN_NAME : name
    const current = $backendCustomCSS.get()

    if (css) {
      if (current[cssKey] !== css) {
        $backendCustomCSS.set({ ...current, [cssKey]: css })
      }
    } else if (current[cssKey]) {
      const next = { ...current }
      delete next[cssKey]
      $backendCustomCSS.set(next)
    }
  }

  if (!apply) {
    // Connect-time seed: record without painting. A reconnect re-seed keeps an
    // earlier real apply's flag so repeat events can't override a manual switch.
    if (lastSynced?.name !== name || !lastSynced.applied) {
      lastSynced = { applied: false, name }
    }

    return
  }

  if (name !== lastSynced?.name || !lastSynced.applied) {
    lastSynced = { applied: true, name }
    $pendingSkinApply.set(name)
  }
}

// This is a boot fallback, not a remote activation. ThemeProvider uses the
// name only when the desktop has no saved appearance of its own, while this
// registers the custom palette early enough for that first paint to resolve.
// Boot fallback: the Electron main process reads the active local `display.skin`
// before the renderer exists, giving the registry an early copy. The FULL catalog
// is seeded right after connect (`requestBackendSkinCatalog` below).
if (localSkin) {
  ingestBackendSkin(localSkin, { apply: false })
}

/**
 * Seed every installed skin from the gateway's `config.get skins` catalog.
 *
 * The event stream only ever carries the ACTIVE skin (`gateway.ready` /
 * `skin.changed`), so a user-installed skin stayed invisible in the theme
 * picker until each had been active while connected. Calling this after
 * `gateway.ready` registers the whole catalog at once; `$backendThemes`
 * persists to localStorage, so the cost is one request per connect and the
 * picker is complete on every later boot. Built-in names keep the desktop's
 * hand-tuned palettes (see ingestBackendSkin), their payloads are simply
 * ignored here — no shadowing.
 */
export async function requestBackendSkinCatalog(fetcher: {
  requestGateway: (method: string, params?: Record<string, unknown>, timeoutMs?: number) => Promise<{
    skins?: Array<Record<string, unknown>>
  }>
}): Promise<number> {
  try {
    const result = await fetcher.requestGateway('config.get', { key: 'skins' }, 10000)
    const skins = Array.isArray(result?.skins) ? result.skins : []
    let seeded = 0
    for (const skin of skins) {
      const payload = skin as MerlinSkin
      if (!payload || typeof payload !== 'object' || !String(payload.name ?? '').trim()) {
        continue
      }
      // apply:false — the user's persisted desktop theme must not be stomped
      // by whatever the backend currently has active; this registers only.
      ingestBackendSkin(payload, { apply: false })
      seeded += 1
    }
    if (seeded > 0) {
      // eslint-disable-next-line no-console -- one-line diagnostic, not a logger dep
      console.info(`[themes] seeded ${seeded} skins from the backend catalog`)
    }
    return seeded
  } catch {
    // A pre-1.0 backend without `config.get skins` (or a dropped socket):
    // the active-skin seed from gateway.ready is already in place, so this is
    // a graceful degradation, not an error surface.
    return 0
  }
}
