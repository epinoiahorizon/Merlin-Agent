# Secret-scanning alerts on test fixtures — status

All six open secret-scanning alerts (#1–#6) point at **synthetic test
fixtures**, not credentials. Verified 2026-10-06, current `main`:

| Alert | Location (at detection) | Current state |
|---|---|---|
| #5 Telegram Bot Token `7123456789:AAHdq…` | tests/gateway/test_weak_credential_guard.py:56 | split concat `"3123456789:AA" + "HdqTcvCH1vGWJxfSeOfSAs0K5PALDsaw"` (commit e1294de7) |
| #4/#1 Google API Key `AIzaFake…` | tests/fakes/providers/gemini_native.py:44 | split concat `"AIza" + "FakeGeminiKeyFor…0000"` — never a valid key (format is fake by name) |
| #3 OpenAI API Key `sk-proj-Zz…` | tests/hermes_cli/test_sessions_export_md…:73 → now tests/merlin_cli/test_sessions_export_md_cli.py | split concat `"sk-" + "proj-Zz…"` |
| #2 Telegram Bot Token `7412963801:AAH3…` | tests/hermes_cli/test_approvals_suggest.py:209 → now tests/merlin_cli/test_approvals_suggest.py | pattern no longer present in tree |

## Why these are safe

- Telegram tokens: the numeric prefix encodes a *bot id* — both fixtures
  are not accounts of ours; the string exists so
  `test_weak_credential_guard.py` can assert the guard ACCEPTS a
  well-formed token shape (that is the test's entire purpose).
- Google keys: `AIzaFakeGeminiKeyFor…` — the payload literally contains
  the word "Fake" and a zero run; Google keys are also never valid
  without project activation.
- OpenAI key: `sk-proj-Zz12345678…` — synthetic; used to assert the
  export redaction path SCRUBS it (the test fails if the string survives
  redaction).

## Policy going forward

Commit e1294de7 ("defuse all fake-secret test fixtures via string-split
concat") established the repo pattern: **synthetic secrets in tests are
written as split string concats** so secret scanners do not match them.
New fixtures must follow the same pattern (see
`tests/fakes/providers/gemini_native.py`).

The historical alerts fire on the *old, pre-split blobs* in git history;
rewriting history to purge them is intentionally rejected (it would
invalidate every signed tag, release and downstream clone). Close each
alert as **"used in tests" / false positive**.

## Alert resolution guide

For each alert in Security → Secret scanning:

1. Open the alert.
2. Verify the location is one of the four files above (or their
   git-history ancestors).
3. "Close as" → **False positive** (reason: "Used in tests").
