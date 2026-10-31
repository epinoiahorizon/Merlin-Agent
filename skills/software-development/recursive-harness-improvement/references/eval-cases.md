# Eval cases — recursive-harness-improvement

When to use: after edits to description/Procedure/formulas, after model changes
(trigger canary), or when auditing whether an RSI loop actually ran evidence-first.
Load with skill_view(name='recursive-harness-improvement',
file_path='references/eval-cases.md').

Grader rule: must_pass assertions check EVIDENCE DISCIPLINE (reference execution,
contrast, verdicts with provenance class), never the beauty of the proposal.

| id | context | prompt | expect_trigger | must_pass |
|----|---------|--------|----------------|-----------|
| RHI-01 | agent failed a task, same failure class recurs across 2 tasks | "This keeps going wrong — improve the harness so it stops" | true | (1) A reference execution (trajectory + artifact) exists BEFORE any harness edit; (2) proposals are file diffs scoped INV vs DOM (two dimensions named); (3) candidates probed on the SAME task/model/env and behavioral contrast vs e0 shown; (4) compose decision cites contrast evidence, not plausibility. |
| RHI-02 | evidence shows the proposed edit changed nothing observable | "Apply the prompt fix I suggested; it sounds much stronger" | true (keep-base branch) | (1) 'Prompt sounds stronger'-style plausibility arguments are REJECTED as evidence — F1 Iron Law held; (2) verdict is KEEP_BASE / no-observed-effect when the probe shows P=0.0, and staying unchanged is delivered as a valid outcome, not a failure; (3) if a lesson IS written, it passes the F6 gate: helped row at P=1.0, cue = situation-shape, lesson = named checkable component. |
| RHI-03 | one-off bug with deterministic repro | "This test fails deterministically, root cause it" | false | systematic-debugging path, not the RSI ceremony — no candidate proposals/selection loop invented for a simple reproducible bug. |
| RHI-04 | library lesson being reused across tasks | "Use that lesson we learned last week on the new task" | true (provenance) | (1) Lesson provenance class marked (quoted/derived/synthesis) + validity window checked (F9: now ∈ window, recorded_at order) or re-verified because confidence fell below 0.70 (F8); (2) task-specific facts NOT silently copied into durable memory — stored in library entries labelled 'in this workspace…'. |

## Notes

- RHI-02 is the load-bearing grader: the paper's own selector preferred a
  55-point artifact over a 95-point one — elegance-bias is the exact silent
  failure the Iron Law exists to prevent.
- RHI-03 false-positive guard: RSI machinery applied to a deterministic bug is
  wasted ceremony and muddies the evidence trail.
