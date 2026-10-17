# Luminaria — full scope of work

Checkpoint: October 17, 2026. `main` is at 0.2.17, which is the latest published release.

This document puts every planned requirement in one place, area by area, with what is built
and what remains. It combines:

- [MASTER-SPEC.md](MASTER-SPEC.md) (accepted October 16) and [SCOPE.md](SCOPE.md) (history).
- [CURRENT-SCOPE.md](CURRENT-SCOPE.md) (decisions through October 16).
- [ROADMAP-2026-10-17.md](ROADMAP-2026-10-17.md) (account, insights, memory, reliability, UI refinement).
- Aaron's spatial-interface and appearance brief, the "layer this into what you have" brief
  and the earlier eight-part scope list (captured in chat, summarized here).
- The 12 annotations from the October 17 review ([../ANNOTATION-UPDATE-2026-10-17.md](../ANNOTATION-UPDATE-2026-10-17.md)).
- Aaron's 0.2.13 testing feedback, and the profile page reference shared on October 17.
- [../remaining-scope-0.2.8.md](../remaining-scope-0.2.8.md) and [../followup-spatial-workspace.md](../followup-spatial-workspace.md).

Where documents disagree, the newest instruction wins. Superseded directions are listed in
section 0.3 so they are not reintroduced. This is a work list, not a completion claim.

---

## 0. How to read and use this document

### 0.1 Status levels
**Planned · Implemented · Automated checks passed · Desktop verified · Released.**

- An item moves up only when that level has actually been reached. Code existing, a screenshot
  looking right or unit tests passing do not make a feature complete.
- Every check names its layer:
  - **Unit:** isolated Python or Node tests.
  - **Browser:** a scripted browser against the real backend, possibly with stubbed or seeded data.
  - **Provider:** a real external service such as GitHub, Google or the Cloudflare Worker.
  - **Desktop:** the installed Windows app.
- Browser checks are never desktop verification. Publishing an installer is not acceptance.
  Every release so far is an **unsigned testing release**.
- In each area below, **Built** means implemented with automated checks unless stated
  otherwise. **Remaining** lists both work still to build and acceptance still owed.

### 0.2 Ground rules (non-negotiable)
- **Local-first.** Raw chats, files, tool output, page contents, credentials and audio never
  leave the PC unless an explicitly connected integration uses them. Insights sync is opt-in
  and sends daily totals only.
- **Secrets.** No secrets, personal histories, private configuration, model weights or test
  recordings in Git, logs, release assets or model-visible output.
  - Provider secrets live only in the Worker (`wrangler secret put`).
  - `GITHUB_RELEASES_TOKEN` is never echoed.
  - Use the owner's personal Cloudflare account, never ACT resources.
- **Identity.** Signing in to Luminaria never grants integration access. Never merge identities
  by email. No password login unless explicitly requested. Mandatory sign-in stays off until it
  is desktop verified and explicitly turned on.
- **Truthfulness.**
  - No invented telemetry, confidence, temperature, CPU/GPU load or "thoughts". Show real
    measurements or say a value is unavailable.
  - Tool and workflow events are execution evidence. Model-provided plans and reasoning are
    labelled as such. A model claiming it did something is not proof.
  - Ambient animation must be distinguishable from real activity.
- **Stack.** Plain HTML/CSS/JS with local assets, Python backend, SQLite, native Windows
  packaging. No React, no new frontend toolchain, no runtime CDN.
- **Location.** Everything Luminaria owns lives under `C:\Users\desse\Desktop\Luminaria`.
- **Testing.**
  - Use the installed models; don't download large weights to test UI or graphics.
  - The additional model budget is 100 GB.
  - Run Python tests one module at a time. `tests/memory_denial.py` calls the installed app at
    import time, so broad discovery is off limits.
  - Use an isolated test instance (`STUDIO_PORT`, separate data folder). Don't disturb
    Aaron's running app.
- **Hand-offs.** Don't automate microphone permission or sign-in dialogs; hand those steps to Aaron.
- **Working conventions.**
  - One open PR at a time.
  - PowerShell instructions come as one combined `& { ... }` block, using `npm.cmd`/`npx.cmd`
    or `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force`.
  - Never run `publish-release.ps1` on a branch whose `VERSION` differs from the intended release.

### 0.3 Superseded directions (do not reintroduce)
- Acid Mint default, "Studio" branding, many theme presets and saved personal palettes
  (from SCOPE.md).
- The Graphite & Ivory palette (MASTER-SPEC). It was replaced by the **black-and-white**
  identity with optional accents.
- "No custom color editor" (from the "layer this in" brief). It was replaced by **global
  appearance customization**.
- A brain that simply switches into a torus. It was replaced by an **entity that navigates a
  neural lattice**, with both coexisting.
- "Additional abliterated models and separate groups deferred". It was replaced by the
  **downloadable model library** with Standard and Abliterated sections.

### 0.4 Locations
| What | Where |
| --- | --- |
| Project root | `C:\Users\desse\Desktop\Luminaria` |
| Installed app, data, models | `App\LocalAIStudio.exe`, `App\data`, `App\models` |
| Runtime and Python | `runtime\local-ai`, `runtime\local-ai\agent-tools\python-env\Scripts\python.exe` |
| Identity service | `auth-service` → `https://luminaria-identity.johnnycox4431836.workers.dev` (D1 `luminaria-identity`) |
| Repository | `xAaronEXE/luminaria`, branch `main` (private) |
| Release process | Bump `VERSION`, write `docs/release-notes/X.Y.Z.md`, then `build.ps1` and `publish-release.ps1` |

### 0.5 Where things stand
- **Published:** 0.2.17 is the latest release and the update channel serves it. It includes
  0.2.15 and 0.2.16.
- **Identity Worker:** deployed with the remembered-device and insights routes (both answer
  "Sign-in required" without a session). D1 migrations 0002 and 0003 were applied.
- **Desktop acceptance:** none of the features added since 0.2.8 has been accepted in the
  installed app. This is the largest gap.
- **Housekeeping:**
  - A leftover **Draft** release for v0.2.17 sits beside the published one. Delete it.
  - Merged `cursor/*` and `codex/*` branches can be pruned.

### 0.6 Verified so far (real, not automated)
- **Sign-in:** installed 0.2.4 completed real GitHub sign-in as xAaronEXE, with server-side
  validation and a DPAPI-encrypted session. A later running instance reported the session
  verified by the identity server.
- **Voice:**
  - Aaron heard Qwen speak "42".
  - Interrupting playback stopped the old answer and produced "four".
  - The full interruption matrix is not established.
- **Source-build checks (one each):**
  - A real routing handoff, Qwen 4B to Qwen Coder 30B.
  - A real automatic compaction that kept Atlas / ATLAS-731, the constraints and the pending work.
- **Update channel:** serves each release with a checksum matching the GitHub asset. Releases
  0.2.5 through 0.2.17 were published. An in-app upgrade with data preservation has not been
  formally accepted.

---

## 1. Product identity and brand

**Requirement**
- Permanent name Luminaria, used everywhere: window, installer, icons, docs, repository and
  sharing imagery.
- Keep the approved neutral logo, which works in both appearances.
- Mission: a local-first AI harness for coding, reasoning, research, planning, documents,
  tools, automation, vision and voice. Everything runs on user-owned hardware by default.
- "Impeccable" quality bar: clear hierarchy, precise spacing, crisp typography, smooth motion,
  no clutter, fake dashboards, placeholder controls or unnecessary explanatory text.

**Built:** branding, logo, installer, icons and sharing imagery.

**Remaining**
- [ ] A final polish pass across all screens: spacing, typography, dialogs, loading, empty,
      error and disabled states.
- [ ] Public homepage and privacy policy. These are needed for Google production sign-in and
      any public distribution (see 15).

---

## 2. Appearance and customization

**Requirement** (spatial brief, sections 1–2)
- Predominantly **black-and-white**.
  - Dark: black and near-black backgrounds with white text.
  - Light: white backgrounds with black text.
  - Both designed deliberately, never by an inversion filter.
  - Light is the default.
- Optional accent color for buttons, selection, focus, progress and highlights.
- **Global token system** covering every surface: background and ambient space, sidebar,
  panels, dialogs, inspector, raised and hover surfaces, text, borders, composer, inputs,
  menus, tooltips, code blocks, buttons and their states, progress, model library, skills,
  approvals, settings, the entity, lattice, pathways, particles and lighting.
- The CSS interface and the 3D renderer consume the same settings through an explicit update
  mechanism. No scattered hardcoded colors.
- Light, Dark and Follow system modes.
  - Shared accents, with optional per-mode overrides.
  - Separate surface and text adjustments for each mode.
  - Switching modes restores that mode's adjustments.
- Persistence:
  - Saved per profile.
  - Survives navigation, restart and updates.
  - Applied before first paint, with no theme flash.
  - New panels inherit the current settings immediately.
  - Compatible old settings migrate.
- Controls:
  - Simple accent picker.
  - Expandable advanced controls for surfaces, text, borders, controls and 3D.
  - Live application and save status.
  - Reset the current mode, and a separately confirmed reset of everything.
- Contrast warnings with reliable recovery. Status is never conveyed by color alone.
- **Semantic function accents** (roadmap): restrained color on selected words, icons,
  indicators and state labels. Memory gets its own color, as do other functions. Neutral
  surfaces stay dominant. Custom accents never erase the error, warning and success distinctions.

**Built**
- Black/white Light, Dark and Follow system, with persistent shared and per-mode accents (0.2.8).
- Per-mode UI and spatial color controls with contrast warnings and resets (0.2.8).
- The accent tints the whole interface and the 3D scene unless a color is set individually (0.2.11).
- Immediate, ordered saves that persist after restart and profile changes (0.2.13). This fixed
  Aaron's "accent didn't stay after reopening" report.
- Function accents for memory and tools; state colors stay distinct (0.2.15).
- The motion switch lives in Appearance and honors Windows reduced motion (0.2.15).

**Remaining**
- [ ] **Build:** apply each profile's appearance before first paint. The startup cache is per
      PC, so switching profiles can briefly flash the previous colors.
- [ ] **Build:** remove the legacy custom palette values that are stored but no longer applied.
- [ ] **Build:** check that no hardcoded legacy colors remain. Aaron reported that changing the
      dark-mode accent to red changed only a few things (addressed in 0.2.11 and 0.2.13; re-verify).
- [ ] **Desktop:**
  - Light, Dark and Follow system with a real Windows theme change.
  - Accents and advanced colors persist after restart and after an update.
  - Mode switching keeps each mode's adjustments.
  - Each profile keeps its own appearance.
  - Low-contrast warning and the resets.
  - Readable menus, approvals, errors, code, Models and the 3D view in both modes.
  - Follow the full checklist in `followup-spatial-workspace.md`.

---

## 3. Main layout, navigation and chat management

**Requirement**
- Codex-inspired composition: a narrow left sidebar, a spacious central conversation, a
  refined bottom composer and an optional files/activity/context inspector.
- Plain language, such as **My files** instead of "workspace".
- **Sidebar order** (top to bottom):
  1. Memory
  2. Tools
  3. Integrations
  4. Skills
  5. Automations (never removed)
  6. Model library
  7. Archive & trash
  8. Account & settings, anchored bottom-left
- No "Pause background motion" entry in the sidebar.
- **Chat actions:** new chat, search, rename, fork/branch, archive, restore, trash with
  recovery, and permanent delete with confirmation. Streaming, cancel, error and approval states.
- **Compact chat menu** (annotation): a small anchored right-click-style menu, not a large side sheet.
- **Message queue:** typing while a task runs queues messages per chat. They can be cancelled
  or retried, and voice turns take priority.

**Built**
- Layout, My files, the inspector and searchable history.
- Rename, fork, archive, restore, trash, plus permanent delete and Empty trash (0.2.6 era).
- Message queue (0.2.8): memory-only, up to ten unsent messages, with a warning on close.
- Compact anchored, keyboard-accessible chat menus (0.2.13).
- Account & settings in the sidebar footer (0.2.13).
- Sidebar reorder, separate Tools and Integrations panels, and the motion entry removed (0.2.15).
- Activity search across all chats, with filters for errors, denials and interruptions.

**Remaining**
- [ ] **Decide:** whether queued messages should persist across restarts. They are memory-only today.
- [ ] **Desktop:**
  - Sidebar order and panels.
  - Chat menu.
  - Fork, archive, restore, trash and permanent delete.
  - Queue versus voice priority.
  - Narrow windows and keyboard focus.

---

## 4. Composer and live information

**Requirement**
- Keep the approved composer shape. It includes:
  - The message input.
  - An expandable **plus menu** with attachments, local files and folders, skills, integrations
    and setup indicators.
  - A **model selector**.
  - Accurately explained **reasoning controls** supported by the selected model.
  - A **dictation microphone** that fills the composer without sending.
  - A separate **conversational voice** control beside Send.
  - Polished Send/Stop.
- **Live strip:**
  - Shows the active model, context usage and capacity, tokens per second, time to first token,
    and compaction status with a manual compact button beside the context figure.
  - Live values, completed-run figures and historical benchmarks are distinguished.
  - Shows "unavailable" rather than fake numbers.
- **Working folder** (annotation): choose where the AI works from the composer menu.
- **Model button** (0.2.13 feedback): opens a model menu, not Settings.

**Built**
- Composer, plus menu, dictation, voice button and live strip with compaction beside context.
- Working folder from the composer menu and from Settings with a folder browser (0.2.13).
- Model button menu with Auto, plus Standard and Abliterated groups (0.2.14). This fixed the
  feedback that it opened account settings.
- Completed-run model and speed stay readable after a restart (0.2.13).
- Brief button and `/brief` beside the session meter (0.2.17).

**Remaining**
- [ ] **Build:** reasoning levels, where a model supports more than on/off. Today Luminaria
      offers on/off only.
- [ ] **Desktop:**
  - Plus menu items and setup indicators.
  - Model menu.
  - Live strip values with a real model (no placeholders).
  - Manual compact.
  - Working-folder picker.

---

## 5. Spatial interface: entity and neural lattice

**Requirement** (spatial brief, sections 3–9 and 12; annotations)
- **The entity and lattice coexist.**
  - The entity is the recognizable presence Aaron talks to.
  - The lattice is the environment representing its real observable work.
  - The environment extends across the background without hurting readability.
- **Entity:**
  - A flowing particle organism, deforming mesh and toroidal energy structure with internal
    circulation.
  - Recognizable in every state:
    - **Idle:** breathing.
    - **Listening:** receptive expansion driven by the microphone.
    - **Generating:** focused activity.
    - **Speaking:** synced to the output audio.
    - **Interrupted:** immediate release.
    - **Waiting for approval:** visibly suspended at that step.
    - **Error:** recoverable.
    - **Complete:** settles.
  - Real Web Audio analysis drives it: RMS sets energy, bass sets expansion, higher frequencies
    set fine and vertical deformation. With no audio it shows an ambient idle, never invented values.
- **Lattice:**
  - Connected clusters in depth, curved pathways, occlusion and perspective, restrained ambient
    particles, directional pulses on active connections, quiet inactive regions.
  - Regions for planning and reasoning, memory, retrieval and research, files and code, tools,
    generation and verification. These are visual groupings, not anatomy.
  - Meaningful nodes come only from real task structure. Older runs collapse into inspectable
    clusters.
- **Movement follows real work.**
  - Research: request → plan → search branches → sources → compare → write → verify.
  - Coding: inspect → edit → run → failure → revise → test.
  - Parallel work branches. Failures stay visible and link to retries. Cancellation stops a branch.
  - Planned steps are distinguished from executed ones. Dependencies are shown only when known.
- **Continuous conversation during work.**
  - Aaron can keep talking: "Why are you checking that file?" while the step stays highlighted,
    or "Stop that, use the other library" to cancel the old branch and redirect.
  - The scene never resets when speech starts.
- **Event layer:**
  - Covers run, plan, step, generation, reasoning, streaming, tool, approval, retrieval, memory,
    compaction, retry and voice events.
  - Each event has stable ids (chat/run, node, parent/step/tool call), type, time, status, label
    and an evidence reference. No copying of sensitive content.
  - Handles duplicates, out-of-order delivery, reconnects, chat switching, concurrent runs,
    reopening and superseded runs.
- **Inspection:**
  - Selecting a node shows its step, tool call and result, source, file diff, reasoning,
    approval, test, error or artifact.
  - Links go both ways between Activity and nodes.
  - Follow activity, Focus, Overview, Return to chat, Pause motion, and a simplified non-3D
    outline. Keyboard accessible.
- **Annotations:**
  - Toolbar limited to **Follow activity** and **Return to chat**.
  - Pan the view; 3D drag and pan.
  - **A color per activity type** (files, retrieval, planning, verification, generation, tools),
    for a more interactive and dynamic look.
- **Voice mode:** presence comes forward and the working UI recedes modestly. Stop, approvals
  and errors stay readable.
- **Performance:**
  - Adaptive quality, bounded nodes and particles, instancing, buffer reuse and disposal.
  - Frame-independent motion and event coalescing, with no rebuild per token.
  - Idle throttling, reduced motion, pause, and WebGL context-loss fallback.
  - Measured performance only.

**Built**
- Persistent particle entity navigating an execution lattice from recorded work events (0.2.8).
- Overview, follow, focus, labels, evidence cards, Activity links in both directions, keyboard
  controls and an accessible outline/fallback (0.2.8).
- Clusters for older runs, recovery after reconnects, adaptive resolution, buffer reuse and
  real audio-frame inputs (0.2.8).
- Light-mode lattice and the Task overview redesign: torus lattice by region, Overview and
  Evidence tabs (0.2.9 and 0.2.10).
- Entity state colors and a status pill: Ready, Working · Read file, Waiting for approval (0.2.11).
- Orbit, pan and zoom by mouse and keyboard; region colors; toolbar reduced to Follow activity
  and Return to chat (0.2.13).
- Aaron said the new toroid and chat UI "looks good" (0.2.13 testing).

**Remaining**
- [ ] **Build:** persist voice state in the execution record (client-side only today).
- [ ] **Verify, then build if missing:** a spoken redirect ("stop that, use the other
      library") cancels or suspends the old branch and draws the new one linked to it.
- [ ] **Desktop:**
  - Real text and voice tasks: travel between real steps, failure and retry, approval wait,
    cancellation, and no mixed runs when switching chats.
  - No duplicate graph state after reconnect. Restored history matches the saved evidence.
  - Real microphone and speaker reactivity.
  - Conversation continues during work. Barge-in clears the old audio, generation and motion.
  - Reduced motion, pause and fallback.
  - Long-session performance and resource cleanup after repeated voice and task cycles.
  - Native pointer and touch drag.

---

## 6. Voice

**Requirement**
- Local speech recognition and synthesis.
- Natural **male and female** voices with previews.
- Settings for microphone device, voice, playback speed, speech threshold, silence timing,
  pauses and interruptibility.
- Dictation fills the composer. Conversation mode listens and answers aloud.
- **Barge-in** stops both playback and the active generation, plus the old visual trajectory.
  No stale transcripts, replies or audio. No leaked microphone tracks or audio nodes.
- Works during tools, approvals, failures, retries and cancellations.

**Built**
- Local STT/TTS with voice choices, previews, settings and barge-in.
- Real-audio-driven entity states.

**Remaining**
- [ ] **Desktop:**
  - Each voice and its preview.
  - Device changes, threshold and silence settings.
  - Recognition and speech failures.
  - Barge-in during generation and during playback.
  - Tasks during voice that use tools, wait for approval, fail, retry or get cancelled.
  - No leaked audio resources after many cycles.

---

## 7. Models: library, management, benchmarks and orchestration

### 7.1 Model library
**Requirement**
- A real downloadable library in Models, with **Standard** and **Abliterated** sections and an
  **Installed** filter.
- A restrained fractured or "cracked" identifier on Abliterated entries. Labels stay readable,
  with the honest note that abliteration doesn't guarantee zero refusals or better quality.
- Each card shows purpose and capabilities, parameter count, quantization choices, download
  size, configured versus supported context, vision/projector needs, publisher, source,
  license, measured local performance and hardware guidance (no invented fit guarantees).
- Actions: Download, Pause/Resume, Cancel (removing partial files), Use this model, Benchmark
  and Uninstall.
- Downloads:
  - Go only into Luminaria's models folder and show real progress.
  - Check disk space first.
  - Use pinned revisions and verify size and SHA-256.
  - Recover from interruption.
  - Register only after verification.
  - Never execute repository code.
  - Never switch the active model silently.
  - Respect the 100 GB budget.
- **Storage meter** at the top of Models: drive capacity, used and free space, the registered
  model footprint, download size and estimated remaining space, all from one synchronized snapshot.
- **More models** (Aaron, after 0.2.5): add more Standard and Abliterated models.

**Built**
- The library, with queue, resume, checksum, budget, disk-space refusal and the storage meter (0.2.5).
- 30 single-file GGUF models: 15 Standard and 15 Abliterated, each from its own publisher repo,
  pinned to a commit, with shared Gemma 3 vision projectors (0.2.7).
- Uninstall labelling (0.2.11).

**Remaining**
- [ ] **Build:** split/sharded weight sets are excluded today. Add them if needed. No claim of
      unrestricted Hub search.
- [ ] **Desktop:**
  - A real multi-gigabyte download: queue, cancel, resume, checksum, registration, storage
    refresh and model-manager reload.
  - Low-space refusal.
  - The cracked styling in both modes.

### 7.2 Model management and benchmarks
**Requirement**
- Load and unload, failed-load recovery, and context and quantization information.
- **Per-model context window** (annotation), with validation against the file and the known
  limit, and safe reload.
- Benchmark beside Use this model. Speed (tokens per second, first token) is kept separate from
  coding/reasoning **quality**.
- Results refresh the library and settings immediately and persist in SQLite.
- Benchmark candidates before choosing defaults.
- Validate larger contexts against memory use and quality before adding advanced context
  expansion. Compaction does not raise a model's native context.

**Built**
- Speed benchmark with history.
- A 12-question quality check stored separately (0.2.6 era).
- Model failure explanations (out of memory, damaged file, projector, port, timeout), with
  one automatic manager restart.
- Per-model context controls with validation, and ownership and active-run checks before reload (0.2.13).

**Remaining**
- [ ] **Desktop:**
  - Speed and quality runs against real models, with immediate refresh.
  - Real load failures where it is safe to cause them.
  - Per-model context reload in the process that owns the model manager.
- [ ] **Build** (with section 13): advanced context expansion, only after measurement.

### 7.3 Multi-model orchestration ("Auto")
**Requirement**
- A strong **low-VRAM orchestrator** model that delegates to the other installed models
  automatically (annotation).
- **Pool selection by individual model or by Standard/Abliterated** (0.2.13 feedback).
- Show which models are included and why others are excluded. Respect image and context needs.
- Never download implicitly. Never route outside the pool, and explain the fallback.
- Choosing the router is not permission to use every model.
- Record the selected model and the reason as routing output, not a quality guarantee.
- **Better choices** (0.2.13 feedback: "routing didn't really choose the best optimized model").

**Built**
- Optional router that picks one specialist per new task turn (0.2.13).
- The router only describes the task; Luminaria ranks allowed models by strengths, size,
  GPU-memory fit and local speed and quality results. Obvious requests skip the router (0.2.14).
- Pool controls: all, Standard, Abliterated or ticked models (0.2.14).
- Included and excluded list with reasons. No fallback outside the pool; keyword routing if
  the router is missing (0.2.15).

**Remaining**
- [ ] **Build:**
  - A representative task set (coding, reasoning, vision, writing, quick questions).
  - Record which model is chosen and the outcome, then tune the ranking from that data.
  - Measure model-switch time and VRAM.
  - Recommend a default low-VRAM orchestrator from those measurements.
- [ ] **Decide later:** parallel or multi-specialist subtasks. None are claimed today.
- [ ] **Desktop:** the included and excluded list matches the installed models; the GPU-memory
      check works on Windows; routing quality on real tasks.

---

## 8. Agent work: tools, permissions, planning and reliability

### 8.1 Tools and permissions
**Requirement**
- Agent operation is on by default (`--agent`).
- Capabilities: file operations, shell, Python/JS, search, browsing, vision and computer use,
  document creation and scheduled workflows (Automations).
- Default file work is confined to the app-managed working folder. Broader access needs
  explicit permission and approvals.
- **Review mode** and **Full Access**. Full Access is latched at restart and cannot grant
  missing credentials or override Windows permissions.
- Approval cards, cancellation, error reporting and execution history.
- PDF, DOCX and folder ingestion, with cancel, denial and recovery.

**Built**
- All tool families, approvals, Review and Full Access, and the working-folder boundary.
- PDF and DOCX attachments up to 25 MB / 500 pages; folders up to 200 files / 100 MB (0.2.6 era).
- Execution history and the Activity search.

**Remaining**
- [ ] **Desktop:**
  - Real file edits, code and shell, web and browser, vision and computer use, document
    creation and Automations, including deny, cancel and failure recovery.
  - Review versus Full Access after restart.
  - The folder boundary.
  - Attachments in the packaged app.

### 8.2 Planning
**Requirement**
- Plan mode builds a plan actively from what the user describes and presents it on request
  (0.2.13 feedback).
- Carry out the plan by following the recorded steps.

**Built**
- Plan only, limited to read-only tools (0.2.11).
- Drafts immediately and presents within a few rounds. The plan is saved with the chat; open it
  with View plan or `/plan`; carry out, revise, copy or clear (0.2.14).

**Remaining**
- [ ] **Desktop:** plan quality and plan-following with real models. Record the model and the
      outcome; this is model behaviour, not a guarantee.

### 8.3 Stops, checkpoints and retrieval reliability
**Requirement** (roadmap, "Retrieval and skills hardening")
- The 18-round limit becomes a checkpoint with a truthful partial-results report in chat:
  what was completed, found and failed, what remains, files changed, and sources.
- Continue without repeating successful side effects. Detect no-progress loops.
- Retrieval:
  - Diagnose before changing anything, using redacted diagnostics.
  - Distinct outcomes for auth, permission, missing source, network, timeout, throttling,
    unsupported content, extraction failure, empty result and context budget.
  - Input validation. Bounded retries for transient failures only.
  - Normalized results with source, time, type, text, truncation and error.
- Web fetch: redirects, HTML, PDF, encodings, size limits, main-content extraction, an
  **authorized browser fallback** for JavaScript pages (never bypass access controls), a cache
  with freshness, and saved evidence linked to source and time.
- Retrieval quality:
  - **Chunked results with stable source references.**
  - **Exact-term plus semantic search** where available, deduplicated, with context around
    matches. Benchmark before adding a reranker.
  - **Cache invalidation when a source changes.**
  - Clearly separate summary from verbatim, stale from fresh, and no match from failure.
- Untrusted retrieved text is never treated as instructions.

**Built (0.2.15)**
- Checkpoint report built from the action journal. Continue task skips completed actions.
  Three identical failures stop early.
- In-process web search and fetch with ok/empty/error outcomes and reasons, retries,
  rate-limit waits, PDF text, encoding detection, boilerplate removal and a 10-minute cache.
- Redacted `retrieval_events` diagnostics (no queries or addresses).
- A saved-page acceptance set. Retrieved text is labelled untrusted.

**Remaining**
- [ ] **Build:**
  - The browser fallback. Today `needs_javascript` is detected but only suggested.
  - Chunked retrieval with source references.
  - SQLite FTS5 exact-term search, plus semantic search if a local embedding model is available.
  - Invalidation when a file changes.
  - Explicit stale and summary labels.
- [ ] **Desktop:**
  - Real sites (an article, a PDF, a JavaScript-only page, a blocked page, a 404) with outcome
    and time recorded.
  - Real failure rates from `retrieval_events`.
  - A real round-limit checkpoint and Continue task.

---

## 9. Skills and integrations

**Requirement**
- **Skills:**
  - A searchable library with descriptions, enable/disable, Markdown import and chat injection.
  - Better display (annotation).
  - Each skill states purpose, prerequisites, inputs, outputs and permissions.
  - Dependency and credential check before running.
  - States: Ready, Needs setup, Running, Failed, Completed, each with a reason.
  - Validated arguments and outputs. Recovery paths. Cancellation reaches subprocesses.
    No duplicate side effects.
  - One shared retrieval implementation.
  - Reconcile the **original requested skill list**.
  - Browsing a skill is counted separately from using it.
  - A trust, install and update flow before any marketplace.
- **Tools and integrations:**
  - Separate panels with distinct copy (tools are actions; integrations connect services that
    add tools). Better display (annotation).
  - **Easier connection flow** (annotation): guided authorize, cancel, verify, reconnect and
    disconnect. Plain-language scopes, readiness and searchable categories.
  - Cached capability discovery, invalidated when a connector changes.
  - Consistent results with status, evidence, duration and recovery guidance. Bounded retries.
  - Never show a planned integration as connected.
  - Identity sign-in stays separate from Gmail, Drive and repository permissions.

**Built**
- 21 installed skills inventoried in `skills/inventory.json`, showing Ready or what is missing;
  a test enforces the inventory.
- Skill instruction inspection; clearer skills, tools and integrations display (0.2.13).
- Real connections:
  - GitHub (own token).
  - Linear and Notion (browser sign-in).
  - Slack (own app).
  - Gmail, Drive and Calendar (own Google OAuth client).
  - Read-only where offered. DPAPI-encrypted credentials.
  - A service shows connected only when its tools loaded.
  - A custom MCP connector that starts without a restart.
- Separate Tools and Integrations panels (0.2.15).

**Remaining**
- [ ] **Build:**
  - Fuller skill states and a pre-run dependency check.
  - Guided connect, verify, reconnect and disconnect.
  - Capability cache with invalidation.
  - Integration tools usable after the user approves a connection, without needing "Computer
    and command tools" or Full Access (they need it today).
  - A Discord and database connector approach (no official hosted servers exist).
- [ ] **Aaron to supply:** the original skill list. It was never received; the 21 installed
      skills were used instead.
- [ ] **Desktop:**
  - Connect each real service once.
  - Disconnect and reconnect.
  - A multi-step skill that retrieves evidence, produces output and verifies it.

---

## 10. Memory, context and compaction

**Requirement**
- **Layered memory:**
  1. A pinned **working brief**: goals, permissions, constraints, decisions, pending work and
     references. The user can view, edit, pin and remove entries, with explicit supersede rules.
  2. Recent turns kept verbatim.
  3. Versioned summaries.
  4. Full original history and tool output on disk.
  5. A bounded retrieval cache with source ids and freshness.
- Personal facts are kept apart from task state. Store where secrets are kept, never the secrets.
  Never promote web or tool output into instructions.
- Be honest that a disk or RAM cache is not model context. Show measured KV-cache reuse, not
  "permanently loaded memory".
- **Compaction:**
  - Count the full request.
  - Start with headroom.
  - Keep tool-call pairs and approval boundaries.
  - Preserve exact goals, permissions, denials, corrections, decisions, paths, evidence,
    uncertainty and unfinished work.
  - Summarize in chunks with sections and source ranges.
  - Validate, retry within limits, and commit only after validation. Keep the last good summary
    and every original if it fails.
  - Re-check after compaction and explain inputs that are too large.
  - Avoid drift by recovering exact originals.
  - Track metrics.
  - Test with realistic long workflows.
- **Plain-language controls** (annotation): compaction trigger, recent turns kept and reply space.
- **More robust compaction** (annotation).

**Built**
- SQLite history, tool evidence, durable facts and automatic compaction with a reserved reply budget.
- Validation, retries, source references and preserved history (0.2.13). One real compaction was
  verified in a source build.
- Sliders, stepper and presets with validation and save state (0.2.15).
- Working brief per chat (0.2.17): pinned into the prompt, edit history, permissions from the
  user only, the assistant's proposals marked, secrets refused.
- Hardened compaction (0.2.17): validated chunked summaries, exact references restored and
  carried forward, never split at an unanswered tool call, metrics in Memory & context, and
  overflow errors that name the cause.

**Remaining**
- [ ] **Build:**
  - The bounded retrieval cache (layer 5) with freshness. It overlaps section 8.3.
  - Measured KV-cache reuse display, where the runtime reports it.
- [ ] **Desktop:**
  - A long real chat on a local model compacting at least twice, keeping brief entries,
    decisions, pending work and exact paths.
  - Restart persistence.
  - Profile isolation of memory.

---

## 11. Accounts and sign-in

**Requirement**
- A proper **login screen** before the workspace when sign-in is required.
- Server-validated sessions with Google, GitHub and Discord, on the personal Cloudflare Worker.
- **One account** with explicitly linked providers. Aaron: "should be able to be signed in on
  all accounts at once"; "there should be one account". Never merge by email.
- A **remembered device**: encrypted (DPAPI), with expiry, revocation and a defined offline period.
- Account and settings under the sidebar profile control: profile info with settings wrapped
  under it (annotation). Remove the old multiple-profile account UI.
- Local profiles migrate by explicit choice, never silently.
- Verify consent, denial, cancel, restart recovery, expiry, logout and revocation, offline use
  and required-sign-in enforcement before enabling the gate.

**Built**
- GitHub sign-in (real, 0.2.4).
- Google and Discord on the service side (0.2.11). Google is in Testing mode with Aaron as a
  test user; secrets are stored in the Worker.
- Cancel and denial stop the desktop waiting (0.2.11).
- Coexisting sessions and linking a second provider to the same account (0.2.13).
- Profile page as the first settings section; remembered devices with 30-day idle and 90-day
  maximum; list and sign-out of other devices; login screen with cancel; per-profile migration
  choice (0.2.16, released in 0.2.17).
- Required sign-in is built but **off**, with 7-day offline grace.

**Remaining**
- [ ] **Build:** Google production publishing (homepage and privacy policy, then leave Testing).
- [ ] **Desktop:**
  - Real Google and Discord sign-in.
  - Restart recovery, 30/90-day behaviour, and signing out another PC and confirming it is out.
  - Denial, expiry and offline use within and beyond 7 days.
  - Per-profile migration choices.
  - Profile isolation for history, memory, settings and files.
- [ ] **Decide** (after acceptance): turn on required sign-in.

---

## 12. Profile page and insights

### 12.1 Profile page (reference shared October 17)
Aaron shared a reference profile page and asked for sign-in and profile metrics "something like
this". The requirement, based on that reference:

- **Header, centered:**
  - A large circular **avatar**. Initials on the accent color, unless a locally stored picture
    is added later; no remote image loading.
  - The **display name**.
  - The public **@username** (GitHub login or Discord username; Google has none; never an email).
  - The linked sign-in methods.
- **Stat strip**, a single rounded row of five figures:
  1. **Lifetime tokens.**
  2. **Peak tokens:** defined as the busiest day; the label and tooltip must say which measure it is.
  3. **Longest task:** active time, excluding approval waits and pauses.
  4. **Longest streak.**
  5. **Current streak.**
  - Each figure has a tooltip with its rule. Values are compact (556.3M, 1h 14m, 3 days).
- **Token activity:**
  - A year-long heatmap of daily token totals: 53 week columns by 7 weekday rows, month labels,
    shading from the accent color, and a legend.
  - **Daily / Weekly / Cumulative** views.
  - Days before recording started are shown as not recorded, never as zero.
  - Each cell has a tooltip with the date and tokens.
- **This PC / All devices** switch when insights sync is on: lifetime, peak, streaks and the
  heatmap use synced totals; longest task and top tools stay "this PC" because they aren't synced.
- **Top plugins / tools:**
  - A row of tiles for the most-used tools, integrations and skills, with uses and failures.
  - The reference shows "Top plugins"; Luminaria's equivalents are tools, integrations and skills.
- **Showcase** (in the reference): a gallery of things made with Luminaria, filtered by All,
  Sites and Skills. Luminaria has no artifact gallery today. **Decide** whether to add one,
  for example from saved files and documents in My files, or skills created.
- Keep the existing Profile sections below the header: sign-in methods, devices, required
  sign-in and local profiles. An "All insights" button opens the full Insights page.
- Works signed out (local profile name, "Not signed in") and offline, and shows clear empty and
  error states.

**Status:** Planned. The data exists (0.2.17 records lifetime tokens, busiest day, longest task,
streaks and tools on this PC, plus synced daily totals), but the Profile page has no header,
stat strip or heatmap yet. Insights currently shows a 30-day chart.

**Build list**
- [ ] Identity service: store the public username (`identities.handle`) from GitHub `login`
      and Discord `username`; return it from `/session`. Needs D1 migration 0004, applied
      **before** the Worker deploy. Existing identities pick it up at their next sign-in.
- [ ] Backend: 53 weeks of daily totals in `/api/insights`, aligned to weeks, with coverage
      flags. Keep per-day synced totals in the account view so All devices can draw its own
      heatmap. Recompute account streaks for today instead of freezing them at sync time.
- [ ] Frontend: the profile header, stat strip, heatmap with the three views, scope switch and
      top-tools tiles, using the black/white tokens and accent. Keyboard and screen-reader
      friendly. No horizontal overflow at narrow widths.
- [ ] Tests: unit tests for grid alignment, coverage and account recomputation; username
      validation; Worker tests; a browser check in both modes plus the empty, error and
      signed-out cases.
- [ ] Desktop: real figures after normal use; the username after re-signing in; All devices
      after syncing on two PCs.

A prototype of the backend and Worker parts plus a first UI pass exists on the local branch
`cursor/profile-overview-11de` (unpushed, unreviewed). Pick it up or discard it when this
item is scheduled.

### 12.2 Insights
**Requirement** (roadmap, "Profile insights")
- Lifetime input, output and total tokens, with cached tokens shown separately when measured.
- Peak activity with the period defined. Busiest day, largest task and fastest speed are
  different measures.
- Longest task, separating active time from approval waits and pauses.
- Streaks with a defined time zone and qualifying activity.
- Token history.
- Reasoning use, including which levels where supported.
- Skills explored, enabled and invoked, counted separately.
- Most-used plugins, integrations and tools, with successes and failures.
- Model usage and measured speed trends.
- Durable events with stable ids and idempotent sync. A coverage start date, missing data
  labelled, no invented history.
- Sync aggregates only. Retention, export and delete.

**Built (0.2.17)**
- Local `usage_events` with idempotent ids.
- Insights page: totals, cached tokens, streaks, busiest day, fastest speed, a 30-day chart,
  largest and longest task, reasoning on/off, skills, tools, integrations, models, a list of
  what isn't measured, time zone, export and delete.
- Opt-in daily-total sync to the Worker (upsert per device, two-year retention) with an account
  view and deletion of synced data.

**Remaining**
- [ ] **Build:** the profile header and year heatmap (12.1). Reasoning levels where reported.
      Speed trends over time per model.
- [ ] **Desktop:**
  - Real counts after use; time zone; export and delete.
  - Sync on two PCs with no double counting; deletion of synced totals.
- [ ] **Decide:** keep sync off by default (current behaviour).

---

## 13. Hardware page and tuning (Ryzen 7 7800X3D)

**Requirement** (roadmap)
- A system information page showing CPU, GPU, VRAM, RAM and runtime version.
- An opt-in benchmark using `llama-bench` or the existing runtime, covering thread counts and
  CPU-only, partial and full offload.
- Measure first-token time, prompt processing, decode speed, RAM and VRAM, and UI responsiveness.
- Save the best measured profile per model, runtime and hardware combination, with provenance
  and rollback. Nothing changes automatically.
- The 96 MB L3 cache cannot hold model weights and cannot be reserved by an app. No "X3D
  optimized" label without repeated measured gains. No experimental forks, no BIOS advice.

**Status:** Planned.

**Build list:** detection page → benchmark runner → profile storage and rollback → apply a
profile on model load → desktop measurement runs on Aaron's PC.

---

## 14. Autonomous computer operation

**Requirement** (roadmap)
- An observe → plan → act → verify → recover loop.
- Set the objective, allowed locations and completion criteria before a long run.
- Fresh screenshots and accessibility state only; never invented coordinates.
- Respect Review and Full Access and OS permissions.
- Visible activity, interruption and an immediate **Stop**.
- Verify every file and UI result. Checkpoints and idempotency, with no replay of completed
  actions after a failure or restart.
- Recoverable deletes by default; permanent deletion explicit.
- Treat pages, files and tool output as untrusted.

**Status:** Planned. Vision and computer-use tools exist, but the loop does not.

**Build list:** start with file workflows (read, create, edit, move to trash) with
verification; then app control; then long multi-step runs with checkpoints.

---

## 15. Packaging, updates and distribution

**Requirement**
- A branded Windows app with installer, uninstaller, desktop icon, versions and release notes.
- GitHub-release updates through the Worker:
  - Verified downloads; data-preserving upgrades.
  - The update UI shows version, availability, notes and actions, never repository setup.
- An **update notice on launch**: a small popup that never downloads by itself.
- Clean-machine install, upgrade, rollback/recovery and uninstall tests.
- **Code signing** before ever claiming signed builds.
- A public distribution and landing page, separate from the private release channel.

**Built**
- Installer and uninstaller; the update channel via the Worker with size and SHA-256 checks.
- Graceful update handoff that stops the app and its model manager safely (0.2.9).
- Update notice on launch (0.2.15).
- Releases 0.2.5 through 0.2.17 published (unsigned testing releases).

**Remaining**
- [ ] **Build:** code signing. Landing page and public distribution, if wanted.
- [ ] **Desktop:**
  - An in-app update with data preserved.
  - Interrupted update and corrupted download.
  - Clean-machine install, upgrade and uninstall.
  - The update notice (first real check: an update from 0.2.17).

---

## 16. Final end-to-end acceptance (release gate)

Run in the packaged desktop app before calling any release accepted rather than "testing":

1. Sign in, then recover the session after a restart.
2. Select and load a model.
3. Chat and confirm genuine performance figures.
4. Run tools through both the approval and Full Access paths.
5. Save files and retrieve persistent memory.
6. Trigger automatic compaction and continue correctly; check the brief.
7. Start voice, interrupt playback and generation, and inspect the reactive graphics.
8. Benchmark a model and confirm settings update.
9. Install an update without losing profiles, chats, files or models.
10. Spatial: a truthful execution path, approval wait, cancellation, chat switching and reconnect.
11. Appearance: modes, persistence, profiles, reset, and no theme flash.
12. Resilience: reduced motion, pause, graphics fallback, keyboard access and long-task
    responsiveness.

A checklist file (`docs/testing-0.2.17.md`) should be written from sections 2–15 for Aaron to run.

---

## 17. Decisions needed from Aaron

1. The original requested **skill list** (section 9), or confirm the 21 installed skills are the target.
2. Whether to add a **Showcase** gallery to the profile page, and what it shows (12.1).
3. Whether to turn on **required sign-in** after section 11 passes.
4. Whether **insights sync** stays off by default.
5. How to handle **Discord and database** integrations.
6. **Code signing:** now, or before public release.
7. Whether **queued messages** should survive a restart.
8. **Parallel or multi-specialist** orchestration: wanted later or not.

## 18. Suggested order

1. **0.2.17 desktop checklist** from section 16. Aaron runs it; one fix release for what fails.
2. **Profile page header and year heatmap** (12.1). Small and self-contained; the data already exists.
3. **Retrieval, skills and integrations hardening** (8.3 and 9).
4. **Orchestration quality and plan mode measurements** (7.3 and 8.2).
5. **Hardware page and tuning** (13).
6. **Autonomous computer operation** (14), starting with files.
7. Appearance, voice and spatial follow-ups (2, 5, 6), folded into the nearest release.
8. **Signing, clean-machine testing and public release readiness** (15 and 16).
