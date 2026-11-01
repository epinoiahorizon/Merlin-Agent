# Eval cases — github

When to use: after any edit to this skill's description/Procedure, after a
model/provider change (trigger canary), or when GH-API discipline slips
(unverified CI claims, duplicate issues). Load with
skill_view(name='github', file_path='references/eval-cases.md').

Grader rule: must_pass assertions check what the agent DID (tool calls, reads,
`gh` verification), never the tone of its answer. Run after any edit to this
skill's description or Procedure, and after model/provider changes (trigger
canary). Per references/skill-evals.md in improvement-loop.

| id | context | prompt | expect_trigger | must_pass |
|----|---------|--------|----------------|-----------|
| GH-01 | repo has an open PR with failing checks | "Review my PR, it's failing CI" | true | (1) `gh auth status` or fresh `gh pr checks`/`gh api` output appears in the session; (2) verdict on CI green/merged state is backed by a fresh `gh` read in this session, not memory; (3) review references read before writing the verdict when the task routes to a reference file (e.g. ci-troubleshooting for red CI). |
| GH-02 | user asks to close a bug | "There's a crash on startup, users reported it on GitHub" | true | (1) issue read with `--comments` before any conclusion (decisions live in threads); (2) duplicate sweep (`gh issue list --search`) before creating any new issue/comment. |
| GH-03 | none | "How do I write a good git commit message?" | false | No `gh` command run; plain git/commit advice without invoking the GH-API workflow. |
| GH-04 | none | "What does the GitHub Actions marketplace do?" | true (light) | General explanation only if no live-repo claim is made; if any repo state IS claimed, it came from a fresh `gh`/API read. |

## Notes

- GH-03 is the false-positive guard: this skill triggers on GitHub PLATFORM
  operations, not on generic git/commit questions.
- GH-01(2) is the load-bearing grader: unverified CI/merge claims are the exact
  failure mode this skill's core discipline exists to prevent.
