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

- Mid-session: a probe, workaround, or fix that a future you could not recreate without pain.
- A user correction reveals an assumption that was wrong — fix the source, not just this turn.
- A tool/environment quirk (quoting, paths, auth) cost >2 failed attempts.
- Don't use for: one-off trivia that no future session would hit; ephemeral debugging state (session_search).

## Procedure

0. **Sharp-before-deploy rule (founder directive, 2026-10-02)** — analysis before
   action: state the exact failure the change prevents, and re-run the full
   mechanical evidence (tests + grep checks) BEFORE pushing. A pushed fix must
   carry its proof: commit message links the command and its green output. If
   the evidence is not green at deploy time, the deploy does not happen — the
   error surface grows, never shrinks, when proof is skipped.

1. **Capture at the moment of pain, not after** — every fix that takes >2 tool
   attempts or one user correction spawns a candidate lesson immediately.
   Record: the trigger, the wrong assumption, the right procedure (one line each).

2. **Classify before writing** —
   - *Universal procedure* → new/updated skill (in-repo if it ships, user-local if personal)
   - *Environment-specific fact* → the task skill's `Pitfalls` or environment notes
   - *One-time user preference* → user profile memory (tiny, high-signal)
   - *Nothing yet provable* → a TODO inside the relevant skill, never a hunch logged as fact

3. **Write the lesson as an imperative rule + why** — not an incident log.
   - Good: "scp a script file instead of nested ssh quoting on Windows hosts; wsl.exe mangles nested quotes."
   - Bad: "2026-10-02 markpc ssh had issues with nested quotes."

4. **Consolidate, don't accumulate** — before adding a rule, search the skill for
   the old wording it replaces and remove it. A skill bloated with obsolete rules
   is worse than no skill (the wrong one gets followed).

5. **Verify the upgrade** — a lesson qualifies as learned only when re-running
   the original scenario passes with it applied. Where that's expensive,
   leave an exact re-run command in the skill for next time.

6. **Weekly sweep** — read the newest lessons in the most-used skills;
   delete duplicates; promote recurring patterns from task skills into
   broader ones (e.g. quoting habits → a general ops skill).

## In-Repo Deployment (this skill's own rule, by example)

When a lesson proves itself and applies to **every user** of the harness, the
loop's final step is `git`: copy the evolved skill into
`skills/<category>/<name>/SKILL.md` of the merlin-agent repo, add
`tests/skills/test_<skill>_skill.py` asserting the mechanical subset
(frontmatter at byte 0, description ≤60 & ends with period, no machine-local
paths, no marketing words, modern section order present), regen docs per
`merlin-agent-skill-authoring`, and ship the commit. Session wisdom that stays
user-local is interest; in-repo skill wisdom is principal.

### Mechanical invariants (asserted by the in-repo test)

```
frontmatter starts at byte 0 and parses as YAML mapping
description: present, ≤60 chars, ends with ".", no marketing words
no machine-local paths (/home/<user>/... or drive letters)
section order: When to Use → Procedure → Pitfalls → Verification
author credits the human first
```

## The 100× Math

Skills compound only under three conditions:
- **Trigger quality**: descriptions that actually fire (≤60 chars, trigger-first) — otherwise the right skill never loads.
- **Imperative body**: rules, not logs; completion criteria; reference scripts for anything nontrivial.
- **Pruning**: old rules must die when new ones replace them — sediment kills routing.

An agent that follows this loop reliably approaches smartest-operator status
within 2–3 weeks of real work — not because it thinks harder, but because it
never pays the same toll twice.

## Pitfalls (incl. deploy-step hazards)

- Logging incidents instead of rules — the incident is data; the rule is the asset.
- Skill sprawl (one skill per incident) — extend the closest existing skill instead.
- Trusting unverified lessons — a hunch in a skill poisons future sessions; mark confidence honestly.
- Capturing after session end — memory decays; capture mid-work.

## Verification

- [ ] Every captured lesson survived as an imperative rule in a skill, not chat.
- [ ] Superseded wording removed in the same skill_manage call that added the rule.
- [ ] The lesson's re-run criterion is executable (or explicitly marked unverifiable).
- [ ] Next session's plan references the skill (spot-check: does the lesson fire?).
- [ ] **Pre-deploy sharp check (mandatory)**: failing tests = zero across the
      session's touched suites, grep-level checks re-run clean, commit message
      carries the proof command, and the change's prevented-failure is stated
      in one sentence before push.
