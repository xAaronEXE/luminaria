# Remaining-work audit and implementation gate — October 17, 2026

This is a source inspection, not desktop/provider acceptance. The roadmap Delivery
status table remains authoritative. No statuses are advanced by this document.
The pre-existing untracked ACCOUNT-MEMORY-AGENT-DIRECTION document is left untouched.

## Agreed working brief

Preserve current black/white light/dark UI, customization, layout, composer arrangement,
inspector behavior, density, Automations, and spatial prominence. Improve small labels.
Current action goes above composer; short outcomes expand into Activity details.
Chat checkpoints show findings/completed/failed/uncertain/remaining work and Continue.
Approvals show action/target/effect with expandable technical detail. Keep the current
visuals and measure their cost before changing them. Reliability is first priority.
At 18 rounds checkpoint and ask; inspect uncertain outcomes, then ask if still unclear.

## Inspection findings before implementation

- `backend/checkpoint.py`: deterministic reports exist, but only direct file operations
  contribute to "Changes made". Commands and connector tools can have effects, making
  the unconditional no-files-changed statement unsafe. Interrupted actions need a
  separate uncertain-outcome section. Completion is not independent verification.
- `backend/engine.py`: journal, repeated-failure stop, checkpoint and continuation
  already exist. Continuation deduplication uses a fixed builtin name set and serialized
  arguments; connector side effects and semantically equivalent arguments need a later
  audit. Do not promise universal duplicate prevention from these checks.
- `backend/retrieval.py`: normalized results, extraction, retries, ten-minute URL cache,
  and JavaScript-needed guidance exist. No automatic authorized browser fallback is
  implemented here. Cache freshness is time-based; authenticated/sensitive-response
  exclusions need inspection and tests before broader reuse.
- `backend/tools.py`: file search is literal matching with limits; memory/history search
  is literal substring matching. These paths are not a shared semantic/chunk retrieval
  implementation. Stable chunk references, changed-source invalidation, scan-limit
  transparency, and uniform failure categories need hardening.
- `backend/skills.py`: catalog includes category, dependency gaps, availability and
  descriptions. Loading instructions does not itself check dependencies; execution
  lifecycle and validated output contracts are not provided by this module. Imported
  skills have no inventory requirements by default. Audit runtime call sites before
  claiming these gaps closed or treating "available" as verified readiness.
- `backend/connectors.py`: tools load once at connection, clear on shutdown, and UI
  notification exists. Cancellation of a queued caller does not itself establish that
  an in-flight provider action stops. Refresh/invalidation and cancellation require
  focused tests without destroying a shared connection indiscriminately.
- `backend/identity.py`: required-sign-in gate and offline policy exist; source describes
  seven-day offline grace. Do not change these policies during acceptance repair.
- `backend/usage.py`: durable events and aggregate sync fields exist. Audit metric
  definitions against real captured events; no seeded total is desktop acceptance.

## Acceptance and release boundary

First complete docs/testing-0.2.17.md with user-run packaged-app evidence. Account,
insights, working brief, compaction, updates and orchestration are acceptance work,
not omitted features and not automatically new implementations.

The user's later instruction to continue the full plan authorizes development beyond
the pending desktop gate. Desktop acceptance still gates release readiness and status
advancement; it no longer blocks local implementation. No new release split is introduced.

Implementation order:

1. **0.2.18**: confirmed retrieval/skills/integrations gaps, truthful recovery, cancellation,
   deduplication and the agreed progress/approval/label polish. Audit before each change.
2. **0.2.19**: hardware page and opt-in measured tuning; provenance/rollback and no
   automatic profile application, downloads, experimental forks or BIOS changes.
3. **0.2.20**: file-first observe/plan/act/verify/recover with explicit boundaries,
   fresh evidence, Stop, recoverable deletion and uncertain-outcome recovery.

Keep one open PR. Each step has its own branch/release notes/version and verification
table. User runs builds/publishing. Do not enable mandatory sign-in or deploy the Worker
as a side effect. Keep provider secrets in the Worker and never print release tokens.

## Verification record for this change

This section records the initial acceptance repair. Subsequent local implementation
through 0.2.20 and its 174-test Python verification are recorded in
`verification-0.2.20.md`; findings above remain the pre-change audit, not a claim that
every listed gap is still present. The full approved scope remains in
`remaining-scope-2026-10-17.md`.

- `python -m unittest tests.checkpoint_continuation`: 8 passed, including command/
  integration effects, interrupted/errored mutations and continuation skips.
- `python -m unittest tests.retrieval_reliability`: 10 passed (isolated tests).
- `python -m unittest tests.web_fetch_fixtures`: 14 passed (saved fixtures).
- `python -m unittest tests.work_events`: 5 passed (scripted model responses).
- Total: 37 passing tests, each module run separately with the existing build Python.
- Reporting repair implemented: successful tool calls are not labeled independently
  verified; commands/connectors cannot yield an unconditional no-change claim;
  interrupted/errored mutations expose uncertain outcomes; continuation skips are
  separated from new actions. This does not implement general connector idempotency.
- Packaged desktop, real-model, real-provider, two-PC, installer/update: not run.
- No UI appearance change; no hardware tuning; no production deployment.
