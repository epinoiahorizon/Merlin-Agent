// data-paths.mjs — the pure path-resolution core, shared by the desktop app
// (via data-paths.ts, a typed re-export) and the CI smoke driver (which runs
// under Node's type-stripping and therefore cannot import the app's
// extensionless TypeScript directly). No Electron imports here; only node:path.
//
// data-paths.ts re-exports these names and adds the TypeScript-facing
// `MerlinHomeOptions` interface. Keep the two in lockstep: every behavior in
// this file is exercised by data-paths.test.ts through the re-export.

import path from 'node:path'

/** A MERLIN_HOME rooted inside a `profiles/` directory names the profile's
 * parent (the home), not the profile directory itself. */
function normalizeMerlinHomeRoot(merlinHome, pathModule) {
  if (!merlinHome) {
    return merlinHome
  }
  const resolved = pathModule.resolve(String(merlinHome))
  const parent = pathModule.dirname(resolved)
  if (pathModule.basename(parent).toLowerCase() === 'profiles') {
    return pathModule.dirname(parent)
  }
  return resolved
}

export function platformDefaultMerlinHome(home, env = process.env, platform = process.platform) {
  const suffix = env.MERLIN_DATA_DIR_SUFFIX || ''
  if (platform === 'win32') {
    const base = (env.LOCALAPPDATA || '').trim() || path.win32.join(home, 'AppData', 'Local')
    return path.win32.join(base, 'merlin') + suffix
  }
  return path.posix.join(home, '.merlin') + suffix
}

export function resolveDesktopUserData(defaultPath, env = process.env) {
  return env.MERLIN_DESKTOP_USER_DATA_DIR
    ? path.resolve(env.MERLIN_DESKTOP_USER_DATA_DIR)
    : defaultPath + (env.MERLIN_DATA_DIR_SUFFIX || '')
}

export function resolveDesktopMerlinHome({ home, env = process.env, platform = process.platform, directoryExists = () => false, readWindowsHome = () => null }) {
  const paths = platform === 'win32' ? path.win32 : path.posix
  if (env.MERLIN_HOME) {
    return normalizeMerlinHomeRoot(env.MERLIN_HOME, paths)
  }
  // Fresh-install rehearsals must not touch the real Merlin home.
  if (env.MERLIN_DESKTOP_USER_DATA_DIR) {
    return paths.join(paths.resolve(env.MERLIN_DESKTOP_USER_DATA_DIR), 'merlin-home')
  }
  if (platform === 'win32' && env.MERLIN_HOME === undefined) {
    // Explorer can miss setx changes. An explicit empty value opts out of that fallback.
    const registryHome = readWindowsHome()
    if (registryHome) {
      return normalizeMerlinHomeRoot(registryHome, paths)
    }
  }
  const defaultHome = platformDefaultMerlinHome(home, env, platform)
  // Keep the legacy migration for ordinary installs, not isolated suffix runs.
  if (platform === 'win32' && !env.MERLIN_DATA_DIR_SUFFIX) {
    const legacy = paths.join(home, '.merlin')
    if (!directoryExists(defaultHome) && directoryExists(legacy)) {
      return legacy
    }
  }
  return defaultHome
}
