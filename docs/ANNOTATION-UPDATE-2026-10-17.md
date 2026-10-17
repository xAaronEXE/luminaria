# Annotation update — 17 October 2026

Branch: `feature/annotated-workspace`. Source review: `http://127.0.0.1:3211/`.
This is a running source build, not an installed desktop release. Its chats,
settings and test artifacts use `data/annotation-review`; installed app data
and history are not used as the review database. Installed weights and the
existing inference manager are reused for real inference.

## Changes

- Immediate, ordered appearance saves; app-wide appearance survives local
  profile changes. Atomic storage in the app data directory.
- Account/settings entry in the sidebar footer; removed Accounts from the
  composer menu. Existing local profiles remain under a recovery disclosure.
- Independent encrypted provider sessions can coexist in the current data
  profile. A new provider sign-in does not create/select a new profile.
  These are local sign-in sessions, **not server-side account linking**.
- Anchored, keyboard-accessible chat menus instead of the large side sheet.
- Spatial toolbar reduced to Follow activity and Return to chat. Pointer
  orbit, Shift/right-drag pan, wheel zoom; keyboard Alt+arrows orbit,
  Shift+arrows pan, +/- zoom. Semantic colors for seven activity regions.
- Working folder entry in the composer menu; direct folder setting with
  a plain-language explanation of file-tool scope.
- Plain-language context options: percentage trigger, recent turns retained,
  next-answer budget. Summaries retain provenance and are retried on truncation
  or budget failure. Original history and prior summary versions remain saved.
- Fixed Qwen template compatibility: planning instructions and working summary
  share the single initial system message, rather than separate system messages.
- Per-installed-model context controls, installed-file and known context-limit
  validation; model-manager ownership and active-run checks before reload.
- Skill instruction inspection; clearer tool purposes and grouping; integration
  search and clearer setup guidance. Existing service-specific credential setup
  is still necessary where the publisher has not supplied a hosted connector.
- Optional installed-model router. It selects one specialist per new task turn;
  ordinary tools, approvals and Plan only restrictions remain in force. Uses
  task-local inference settings, preserves specialist on resume, validates IDs,
  and falls back to the user's selected model on invalid routing.
- Completed run model and measured speed remain readable after backend restart.

## Verified

- 42 focused Python checks: appearance, source persistence, compaction validation,
  concurrent provider-session status, startup gate, routing, planning restrictions,
  recorded work and approval replay. JavaScript syntax and whitespace checks pass.
- Real Qwen 4B routing selected Qwen Coder 30B for a coding task. The specialist
  returned the requested Python function. This is one handoff test, not an
  evaluation of general routing quality or a VRAM benchmark.
- Real automatic compaction completed at a deliberately small logical context
  budget; two summary versions were retained. Ten original test messages remained
  unchanged. The next reply recovered Atlas, ATLAS-731, constraints and pending work.
- Accent persisted through a source-backend restart. Test palette was restored.
- Browser checked compact chat menu, profile/settings navigation, model context
  field, orchestration selector, simplified spatial toolbar and keyboard pan/orbit.

Test artifacts are local and ignored under `data/annotation-review`.

## Still requires acceptance

- Native desktop rebuild/install/restart and microphone/voice regression checks.
- Real multi-provider sign-in and sign-out on the new session implementation;
  automated checks use encrypted disposable sessions and mocked identity responses.
- A unified hosted Luminaria account with explicitly linked providers. No automatic
  email-based identity merging was introduced. Google production publication still
  requires its public branding/privacy setup.
- Per-model context reload in a process that owns the model manager. The review
  build must refuse to replace another desktop process's manager.
- Native pointer/touch drag testing, routing quality across a representative task
  set, measured model-switch latency and VRAM use, and connection acceptance for
  each external service. No claim of parallel agents or multi-specialist subtask
  orchestration is made by this first routing implementation.
- Installer packaging, release notes, updater publication and deployment. None of
  these changes have been published by this work.
