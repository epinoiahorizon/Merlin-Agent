#!/usr/bin/env node
// Registry-resolution guard: every package the lockfile pins must exist as a
// downloadable tarball. Catches the class of failure a Malaysia user hit first
// on 2026-10-10: a repo-wide rename (hermes->merlin) rewrote third-party names
// inside package-lock.json; dev machines never noticed (reuse path skips npm
// ci) and the scheduled E2E ran no release tags, so the first signal was a
// real user's npm E404 at "Building the merlin command and apps".
//
// What it checks (no install, seconds, no network writes):
//   1. every lockfile entry's tarball URL returns HTTP 200 (HEAD);
//   2. every lockfile entry's integrity hash matches the registry's published
//      digest (proves the pinned bytes are the bytes npm serves).
// Only http(s) registry URLs are checked; file:/ link:/ workspace entries are
// local by definition.
//
// Usage: node scripts/build/check-registry-resolution.mjs [lockfile...]
// Exit 0 = all resolvable; exit 1 = prints the offending entries.

import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { parseArgs } from 'node:util'
import https from 'node:https'

const { positionals } = parseArgs({
  allowPositionals: true,
  args: process.argv.slice(2),
})
const lockfiles = positionals.length ? positionals : ['package-lock.json']

function getJsonHead(url, method) {
  return new Promise(resolve => {
    const req = https.request(url, { method }, res => {
      // Drain (HEAD has no body, but a GET must be consumed to free the socket).
      res.resume()
      resolve({ status: res.statusCode, etag: res.headers.etag || '' })
    })
    req.on('error', e => resolve({ status: 0, etag: '', error: String(e) }))
    req.on('clientRst', () => resolve({ status: 0, etag: '', error: 'reset' }))
    req.setTimeout(20_000, () => { req.destroy(); resolve({ status: 0, etag: '', error: 'timeout' }) })
    req.end()
  })
}

// Run async work over items with bounded concurrency; keeps a 1.6k-URL sweep
// in seconds instead of minutes (sequential × RTT was a 4-minute hang).
async function pool(items, limit, fn) {
  const results = new Array(items.length)
  let next = 0
  async function worker() {
    while (next < items.length) {
      const i = next++
      results[i] = await fn(items[i], i)
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker))
  return results
}

function sriToHex(sri) {
  const m = /^(sha512|sha1|sha256)-([A-Za-z0-9+/=]+)$/.exec(sri || '')
  if (!m) return null
  const raw = Buffer.from(m[2], 'base64')
  if (m[1] === 'sha512') return raw.toString('hex') // registry integrity is base64 of digest; compare raw digests directly
  return raw.toString('hex')
}

function registryDigestMatches(integrity, etag) {
  // npm tarball responses carry ETag = "sha512-<base64>" (quoted, strong).
  const m = /"(sha512|sha1|sha256)-([A-Za-z0-9+/=]+)"/.exec(etag || '')
  if (!m || !integrity) return null // no ETag: cannot compare, count as unverifiable
  const a = Buffer.from(m[2], 'base64')
  const sri = /^(sha512|sha1|sha256)-([A-Za-z0-9+/=]+)$/.exec(integrity)
  if (!sri || sri[1] !== m[1]) return null
  return a.equals(Buffer.from(sri[2], 'base64'))
}

let bad = 0
let checked = 0
for (const lockPath of lockfiles) {
  const lock = JSON.parse(readFileSync(lockPath, 'utf8'))
  const packages = lock.packages || {}
  const entries = Object.entries(packages).filter(([, p]) => {
    const r = p.resolved || ''
    return /^https:\/\/registry\.npmjs\.org\//.test(r) && !p.link
  })
  console.log(`${lockPath}: ${entries.length} registry-resolved packages`)
  // Same URL can appear under multiple keys (aliases/dups); check each once.
  const seen = new Map()
  for (const [key, p] of entries) {
    const url = p.resolved
    if (seen.has(url)) continue
    seen.set(url, key)
  }
  const probes = [...seen]
  const outcomes = await pool(probes, 50, async ([url, key]) => {
    const entry = packages[key]
    const head = await getJsonHead(url, 'HEAD')
    checked++
    if (head.status !== 200) {
      bad++
      console.error(`  MISSING  ${key} -> ${url} (HTTP ${head.status}${head.error ? ', ' + head.error : ''})`)
      return
    }
    const match = registryDigestMatches(entry.integrity, head.etag)
    if (match === false) {
      bad++
      console.error(`  HASH MISMATCH  ${key} -> ${url}`)
    }
  })
  await Promise.all(outcomes)
}

console.log(`checked ${checked} distinct tarball URLs`)
if (bad) {
  console.error(`REGISTRY GUARD: ${bad} broken pin(s) — fresh installs will E404`)
  process.exit(1)
}
console.log('REGISTRY GUARD: all pins resolve and match registry digests')