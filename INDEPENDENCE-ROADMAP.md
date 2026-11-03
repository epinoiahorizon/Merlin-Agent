# Merlin Independence Roadmap — Epinoia Horizon

Purpose: make Merlin stand as its own agent — its own code, its own story,
its own measurements — instead of "a rebrand of someone else's agent".
Pairs with `BRAND-ORIGINALITY.md` (identity charter; attribution policy is
section 1a). Legal ground rule, never to be violated: `NOTICE` and `LICENSE`
are the complete, accurate provenance record. Independence means the *story,
voice, direction and eventually the code* are ours — not that the record is
scrubbed.

## Phase 0 — Identity surfaces (done 2026-11-03)

- [x] README + translations: Merlin-first hero; provenance confined to the
      bottom `License & Provenance` section; self-deprecating wording
      ("upstream is ahead of us", "we lag it") removed everywhere.
- [x] Landing page meta + hero: Merlin-only identity.
- [x] Docs header (`website/docs/index.mdx`): Merlin-first, provenance link only.
- [x] llms.txt identity block: Merlin-only.
- [x] Internal comments / fixtures doc: references to the old name reworded.
- [x] `@merlin/ui` dist: poster text stopgap-patched (source package still must
      be republished — Phase 2).

## Phase 1 — Provenance and ownership inventory (next)

Build the factual map of what is ours. Without it, independence is rhetoric.

1. Take an upstream reference tree (the 2026-09-30 import) and diff module by
   module against `main`.
2. Classify every top-level component: **Merlin-authored** (Atlas Portal,
   policy seal, PM, `@merlin/ui`, installer/MSIX, desktop hardening),
   **heavily modified**, or **upstream-derived (unchanged/little-changed)**.
3. Publish as `docs/PROVENANCE.md`: a table with LOC-changed percentages and
   who owns the tests. `NOTICE` stays the legal summary; this is the working
   map that drives Phases 3–5.

## Phase 2 — Own every pixel and every string

- Republish `@merlin/ui` from its source with scrubbed copy (the dist patch is
  a stopgap and will be overwritten on the next vendor update).
- Desktop app: verify window titles, about page, package metadata all say
  Merlin (charter checklist item).
- Persona gateway audit: every platform adapter's bot bio/about/handle text —
  no residual old identity; charter "voice" rule applies inside the agent's
  self-description (SOUL.md already clean).
- BotFather / platform control panels: manual renames (outside the repo).
- Docs site: grep-driven sweep for old-name phrasing in `website/docs` and
  `skills/` once per release (extend `scripts/check_release_artifact.py`
  coverage if new surfaces appear).

## Phase 3 — Differentiate by capability, measured

Charter rule: every technical claim ships with a real measurement. So
independence is proven by benchmarks Merlin owns:

- Lead with what only Merlin has: no-terminal Windows install, Atlas Portal,
  policy seal, PM quarantine policy, arcane skin system, MSIX update ownership.
- Grow `evals/` with Merlin-branded benchmarks (install success rate, cold
  start, compaction quality, skills-authoring success) and publish the numbers
  in docs and landing — being measurably good is the only durable way to stop
  being "the fork that lags".
- Port policy: from here on, upstream changes are *reviewed*, not blindly
  ported; take security fixes promptly, features only if they serve Merlin's
  roadmap. Update NOTICE wording when this policy fully lands.

## Phase 4 — Replace upstream-derived components (ladder order)

Order by (user-visible value × lowest coupling risk); core loop LAST:

1. Docs site + llms pipeline (already ours) → finish.
2. Vendored UI/design system → own the source end-to-end.
3. Installer / PM / update channels → already ours; document as such.
4. Gateway platform adapters → rewrite the lowest-quality ones first; new
   platforms are always Merlin-native.
5. Skills engine + memory curation → replace with Merlin's own design if
   Phase 3 measurements say the upstream design limits us.
6. Agent turn loop / tool schema → only after everything above; a clean-room
   core is the final step and the riskiest — it gets its own design doc, its
   own evals, and a coexistence window.

Each replacement: ships behind the existing test suite, updates `NOTICE` (and
`docs/PROVENANCE.md`) in the same PR, and deletes the paired upstream code —
no dual-architecture shims.

## Phase 5 — Release independence

- Own versioning and security response fully (MSIX/App Installer channel).
- Upstream becomes reference material, not a dependency: no mirror sync jobs,
  no "expect lag" language anywhere.
- When the last upstream-derived component is replaced, rewrite `NOTICE` to
  the final form (origin history preserved; no current upstream code) — the
  charter 1a rule still applies: the record updates, never disappears.