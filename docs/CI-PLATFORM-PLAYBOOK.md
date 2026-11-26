# CI Platform Playbook - Merlin-Agent

> How CI works in this repo, why the decisions are what they are, and the
> traps that produced them. Any agent (Merlin or not) or human working in
> this repository: follow these rules; do not re-derive settled decisions.

## Settled decisions

| Decision | Reason |
|---|---|
| GitLab is the single upstream | migration complete; main pipeline green; release 0.1.8 cut here |
| GitHub `epinoiahorizon/Merlin-Agent` is read-only | archived 2026-11-15 to stop accidental pushes; un-archiving is an owner decision |
| Quality gates (test-python, test-js) run on the self-hosted runner (`wsl-gitlab`) | 60-90 min per run; the namespace compute quota is 400 min/month on the trial (paid Ultimate = 50,000) and one hosted run would burn a quarter of it. Self-hosted jobs never consume the quota |
| Hosted runners (`saas-linux-small-amd64`) for build-docs, pages, and the Ultimate scanners | small jobs only; scanners additionally gated behind `$SAAS_SCANNERS=on` and docs behind `$SAAS_DOCS=on` so an exhausted quota never leaves pipelines queued against an unwinnable runner |
| No `tags: [self-hosted]` in the `default:` block | analyzer jobs ship as Docker images and cannot run on a shell executor; job-level tags only |
| Gates run on the default branch only | an MR pipeline would duplicate the branch pipeline on the same commit |
| `allow_failure: true` on test-python/test-js is transitional | environment buckets are being fixed (see issue #4); flip to false once both gates are green on consecutive runs |
| `pages.needs` is `{job: build-docs, optional: true}` | build-docs legitimately may not exist in a pipeline ($SAAS_DOCS off); a hard needs reference produced zero-job "failed" pipelines on main |

## Quota facts (docs.gitlab.com/ci/pipelines/compute_minutes)

- Trial namespace = **400 compute minutes/month** (Premium 10,000; Ultimate 50,000)
- The limit **applies to public projects on GitLab.com too**
- Jobs on your own runners **never** consume the quota
- Usage resets on the 1st of each month; purchased minutes are consumed after the included quota

## Incident trail (why the rules above exist)

- **WSL VM idle-out (~60 s)**: the VM dies without a console client; a running
  runner gets a shutdown signal and GitHub (in the previous era) pruned its
  registration. Do not run CI-dependent workloads on machines that sleep.
- **GitHub hosted-runner billing block**: jobs were refused before checkout;
  their logs were purged (BlobNotFound) and jobs carried no steps. Signature:
  instant failure + unusable logs = provisioning refusal, not a code bug.
- **allow_failure masking**: a "green" pipeline once concealed two red test
  suites (30+ failing files). A green pipeline is not a passing job set -
  always read per-job results.
- **Stale checkout cache**: `bad object refs/remotes/pull/N/merge` on a reused
  runner checkout; clear `_work` or prefer ephemeral (container) executors.
- **Runner registration auto-delete**: registrations that rarely reconnect get
  dropped server-side; a re-register watchdog is a patch, not a cure.
- **Supervisor env leak**: a gitlab-runner service is itself a systemd unit,
  so `INVOCATION_ID`/`NOTIFY_SOCKET` leak into pytest and production code took
  the managed-systemd paths. conftest unsets them (invariant 5).
- **Owning-install retarget under pytest**: a PM-managed venv resolves an owner
  different from the test's project root and re-ran the CLI with the runner's
  argv; the child argparse failed and masked the real test outcome.
  `update_owning_install.py` now skips redirection under pytest.
- **Full-SaaS experiment (!13)**: reverted by !15 within hours - the trial
  quota could not sustain 60-90 minute gates and the slim image lacked build
  tools. The self-hosted pin was budget protection, remember that.

## Tooling for agents working in this repo

- Clone: `https://gitlab.com/epinoia-horizon-group/merlin-agent.git`
- Push: a GitLab PAT (scope `api`/`write_repository`) kept in the agent env;
  never print tokens to chat or commit them
- MR flow: every CI change goes through an MR; the MR pipeline must be green;
  the owner merges
- Never push to GitHub (archived). There is no CI there anymore.
- Working timezone: Asia/Makassar (WITA, UTC+8)
- Triage board: issue #4 (test failures), this file (platform rules)

## When a pipeline is red

1. Read per-job logs; pipeline status alone hides allow-failed skeletons and
   skip-shaped emptiness.
2. Classify the red: (a) real code bug, (b) runner/environment, (c)
   provisioning/quota. Each has a different fix.
3. `allow_failure: true` is allowed short-term but must carry a reason and a
   removal plan.
4. Never "rescue" a job by pinning it to self-hosted ad hoc - that is a
   regression to the budget the rules above protect.
