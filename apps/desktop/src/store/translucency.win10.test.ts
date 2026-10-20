// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest'

// Simulate Windows 10: pin the platform to Win32 AND tell the preload bridge
// that glass is unsupported (Electron computes `glassSupported` from
// `os.release()`, so Win10 — below the 22H2 floor — reports false). Both must
// be in place BEFORE the store module is evaluated (hoisted above the imports)
// so GLASS_SUPPORTED resolves false and GLASS_IS_WINDOWS collapses to false.
//
// That is the exact shape of the bug this test guards: the $translucency
// computed used to pass GLASS_IS_WINDOWS as the "isWindows" argument to
// resolveTranslucency. On Win10 glass is unsupported, so GLASS_IS_WINDOWS is
// false and the fallback defaults came from the MAC table instead of the
// WINDOWS table. The fix passes isWindowsPlatform() instead, which is true
// on Win32 regardless of glass support.
vi.hoisted(() => {
  Object.defineProperty(globalThis.navigator, 'platform', { configurable: true, value: 'Win32' })
  Object.defineProperty(globalThis.window, 'merlinDesktop', {
    configurable: true,
    value: { glassSupported: false }
  })
})

import { defaultTranslucencyValues } from '@merlin/shared/translucency'

import { $translucency, $translucencyBook, GLASS_SUPPORTED, setAppearance } from './translucency'

// The Windows table must win on Win10, even when tint matches macOS.
const WINDOWS_DARK = defaultTranslucencyValues('dark', true)
const WINDOWS_LIGHT = defaultTranslucencyValues('light', true)

describe('Win10 translucency defaults (regression for #90824)', () => {
  it('runs its assertions for real in this environment', () => {
    // Guard the guard: if the platform pin or the glass bridge ever stops
    // landing, every assertion below silently tests the wrong table.
    expect(navigator.platform).toBe('Win32')
    expect(GLASS_SUPPORTED).toBe(false)
  })

  it('resolves an untouched profile to the WINDOWS defaults, not the mac ones', () => {
    // Untouched profile: no persisted book, so the store falls through to the
    // platform defaults. The store's initial appearance is dark.
    //
    // Tint is 0, not the table's 29: on this machine the mode resolves to
    // 'clear', where the number is native window OPACITY (whole window, text
    // included), not a glass tint. A profile nobody tuned must open solid.
    expect($translucency.get()).toEqual({ ...WINDOWS_DARK, intensity: 0, mode: 'clear' })

    expect($translucency.get().material).not.toBe(defaultTranslucencyValues('dark', false).material)

    // Light appearance must resolve the windows light table too.
    setAppearance('light')
    expect($translucency.get()).toEqual({ ...WINDOWS_LIGHT, intensity: 0, mode: 'clear' })
    expect($translucency.get().material).not.toBe(defaultTranslucencyValues('light', false).material)
  })

  it('opens solid: window opacity is 1, not a 29% fade', async () => {
    // The regression this guards: 'clear' + table default 29 went through
    // opacityRamp() and shipped a 94%-opaque window — washed-out text and
    // duller colours on every Win10 machine that never touched the setting.
    const { windowOpacityFor } = await import('@merlin/shared/translucency')

    expect(windowOpacityFor($translucency.get())).toBe(1)
  })

  it('keeps the mode clear when glass is unsupported', () => {
    // Win10 cannot back glass, so an untouched profile must land on 'clear' —
    // never 'glass' (which is what a glass-capable OS would pre-select).
    expect($translucency.get().mode).toBe('clear')
  })

  it('still resolves windows defaults after an explicit reset to an empty book', () => {
    // A fresh book with no values is the same "untouched" shape the store
    // starts from; the platform defaults must still be the windows ones, and
    // the tint must still be the solid-by-default 0 on a clear-only machine.
    $translucencyBook.set({ mode: 'clear', base: {}, light: {}, dark: {} })
    setAppearance('dark')

    expect($translucency.get()).toEqual({ ...WINDOWS_DARK, intensity: 0, mode: 'clear' })
  })
})
