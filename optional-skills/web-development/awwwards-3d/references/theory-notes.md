# 3D Theory Notes — from real books (grows as reading progresses)

Sources (downloaded, readable, extraction verified):
- LearnOpenGL (Joey de Vries) — 523 pages — /home/nxelleai/books/learn-opengl.pdf
  (free, official: learnopengl.com/book/book_pdf.pdf)
- 3D Math Primer for Graphics & Game Development 2e (Dunn & Parberry) — 449 pages
  — /home/nxelleai/books/3d-math-primer.pdf

Honesty rule for this file: only add notes from sections actually read (cite
page numbers). Do not summarize from memory of "what the book probably says".

## From 3D Math Primer (read: ch3 p35-41, ch4 p47-59, ch10 p172-174)

- Coordinate spaces hierarchy (ch3): object space → inertial space → world
  space. Inertial space = object-space axes, world-space origin — the bridge
  that makes object↔world transforms a pure rotation. Useful mental model for
  camera rigs: position in world, orientation in object.
- Vectors describe relative positions/displacements (ch4); the zero vector is
  the additive identity — "a point has position, a vector has none" framing.
- Quaternions (§10.4, p162-174): a quaternion encodes angular displacement as
  rotation of θ radians about axis n — axis-angle in 4 numbers, but w ≠ θ and
  v ≠ n (eq 10.4). Why engines prefer them over Euler/matrix for orientation:
  no gimbal lock, slerp for smooth interpolation, cheap normalization.
  In three.js: `Quaternion.slerp` is what OrbitControls damping-style motion
  and keyframe rotation blending should use — never lerp Euler angles.

## From LearnOpenGL (read: TOC, §12 Colors p108, §13 Basic Lighting p113-117, PBR Theory p377-379)

- Phong lighting model (§13): three components — ambient (constant so nothing
  is pure black), diffuse (directional impact; the visually dominant term),
  specular (highlight, tends toward the LIGHT's color, not the object's).
  Direct mapping to our templates: key/rim DirectionalLights + IBL ambient in
  minimal.html are a physical-style upgrade of exactly these three terms.
- Colors as light fractions (§12): object color = fraction of light reflected
  per channel (a coral (1.0, 0.5, 0.31) reflects mostly red...). Explains why
  envMap-less metal turns black: metalness reflects via environment, and with
  no environment there is nothing to reflect.
- PBR (Part VI §43, p378+): the metallic/roughness workflow comes from Disney's
  research, adopted for real-time by Epic. MeshStandardMaterial/MeshPhysical
  (our templates) ARE this workflow — metalness 0-1 binary-ish by convention,
  dielectrics ~0.04 base reflectivity. Prerequisites the book lists before PBR:
  framebuffers, cubemaps, gamma correction, HDR, normal mapping → in WebGL
  terms: env maps + tone mapping (we already ship ACESFilmic + sRGB output).

## Applicable-to-skill rules (distilled)

1. Rotation blending = quaternion slerp, never Euler lerp (Primer §10.4).
2. Specular highlights tint toward light color; keep light colors warm/cool
   deliberately — pure white lights flatten materials (Phong §13).
3. Never fully black shadows: keep a small ambient/IBL floor (Phong §13).
4. metalness>0 without envMap = black blob, now with the WHY (PBR reflectance).
5. Object/inertial/world space distinction (Primer ch3) when rigging cameras
   that follow moving objects: parent to inertial-equivalent groups.
