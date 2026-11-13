#!/usr/bin/env node
/**
 * Pin every GitHub Action reference in .github/workflows to a commit SHA.
 *
 * Why: a tag like `actions/checkout@v4` is a mutable pointer. Whoever controls that repository can move
 * it to different code, and every workflow here — including the installers we publish — would run the new
 * code with our secrets. A 40-character SHA cannot be moved.
 *
 * The tag is kept as a trailing comment so a human can still read the file and Dependabot can still bump it.
 *
 *   node scripts/pin-actions.mjs             # rewrite in place
 *   node scripts/pin-actions.mjs --dry-run   # report only
 *
 * Idempotent: a second run reports "0 to pin". Local actions (./…) and docker:// refs are left alone.
 */
import { readdirSync, readFileSync, writeFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

const dryRun = process.argv.includes('--dry-run');
const ROOT = '.github/workflows';
const SHA = /^[0-9a-f]{40}$/;

const token = (() => {
  try {
    return execFileSync('gh', ['auth', 'token'], { encoding: 'utf8' }).trim();
  } catch {
    return process.env.GITHUB_TOKEN || process.env.GH_TOKEN || '';
  }
})();
if (!token) {
  console.error('no GitHub token: run `gh auth login` or set GITHUB_TOKEN');
  process.exit(1);
}

const resolveCache = new Map();

async function shaFor(repo, ref) {
  const key = `${repo}@${ref}`;
  if (resolveCache.has(key)) return resolveCache.get(key);
  const url = `https://api.github.com/repos/${repo}/commits/${encodeURIComponent(ref)}`;
  const res = await fetch(url, {
    headers: { authorization: `Bearer ${token}`, accept: 'application/vnd.github+json', 'user-agent': 'merlin-pin-actions' },
  });
  if (!res.ok) throw new Error(`${key}: HTTP ${res.status}`);
  const body = await res.json();
  const sha = body.sha;
  if (!SHA.test(sha || '')) throw new Error(`${key}: unexpected sha ${sha}`);
  resolveCache.set(key, sha);
  return sha;
}

function workflowFiles(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) out.push(...workflowFiles(path));
    else if (/\.ya?ml$/.test(name)) out.push(path);
  }
  return out;
}

const LINE = /^(\s*(?:-\s+)?uses:\s*)([^\s#]+)(\s*#\s*(.*))?$/;
let pinned = 0;
let already = 0;
const failures = [];
const touched = [];

for (const file of workflowFiles(ROOT)) {
  const original = readFileSync(file, 'utf8');
  // Workflow files here were authored on Windows and carry CRLF. Splitting on \n alone leaves a trailing
  // \r that silently defeats every $ anchor below, which is how "168 unpinned" became "13" on the first
  // dry run: most lines never matched. Split on the real line ending and write the same ending back.
  const crlf = original.includes('\r\n');
  const lines = original.split(/\r?\n/);
  let changed = false;

  for (let i = 0; i < lines.length; i++) {
    const match = LINE.exec(lines[i]);
    if (!match) continue;
    const [, prefix, rawRef, , existingComment] = match;
    if (rawRef.startsWith('./') || rawRef.startsWith('docker://')) continue;

    const at = rawRef.lastIndexOf('@');
    if (at === -1) {
      failures.push(`${file}:${i + 1} uses without @ref: ${rawRef}`);
      continue;
    }
    const spec = rawRef.slice(0, at);
    const ref = rawRef.slice(at + 1);
    if (SHA.test(ref)) {
      already += 1;
      continue;
    }

    // Reusable workflows carry a path after the repo: owner/repo/.github/workflows/x.yml@ref
    const [owner, repo] = spec.split('/');
    if (!owner || !repo) {
      failures.push(`${file}:${i + 1} cannot parse ${rawRef}`);
      continue;
    }

    try {
      const sha = await shaFor(`${owner}/${repo}`, ref);
      const comment = existingComment ? `# ${existingComment}` : `# ${ref}`;
      lines[i] = `${prefix}${spec}@${sha} ${comment}`;
      changed = true;
      pinned += 1;
    } catch (error) {
      failures.push(`${file}:${i + 1} ${error.message}`);
    }
  }

  if (changed) {
    touched.push(file);
    if (!dryRun) writeFileSync(file, lines.join(crlf ? '\r\n' : '\n'));
  }
}

console.log(`${dryRun ? 'would pin' : 'pinned'}: ${pinned} | already pinned: ${already} | files: ${touched.length}`);
if (failures.length) {
  console.error('could not resolve:\n  ' + failures.join('\n  '));
  process.exit(1);
}
