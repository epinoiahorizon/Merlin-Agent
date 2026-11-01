# Eval cases — test-driven-development

When to use: after edits to description/Procedure, after model changes (trigger
canary), or when auditing whether a 'TDD' claim actually followed the cycle.
Load with skill_view(name='test-driven-development',
file_path='references/eval-cases.md').

Grader rule: must_pass assertions check CYCLE FIDELITY (watched-fail evidence,
minimal green, vertical slices), never test count.

| id | context | prompt | expect_trigger | must_pass |
|----|---------|--------|----------------|-----------|
| TDD-01 | new feature requested | "Add X to the tool" | true | (1) A failing test written and RUN with its failure SHOWN (watched-fail evidence in session: the red run output exists) before any production code; (2) failure reason is the missing feature, not a typo/import error left unfixed; (3) minimal green: no logging/batching/extra features beyond what the test requires; (4) full suite re-run green after. |
| TDD-02 | bug fix | "Fix the bug where Y breaks" | true | A failing test reproducing THE bug exists first — the fix commit carries the regression test; bug closed by test proof, not by 'I checked manually'. |
| TDD-03 | one cycle complete, tests green | (mid-loop) | true (slice discipline) | Next behavior starts as the NEXT failing test (vertical tracer bullet), NOT as a pile of pre-written tests for imagined interfaces — check the session for horizontal RED-fists (multiple tests before any impl). |
| TDD-04 | throwaway spike / config-only change | "Prototype the idea quickly to see if it works; config tweak too" | false | TDD ceremony NOT forced on the explicitly-permitted exception (prototype/config) — the exception branch with user consent is the correct path. |

## Notes

- TDD-01(1) is the load-bearing grader: a test that passed on first run proves
  nothing — the watched-RED run must exist as session evidence.
- TDD-03 catches the horizontal-slice drift, the subtlest regression: it looks
  like MORE diligence while actually being brittle tests designed in the dark.
