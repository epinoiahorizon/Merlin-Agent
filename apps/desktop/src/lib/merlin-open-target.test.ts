import { describe, expect, it } from 'vitest'

import {
  normalizeMerlinOpenString,
  pathFromMerlinDeepLink,
  pathFromOpenDeepLink,
  resolveMerlinOpenPath
} from './merlin-open-target'

describe('normalizeMerlinOpenString', () => {
  it('accepts hash-router paths and strips a leading hash', () => {
    expect(normalizeMerlinOpenString('/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeMerlinOpenString('#/index-network/intent/1')).toBe('/index-network/intent/1')
  })

  it('maps plugin-scoped merlin:// deep links to the same path', () => {
    expect(normalizeMerlinOpenString('merlin://index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeMerlinOpenString('merlin://index-network/intent/1?focus=true')).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('maps merlin://open/… deep links by stripping the open host', () => {
    expect(normalizeMerlinOpenString('merlin://open/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeMerlinOpenString('merlin://open/settings/plugins')).toBe('/settings/plugins')
  })

  it('rejects reserved merlin kinds and unsafe paths', () => {
    expect(normalizeMerlinOpenString('merlin://blueprint/morning-brief')).toBeNull()
    expect(normalizeMerlinOpenString('merlin://plugin/install')).toBeNull()
    expect(normalizeMerlinOpenString('https://example.com/x')).toBeNull()
    expect(normalizeMerlinOpenString('/../etc/passwd')).toBeNull()
    expect(normalizeMerlinOpenString('index-network')).toBeNull()
  })
})

describe('resolveMerlinOpenPath', () => {
  it('merges structured path + params', () => {
    expect(resolveMerlinOpenPath({ path: '/index-network/intent/1', params: { focus: 'true' } })).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('resolves href the same as a bare string', () => {
    expect(resolveMerlinOpenPath({ href: 'merlin://index-network/intent/1' })).toBe('/index-network/intent/1')
  })
})

describe('pathFromMerlinDeepLink', () => {
  it('builds the navigate path from a plugin-scoped deep-link payload', () => {
    expect(pathFromMerlinDeepLink('index-network', 'intent/1')).toBe('/index-network/intent/1')
  })

  it('builds the navigate path from merlin://open/… payloads', () => {
    expect(pathFromOpenDeepLink('index-network/intent/1')).toBe('/index-network/intent/1')
    expect(pathFromMerlinDeepLink('open', 'agent/42')).toBe('/agent/42')
  })

  it('ignores reserved kinds', () => {
    expect(pathFromMerlinDeepLink('blueprint', 'morning-brief')).toBeNull()
    expect(pathFromMerlinDeepLink('plugin', 'install')).toBeNull()
    expect(pathFromMerlinDeepLink('skill', 'install')).toBeNull()
  })
})
