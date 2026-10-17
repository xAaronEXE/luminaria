# Luminaria — full scope of work

Checkpoint: October 17, 2026, `main` at 0.2.17. This document puts everything that was
planned in one place: the master specification, the delivery scope, the October 17 roadmap,
the annotation review, the 0.2.13 testing feedback and the remaining-scope lists. Older
documents stay as history; this list wins where they disagree. It is a work list, not a
completion claim.

Sources: [MASTER-SPEC.md](MASTER-SPEC.md), [CURRENT-SCOPE.md](CURRENT-SCOPE.md),
[ROADMAP-2026-10-17.md](ROADMAP-2026-10-17.md), [../ANNOTATION-UPDATE-2026-10-17.md](../ANNOTATION-UPDATE-2026-10-17.md),
[../remaining-scope-0.2.8.md](../remaining-scope-0.2.8.md), [../followup-spatial-workspace.md](../followup-spatial-workspace.md).

## How status is reported

Planned · Implemented · Automated checks passed · Desktop verified · Released.

- An item moves up only when that level has actually been reached. Code existing, a
  screenshot looking right or unit tests passing do not make a feature complete.
- Say which layer each check covers: unit test, scripted browser against the real backend,
  real provider or service, or the installed desktop app. Browser checks with mocked or
  seeded data are never desktop verification.
- Publishing an installer is not acceptance. Every release so far is an **unsigned testing
  release**.

## Where things stand

| Area | State |
| --- | --- |
| Published | 0.2.17 is the latest GitHub release and the live update channel serves it. It also contains 0.2.15 and 0.2.16. |
| Identity Worker | Deployed with the device-session and insights routes (both answer "Sign-in required" without a session). D1 migrations 0002 and 0003 were run before the deploy. |
| Desktop acceptance | Not done for any feature added since 0.2.8. That is the main gap: see Part A. |
| Signing | None. Installers are unsigned. |
| Housekeeping | A leftover **Draft** release for v0.2.17 exists beside the published one. Delete it. Old merged `cursor/*` and `codex/*` branches can be pruned. |

## Ground rules (carried forward, non-negotiable)

- Local-first. Raw chats, files, tool output and audio never leave the PC unless an explicit
  integration uses them. Insights sync is opt-in and sends daily totals only.
- No secrets, personal histories, private configuration, model weights or test recordings in
  Git, logs, release assets or model-visible output. Provider secrets live only in the Worker
  (`wrangler secret put`). `GITHUB_RELEASES_TOKEN` is never echoed.
- Signing in to Luminaria never grants integration access. Never merge identities by email.
  No password login unless explicitly requested. Mandatory sign-in stays off until desktop
  verified and explicitly turned on.
- No invented telemetry, confidence or "thoughts". Show real measurements or say a value is
  unavailable. The lattice is an activity view, not hidden-thought inspection.
- Plain HTML/CSS/JS with local assets. No React, no new frontend toolchain, no runtime CDN.
- Keep the black/white light and dark modes plus full customization. Never silently remove
  Automations.
- Use the models already installed for testing; don't download large weights for UI tests.
  Additional model budget: 100 GB.
- Run Python tests one module at a time. `tests/memory_denial.py` calls the installed app at
  import time, so broad discovery is off limits.
- Don't automate microphone permission or sign-in dialogs; hand those steps to Aaron.
- One open PR at a time. PowerShell instructions come as one combined `& { ... }` block, using
  `npm.cmd`/`npx.cmd` or `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force`.

---

## Part A — Built, needs desktop acceptance

Everything here is in the installed 0.2.17 but has only passed automated checks (or
earlier partial checks noted below). Each line is a check for Aaron to run in the installed
app; failures get fixed and the affected checks repeated. A checklist file
(`docs/testing-0.2.17.md`) should be written from this section.

### A1. Update and install
- [ ] The update notice appears briefly on launch when a newer release exists. View opens
      Settings → Updates. Dismissing it hides it for that version. It never downloads by itself.
- [ ] An in-app update from one release to the next: manifest, size and SHA-256 check,
      installer exit, new version shown, and profiles, data and models preserved.
- [ ] Interrupted update, corrupted download and recovery.
- [ ] Clean-machine install, upgrade and uninstall. Shortcuts and icon.

### A2. Account and sign-in (0.2.16 work)
- [ ] Real sign-in with GitHub (worked historically in 0.2.4), Google (still in Google's
      Testing mode) and Discord, from the sign-in screen. Cancel while waiting.
- [ ] The device stays signed in after a restart. 30-day idle and 90-day maximum behave as
      described.
- [ ] Profile page: account, linked methods, device list with names. Sign out another PC
      and confirm that PC is really signed out. Sign out all other devices.
- [ ] Denied consent, expired session, server revocation, offline use within and beyond
      the 7-day grace period.
- [ ] Per-profile migration choice (attach, keep separate, leave untouched). Nothing moves or merges.
- [ ] Profile separation for history, settings, memory and files. The startup appearance
      flash when switching profiles (see B8).
- [ ] Only after all of the above: try required sign-in, then decide whether to enable it.

### A3. Insights (0.2.17)
- [ ] Real counts appear after normal use: tokens (cached where the runtime reports them),
      streaks, busiest day, fastest speed, largest and longest task with wait time apart.
- [ ] The time zone setting changes days and streaks. Export downloads JSON. Delete removes data.
- [ ] Sync on two PCs. Account totals add up with no double counting after uploading twice.
      Deleting synced totals works.

### A4. Working brief and compaction (0.2.17)
- [ ] Add, edit, pin, unpin and remove brief entries. History shows replaced wording.
      `/brief` opens it.
- [ ] The assistant proposes an entry; it cannot add a permission or change Aaron's entries.
      Passwords and keys are refused.
- [ ] A long real chat on a local model compacts at least twice. Pinned brief entries,
      decisions, pending work and exact file paths survive. Originals stay retrievable.
- [ ] Memory & context → "Compaction on this PC" shows the real runs, including failures.

### A5. Reliability (0.2.15)
- [ ] A task reaching the tool-round limit leaves a readable partial-results message in
      chat. Continue task resumes without repeating completed writes.
- [ ] Three identical failures stop early with an explanation.
- [ ] Web fetch on real sites: an article, a PDF, a JavaScript-only page, a blocked page and
      a 404. Record outcome and time for each. Measure real failure rates.
- [ ] Retrieval errors show distinct, useful messages: missing file, denied access, timeout,
      empty search.

### A6. Settings and UI (0.2.13 to 0.2.15)
- [ ] Sidebar order: Memory, Tools, Integrations, Skills, Automations, Model library,
      Archive & trash, Account & settings at the bottom. No motion entry in the sidebar.
- [ ] Memory & context sliders: keyboard use, validation, saved state, whether a reload is needed.
- [ ] Semantic accents in both modes. A custom accent never hides error, warning or success.
      Accent and colors persist after closing and reopening (reported broken before 0.2.13).
- [ ] All appearance controls from the 0.2.8 checklist, including Follow system with a real
      Windows theme change and real reduced motion.
- [ ] Compact chat menu, working-folder picker, per-model context setting with reload.

### A7. Models and orchestration
- [ ] A real catalog download: queue, cancel, resume, checksum, registration, storage meter
      refresh, model manager reload. Low-space refusal.
- [ ] Use this model, Benchmark (speed) and the 12-question quality check against a real
      model. Results persist and refresh immediately.
- [ ] Orchestration: the included and excluded list matches installed models, with reasons.
      The Standard / Abliterated / both filter and the allowlist are respected. Nothing
      routes outside the pool. The chat model picker opens the model list, not settings.
- [ ] Model failure explanations (out of memory, damaged file, projector, port, timeout)
      with real failures where safe.

### A8. Planning and agent work
- [ ] Plan only builds a plan from what was described, shows it on request, and Carry out
      plan follows the recorded steps. Record model and result: plan quality is model behaviour.
- [ ] Real file edits, code and shell, web and browser, vision and computer use, document
      creation and scheduled automations, including deny, cancel and failure recovery.
- [ ] Review vs. Full Access after restart, and the working-folder boundary.
- [ ] PDF, DOCX and folder attachments; chat rename, fork, archive, restore, trash and
      permanent delete.

### A9. Voice and spatial workspace
- [ ] Real microphone and speaker reactivity; male and female voices with previews; device
      changes, speed, silence and threshold settings; recognition and speech failures.
- [ ] Barge-in during generation and during playback, with no stale audio or replies.
      Queued typed messages vs. new spoken turns. Approvals and errors during voice.
- [ ] Lattice and toroid transitions during real text and voice tasks: travel between steps,
      failures, cancellation, history after reconnect. Orbit, pan and zoom by mouse and keyboard.
- [ ] Narrow windows, keyboard focus, real reduced motion, graphics fallback, sustained
      performance and GPU use over a long session.

### A10. Integrations
- [ ] Connect each real service at least once: GitHub, Linear, Notion, Slack, Gmail, Drive,
      Calendar, and a custom MCP connector. Read-only where offered. A service only shows
      connected when its tools loaded. Disconnect and reconnect.

---

## Part B — Planned work not built yet

Ordered by the roadmap's suggested sequence. Each phase ships as its own release with a
verification table.

### B1. Retrieval, skills and integrations hardening (next: 0.2.18)
Roadmap rows "Skills and integrations hardening" plus the unfinished parts of
"Retrieval and skills hardening". Audit against the code first. Known gaps on `main`:

Retrieval
- Authorized browser fallback for JavaScript-only pages. Today `needs_javascript` is
  detected and the user is told a browser tool can read it; there is no automatic
  fallback. Never bypass access controls or logins.
- Better search over history, memory and files: chunked results with stable source
  references, exact-term search (SQLite FTS5) plus semantic search where a local embedding
  model is available, deduplication and context around matches. Benchmark usefulness
  before adding a reranker.
- Freshness: invalidate cached content when a source file changes. Clearly separate summary
  vs. verbatim, stale cache vs. fresh read, and "no match" vs. "retrieval failed".
- Saved evidence and excerpts linked to source and retrieval time.
- Measure failure rates by category from `retrieval_events` on the desktop, reproduce the
  common ones with saved fixtures, then fix.

Skills
- Each skill states purpose, prerequisites, inputs, outputs and permissions in plain English.
- Dependency and credential check before running. States: Ready, Needs setup, Running,
  Failed, Completed, each with a reason (today only Ready / missing requirements is shown).
- Validated arguments and outputs. Recovery for missing sources, partial output, expired
  auth and interruption. Cancellation reaches subprocesses. No duplicate side effects on continue.
- Review overlapping skills; one shared retrieval implementation.
- Reconcile the **original requested skill list** (never received; 21 installed skills were
  inventoried instead). Aaron to supply it.
- A trust, install and update flow before any external skill marketplace.

Integrations
- Guided connect flows: authorize, cancel, verify, reconnect, disconnect, with plain-language
  scopes and readiness. Searchable categories.
- Cached capability discovery, invalidated when a connector changes.
- Consistent structured results (status, evidence, duration, recovery guidance), bounded
  retries, no duplicated side effects.
- Integration tools usable without needing Full Access where the user approved the connection
  (today they need Computer and command tools or Full Access).
- Discord and databases: no official hosted server; decide on a supported connector.
- Never show a planned integration as connected before credentials and a live check succeed.

Acceptance: the roadmap's "Acceptance checks before calling this complete", including a
multi-step skill that retrieves evidence, produces output and verifies it in the desktop app.

### B2. Orchestration quality and plan mode (0.2.18 or 0.2.19)
From the 0.2.13 testing feedback and the annotation review. Eligibility controls shipped in
0.2.14 and 0.2.15; quality did not.
- Routing chose poorly in testing. Build a small representative task set (coding, reasoning,
  vision, writing, quick questions), record which model each route picks and how it does,
  and tune the routing prompt or rules from that data. Measure model switch time and VRAM.
- A strong low-VRAM default orchestrator recommendation, chosen from measurements.
- Plan mode: build the plan actively from the user's description, keep it updated, and show
  it on request. Measure with real models.
- No parallel agents or multi-specialist subtasks are claimed; decide later whether to add them.

### B3. Hardware page and tuning benchmark (0.2.19 or 0.2.20)
- System information page: CPU (Ryzen 7 7800X3D), GPU, VRAM, RAM, runtime version.
- Opt-in benchmark with `llama-bench` or the existing runtime: thread counts, CPU-only vs.
  partial vs. full GPU offload. Measure first-token time, prompt processing, decode speed,
  RAM and VRAM, and UI responsiveness.
- Save the best measured profile per model, runtime and hardware combination, with
  provenance and rollback. Nothing changes automatically.
- No "X3D optimized" label without repeated measured gains. No experimental runtime forks or
  BIOS advice.
- Related: validate larger context settings against memory use and quality before adding
  advanced context expansion. Compaction does not increase a model's native context.

### B4. Autonomous computer operation (later)
- Observe → plan → act → verify → recover loop.
- Objective, allowed locations and completion criteria set before a run.
- Fresh screenshots and accessibility state only; never invented coordinates.
- Respects Review / Full Access and OS permissions. Visible activity, interrupt and an
  immediate Stop.
- Verify every file and UI result. Checkpoints and idempotency so completed actions are
  never replayed after a failure or restart.
- Recoverable deletes by default; permanent deletion explicit. Pages, files and tool output
  are untrusted.
- Start with file workflows (read, create, edit, move to trash), then app control.

### B5. Account follow-ups
- One account with explicitly linked providers, shown together (multiple provider sessions
  can already coexist locally; server-side linking of a second provider to the same account
  needs a desktop check and possibly a "link another method" flow).
- Google production publishing: public homepage and privacy policy, then move the OAuth app
  out of Testing.

### B6. Insights follow-ups
- Reasoning levels used, where the runtime reports them (currently only reasoning on/off).
- Account-wide streak and time zone defined at the account level once sync is verified.

### B7. Voice and spatial follow-ups
- Persist voice state in the execution record (currently client-side only).
- Optionally persist queued typed messages across restarts (currently memory-only, max ten).
- Native pointer and touch drag testing; tune motion and performance from real measurements.

### B8. Appearance follow-ups
- Per-profile startup appearance before first paint (the cache is per PC, so switching
  profiles can briefly flash the previous colors).
- Remove the legacy custom palette values that are stored but no longer applied.

### B9. Distribution and release readiness
- Code signing before ever calling a build signed.
- Clean-machine, upgrade, uninstall, interrupted-update and corrupted-download tests (A1)
  as a standing release gate.
- Public distribution and landing page, separate from the private GitHub release channel.
- Keep source, VERSION, release notes, installer and checksum aligned; one release per tag.
- Final end-to-end acceptance across every area in Part A before calling any release
  accepted rather than testing.

---

## Decisions needed from Aaron

1. The original requested skill list (for B1), or confirm the 21 installed skills are the target.
2. Whether to turn on required sign-in after A2 passes.
3. Whether insights sync should stay off by default.
4. Discord and database integration approach (custom MCP connector vs. a maintained one).
5. Whether to spend money and time on code signing now or before public release.
6. Release order: the suggestion is 0.2.18 = B1, 0.2.19 = B2, 0.2.20 = B3, then B4.

## Suggested order

1. Write `docs/testing-0.2.17.md` from Part A. Aaron runs it; fix what fails, one testing release.
2. B1 retrieval, skills and integrations hardening.
3. B2 orchestration quality and plan mode, using measured task sets.
4. B3 hardware page and tuning benchmark.
5. B4 autonomous computer operation, starting with files.
6. B5 to B8 follow-ups as they come up, folded into the nearest release.
7. B9 signing, clean-machine testing and public release readiness.
