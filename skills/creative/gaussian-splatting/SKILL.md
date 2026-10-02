---
name: gaussian-splatting
description: "Use for 3D gaussian splatting: train, edit, convert, serve."
version: 0.1.0
author: Merlin Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  merlin:
    tags: [3dgs, gaussian-splatting, nerf, colmap, supersplat, gltf, novel-view-synthesis]
    related_skills: [manim-video, claude-design]
---

# Gaussian Splatting (3DGS)

## When to Use

- Reconstruct a 3D scene from photos/video (capture → COLMAP → train → edit → export)
- Task mentions .ply / .splat / SPZ / KHR_gaussian_splatting assets, floaters cleanup, or SuperSplat
- Asked to build a splat viewer/editor (Three.js, Babylon, self-hosted SuperSplat)
- Don't use for plain point clouds (no photometric training), meshes, or NeRF training

## What it is

Explicit scene representation: millions of 3D Gaussians, each with 6 attribute groups —
position μ (3 floats), rotation quaternion q (4), log-scale s (3), opacity α (1),
and view-dependent color as spherical harmonics (SH degree 3 ⇒ 16 coefficients × 3 channels = 48).
Covariance is never stored directly; it is composed `Σ = R S Sᵀ Rᵀ` so gradient descent
always yields a valid positive semi-definite matrix. Scenes run ~100k Gaussians (SfM seed)
→ 1–5M after densification. No MLP: rendering is GPU rasterization at 100+ FPS; training
10–30 min on an RTX 4090 for a typical scene.

## Pipeline (the 2026 production stack)

1. **Capture** — 20–50 photos / video frames; move slowly, parallax over every subject, avoid motion blur
2. **Poses** — COLMAP or GLOMAP (SfM) ⇒ camera extrinsics + intrinsics + sparse point cloud
3. **Train** — `nerfstudio` splatfacto / `gsplat` / inria `gaussian-splatting` / PostShot desktop
4. **Edit** — SuperSplat (browser editor; a self-hosted build works — bundled build
   is a PWA with the spz/Niantic codec) — delete floaters, crop, segment
5. **Export** — `.ply` (raw/portable) · `.splat` (PlayCanvas quantized) · glTF `KHR_gaussian_splatting`
   (Khronos 2026 RC) · OpenUSD 26.03 `UsdVolParticleField3DGaussianSplat`
6. **View** — Three.js GaussianSplats3D, Babylon.js 9, Unreal, Cesium, Vision Pro

## Rendering math (what makes it work)

- 3D Gaussian → 2D screen splat: `Σ' = J W Σ Wᵀ Jᵀ` (W = world-to-camera, J = Jacobian of
  perspective projection at the splat center — EWA-splatting first-order approx)
- Per pixel, depth-sorted alpha compositing front-to-back:
  `C = Σᵢ αᵢ Tᵢ cᵢ`, `Tᵢ = Π_{j<i}(1−αⱼ)`, `αᵢ = opacityᵢ · exp(−½ dᵀ Σ'⁻¹ d)`
- Same volumetric equation NeRF integrates — hence equivalent quality, minus per-pixel MLP queries
- Color at view direction d: evaluate SH basis at d, dot with learned coefficients
  (degree 0 = flat diffuse; degree 3 captures specular/sheen)

## Training dynamics

Photometric loss (L1 + D-SSIM), Adam, ~30k iterations. Adaptive density control every N iters:
- **clone**: high positional gradient + small scale (under-reconstruction)
- **split**: high gradient + large scale, into two smaller Gaussians (over-reconstruction)
- **prune**: opacity below threshold → drop

Unconstrained params mapped through activations at render time (log-scale, logit-opacity,
quaternion normalized) — the standard parameterization in every implementation.

## Quickstart (this machine's environment)

```bash
pip install nerfstudio gsplat            # Meta's gsplat CUDA rasterizer
ns-download-data example                  # or your own COLMAP'd capture
ns-train splatfacto --data <dir>          # 10–30 min on decent GPU
```

## Executable proof: scripts/toy2d.py

The 2D toy is now a runnable script (in-repo: skills/creative/gaussian-splatting/scripts/toy2d.py,
commit cfd084c7; needs torch+numpy CPU only, ~30s):

    python toy2d.py

Verified result (2026-10-02): step 199 mse 0.0043, 91.5% pixels within 0.2 of
target, PASS — the formula chain (Σ=R diag(s²)Rᵀ → exp(−½dᵀΣ⁻¹d) → depth-sorted
alpha blend → Adam) is executable evidence, not prose. Re-run after any touch
of the skill's math sections.

## SuperSplat (editor)

SuperSplat is the browser editor for splat cleanup: floater removal, crop,
segment, transform, then export .ply/.splat/SPZ/glTF. Options: the hosted app
or a self-hosted build (it ships as a PWA — index.html, sw.js, spz codec bundle;
any static server pointed at the dir works). Detection lesson: a Windows-side
merlin install check can show NO-MERLIN when the install actually lives in the
user's WSL — probe via `wsl -e bash -lc` before concluding absence.

## Pitfalls

- Training needs CUDA; CPU-only = the 2D toy or viewer-only work (Three.js can render 2M+ splats client-side)
- Baked lighting: 3DGS bakes illumination into SH — relighting needs GaussianShader-class variants
- Memory: 1–5M Gaussians × 59 floats ≈ hundreds of MB/scene — quantize (.splat/SPZ) for web delivery
- Secondary rays (reflections/refractions) are weak in vanilla 3DGS
- COLMAP feature matching struggles on texture-less/reflective surfaces — add texture or masks

## References

- Kerbl et al., SIGGRAPH 2023 "3D Gaussian Splatting for Real-Time Radiance Field Rendering" (the paper)
- arXiv 2510.18101 — "From Volume Rendering to 3DGS: Theory and Applications" (tutorial survey)
- IPOL 2025 "Gaussian Splatting: An Introduction" (1D→2D→3D pedagogical derivation)
- ai-engineering.academy/learn/04-computer-vision/22-3d-gaussian-splatting (from-scratch code)
- 3dgs.zip — exhaustive extension catalog
