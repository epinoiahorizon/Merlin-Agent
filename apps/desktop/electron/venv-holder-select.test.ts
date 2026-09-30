import assert from 'node:assert/strict'

import { test } from 'vitest'

import { hasWindowsPathPrefix, isExternalVenvHolder, isMerlinOwnedVenvDaemon } from './venv-holder-select'

const SCRIPTS = 'C:\\Merlin\\venv\\Scripts'

test('matches the hindsight daemon shim (exe under venv Scripts + hindsight cmdline)', () => {
  assert.equal(
    isMerlinOwnedVenvDaemon(
      'C:\\Merlin\\venv\\Scripts\\pythonw.exe',
      'C:\\Merlin\\venv\\Scripts\\pythonw.exe -m hindsight_api.main --daemon --idle-timeout 300 --port 9177',
      SCRIPTS
    ),
    true
  )
})

test('Windows path prefix match is ordinal case-insensitive', () => {
  assert.equal(
    isMerlinOwnedVenvDaemon(
      'c:\\merlin\\venv\\scripts\\python.exe',
      'python.exe -m hindsight_api.main --daemon',
      'C:\\Merlin\\venv\\Scripts'
    ),
    true
  )
})

test('excludes external venv holders that are not the hindsight daemon', () => {
  // a user terminal running the merlin CLI from the venv — must NOT be killed
  assert.equal(isMerlinOwnedVenvDaemon('C:\\Merlin\\venv\\Scripts\\merlin.exe', 'merlin chat -q "hi"', SCRIPTS), false)
  // an unrelated python script using the venv interpreter
  assert.equal(
    isMerlinOwnedVenvDaemon('C:\\Merlin\\venv\\Scripts\\python.exe', 'python C:\\tools\\import.py', SCRIPTS),
    false
  )
})

test('excludes exes outside the venv even when the cmdline mentions hindsight', () => {
  assert.equal(
    isMerlinOwnedVenvDaemon('C:\\Other\\pythonw.exe', 'pythonw -m hindsight_api.main --daemon', SCRIPTS),
    false
  )
})

test('prefix boundary: sibling dirs (ScriptsX) do not match', () => {
  assert.equal(hasWindowsPathPrefix('C:\\Merlin\\venv\\ScriptsX\\python.exe', SCRIPTS), false)
  assert.equal(hasWindowsPathPrefix('C:\\Merlin\\venv\\Scripts\\python.exe', SCRIPTS), true)
})

test('null/undefined fields never match', () => {
  assert.equal(isMerlinOwnedVenvDaemon(null, 'x', SCRIPTS), false)
  assert.equal(isMerlinOwnedVenvDaemon('C:\\Merlin\\venv\\Scripts\\pythonw.exe', null, SCRIPTS), false)
  assert.equal(isMerlinOwnedVenvDaemon(undefined, undefined, SCRIPTS), false)
})

// --- isExternalVenvHolder (#62311) ------------------------------------------

test('matches the autostart gateway shim (merlin.exe under venv Scripts)', () => {
  assert.equal(
    isExternalVenvHolder(
      'C:\\Merlin\\venv\\Scripts\\merlin.exe',
      '"C:\\Merlin\\venv\\Scripts\\merlin.exe" gateway run --external-supervisor',
      SCRIPTS
    ),
    true
  )
})

test('matches the dashboard scheduled task (python -m merlin_cli / -m merlin)', () => {
  assert.equal(
    isExternalVenvHolder(
      'C:\\Merlin\\venv\\Scripts\\python.exe',
      '"C:\\Merlin\\venv\\Scripts\\python.exe" -m merlin_cli.main dashboard',
      SCRIPTS
    ),
    true
  )
  assert.equal(
    isExternalVenvHolder('C:\\Merlin\\venv\\Scripts\\pythonw.exe', 'pythonw.exe -m merlin serve', SCRIPTS),
    true
  )
})

test('never matches an unrelated process that merely borrows the venv interpreter', () => {
  // a user's own script running on the venv python — NOT Merlin, must NOT be killed
  assert.equal(
    isExternalVenvHolder('C:\\Merlin\\venv\\Scripts\\python.exe', 'python C:\\tools\\import.py', SCRIPTS),
    false
  )
  // hindsight daemon is selected by isMerlinOwnedVenvDaemon, not here
  assert.equal(
    isExternalVenvHolder('C:\\Merlin\\venv\\Scripts\\pythonw.exe', 'pythonw -m hindsight_api.main --daemon', SCRIPTS),
    false
  )
})

test('never matches a process outside the venv, even with merlin in the cmdline', () => {
  // an editor / shell whose command line mentions the install root (#62445 regression guard)
  assert.equal(
    isExternalVenvHolder('C:\\Windows\\System32\\cmd.exe', 'cmd /c cd C:\\Merlin\\venv\\Scripts && dir', SCRIPTS),
    false
  )
  assert.equal(isExternalVenvHolder('C:\\Other\\merlin.exe', 'merlin gateway run', SCRIPTS), false)
})

test('sibling-dir and boundary safety for the external selector', () => {
  assert.equal(isExternalVenvHolder('C:\\Merlin\\venv\\ScriptsX\\merlin.exe', 'merlin gateway run', SCRIPTS), false)
  assert.equal(isExternalVenvHolder(null, 'merlin gateway run', SCRIPTS), false)
  assert.equal(isExternalVenvHolder('C:\\Merlin\\venv\\Scripts\\merlin.exe', null, SCRIPTS), false)
})
