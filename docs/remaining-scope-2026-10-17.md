# Approved remaining scope — October 17, 2026

Implementation authorized in chat. This is the durable working scope, not completion
evidence. The roadmap Delivery status table controls implementation status; latest chat
decisions override older aesthetic/stack specifications. Source/browser tests never
establish packaged-desktop acceptance.

## Acceptance gate

Complete `testing-0.2.17.md` and repair failures reported from the installed app.
Later chat authorization permits local development of subsequent stages in parallel
with pending user acceptance; no pending desktop test is thereby considered passed.
Account prerequisites are D1 migrations 0002/0003 and the identity Worker deployment.
User handles provider dialogs and supplies packaged-desktop results. Mandatory sign-in
stays off. Current acceptance repair/evidence is in `implementation-audit-2026-10-17.md`.

## Account and Insights remain in scope

- Dedicated login screen when required, server-validated Google/GitHub/Discord sessions,
  explicit provider linking, encrypted remembered-device credentials, expiry/revocation,
  offline grace and readable error states. No email-based merging or password login.
- Bottom-left account access to Profile, providers, devices, settings and Insights.
  Identity never implies integration permissions. Explicit per-local-profile choices;
  no silent history merging or movement, preserve profile isolation and local data.
- Lifetime input/output/total tokens since coverage start; cached tokens only when
  measured; labeled peak period; longest task with active versus wait/paused time;
  current/longest streak with timezone and qualifying activity; token history;
  requested reasoning modes/levels; skills explored/enabled/invoked separately;
  plugins/integrations/tools with success/failure; model usage/measured speed trends.
- Durable IDs and duplicate-resistant opt-in daily aggregate sync. Coverage start,
  retention, sync failures, export and deletion must be clear. No historical inventions
  or implicit raw chat/file/web/credential/tool-output/recording uploads. Verify retry,
  timezone, deletion and two-PC totals with actual providers/devices, not seeded demos.

## UI decisions to keep handy

Preserve black/white modes, full customization, restrained semantic accents, current
layout, density, composer arrangement, inspector behavior, Automations and spatial
appearance/prominence. Measure renderer cost before changing it. Improve small labels.
Current action above composer, short outcomes with expandable Activity detail, available
Stop, approval action/target/effect plus expandable technical details. Chat checkpoints:
completed/findings/failed/uncertain/remaining/Continue. Readable inspector folder names,
empty states and evidence links. Navigation: Memory, Tools, Integrations, Skills,
Automations, Model library, Archive & trash, account/settings. Motion in Appearance,
respect reduced motion. Accessible memory controls with units/bounds/defaults/presets,
precise entry where useful, save/errors and reload/restart explanations.

## 0.2.18 — reliable workflows, retrieval, skills and polish

- Audit and list confirmed gaps before coding. Keep 18-round checkpoint and three
  identical-failure stop; continuation requires user choice. Broader no-progress stop
  only for confirmed gaps. Deterministic useful partial results even if generation fails;
  source/file links, explicit no-useful-result state, truthful change accounting.
- Journal attempted/executed/verified distinctly. Cover commands/integrations, prevent
  duplicate side effects on continuation/restart. Inspect uncertain actions first and
  ask if unclear. Cancellation reaches requests/subprocesses; preserve partial outputs.
- Memory layers: pinned brief, recent verbatim turns, versioned summaries, searchable
  originals/full outputs, bounded fresh retrieval cache. Separate durable facts/task
  state; supersede corrections; user-only permissions; references rather than secrets.
- Compaction counts the whole request plus output reserve, uses headroom and bounded
  chunks/source ranges, preserves tool pairs/approvals/denials/exact references, validates
  summaries before commit with bounded retries, keeps last good summary/originals,
  rechecks assembled context, recovers originals to limit drift. Record duration,
  tokens before/after, summary size, retrieval frequency and failed validations. Verify
  long real workflows; only claim measured KV-cache reuse, not permanently loaded RAM.
- Normalize retrieval source/time/type/text/truncation/errors; separate file/history,
  memory, search, fetch, integration diagnostics. Redact queries/secrets. Distinct auth,
  permission, missing, network, timeout, throttle, unsupported, extraction, empty and
  context-budget outcomes. Validate scope; bounded appropriate retries.
- Handle redirects/encoding/PDF/downloads/oversized responses/boilerplate. Authorized
  browser fallback for JavaScript/session pages, never bypass controls. Bounded stable
  chunks, exact plus semantic where available, deduplication; benchmark before reranking.
  Changed-source invalidation, timestamps/refresh, sensitive/authenticated cache limits,
  summary/verbatim and stale/fresh/no-match/failure distinctions. Sources are untrusted.
- Searchable skill categories/purposes/prerequisites/inputs/outputs/permissions; preflight
  dependencies/credentials/access, lifecycle states with reasons, argument/output
  validation, interruption/auth/missing-source recovery, common retrieval implementation,
  overlap/conflict audit. Expand after existing workflows demonstrate reliability.
- Integration connect/authorize/cancel/verify/reconnect/disconnect; cached discovered
  capabilities invalidated on changes; Connected only after live success. Structured
  results/evidence/duration/recovery. Sign-in never grants integration permissions.
- Orchestration: standard/abliterated/both, all eligible downloaded or allowlist,
  image/context needs, inclusion/exclusion reasons, no-eligible behavior, separate router
  and specialist policy, no implicit downloads or out-of-pool route, honest routing reason.

## 0.2.19 — measured hardware tuning

CPU/GPU/VRAM/RAM/runtime page; opt-in existing-runtime or llama-bench comparisons for
threads and supported CPU/partial/full offload. Measure TTFT, prompt/decode, RAM/VRAM
and responsiveness. Best measured profiles keyed to model/runtime/hardware with
provenance/rollback; no automatic application. Installed models only, no experimental
forks/BIOS advice or X3D claims without repeated gains. Separate renderer/model measures.

## 0.2.20 — file-first autonomy

Read/create/edit/move-to-trash before app control. Objective/allowed locations/criteria
first; observe/plan/act/verify/recover with fresh screenshots/accessibility, no invented
coordinates. Review/Full Access and OS boundaries, visible activity/interrupt/immediate
Stop, verify results, durable checkpoints/no replay, inspect uncertainty, recoverable
deletes and explicit permanent deletion. External content untrusted; user handles login
and microphone permissions. App control follows verified file foundations.

## Delivery invariants

Each step has its own branch/release/PR, one open PR at a time; additional splits need
explicit scope revision. Reuse current frontend/backend contracts and document changes
and migrations. FastAPI, plain HTML/CSS/JS, WebView2, SQLite, PyInstaller/Inno stay;
no React/build pipeline/CDNs or model downloads for testing.

Separate unit/fixture, scripted-browser, real-provider, real-model and packaged-desktop
evidence. Include crash/cancel/restart/duplicate prevention, failed final generation,
bad/missing/denied/expired/throttled/oversized sources, stale caches and two-PC sync.
Verify a desktop evidence-retrieve/create/verify skill. Never broadly discover Python
tests (memory_denial contacts the installed app at import); run modules individually,
existing Node tests and auth-service npm test.

Update Delivery status honestly. PR verification lists unchecked layers and gaps.
Bump VERSION/write versioned release notes when preparing that release. User runs
build.ps1/publish-release.ps1; desktop/update/migration regression before release-ready.
Unsigned builds. Provider secrets only in Worker; never print GITHUB_RELEASES_TOKEN.
No private config/history/secrets/recordings/weights in commits. PowerShell instructions
as a single & { ... } block, using npx.cmd when needed. No deployment as a side effect.
