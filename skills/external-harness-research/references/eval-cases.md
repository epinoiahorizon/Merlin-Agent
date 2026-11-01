# Eval cases — external-harness-research

When to use: after edits to description/Procedure, after model changes (trigger
canary), or when reviewing whether a framework verdict was evidence-based.
Load with skill_view(name='external-harness-research',
file_path='references/eval-cases.md').

Grader rule: must_pass assertions check evidence discipline (source read, gap
table, verdicts), never report length. Run after edits to description/Procedure
and after model changes (trigger canary). Per references/skill-evals.md in
improvement-loop.

| id | context | prompt | expect_trigger | must_pass |
|----|---------|--------|----------------|-----------|
| EHR-01 | user pastes a framework repo URL | "Check this framework — useful for our agent?" | true | (1) README treated as marketing: at least one upstream subsystem SOURCE file read alongside OUR equivalent code before the verdict; (2) deliverable is gap-vs-patterns (our gap / their pattern), not a feature inventory; (3) every borrowed pattern classified PATTERN vs DEPENDENCY with licence named; (4) implementation order cheapest-first with prerequisites. |
| EHR-02 | report just delivered, user says go | "OK, implement the top pattern" | true (impl phase) | (1) Target tool's live code + callers audited (grep'd and read) before editing — not the report's snapshot; (2) no LLM credential in session → factory seam + fake-based unit test, e2e explicitly deferred and stated; (3) any guard added is sampled INSIDE the gated operation (proven active at runtime); (4) MIT attribution header present when a pattern visibly derives from an MIT source; full suite re-run green beside new tests. |
| EHR-03 | none (internal feature question) | "How do I add a provider to Merlin?" | false | Normal merlin-provider-integration/merlin-agent workflow; no external-framework research ceremony invented. |
| EHR-04 | user proposes a SaaS observability product | "Should we just use LangSmith instead of building evals?" | true | Verdict applies the SaaS pitfall: take the pattern (trace replay, eval-vs-expectation), self-host; dependency adoption requires the offsetting-gain argument stated explicitly. |

## Notes

- EHR-01(2) is the load-bearing grader: a feature inventory (what the library
  does for ITS runtime) is the exact failure this skill's procedure exists to
  prevent — the question is always what OUR harness does.
- EHR-03 false-positive guard keeps internal config questions from decaying
  into framework research.
