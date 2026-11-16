#!/usr/bin/env node
// Runs website/scripts/extract-skills.py and generate-llms-txt.py before
// docusaurus build/start so that:
//   - website/static/api/skills.json (lazy-fetched by src/pages/skills/index.tsx)
//   - website/static/api/skills-meta.json (sidecar metadata for the Skills Hub)
//   - website/static/llms.txt (agent-friendly short docs index)
//   - website/static/llms-full.txt (full docs concat for LLM context)
// all exist without contributors remembering to run Python scripts manually.
// CI workflows still run the extraction explicitly, which is a no-op duplicate
// but matches their historical behaviour.
//
// We also try to pull a fresh copy of skills-index.json (the unified
// multi-source catalog) from the live docs site if it's not already on disk.
// That way local `npm run build` doesn't have to wait on
// scripts/build_skills_index.py crawling every skill source — which takes
// several minutes and burns GitHub API quota — but still gets the same
// 2000+ external skills the deployed site has.
//
// If python3 or its deps (ruamel.yaml) aren't available on the local machine, we
// fall back to writing an empty skills.json so `npm run build` still
// succeeds — the Skills Hub page just shows an empty state, and llms.txt
// generation is skipped. CI always has the deps installed, so production
// deploys get real data.

import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync, existsSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const websiteDir = resolve(scriptDir, "..");
const repoRoot = resolve(websiteDir, "..");
const extractScript = join(scriptDir, "extract-skills.py");
const llmsScript = join(scriptDir, "generate-llms-txt.py");
const cronBlueprintsScript = join(scriptDir, "extract-automation-blueprints.py");
const pluginsScript = join(scriptDir, "extract-plugins.py");
const pluginStarsScript = join(scriptDir, "fetch-plugin-stars.py");
const outputFile = join(websiteDir, "static", "api", "skills.json");
const pluginsOutputFile = join(websiteDir, "static", "api", "plugins.json");
const pluginsMetaOutputFile = join(websiteDir, "static", "api", "plugins-meta.json");
const unifiedIndexFile = join(websiteDir, "static", "api", "skills-index.json");
const UNIFIED_INDEX_URL =
  "https://withmerlin.online/docs/api/skills-index.json";
const UNIFIED_INDEX_MAX_AGE_MS = 24 * 60 * 60 * 1000; // 24h

// The Windows install ships `python` with no `python3` alias, so spawning
// "python3" directly made every local docs build emit an empty catalog while
// the build itself stayed green. Resolve once, prefer explicit configuration,
// and let the caller decide whether absence is fatal.
function resolvePython() {
  const candidates = [process.env.MERLIN_PYTHON, "python3", "python", "py"].filter(Boolean);
  const usable = [];

  for (const cmd of candidates) {
    const probe = spawnSync(cmd, ["-c", "import sys; sys.exit(0)"], { stdio: "ignore" });
    if (!probe.error && probe.status === 0) usable.push(cmd);
  }

  // An interpreter that runs is not enough: the extractors need ruamel.yaml, and
  // a bare python silently produces empty catalogs. Prefer one that can import
  // it, and only fall back to a bare interpreter when none can.
  for (const cmd of usable) {
    const deps = spawnSync(cmd, ["-c", "import ruamel.yaml"], { stdio: "ignore" });
    if (!deps.error && deps.status === 0) return cmd;
  }

  return usable[0] ?? null;
}

const PYTHON = resolvePython();

// Locally, degrading keeps contributors without Python unblocked. In CI a
// missing generator means the published catalog is wrong, so fail loudly there
// instead of shipping an empty snapshot to every installed app.
const STRICT_CATALOG =
  process.env.CI === "true" || process.env.MERLIN_CATALOG_STRICT === "1";

function skipOrFail(label, reason) {
  const message = `[prebuild] ${label} skipped (${reason})`;
  if (STRICT_CATALOG) throw new Error(message);
  console.warn(message);
}

function writeEmptyFallback(reason) {
  if (STRICT_CATALOG) {
    throw new Error(
      `[prebuild] extract-skills.py skipped (${reason}); refusing to publish an empty ` +
        `skills.json in CI. Install python3 + ruamel.yaml in the build image.`,
    );
  }
  mkdirSync(dirname(outputFile), { recursive: true });
  writeFileSync(outputFile, "[]\n");
  console.warn(
    `[prebuild] extract-skills.py skipped (${reason}); wrote empty skills.json. ` +
      `Install python3 + ruamel.yaml locally for a populated Skills Hub page.`,
  );
}

function runPython(script, label) {
  if (!existsSync(script)) {
    console.warn(`[prebuild] ${label} skipped (script missing)`);
    return false;
  }
  if (!PYTHON) {
    skipOrFail(label, "no python interpreter found");
    return false;
  }
  const r = spawnSync(PYTHON, [script], { stdio: "inherit", cwd: websiteDir });
  if (r.error && r.error.code === "ENOENT") {
    skipOrFail(label, `${PYTHON} not found`);
    return false;
  }
  if (r.status !== 0) {
    console.warn(`[prebuild] ${label} exited with status ${r.status}`);
    return false;
  }
  return true;
}

async function ensureUnifiedIndex() {
  // If we have a recent copy on disk, trust it.
  if (existsSync(unifiedIndexFile)) {
    try {
      const age = Date.now() - statSync(unifiedIndexFile).mtimeMs;
      if (age < UNIFIED_INDEX_MAX_AGE_MS) {
        return true;
      }
      console.log(
        `[prebuild] skills-index.json is ${(age / 3600000).toFixed(1)}h old; ` +
          `refreshing from ${UNIFIED_INDEX_URL}`,
      );
    } catch {
      // fall through to re-fetch
    }
  }

  try {
    const resp = await fetch(UNIFIED_INDEX_URL, {
      headers: { accept: "application/json" },
    });
    if (!resp.ok) {
      console.warn(
        `[prebuild] skills-index.json fetch returned HTTP ${resp.status}; ` +
          `using local copy if any`,
      );
      return existsSync(unifiedIndexFile);
    }
    const text = await resp.text();
    // Sanity check: must be valid JSON with a skills array
    try {
      const parsed = JSON.parse(text);
      if (!parsed || !Array.isArray(parsed.skills)) {
        console.warn(
          "[prebuild] skills-index.json from live site has no skills array; ignoring",
        );
        return existsSync(unifiedIndexFile);
      }
    } catch (e) {
      console.warn(`[prebuild] skills-index.json from live site is not valid JSON: ${e}`);
      return existsSync(unifiedIndexFile);
    }
    mkdirSync(dirname(unifiedIndexFile), { recursive: true });
    writeFileSync(unifiedIndexFile, text);
    console.log(
      `[prebuild] downloaded skills-index.json from ${UNIFIED_INDEX_URL} ` +
        `(${(text.length / 1024).toFixed(0)} KB)`,
    );
    return true;
  } catch (e) {
    console.warn(`[prebuild] skills-index.json fetch failed: ${e}`);
    return existsSync(unifiedIndexFile);
  }
}

// 0) Pull unified index if we don't have a fresh one.
await ensureUnifiedIndex();

// 1) skills.json — required for the Skills Hub page.
if (!existsSync(extractScript)) {
  writeEmptyFallback("extract script missing");
} else {
  if (!PYTHON) {
    writeEmptyFallback("no python interpreter found");
  } else {
    const r = spawnSync(PYTHON, [extractScript], {
      stdio: "inherit",
      cwd: websiteDir,
    });
    if (r.error && r.error.code === "ENOENT") {
      writeEmptyFallback(`${PYTHON} not found`);
    } else if (r.status !== 0) {
      writeEmptyFallback(`extract-skills.py exited with status ${r.status}`);
    }
  }
}

// 2) llms.txt + llms-full.txt — agent-friendly docs entrypoints. Non-fatal.
runPython(llmsScript, "generate-llms-txt.py");

// 3) automation-blueprints-index.json — Automation Blueprints catalog page. Non-fatal; the page
//    renders an empty state if the generator can't run.
runPython(cronBlueprintsScript, "extract-automation-blueprints.py");

// 4a) plugin-stars.json — GitHub star counts for catalog ranking. Reuse-only here
//     (live site copy via one CDN GET, else on-disk, else empty); GitHub itself is
//     probed only by the scheduled skills-index workflow. Never fails the build.
runPython(pluginStarsScript, "fetch-plugin-stars.py");

// 4) plugins.json + plugins-meta.json — Plugin Catalog page. The script itself
//    degrades gracefully (empty catalog, exit 0) when plugin-catalog/ is absent;
//    if python3 is missing entirely, write the same empty fallback so the page
//    renders its "just getting started" state instead of a fetch error.
if (!runPython(pluginsScript, "extract-plugins.py")) {
  mkdirSync(dirname(pluginsOutputFile), { recursive: true });
  writeFileSync(pluginsOutputFile, "[]\n");
  writeFileSync(
    pluginsMetaOutputFile,
    JSON.stringify({
      generatedAt: new Date().toISOString(),
      total: 0,
      byTier: { official: 0, community: 0 },
      removedCount: 0,
    }) + "\n",
  );
  console.warn("[prebuild] wrote empty plugins.json fallback");
}
