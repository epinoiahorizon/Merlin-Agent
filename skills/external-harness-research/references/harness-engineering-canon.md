# Harness Engineering Canon (2026) — curated reading map

Curated from ai-boost/awesome-harness-engineering (CC0, 5.0k★, active) — entries
re-selected for OUR harness mission; each entry: what it proves + what to harvest.
Read the SOURCE, never this map's paraphrase, before borrowing a pattern.

## Foundations (define the discipline)

- **OpenAI — Harness Engineering** (openai.com/index/harness-engineering) — the
  framing: scaffolding (context delivery, tool interfaces, verification, memory,
  sandboxes) determines success more than the model.
- **Anthropic — Harness Design for Long-Running Apps** — key discipline: every
  harness component assumes the model can't do something; those assumptions EXPIRE.
  Re-audit components each model upgrade (directly our recursive-harness-improvement).
- **Martin Fowler — Harness Engineering** — three interlocking systems: context
  engineering, architectural constraints (deterministic linters), entropy management
  (periodic agents repairing doc drift). "Humans on the loop" framing.
- **LangChain — Anatomy of an Agent Harness** — five primitives: filesystem,
  code execution, sandbox, memory, context management. Co-evolution warning:
  models trained with a specific harness overfit to its design choices.
- **arXiv 2606.10106** — necessary/sufficient conditions for calling something a
  harness: agent loop + tool interface + context management + control mechanisms.
  Use as the inclusion test when triaging a framework.
- **arXiv 2604.18071** — empirical study of 70 agent systems, five recurring
  dimensions; turns harness selection into reasoned trade-off comparison.

## High-signal production evidence

- **LangChain — Improving Deep Agents with Harness Engineering** — harness-only
  changes moved their agent rank 30 → top 5 on Terminal-Bench 2.0, no model swap:
  verification loops, directory-map context injection, loop-detection middleware,
  "reasoning sandwich" (max thinking at plan + verify phases).
- **LangChain — Tuning the harness, not the model** (Nemotron 3 Ultra playbook) —
  harness-only tuning brought a cheap model within 1 point of frontier at 1/10
  cost ($4.48 vs $43.48). Evals are the training data for harness work.
- **Meta — Ranking Engineer Agent (REA)** — hibernate-and-wake checkpointing:
  resume a 6-hour interrupted task without losing context. Pattern candidate for
  long cron/terminal jobs.
- **Microsoft — Azure SRE Agent** — replaced 100+ bespoke tools with
  filesystem-based context (everything as files + read/grep/shell): Intent-Met
  45% → 75% on novel incidents. Validates files-first tool design.
- **Anthropic — April-23 postmortem** — three independent harness-level changes
  (reasoning-effort downgrade, cache bug dropping thinking history, verbosity
  prompt) compounded into visible product regression. Template for diagnosing
  our own "sudden quality drop" reports.

## Patterns with direct harvest value

- **Claude Code compaction anatomy (arXiv 2604.14228)** — five-stage progressive
  compaction: budget-reduction → snip → microcompact → context collapse →
  auto-compact; subagent isolation with rebuilt permission contexts; 27-event
  hook pipeline. The reference map for our P3 compaction work.
- **LangChain — Autonomous Context Compression** — agent-CALLED compression tool
  instead of at-limit auto-compaction: avoids interrupting mid-subtask and
  corrupting in-flight reasoning. Better default than threshold-triggered.
- **statewright** — per-phase tool whitelisting via state machines: local models
  2/10 → 10/10 on a SWE-bench subset by shrinking the tool space alone.
- **Anthropic — Effective Harnesses for Long-Running Agents** — initializer agent
  sets environment once; coding agent makes incremental progress per session;
  feature-list + git commits + test gates as cross-session state.
- **GitHub blog — Multi-agent workflows fail like distributed systems** — every
  handoff needs typed schemas and boundary validation (matches our
  delegate_task structured-output contract).
- **Anthropic — Beyond Permission Prompts / MCP tool-annotation risk vocabulary** —
  permissions as structured system, not prompt text; readOnlyHint/destructiveHint
  as inputs to permission decisions.
- **Vercel — Content negotiation (Accept: text/markdown)** — cheap harness
  primitive for our own web properties: serve agents clean markdown at the same
  URL humans use. Adopt for grimoire/fleet pages.
- **context-mode / headroom / token-savior (GitHub)** — intercept bulky tool
  output BEFORE the LLM; retrieve fragments on demand (BM25/symbol index).
  Pattern class: output sandboxing, 60–95% token cut claims — verify before use.

## Selection rule (unchanged from parent skill)

PATTERN vs DEPENDENCY verdict per item; MIT/Apache/CC0 noted; no runtime imports
into the harness. This map is an INDEX — treat entries as leads, cite the source
you actually read.
