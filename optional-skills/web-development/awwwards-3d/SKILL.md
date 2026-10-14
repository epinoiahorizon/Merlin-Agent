---
name: awwwards-3d
description: "Build cinematic Awwwards-style 3D web scenes that render."
version: 2.0.0
author: 'June Arthov (june-arthov), Merlin Agent'
license: MIT
platforms: [linux, macos, windows]
metadata:
  merlin:
    tags: [webgl, threejs, 3d, web-development, creative, verification]
    category: web-development
    related_skills: [scrollcraft]
---

# Awwwards 3D Skill

Builds single-file Three.js scenes (hero objects, planets, material studies)
in the Awwwards lineage — IBL lighting, ACES tone mapping, bloom — and treats
render-proof verification as part of definition-of-done. Hardened from a real
failure: a prior session shipped a "fixed professional" 3D page that rendered
nothing (three stacked fatal bugs, never opened in a browser). This skill
exists so that never repeats.

Delivers: one self-contained `.html` file with an import map, a scene built
from bundled verified templates, and headless-browser proof (screenshot +
non-zero draw calls) before "done" is claimed.

## When to Use

Use for: "Awwwards-style 3D", "WebGL hero", "3D landing hero", "planet/globe
scene", "interactive 3D showcase", "make it look like aengel.io / Lusion /
Active Theory", or any Three.js scene request on the open web.

Do not use for: scroll-timeline landing pages (use `scrollcraft`), WebGPU/TSL
computes, or React Three Fiber projects — this skill is deliberately
WebGLRenderer-first and framework-free for portability.

## Prerequisites

- Browser tooling (`browser_navigate` or the browser harness) for render
  verification — the Iron Law below is unenforceable without it.
- None of the steps need npm, node, or a build step. Scenes load Three.js r170
  from unpkg via import map at runtime.

## How to Run

1. Copy the closest template from `templates/` — never start from an empty
   file. `minimal.html` for material-study heroes, `earth.html` for
   planet/globe scenes (day/night shader, clouds, atmospheric rim).
2. Edit only what the request changes: hero geometry, material colors, HUD
   copy, camera framing. Keep the scaffolding (import map position, renderer
   setup, stats pattern, single-render tick) untouched unless the request
   demands it.
3. Verify per the checklist below, then deliver the file path plus the proof
   (screenshot + stats readout).

## Quick Reference

- Import map MUST sit in `<head>` before the first `<script type="module">`.
- `THREE.WebGLRenderer` by default. `WebGPURenderer` is NOT exported from the
  main build and the postprocessing addon suite is WebGL-only.
- Honest stats: `renderer.info.autoReset = false`, `renderer.info.reset()`
  before `composer.render()`, read stats after.
- Render exactly once per frame — grep the tick loop after refactors.
- Textures: unpkg ships NO texture files (404 forever). Use
  `https://raw.githubusercontent.com/mrdoob/three.js/r170/examples/textures/...`
  (verified HTTP 200, CORS `*`).
- Full case study with code-level detail:
  [references/debug-research.md](references/debug-research.md)

## Procedure

1. Classify the request against the template table; pick or extend.
2. Copy the template, apply edits, save as a single `.html`.
3. Open in a real browser via tooling; wait for module + texture load
   (8–12 s), then probe the exposed `window.__renderer.info`:
   `render.calls > 0` AND `render.triangles > 0`.
4. Require the loader overlay hidden (`#load.done`).
5. Capture a screenshot and look at it: geometry visible, no loading text.
6. Report the file path + screenshot + stats. FPS reads 1–20 in background
   headless tabs (rAF throttling) — environmental, not a defect; do not chase.

## Pitfalls

- Placing the import map after the module script silently kills every import
  — the page looks fine and renders nothing. Position is load-bearing.
- Mixing `WebGPURenderer` with EffectComposer/UnrealBloomPass is impossible;
  that combo signals the file was never executed.
- Stats read AFTER `composer.render()` with default `autoReset` report only
  the last fullscreen-quad pass (1 call, 2 tris) — the HUD lies silently.
- An FPS/objects HUD driven by a bare rAF counter with no scene is fiction;
  every number on screen must come from `renderer.info` or real timers.
- Listing templates that don't exist on disk ("NOT BUILT" must be marked) —
  a skill that references phantom files manufactures its own failures.

## Verification

- [ ] Page opened in a real browser; screenshot shows rendered geometry
- [ ] `window.__renderer.info.render.calls > 0` and `.triangles > 0`
- [ ] Loader overlay hidden; zero console/module-resolution errors
- [ ] Stats HUD populated from `renderer.info` (autoReset disabled pattern)
- [ ] Resize handler updates camera + renderer + composer
- [ ] Only one `composer.render()` call per tick
