import { contextBridge, ipcRenderer, webFrame, webUtils } from 'electron'

import type { DesktopProfileRoute } from './desktop-profile'
import type { HudModifierApi, HudModifierStatus } from './hud-modifier-types'
import { customWindowControlsEnabled } from './window-controls'

// Which translucency the OS can back. Asked synchroatlasly because the renderer
// needs it before its first paint, and answered by main because deciding it
// needs `os.release()` — a sandboxed preload may only require electron, events,
// timers and url, so importing node:os here throws before contextBridge runs
// and takes the ENTIRE bridge down with it (window.merlinDesktop undefined =>
// "Desktop IPC bridge is unavailable"). No reply means no glass, which degrades
// to an ordinary opaque window rather than a page thinned over nothing.
const translucencySupport = ipcRenderer.sendSync('merlin:translucency:support')
const hudWindowing = ipcRenderer.sendSync('merlin:hud:windowing')
const hudNativeDrag = hudWindowing?.nativeDrag === true

const launchFlags: { localModels?: boolean; guestOnboarding?: boolean } | undefined =
  ipcRenderer.sendSync('merlin:feature-flags')

// Local, sanitized skin payload for the first renderer theme paint. This does
// not wait on `gateway.ready`, so an unreachable remote primary cannot force
// the built-in palette over the skin configured on this machine.
const localSkin = ipcRenderer.sendSync('merlin:skin:local')

contextBridge.exposeInMainWorld('merlinDesktop', {
  glassSupported: translucencySupport?.glass === true,
  translucencySupported: translucencySupport?.translucency === true,
  // Launch-flag fact: the app was started with --local, so the renderer may
  // show the local-models surfaces. Static for the window's lifetime.
  localModelsEnabled: launchFlags?.localModels === true,
  // Launch-flag fact: the Atlas free tier is on for this launch
  // (MERLIN_GUEST_ONBOARDING=1 or --guest-onboarding). Read-only; the same
  // decision is stamped onto every backend the app spawns.
  guestOnboardingEnabled: launchFlags?.guestOnboarding === true,
  localSkin: localSkin && typeof localSkin === 'object' ? localSkin : null,
  getConnection: (profile, opts) => ipcRenderer.invoke('merlin:connection', profile, opts),
  // Registry-scoped backend resolution: { connectionId, profile } → descriptor.
  getConnectionFor: payload => ipcRenderer.invoke('merlin:connection:for', payload),
  getProfileRoutes: profiles => ipcRenderer.invoke('merlin:plugin-profile-routes', profiles),
  revalidateConnection: () => ipcRenderer.invoke('merlin:connection:revalidate'),
  touchBackend: (profile, options) => ipcRenderer.invoke('merlin:backend:touch', profile, options),
  getPoolLimits: () => ipcRenderer.invoke('merlin:pool-limits:get'),
  setPoolLimits: limits => ipcRenderer.invoke('merlin:pool-limits:set', limits),
  getGatewayWsUrl: profile => ipcRenderer.invoke('merlin:gateway:ws-url', profile),
  // Registry-scoped fresh WS URL: { connectionId, profile } → result shape of
  // getGatewayWsUrl, minted against that connection's backend.
  getGatewayWsUrlFor: payload => ipcRenderer.invoke('merlin:gateway:ws-url-for', payload),
  // Union agent roster across every registered connection.
  getAgentRoster: () => ipcRenderer.invoke('merlin:agents:roster'),
  openSessionWindow: (sessionId, opts) => ipcRenderer.invoke('merlin:window:openSession', sessionId, opts),
  openSessionInTerminal: (sessionId, opts) => ipcRenderer.invoke('merlin:window:openInTerminal', sessionId, opts),
  openWindow: (options?: DesktopProfileRoute) => ipcRenderer.invoke('merlin:window:openInstance', options),
  openBrowserWindow: tabId => ipcRenderer.invoke('merlin:window:openBrowser', tabId),
  onBrowserPopoutClosed: callback => {
    const listener = (_event, tabId) => callback(tabId)
    ipcRenderer.on('merlin:browser-popout:closed', listener)

    return () => ipcRenderer.removeListener('merlin:browser-popout:closed', listener)
  },
  claimAmbientCue: key => ipcRenderer.invoke('merlin:ambient:claim', key),
  windowControls: {
    custom: customWindowControlsEnabled(),
    minimize: () => ipcRenderer.send('merlin:window-control', 'minimize'),
    toggleMaximize: () => ipcRenderer.send('merlin:window-control', 'toggle-maximize'),
    close: () => ipcRenderer.send('merlin:window-control', 'close')
  },
  wakeIndicator: {
    getState: () => ipcRenderer.invoke('merlin:wake-indicator:get'),
    setState: state => ipcRenderer.send('merlin:wake-indicator:set', state),
    onState: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('merlin:wake-indicator:state', listener)

      return () => ipcRenderer.removeListener('merlin:wake-indicator:state', listener)
    }
  },
  chatOnboarding: {
    grow: request => ipcRenderer.send('merlin:chat-onboarding:grow', request),
    soloBoot: () => ipcRenderer.send('merlin:chat-onboarding:solo-boot')
  },
  petOverlay: {
    // Main renderer → main process: window lifecycle + drag. `request` is
    // `{ bounds, screen }`; resolves with the screen bounds it actually used.
    open: request => ipcRenderer.invoke('merlin:pet-overlay:open', request),
    close: () => ipcRenderer.invoke('merlin:pet-overlay:close'),
    setBounds: bounds => ipcRenderer.send('merlin:pet-overlay:set-bounds', bounds),
    setIgnoreMouse: ignore => ipcRenderer.send('merlin:pet-overlay:ignore-mouse', ignore),
    // Flip the overlay focusable (and focus it) while the composer needs keys.
    setFocusable: focusable => ipcRenderer.send('merlin:pet-overlay:set-focusable', focusable),
    // Main renderer → overlay (forwarded by main): push the latest pet state.
    pushState: payload => ipcRenderer.send('merlin:pet-overlay:state', payload),
    // Overlay → main renderer (forwarded by main): pop back in / composer submit.
    control: payload => ipcRenderer.send('merlin:pet-overlay:control', payload),
    // Overlay subscribes to state pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('merlin:pet-overlay:state', listener)

      return () => ipcRenderer.removeListener('merlin:pet-overlay:state', listener)
    },
    // Main renderer subscribes to overlay control messages.
    onControl: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('merlin:pet-overlay:control', listener)

      return () => ipcRenderer.removeListener('merlin:pet-overlay:control', listener)
    }
  },
  // HUD mode: the chrome-free floating chat. A full app renderer (own gateway)
  // sized as a floating bar, so it mounts the real composer. Main owns the
  // window; `onChanged` keeps every window's toggle truthful.
  hud: {
    nativeDrag: hudNativeDrag,
    windowing: {
      clientPlacement: hudWindowing?.clientPlacement !== false,
      controlDrag: hudWindowing?.controlDrag === true,
      nativeDrag: hudNativeDrag,
      solid: hudWindowing?.solid === true,
      workspaceTransfer: hudWindowing?.workspaceTransfer === true
    },
    open: request => ipcRenderer.invoke('merlin:hud:open', request),
    close: () => ipcRenderer.invoke('merlin:hud:close'),
    setIgnoreMouse: ignore => ipcRenderer.send('merlin:hud:ignore-mouse', ignore),
    beginMove: () => ipcRenderer.send('merlin:hud:begin-move'),
    endMove: () => ipcRenderer.send('merlin:hud:end-move'),
    moveBy: delta => ipcRenderer.send('merlin:hud:move-by', delta),
    setWorkspaceTransfer: transferring => ipcRenderer.send('merlin:hud:workspace-transfer', transferring),
    setBounds: bounds => ipcRenderer.send('merlin:hud:set-bounds', bounds),
    resetLayout: () => ipcRenderer.invoke('merlin:hud:reset-layout'),
    // Whether the band covers the window below the bar. Main pairs it with the
    // user's translucency setting to decide the native frost (macOS vibrancy /
    // Windows 11 DWM backdrop) — see hudFrostFor.
    setFrost: showing => ipcRenderer.invoke('merlin:hud:frost', showing),
    // The HUD tells main which session it is on; main hands that back to the
    // app window when the HUD closes, so the app can re-home onto it.
    setSession: sessionId => ipcRenderer.send('merlin:hud:session', sessionId),
    onGoto: callback => {
      const listener = (_event, sessionId) => callback(sessionId)
      ipcRenderer.on('merlin:hud:goto', listener)

      return () => ipcRenderer.removeListener('merlin:hud:goto', listener)
    },
    onChanged: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('merlin:hud:changed', listener)

      return () => ipcRenderer.removeListener('merlin:hud:changed', listener)
    },
    // Linux only, and silent elsewhere: where the cursor is, in page
    // coordinates, or null when it has left the window. Stands in for the
    // mousemove that `setIgnoreMouseEvents(true, { forward: true })` delivers on
    // macOS and Windows but not here.
    onCursor: callback => {
      const listener = (_event, point) => callback(point)
      ipcRenderer.on('merlin:hud:cursor', listener)

      return () => ipcRenderer.removeListener('merlin:hud:cursor', listener)
    },
    // Main's game-overlay watch: whether a fullscreen app (a game) is under
    // the HUD, so the renderer can step back to the low-opacity overlay
    // treatment while one owns the screen.
    onGameOverlay: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('merlin:hud:game-overlay', listener)

      return () => ipcRenderer.removeListener('merlin:hud:game-overlay', listener)
    }
  },
  hudModifier: {
    getSettings: () => ipcRenderer.invoke('merlin:hud-modifier:settings:get'),
    setEnabled: enabled => ipcRenderer.invoke('merlin:hud-modifier:settings:set', enabled),
    openPermissionSettings: () => ipcRenderer.invoke('merlin:hud-modifier:permission'),
    onStatus: callback => {
      const listener = (_event: Electron.IpcRendererEvent, status: HudModifierStatus) => callback(status)
      ipcRenderer.on('merlin:hud-modifier:status', listener)

      return () => ipcRenderer.removeListener('merlin:hud-modifier:status', listener)
    }
  } satisfies HudModifierApi,
  // macOS native screenshot gesture; captures require a main-issued request.
  screenshot:
    process.platform === 'darwin'
      ? {
          getSettings: () => ipcRenderer.invoke('merlin:screenshot:settings:get'),
          setEnabled: enabled => ipcRenderer.invoke('merlin:screenshot:settings:set', enabled),
          openPermissionSettings: kind => ipcRenderer.invoke('merlin:screenshot:permission', kind),
          capture: requestId => ipcRenderer.invoke('merlin:screenshot:capture', requestId),
          onStatus: callback => {
            const listener = (_event, status) => callback(status)
            ipcRenderer.on('merlin:screenshot:status', listener)

            return () => ipcRenderer.removeListener('merlin:screenshot:status', listener)
          },
          onRequest: callback => {
            const channel = 'merlin:screenshot:request'
            const listener = (_event, requestId) => callback(requestId)

            if (ipcRenderer.listenerCount(channel) === 0) {
              ipcRenderer.send('merlin:screenshot:subscribe', true)
            }

            ipcRenderer.on(channel, listener)

            return () => {
              ipcRenderer.removeListener(channel, listener)

              if (ipcRenderer.listenerCount(channel) === 0) {
                ipcRenderer.send('merlin:screenshot:subscribe', false)
              }
            }
          }
        }
      : undefined,
  // Quick Entry: the global-hotkey mini composer window. Main owns the OS
  // shortcut + the persisted preference; the quick window only captures text
  // and hands it back, and the primary renderer submits it through the normal
  // prompt path.
  quickEntry: {
    getSettings: () => ipcRenderer.invoke('merlin:quick-entry:settings:get'),
    setSettings: patch => ipcRenderer.invoke('merlin:quick-entry:settings:set', patch),
    submit: payload => ipcRenderer.send('merlin:quick-entry:submit', payload),
    dismiss: () => ipcRenderer.send('merlin:quick-entry:dismiss'),
    // Primary renderer → main → quick window: gateway connection state + the
    // recent-session options the target picker offers. Main caches the latest
    // payload so a freshly spawned quick window starts from truth.
    pushState: payload => ipcRenderer.send('merlin:quick-entry:state', payload),
    // Quick window subscribes to those pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('merlin:quick-entry:state', listener)

      return () => ipcRenderer.removeListener('merlin:quick-entry:state', listener)
    },
    // Main → primary renderer: a submit captured by the quick window.
    onSubmit: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('merlin:quick-entry:submit', listener)

      return () => ipcRenderer.removeListener('merlin:quick-entry:submit', listener)
    },
    // Main → quick window: you were just summoned (reset draft + refocus).
    onShown: callback => {
      const listener = () => callback()
      ipcRenderer.on('merlin:quick-entry:shown', listener)

      return () => ipcRenderer.removeListener('merlin:quick-entry:shown', listener)
    }
  },
  getBootProgress: () => ipcRenderer.invoke('merlin:boot-progress:get'),
  getConnectionConfig: profile => ipcRenderer.invoke('merlin:connection-config:get', profile),
  saveConnectionConfig: payload => ipcRenderer.invoke('merlin:connection-config:save', payload),
  applyConnectionConfig: payload => ipcRenderer.invoke('merlin:connection-config:apply', payload),
  testConnectionConfig: payload => ipcRenderer.invoke('merlin:connection-config:test', payload),
  // Opt-in OS-keychain encryption for stored gateway secrets (default off —
  // see secret-storage-policy.ts). get never touches the OS keychain.
  getSecretStorageEncryption: () => ipcRenderer.invoke('merlin:secret-storage:get'),
  setSecretStorageEncryption: (on: boolean) => ipcRenderer.invoke('merlin:secret-storage:set', on),
  // v2 multi-connection registry: named agent sources (local / remote / cloud / ssh).
  connections: {
    list: () => ipcRenderer.invoke('merlin:connections:list'),
    save: payload => ipcRenderer.invoke('merlin:connections:save', payload),
    remove: id => ipcRenderer.invoke('merlin:connections:remove', id),
    setPrimary: id => ipcRenderer.invoke('merlin:connections:set-primary', id),
    setLaunchMode: mode => ipcRenderer.invoke('merlin:connections:set-launch-mode', mode),
    setLastUsed: id => ipcRenderer.invoke('merlin:connections:set-last-used', id),
    test: id => ipcRenderer.invoke('merlin:connections:test', id),
    updateManaged: id => ipcRenderer.invoke('merlin:connections:update-managed', id),
    // Fan out `merlin update` to every eligible registered connection.
    // Optional excludeIds skips rows the caller updates through another path.
    updateAll: options => ipcRenderer.invoke('merlin:connections:update-all', options),
    // Registry lifecycle push (main → renderer): a connection was removed or
    // materially edited, so secondaries scoped to it must be disposed (and,
    // for edits, re-dialed at the new target).
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('merlin:connections:changed', listener)

      return () => ipcRenderer.removeListener('merlin:connections:changed', listener)
    }
  },
  sshConfigHosts: () => ipcRenderer.invoke('merlin:ssh-config:hosts'),
  sshResolveHost: host => ipcRenderer.invoke('merlin:ssh-config:resolve', host),
  probeConnectionConfig: remoteUrl => ipcRenderer.invoke('merlin:connection-config:probe', remoteUrl),
  // `options` lets a registry-editor draft sign in BEFORE it is saved: the
  // main process settles the draft's connection id up front so the login
  // window writes into the per-connection cookie jar the saved entry will
  // read (not the legacy shared jar an unsaved URL would fall back to).
  oauthLoginConnectionConfig: (remoteUrl, options) =>
    ipcRenderer.invoke('merlin:connection-config:oauth-login', remoteUrl, options),
  oauthLogoutConnectionConfig: remoteUrl => ipcRenderer.invoke('merlin:connection-config:oauth-logout', remoteUrl),
  // Merlin Cloud: one portal login powers discovery + silent per-agent sign-in
  // (cloud-auto-discovery Phase 3).
  cloud: {
    status: () => ipcRenderer.invoke('merlin:cloud:status'),
    login: () => ipcRenderer.invoke('merlin:cloud:login'),
    logout: () => ipcRenderer.invoke('merlin:cloud:logout'),
    discover: org => ipcRenderer.invoke('merlin:cloud:discover', org),
    agentSignIn: dashboardUrl => ipcRenderer.invoke('merlin:cloud:agent-sign-in', dashboardUrl)
  },
  profile: {
    getDefault: () => ipcRenderer.invoke('merlin:profile:default:get'),
    setDefault: (route: DesktopProfileRoute) => ipcRenderer.invoke('merlin:profile:default:set', route),
    onDefaultChanged: (callback: (route: DesktopProfileRoute | null) => void) => {
      const listener = (_event: Electron.IpcRendererEvent, route: DesktopProfileRoute | null) => callback(route)
      ipcRenderer.on('merlin:profile:default:changed', listener)

      return () => ipcRenderer.removeListener('merlin:profile:default:changed', listener)
    },
    get: () => ipcRenderer.invoke('merlin:profile:get'),
    remember: name => ipcRenderer.invoke('merlin:profile:remember', name),
    set: name => ipcRenderer.invoke('merlin:profile:set', name)
  },
  api: request => ipcRenderer.invoke('merlin:api', request),
  notify: payload => ipcRenderer.invoke('merlin:notify', payload),
  claimStartupLatency: () => ipcRenderer.invoke('merlin:startup-latency:claim'),
  requestMicrophoneAccess: () => ipcRenderer.invoke('merlin:requestMicrophoneAccess'),
  readWindowBelow: () => ipcRenderer.invoke('merlin:window:readBelow'),
  readFileDataUrl: filePath => ipcRenderer.invoke('merlin:readFileDataUrl', filePath),
  readFileDataUrlForAttach: filePath => ipcRenderer.invoke('merlin:readFileDataUrlForAttach', filePath),
  dataUrlReadMax: {
    get: () => ipcRenderer.invoke('merlin:data-url-read-max:get'),
    set: maxMb => ipcRenderer.invoke('merlin:data-url-read-max:set', maxMb)
  },
  readFileText: filePath => ipcRenderer.invoke('merlin:readFileText', filePath),
  readPluginSource: (filePath: string) => ipcRenderer.invoke('merlin:readPluginSource', filePath),
  selectPaths: options => ipcRenderer.invoke('merlin:selectPaths', options),
  selectSavePath: options => ipcRenderer.invoke('merlin:selectSavePath', options),
  writeClipboard: text => ipcRenderer.invoke('merlin:writeClipboard', text),
  readClipboard: () => ipcRenderer.invoke('merlin:readClipboard'),
  saveGatewayFile: payload => ipcRenderer.invoke('merlin:saveGatewayFile', payload),
  saveImageFromUrl: url => ipcRenderer.invoke('merlin:saveImageFromUrl', url),
  contextMenuEdit: command => ipcRenderer.invoke('merlin:context-menu:edit', command),
  contextMenuCopyImage: () => ipcRenderer.invoke('merlin:context-menu:copy-image'),
  contextMenuSpellcheck: action => ipcRenderer.invoke('merlin:context-menu:spellcheck', action),
  contextMenuGuestAddWord: payload => ipcRenderer.invoke('merlin:context-menu:guest-add-word', payload),
  onContextMenuSpellcheck: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('merlin:context-menu-spellcheck', listener)

    return () => ipcRenderer.removeListener('merlin:context-menu-spellcheck', listener)
  },
  saveImageBuffer: (data, ext, name) => ipcRenderer.invoke('merlin:saveImageBuffer', { data, ext, name }),
  capturePreview: payload => ipcRenderer.invoke('merlin:capturePreview', payload),
  savePastedText: text => ipcRenderer.invoke('merlin:savePastedText', { text }),
  saveClipboardImage: () => ipcRenderer.invoke('merlin:saveClipboardImage'),
  getPathForFile: file => {
    try {
      return webUtils.getPathForFile(file) || ''
    } catch {
      return ''
    }
  },
  normalizePreviewTarget: (target, baseDir) => ipcRenderer.invoke('merlin:normalizePreviewTarget', target, baseDir),
  watchPreviewFile: url => ipcRenderer.invoke('merlin:watchPreviewFile', url),
  watchDirectory: dir => ipcRenderer.invoke('merlin:watchDirectory', dir),
  stopPreviewFileWatch: id => ipcRenderer.invoke('merlin:stopPreviewFileWatch', id),
  setActiveWork: payload => ipcRenderer.send('merlin:active-work', payload),
  setTitleBarTheme: payload => ipcRenderer.send('merlin:titlebar-theme', payload),
  setNativeTheme: mode => ipcRenderer.send('merlin:native-theme', mode),
  setTranslucency: payload => ipcRenderer.send('merlin:translucency', payload),
  setKeepAwake: on => ipcRenderer.send('merlin:keep-awake', on),
  minimizeToTray: {
    get: () => ipcRenderer.invoke('merlin:minimize-to-tray:get'),
    set: on => ipcRenderer.invoke('merlin:minimize-to-tray:set', on),
    onChanged: callback => {
      const listener = (_event, status) => callback(status)
      ipcRenderer.on('merlin:minimize-to-tray:changed', listener)

      return () => ipcRenderer.removeListener('merlin:minimize-to-tray:changed', listener)
    }
  },
  setDisableF12: blocked => ipcRenderer.send('merlin:devtools:disable-f12', blocked),
  setF12ShortcutActive: active => ipcRenderer.send('merlin:f12ShortcutActive', Boolean(active)),
  onF12Shortcut: callback => {
    const listener = (_event, input) => callback(input)
    ipcRenderer.on('merlin:f12-shortcut', listener)

    return () => ipcRenderer.removeListener('merlin:f12-shortcut', listener)
  },
  setPreviewShortcutActive: active => ipcRenderer.send('merlin:previewShortcutActive', Boolean(active)),
  openExternal: url => ipcRenderer.invoke('merlin:openExternal', url),
  mcpOauth: {
    // One-shot loopback listener for MCP OAuth against remote backends: bind
    // on this machine, hand redirectUri to mcp.servers.oauth.start, then wait
    // for the provider redirect and relay code/state via oauth.callback.
    listen: () => ipcRenderer.invoke('merlin:mcp-oauth:listen'),
    wait: (id, timeoutMs) => ipcRenderer.invoke('merlin:mcp-oauth:wait', id, timeoutMs),
    cancel: id => ipcRenderer.invoke('merlin:mcp-oauth:cancel', id)
  },
  openPreviewInBrowser: url => ipcRenderer.invoke('merlin:openPreviewInBrowser', url),
  reachPreviewUrl: url => ipcRenderer.invoke('merlin:preview:reach', url),
  setActiveConnectionRoute: route => ipcRenderer.send('merlin:connection:active-route', route),
  fetchLinkTitle: url => ipcRenderer.invoke('merlin:fetchLinkTitle', url),
  resolveFavicon: url => ipcRenderer.invoke('merlin:resolveFavicon', url),
  sanitizeWorkspaceCwd: cwd => ipcRenderer.invoke('merlin:workspace:sanitize', cwd),
  settings: {
    getDefaultProjectDir: () => ipcRenderer.invoke('merlin:setting:defaultProjectDir:get'),
    setDefaultProjectDir: dir => ipcRenderer.invoke('merlin:setting:defaultProjectDir:set', dir),
    pickDefaultProjectDir: () => ipcRenderer.invoke('merlin:setting:defaultProjectDir:pick')
  },
  zoom: {
    // Current zoom of this window, as { level, percent }.
    get: () => ipcRenderer.invoke('merlin:zoom:get'),
    // Synchronous zoom factor (1 = 100%). Coordinate math needs it in the
    // same tick as the event it converts, so no IPC round-trip here.
    factor: () => webFrame.getZoomFactor(),
    setPercent: percent => ipcRenderer.send('merlin:zoom:set-percent', percent),
    // Fires on every zoom change, including the Ctrl/Cmd +/-/0 shortcuts,
    // so the settings UI can stay in sync with the keyboard.
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('merlin:zoom:changed', listener)

      return () => ipcRenderer.removeListener('merlin:zoom:changed', listener)
    }
  },
  revealLogs: () => ipcRenderer.invoke('merlin:logs:reveal'),
  getRecentLogs: () => ipcRenderer.invoke('merlin:logs:recent'),
  // Fire-and-forget: persists a renderer error-boundary catch (with component
  // stack) to desktop.log so crashes survive the window (#79428).
  reportRendererError: report => ipcRenderer.send('merlin:logs:renderer-error', report),
  logLine: (line: string): void => ipcRenderer.send('merlin:logs:renderer-line', line),
  readDir: dirPath => ipcRenderer.invoke('merlin:fs:readDir', dirPath),
  gitRoot: startPath => ipcRenderer.invoke('merlin:fs:gitRoot', startPath),
  revealPath: targetPath => ipcRenderer.invoke('merlin:fs:reveal', targetPath),
  openDir: dirPath => ipcRenderer.invoke('merlin:fs:openDir', dirPath),
  desktopPluginsRoot: () => ipcRenderer.invoke('merlin:fs:desktopPluginsRoot'),
  reconcileDesktopPlugins: () => ipcRenderer.invoke('merlin:fs:reconcileDesktopPlugins'),
  logsRoot: (profile?: string) => ipcRenderer.invoke('merlin:fs:logsRoot', profile),
  renamePath: (targetPath, newName) => ipcRenderer.invoke('merlin:fs:rename', targetPath, newName),
  writeTextFile: (filePath, content) => ipcRenderer.invoke('merlin:fs:writeText', filePath, content),
  trashPath: targetPath => ipcRenderer.invoke('merlin:fs:trash', targetPath),
  git: {
    worktreeList: repoPath => ipcRenderer.invoke('merlin:git:worktreeList', repoPath),
    worktreeAdd: (repoPath, options) => ipcRenderer.invoke('merlin:git:worktreeAdd', repoPath, options),
    worktreeRemove: (repoPath, worktreePath, options) =>
      ipcRenderer.invoke('merlin:git:worktreeRemove', repoPath, worktreePath, options),
    branchSwitch: (repoPath, branch) => ipcRenderer.invoke('merlin:git:branchSwitch', repoPath, branch),
    branchList: repoPath => ipcRenderer.invoke('merlin:git:branchList', repoPath),
    baseBranchList: repoPath => ipcRenderer.invoke('merlin:git:baseBranchList', repoPath),
    repoStatus: repoPath => ipcRenderer.invoke('merlin:git:repoStatus', repoPath),
    fileDiff: (repoPath, filePath) => ipcRenderer.invoke('merlin:git:fileDiff', repoPath, filePath),
    scanRepos: (roots, options) => ipcRenderer.invoke('merlin:git:scanRepos', roots, options),
    review: {
      list: (repoPath, scope, baseRef) => ipcRenderer.invoke('merlin:git:review:list', repoPath, scope, baseRef),
      diff: (repoPath, filePath, scope, baseRef, staged) =>
        ipcRenderer.invoke('merlin:git:review:diff', repoPath, filePath, scope, baseRef, staged),
      stage: (repoPath, filePath) => ipcRenderer.invoke('merlin:git:review:stage', repoPath, filePath),
      unstage: (repoPath, filePath) => ipcRenderer.invoke('merlin:git:review:unstage', repoPath, filePath),
      revert: (repoPath, filePath) => ipcRenderer.invoke('merlin:git:review:revert', repoPath, filePath),
      revParse: (repoPath, ref) => ipcRenderer.invoke('merlin:git:review:revParse', repoPath, ref),
      commit: (repoPath, message, push) => ipcRenderer.invoke('merlin:git:review:commit', repoPath, message, push),
      commitContext: repoPath => ipcRenderer.invoke('merlin:git:review:commitContext', repoPath),
      push: repoPath => ipcRenderer.invoke('merlin:git:review:push', repoPath),
      shipInfo: repoPath => ipcRenderer.invoke('merlin:git:review:shipInfo', repoPath),
      prList: (repoPath, branches, numbers) =>
        ipcRenderer.invoke('merlin:git:review:prList', repoPath, branches, numbers),
      createPr: repoPath => ipcRenderer.invoke('merlin:git:review:createPr', repoPath)
    }
  },
  terminal: {
    attach: id => ipcRenderer.invoke('merlin:terminal:attach', id),
    cwd: id => ipcRenderer.invoke('merlin:terminal:cwd', id),
    dispose: id => ipcRenderer.invoke('merlin:terminal:dispose', id),
    resize: (id, size) => ipcRenderer.invoke('merlin:terminal:resize', id, size),
    start: options => ipcRenderer.invoke('merlin:terminal:start', options),
    write: (id, data) => ipcRenderer.invoke('merlin:terminal:write', id, data),
    onData: (id, callback) => {
      const channel = `merlin:terminal:${id}:data`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    },
    onExit: (id, callback) => {
      const channel = `merlin:terminal:${id}:exit`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    }
  },
  onClosePreviewRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('merlin:close-preview-requested', listener)

    return () => ipcRenderer.removeListener('merlin:close-preview-requested', listener)
  },
  onPreviewNav: callback => {
    const listener = (_event, command) => callback(command)
    ipcRenderer.on('merlin:preview-nav', listener)

    return () => ipcRenderer.removeListener('merlin:preview-nav', listener)
  },
  onOpenFolderRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('merlin:open-folder-requested', listener)

    return () => ipcRenderer.removeListener('merlin:open-folder-requested', listener)
  },
  onOpenUpdatesRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('merlin:open-updates', listener)

    return () => ipcRenderer.removeListener('merlin:open-updates', listener)
  },
  onDeepLink: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('merlin:deep-link', listener)

    return () => ipcRenderer.removeListener('merlin:deep-link', listener)
  },
  signalDeepLinkReady: () => ipcRenderer.invoke('merlin:deep-link-ready'),
  probePluginRepo: payload => ipcRenderer.invoke('merlin:plugin:probe', payload),
  installDesktopPlugin: payload => ipcRenderer.invoke('merlin:plugin:installDesktop', payload),
  removeDesktopPlugin: payload => ipcRenderer.invoke('merlin:plugin:removeDesktop', payload),
  onWindowStateChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('merlin:window-state-changed', listener)

    return () => ipcRenderer.removeListener('merlin:window-state-changed', listener)
  },
  onFocusSession: callback => {
    const listener = (_event, sessionId) => callback(sessionId)
    ipcRenderer.on('merlin:focus-session', listener)

    return () => ipcRenderer.removeListener('merlin:focus-session', listener)
  },
  onNotificationAction: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('merlin:notification-action', listener)

    return () => ipcRenderer.removeListener('merlin:notification-action', listener)
  },
  onNotificationActivate: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('merlin:notification-activate', listener)

    return () => ipcRenderer.removeListener('merlin:notification-activate', listener)
  },
  onExternalOpenFailed: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('merlin:external-open-failed', listener)

    return () => ipcRenderer.removeListener('merlin:external-open-failed', listener)
  },
  onPreviewFileChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('merlin:preview-file-changed', listener)

    return () => ipcRenderer.removeListener('merlin:preview-file-changed', listener)
  },
  onBackendExit: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('merlin:backend-exit', listener)

    return () => ipcRenderer.removeListener('merlin:backend-exit', listener)
  },
  // Cooperative pool retirement (main → renderer): the pooled backend under
  // `poolKey` is being stopped for a foreground open. Park that scope; do not
  // redial into the slot it vacated.
  onPoolBackendRetiring: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('merlin:pool:retiring', listener)

    return () => ipcRenderer.removeListener('merlin:pool:retiring', listener)
  },
  // Soft gateway-mode apply finished tearing down the primary backend. Renderer
  // should wipe session lists + re-dial without a window reload.
  onConnectionApplied: callback => {
    const listener = () => callback()
    ipcRenderer.on('merlin:connection:applied', listener)

    return () => ipcRenderer.removeListener('merlin:connection:applied', listener)
  },
  onPowerResume: callback => {
    const listener = () => callback()
    ipcRenderer.on('merlin:power-resume', listener)

    return () => ipcRenderer.removeListener('merlin:power-resume', listener)
  },
  // AC ↔ battery transitions; renderers slow their backstop polls on battery.
  getOnBattery: () => ipcRenderer.invoke('merlin:power-battery:get'),
  onBatteryChanged: callback => {
    const listener = (_event, onBattery) => callback(Boolean(onBattery))
    ipcRenderer.on('merlin:power-battery', listener)

    return () => ipcRenderer.removeListener('merlin:power-battery', listener)
  },
  onBootProgress: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('merlin:boot-progress', listener)

    return () => ipcRenderer.removeListener('merlin:boot-progress', listener)
  },
  // First-launch bootstrap progress -- emitted by the install.ps1 stage
  // runner in main.ts (apps/desktop/electron/bootstrap-runner.ts).
  // Renderer's install overlay subscribes to live events and queries the
  // current snapshot via getBootstrapState() to recover after a devtools
  // reload mid-bootstrap.
  getBootstrapState: () => ipcRenderer.invoke('merlin:bootstrap:get'),
  probeLocalBackend: () => ipcRenderer.invoke('merlin:local-backend:probe'),
  continueBootstrapLocal: () => ipcRenderer.invoke('merlin:bootstrap:continue-local'),
  recycleBackend: profile => ipcRenderer.invoke('merlin:backend:recycle', profile),
  resetBootstrap: () => ipcRenderer.invoke('merlin:bootstrap:reset'),
  repairBootstrap: () => ipcRenderer.invoke('merlin:bootstrap:repair'),
  cancelBootstrap: () => ipcRenderer.invoke('merlin:bootstrap:cancel'),
  onBootstrapEvent: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('merlin:bootstrap:event', listener)

    return () => ipcRenderer.removeListener('merlin:bootstrap:event', listener)
  },
  getVersion: () => ipcRenderer.invoke('merlin:version'),
  relaunchApp: () => ipcRenderer.invoke('merlin:app:relaunch'),
  getMachineProfile: () => ipcRenderer.invoke('merlin:machine:profile'),
  getRemoteDisplayReason: () => ipcRenderer.invoke('merlin:get-remote-display-reason'),
  uninstall: {
    summary: () => ipcRenderer.invoke('merlin:uninstall:summary'),
    run: mode => ipcRenderer.invoke('merlin:uninstall:run', { mode })
  },
  updates: {
    check: opts => ipcRenderer.invoke('merlin:updates:check', opts),
    apply: opts => ipcRenderer.invoke('merlin:updates:apply', opts),
    getBranch: () => ipcRenderer.invoke('merlin:updates:branch:get'),
    setBranch: name => ipcRenderer.invoke('merlin:updates:branch:set', name),
    onProgress: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('merlin:updates:progress', listener)

      return () => ipcRenderer.removeListener('merlin:updates:progress', listener)
    },
    takePendingRun: () => ipcRenderer.invoke('merlin:updates:metric:take'),
    ackPendingRun: sent => ipcRenderer.invoke('merlin:updates:metric:ack', sent),
    onPendingRun: callback => {
      const listener = () => callback()
      ipcRenderer.on('merlin:updates:metric:pending', listener)

      return () => ipcRenderer.removeListener('merlin:updates:metric:pending', listener)
    }
  },
  desktopMetrics: {
    setEnabled: (on, profile) => ipcRenderer.invoke('merlin:desktop-metrics:set-enabled', on, profile),
    takeRendererCrashes: () => ipcRenderer.invoke('merlin:desktop-metrics:crash:take'),
    ackRendererCrashes: sent => ipcRenderer.invoke('merlin:desktop-metrics:crash:ack', sent)
  },
  themes: {
    fetchMarketplace: id => ipcRenderer.invoke('merlin:vscode-theme:fetch', id),
    searchMarketplace: query => ipcRenderer.invoke('merlin:vscode-theme:search', query)
  },
  // Find-in-page (Ctrl/Cmd+F): delegates to Electron's
  // webContents.findInPage on the IPC sender's window so a Cmd+F pressed
  // in a secondary session window searches THAT window, not the primary.
  // `onFoundInPage` returns the unsubscribe fn; the renderer wires it via
  // `initFindInPageListener` in store/find-in-page.ts and tears it down
  // when the FindBar unmounts.
  findInPage: (query, options) => ipcRenderer.invoke('merlin:find-in-page', query, options),
  stopFindInPage: () => ipcRenderer.invoke('merlin:stop-find-in-page'),
  onFoundInPage: callback => {
    const listener = (_event, result) => callback(result)
    ipcRenderer.on('merlin:found-in-page', listener)

    return () => ipcRenderer.removeListener('merlin:found-in-page', listener)
  },
  // Main-process `before-input-event` forwards Ctrl/Cmd+F here so renderer
  // can open the FindBar even when the GTK compositor has already grabbed
  // the chord at the windowing layer (#81727).
  onOpenFindBarRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('merlin:open-find-bar', listener)

    return () => ipcRenderer.removeListener('merlin:open-find-bar', listener)
  }
})
