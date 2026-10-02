---
title: "Improvement Loop — Turn each session's friction into persistent skill upgrades"
sidebar_label: "Improvement Loop"
description: "Turn each session's friction into persistent skill upgrades"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Improvement Loop

Turn each session's friction into persistent skill upgrades.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/software-development/improvement-loop` |
| Version | `1.0.0` |
| Author | June Arthov (june-arthov), Merlin Agent |
| License | MIT |
| Platforms | linux, macos, windows |
| Tags | `meta-skill`, `continuous-improvement`, `lessons`, `compounding` |
| Related skills | [`merlin-agent-skill-authoring`](../../bundled/software-development/software-development-merlin-agent-skill-authoring.md), [`systematic-debugging`](../../bundled/software-development/software-development-systematic-debugging.md) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Merlin loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Improvement Loop Skill

Meta-skill: turns one-off work into permanent capability. Without it, hard-won
troubleshooting victories dissolve at session end and we re-pay the same tax
forever. With it, **every session makes the next session cheaper** — this is the
only mechanism by which an agent genuinely compounds (skills are the memory;
process discipline is the multiplier).

## When to Use

- Mid-session: a probe, workaround, or fix that a future you could not
  recreate without pain (>2 tool attempts, or one user correction).
- A user correction reveals a wrong assumption — fix the source, not just this turn.
- A tool/environment quirk (quoting, paths, auth) cost repeated attempts.
- Don't use for: one-off trivia no future session would hit; ephemeral
  debugging state (session_search owns that).

## Prerequisites

Only Merlin tools (`skill_manage`, `search_files`, `terminal`) — no extra env
vars, keys, or installs.

## How to Run

All steps run through `skill_manage` / `search_files` / `terminal` directly in
session; a weekly sweep is a small batch of `skill_manage` operations (steps 4–6).

## Quick Reference

- Capture: draft lesson the moment pain exceeds two attempts.
- Classify: procedure → skill; environment fact → Pitfalls; preference → user memory.
- Write: imperative rule + why; no incident logs, no "be careful".
- Consolidate: `search_files` the target skill; remove superseded wording in the same call.
- Verify: re-run command stored with the lesson; a lesson without a re-run path is a TODO, not a rule.
- Sweep: weekly; dedupe; promote recurring task-skill patterns upward.

## Procedure

1. **Capture at the moment of pain, not after** — every fix that takes >2 tool
   attempts, or one user correction, spawns a candidate lesson immediately:
   *trigger → wrong assumption → right procedure*, one line each.
   Done when: the lesson exists in a file or skill before the next unrelated step.

2. **Classify before writing** —
   - *Universal procedure* → new/updated skill (in-repo if it ships to all
     users, user-local for personal workflow)
   - *Environment-specific fact* → the task skill's `Pitfalls` section
   - *One-time user preference* → user profile memory (tiny, high-signal)
   - *Not yet verified* → a TODO inside the relevant skill, never a hunch
     logged as fact
   Done when: the lesson's home is decided and written to.

3. **Write the lesson as an imperative rule + why** — not an incident log.
   - Good: "scp a script file instead of nested ssh quoting on Windows hosts;
     wsl.exe mangles nested quotes."
   - Bad: "2026-10-02 markpc ssh had issues with nested quotes."
   Done when: a reader can follow the rule without knowing this session happened.

4. **Consolidate, don't accumulate** — before adding a rule, `search_files` the
   skill for the old wording it replaces and remove it **in the same
   skill_manage call**. A skill bloated with obsolete rules is worse than no
   skill: the wrong one gets followed.
   Done when: the skill contains no duplicate/contradictory wording
   (search-verified).

5. **Verify the upgrade** — a lesson qualifies as learned only when re-running
   the original scenario returns the expected result with the rule applied.
   Where the re-run is expensive, store the **exact re-run command** next to
   the lesson so the next session can execute it.
   Done when: re-run passes, or the note explicitly says how to re-verify later.

6. **Weekly sweep** (or at the start of a session continuing a project):
   - Read the newest lessons in the most-used skills.
   - Delete duplicates; merge overlapping rules.
   - Promote recurring patterns from task skills into broader ones (e.g.
     quoting habits → the general ops skill) via `skill_manage` operations.
   - Confirm each lesson's re-run criterion still matches reality (tools drift).
   Done when: diffs show only the sweep's own changes; no unexplained growth.

## The 100× Math

Skills compound only under three conditions:

- **Trigger quality**: descriptions that actually fire (≤60 chars,
  trigger-first, ends with a period) — otherwise the right skill never loads
  and the lesson never gets read.
- **Imperative body**: rules, not logs; completion criteria; helper scripts in
  `scripts/` whenever the procedure is mechanical.
- **Pruning**: a rule must die the day a better one replaces it — sediment
  poisons future routing more surely than missing rules.

An agent that follows this loop approaches strongest-operator status within
2–3 weeks of real work — not because it thinks harder, but because it never
pays the same toll twice, and its tolls are written down where the next
session actually reads them.

## In-Repo Deployment (this skill's own rule, by example)

When a lesson proves itself and applies to **every user** of the harness, the
loop's final step is `git`: copy the evolved skill into
`skills/<category>/<name>/SKILL.md` of the merlin-agent repo, add
`tests/skills/test_<skill>_skill.py` asserting the mechanical subset (see
below), regen docs per `merlin-agent-skill-authoring`, and ship the commit.
Session wisdom that stays user-local is interest; in-repo skill wisdom is
principal.

### Mechanical invariants (asserted by the in-repo test)

- frontmatter starts at byte 0 and parses as a YAML mapping
- `description`: present, ≤60 chars, ends with ".", no marketing words
- no machine-local paths (user home or drive-letter constants)
- section order: When to Use → Procedure → Pitfalls → Verification
- `author` credits the human first
- every `related_skills` entry resolves in-repo

## Pitfalls (including deploy-step hazards)

- Logging incidents instead of rules — the incident is data; the rule is the asset.
- Skill sprawl (one skill per incident) — extend the closest existing skill instead.
- Trusting unverified lessons — a hunch in a skill poisons future sessions;
  mark confidence honestly (verified / unverified) in the rule's comment.
- Capturing after session end — memory decays; capture mid-work.
- Machine-local paths in shipped skills — commits fail review; keep paths
  repo-relative.
- Forgetting the deploy step — user-local skills die with the machine; a
  universal lesson belongs in the repo, with a test, in the same session it
  proved itself.

## Verification

- [ ] Every captured lesson survived as an imperative rule in a skill, not chat.
- [ ] Superseded wording removed in the same skill_manage call that added the rule.
- [ ] The lesson's re-run criterion is executable (or explicitly marked unverifiable).
- [ ] Weekly sweep diff shows pruning, not growth (or justified growth).
- [ ] Lessons applicable to all users committed to the repo, with tests passing
      via `scripts/run_tests.sh tests/skills/test_<skill>_skill.py -q`.
