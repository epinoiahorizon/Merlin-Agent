# Skill Evals — the verification arm for skill edits

A skill that loads ON DESCRIPTION is software with an interface; edits to its
interface (name/description) and body are behavior changes and must be verified
like code. Pattern adapted in spirit from Anthropic skill-creator evals and the
OpenAI "Testing Agent Skills Systematically with Evals" guide (both
Apache/first-party docs; implementation here is original).

## The roll-out formula (repeatable, per skill)

Every high-traffic skill gets `references/eval-cases.md` with EXACTLY this shape:

1. **Header**: When-to-use (after description/Procedure edits, after model change
   = canary run, or when the skill's discipline is slipping) + how to load the file.
2. **Grader rule line**: what must_pass checks in THIS skill — what the agent DID,
   never the tone of its answer.
3. **4 cases in a table** (`prompt / expect_trigger / context / must_pass`):
   - 1–2 core-path cases (`true`) each asserting the skill's LOAD-BEARING
     discipline — the one failure the skill exists to prevent.
   - 1 escalation case where relevant (the rare high-value branch that fails
     silently when it doesn't fire).
   - EXACTLY 1 false-positive guard (`false`) — the adjacent task that must NOT
     summon the ceremony.
4. **must_pass assertions are graded from execution evidence** (tool calls made,
   files read/created, verification runs), numbered, ≤3 per case.
5. **Notes**: one line per guard explaining which silent failure it catches.

Roll-out order: highest-traffic skills first (usage frequency, not alphabetical);
stop at skills where evals cost more than they catch (rare one-shot skills).
A skill without eval cases is NOT broken — it's just unverified; note that
honestly instead of inventing a token eval.

## Roll-out ledger

- Done: github (GH-01..04), systematic-debugging (SD-01..04),
  external-harness-research (EHR-01..04), recursive-harness-improvement
  (RHI-01..04), requesting-code-review (RCR-01..04), test-driven-development
  (TDD-01..04). Formula validated on 6 skills.
- Next batch: merlin-agent, merlin-harness-patching, improvement-loop itself,
  memory-hygiene, merlin-fleet-ops.
- Update this list as batches land; keep it a ledger, not a log.

## Minimal eval set (keep it small and must-pass)

Write `evals.md` (or `evals/cases.md`) next to the SKILL.md:

| field | meaning |
|---|---|
| `prompt` | the user request verbatim |
| `expect_trigger` | `true` = skill must load; `false` = must NOT (false-positive guard) |
| `context` | one line of domain context to place before the prompt |
| `must_pass` | 1–3 deterministic, checkable assertions on what the agent DID |

Include at least one `expect_trigger: false` case — over-eager triggering is
the most common regression and invisible without it.

## Deterministic graders: score what happened, not what it said

Grade from execution evidence, ordered by strength:
1. Exit codes / command success of the steps the skill prescribes.
2. Files/artifacts created with expected shape (path + first line, not vibes).
3. Mechanical greps (the in-repo invariants in the parent skill are graders too).
4. Structured self-report (`status`/`error` keys) only as tiebreaker — never
   as the sole grader, because models self-report success optimistically.

## Comparator A/B for risky edits

When an edit changes behavior (not just wording): run the OLD and NEW skill
version against the same eval set in clean contexts, in parallel (separate
sessions/agents — accumulated context bleeds between runs and corrupts the
comparison). Keep the new version only if it wins on the must-pass set AND
does not regress the `expect_trigger: false` cases.

## When to run

- After ANY edit to a skill's description or Procedure.
- After a model/provider change — trigger behavior can silently shift (evals
  double as a canary: run the set, diff the outcomes).
- Weekly sweep (parent skill step 6) on the most-used skills only.

## Anti-patterns

- Encoding every preference into the eval set — must-pass only; everything
  else stays a pitfall line inside the skill.
- Grading the final text with an LLM judge where a grep would do.
- Editing a skill and shipping without re-running its eval set (unverified
  lesson — parent skill step 5's rule).
