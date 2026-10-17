# Luminaria: remaining delivery scope

Checkpoint: merged main 2699b0e, version 0.2.8. This is a work list, not an
acceptance claim. Current live channel and installed app were checked at 0.2.7
before this update pass. Check the live channel again for current release status.

## Immediate: desktop update and planning

- Install the matching 0.2.8 candidate through the updater when publication is
  authorized. Verify the release manifest, download size/checksum, installer exit,
  new installed version, restart and preservation of profiles/data/models.
- The existing update_plan tool already creates/revises up to 24 steps with known
  dependencies and pending/active/done/blocked/skipped statuses. The engine prompts
  the model to use it for multi-step work; this is model behavior, not a guarantee.
  Run a real Qwen task and inspect plan revisions, executed tools and recovery.
- An explicit user-selectable planning-only mode is separate from this existing
  tool. It has not been added or claimed implemented.
- Run docs/testing-0.2.8.md. Until native acceptance, distinguish publication for
  testing from an accepted release.

## Spatial UI and voice acceptance

- Watch real task/voice transitions in native WebView2: entity travel, branching,
  failure follow-ups, cancellation, retained records and reconnected history.
- Verify real microphone/output reactivity and interruption during both generation
  and playback. Exercise queued text versus new spoken turns, approvals and errors.
- Check keyboard/focus, narrow windows, real OS reduced motion, pause/fallback,
  sustained performance and audio/graphics resource stability.
- Test all appearance controls in the desktop app and persistence after restart.
  Fix the known per-PC startup appearance cache/profile flash if stronger profile
  isolation before first paint is required.
- Natural male/female voices and previews need end-to-end checks, including device
  changes, silence thresholds and recognition/TTS failures; historical 42/four
  voice confirmations do not certify every current configuration.

## Models and context

- Verify a real catalog download through installation, checksum, registration,
  cancellation/resume, storage refresh and model-manager reload on Windows.
- Verify Standard/Abliterated grouping, installed filtering, quantization/context
  descriptions, fractured treatment and actionable low-space/load failures.
- Benchmark real candidates before choosing defaults. Confirm immediate speed-card
  refresh and keep coding/reasoning quality results separate from speed.
- Respect the additional 100 GB budget. Do not download large weights for UI tests.
- Validate larger configured contexts against memory use and quality before adding
  advanced expansion controls. Automatic specialist routing remains deferred until
  measured need. Compaction/retrieval does not increase a model's native context.

## Memory, tools, files and workflows

- Verify persistent history/facts, retrieval and automatic compaction with a real
  long conversation; retain original evidence, decisions and outstanding work.
- Exercise real file edits, code/shell, web/browser, vision/computer use, document
  creation and scheduled workflows, including denial/cancel/failure recovery.
- Verify Review/Full Access restart behavior and file boundaries. Full Access
  cannot grant operating-system permissions or integration credentials.
- Verify PDF/DOCX/folder ingestion, model quality checks and chat trash/fork/restore
  flows in the packaged app; source and fixture tests are not desktop acceptance.
- Reconcile the original requested skill inventory with the 21 recorded installed
  skills; do not count unavailable integrations as working skills. Marketplace or
  external skill discovery needs a defined trust/install/update flow.

## Accounts and integrations

- Real GitHub login was historically confirmed; restart/session recovery, logout,
  revoked/expired sessions, denied consent and offline behavior remain to verify.
- Google and Discord publisher setup and live login flows remain to complete.
- Keep mandatory sign-in disabled until explicitly requested and accepted; local
  profiles and hosted identity are separate from service integration permissions.
- Exercise real Google Workspace, GitHub, messaging, database and other connector
  credentials/scopes. Local/mock OAuth checks do not prove a live service works.
- Verify profile separation for history, settings, memory and files. Keep secrets
  out of source, release assets, logs and model-visible outputs.

## Distribution and ongoing maintenance

- Finish real in-app upgrade and data-preservation checks, then clean-machine
  install/uninstall, interrupted update, corrupted download and recovery tests.
- Configure code signing before claiming signed builds; current installers are
  unsigned. Public distribution/landing-page work is separate from the existing
  private GitHub release channel.
- Keep source, versioned notes, installer and checksum aligned. Preserve explicit
  test evidence and do not equate a merged PR or published asset with acceptance.
- Revisit the full non-conflicting master requirements as each area is accepted;
  this list does not discard older target scope or silently mark it finished.
