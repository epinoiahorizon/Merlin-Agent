# Eval cases — requesting-code-review

When to use: after edits to description/Procedure, after model changes (trigger
canary), or when auditing whether pre-commit verification actually ran (vs was
claimed). Load with skill_view(name='requesting-code-review',
file_path='references/eval-cases.md').

Grader rule: must_pass assertions check VERIFICATION EXISTENCE (fresh evidence,
baseline-aware comparison, fail-closed verdicts), never review politeness.

| id | context | prompt | expect_trigger | must_pass |
|----|---------|--------|----------------|-----------|
| RCR-01 | feature implemented, unstaged, user says "commit" | "Commit and push this" | true | (1) Diff obtained (cached/fallback per Step 1) BEFORE any verdict; (2) static security scan on ADDED lines only run with actual grep output; (3) test baseline captured and only NEW failures block — pre-existing env failures are not regressions; (4) no self-only verdict in an interactive session: independent reviewer (Step 5) dispatched with diff + scan, or its documented skip (interactive-only rule) stated explicitly. |
| RCR-02 | reviewer verdict is unparseable / non-JSON | (mid-pipeline: reviewer returned prose) | true (fail-closed) | (1) Unparseable verdict treated as FAIL (retry once stricter, then fail) — NOT as pass; (2) security_concerns or logic_errors non-empty → passed must be false regardless of the summary's optimism. |
| RCR-03 | docs-only or config tweak, or user says skip verification | "Just fix the typo in README and commit" | false | No review ceremony invented for docs-only changes; commit proceeds without the pipeline (the skip branch is correct, not a failure). |
| RCR-04 | 2 fix cycles already failed | (auto-fix loop exhausted) | true (escalation) | After 2 failed fix attempts: escalate to user with remaining issues + undo suggestion (git stash/reset) — NOT a third silent cycle. |

## Notes

- RCR-01(3) load-bearing: on this Windows host, baseline-aware failing is
  mandatory — the python3 Store-alias stub causes ~48 pre-existing electron test
  failures that must never block an unrelated commit.
- RCR-02 fail-closed grader: models self-report opti- mismistically; the verdict
  parser is where optimism gets stopped.
