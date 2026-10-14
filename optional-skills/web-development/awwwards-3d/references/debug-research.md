# Deep Research: Debugged 3D Web Scenes (Case Study + Technical Facts)

Provenance: every fact below was verified live on 2026-10-14 during a real
debugging session (junepc WSL fixing Windows JM Merlin output). Nothing is
from memory or assumed. Working files preserved in this skill:

- `templates/minimal.html` — material study scene (torus knot, IBL, bloom)
- `templates/earth.html` — day/night Earth (custom shader, cloud layer)
- `references/material-study-debugged.html` — intermediate copies showing the
- `references/earth-debugged.html`   — debugging evolution, kept for diff study

## Case Study: The Triple-Stack Failure

A previous session shipped `awwwards_professional_example_fixed.html` claiming
"WebGPU renderer, ACESFilmic, post-processing, professional". Headless Chrome
proved it rendered NOTHING (stuck at "Initializing…", 0 draw calls). Three
independent fatal bugs were stacked — any one alone would kill the page:

### Bug 1 — Import map placed after the module script

```
<body>
  <script type="module"> import * as THREE from 'three'; ... </script>  ← runs, fails
  <script type="importmap"> { "imports": { "three": ... } } </script>   ← TOO LATE
</body>
```

Symptom: page loads, HTML/CSS visible, loader text forever, console error
`Failed to resolve module specifier "three"`. No other error — silent death of
the whole module graph.

Rule: import map must appear in the document BEFORE the first module script
that uses bare specifiers. Correct order: importmap in `<head>`, module script
at end of `<body>`.

### Bug 2 — `THREE.WebGPURenderer` from the main build is undefined

`new THREE.WebGPURenderer()` with `three` mapped to
`unpkg.com/three@0.170.0/build/three.module.js` throws immediately:
WebGPURenderer is NOT exported from the main build. It lives at
`three/addons/renderers/webgpu/WebGPURenderer.js` (TSL module graph, heavy).

Deeper trap: even correctly imported, WebGPURenderer cannot drive the
`examples/jsm/postprocessing` suite (EffectComposer, RenderPass,
UnrealBloomPass, FXAAShader, OutputPass) — that pipeline is WebGLRenderer-only.
The shipped file used WebGPURenderer + EffectComposer + UnrealBloomPass
together: architecturally impossible, proving it was never run once.

Rule: default `THREE.WebGLRenderer`. Only reach for WebGPU deliberately, with
the addons import path, and without the WebGL postprocessing suite.

### Bug 3 — HUD stats lied (renderer.info under EffectComposer)

With default `renderer.info.autoReset = true`, EACH composer pass resets the
info object. A stats panel reading `renderer.info` after `composer.render()`
reports only the final fullscreen-quad pass: **1 draw call, 2 triangles** —
even while the scene draws 30+ calls. The old file's "FPS 60 / Objects 0 /
Draw Calls 0" HUD was worse: a rAF counter with no scene behind it.

Honest pattern (proven in both templates):

```js
renderer.info.autoReset = false;      // accumulate across all passes
function tick(t) {
    renderer.info.reset();            // clear once, BEFORE render
    composer.render();                // all passes accumulate
    // ...read renderer.info.render.calls / .triangles now
}
```

### Bug 4 (found during Earth work) — double render after refactor

A patch left two `composer.render()` calls in the same tick — 2x GPU cost for
zero visual gain. Rule: after any refactor, grep the tick loop for duplicated
render calls. Render exactly once per frame.

## Verified External-Resource Facts

| Resource | Fact (verified live) |
|---|---|
| `unpkg.com/three@r/examples/textures/*` | **404 ALWAYS** — npm package does not include the textures folder. Any CDN-texture plan via unpkg is dead on arrival |
| `raw.githubusercontent.com/mrdoob/three.js/r170/examples/textures/planets/` | HTTP 200 + `access-control-allow-origin: *` — safe for cross-origin TextureLoader from `file://` |
| Texture set verified | `earth_atmos_2048.jpg` (512 KB), `earth_specular_2048.jpg`, `earth_normal_2048.jpg`, `earth_clouds_1024.png` (226 KB), `moon_1024.jpg` |
| Pin strategy | Pin the TAG (`r170`), not `dev` branch — dev moves under you |

## Day/Night Earth Shader Technique (in earth.html, verified rendering)

- World-space normal in vertex shader: `mat3(modelMatrix) * normal` — correct
  for a rotating mesh; sun direction stays fixed in world space, so the
  terminator stays put while the planet spins under it.
- Terminator softness: `smoothstep(-0.12, 0.25, dot(normal, sunDir))` — tune
  the two edges for twilight width.
- Night side: `dayCol * vec3(0.045, 0.06, 0.10)` — reuse the day texture,
  tinted cool. Cheaper and more coherent than a separate night-lights map.
- Atmospheric rim: `pow(1.0 - abs(dot(normal, viewDir)), 2.5)` fresnel,
  blue-scatter color, masked to the lit side. Subtle bloom (strength 0.28,
  threshold 0.88) finishes it.
- Axial tilt via `rotation.z = 23.4°`, cloud shell at radius ×1.012 rotating
  slightly faster than the surface.
- TextureLoader hard-failure surface: reject → write the error INTO the loader
  overlay (`TEXTURE LOAD FAILED <url>`). A silent black canvas is the enemy.

## Render-Proof Verification Method (headless Chrome via browser tools)

1. `new_tab('file:///...')`, sleep ~8–12 s (module fetch + texture load).
2. Probe `window.__renderer.info` (templates expose the handle):
   require `render.calls > 0` AND `render.triangles > 0`.
3. Require loader overlay `classList.contains('done') === true`.
4. `capture_screenshot()` — LOOK at it: geometry visible, no loading text.
5. Only then claim done. FPS reads low (1–20) in background headless tabs due
   to rAF throttling — that is environmental, not a bug; do not chase it.

## Anti-Pattern: "Skill created" ≠ work done

The failed session ALSO created a skill whose Templates table referenced four
files that were never built. Lessons:

- Never list a template in SKILL.md that does not exist on disk. Mark unbuilt
  work "NOT BUILT — do not claim they exist".
- Skill rules written from real failures (with the failure mode named) are the
  ones that prevent repeat mistakes. Write the rule the day the bug burns you.
