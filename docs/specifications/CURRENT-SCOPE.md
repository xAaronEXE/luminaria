# Luminaria delivery scope

User decisions through 2026-10-16. Requirements are not completion claims.
This addendum wins conflicts with older specifications. Existing non-conflicting
master-spec requirements remain in scope.

The October 17, 2026 direction (account, insights, memory, agent reliability, UI
refinement) and its delivery status live in [ROADMAP-2026-10-17.md](ROADMAP-2026-10-17.md).

## Fixed product decisions

- Permanent identity: Luminaria; use existing approved logo and sharing imagery.
- Plain HTML/CSS/JavaScript, locally bundled assets, Python backend, Windows desktop.
- Black-on-white light mode by default, inverse dark mode and Follow system. Every color,
  including the accent, is user-customizable with pickers; no presets.
- All app-owned binaries, runtime, models and saved data live beneath the consolidated
  Luminaria folder on the owner's Desktop. No model weights or user data in Git.
- Agent operation enabled by default; explicit Review and restart-latched Full Access modes.
- Real measurements or unavailable labels; no invented telemetry, confidence or thoughts.

## Model library and storage

- Discover downloadable models in Standard and Abliterated sections, with Installed filtering.
- Search capabilities; display purpose, parameters, quantization choices, weight size,
  context support, vision/projector requirements, provenance/license and hardware guidance.
- Restrained fractured identifier for Abliterated entries; preserve readable labels.
- Download, cancel, resume where supported, integrity verification, actionable errors,
  disk-space preflight, progress and registration into the local inference manager.
- Download only after user selection. Additional-model budget: up to 100 GB.
- Use this model and Benchmark actions with unavailable/busy/active states.
- Real speed and first-token measurements, persistent benchmark history, immediate
  refresh in both library and settings. Keep quality evaluations separate from speed.
- Storage meter at top of Models: actual model volume capacity, used/free space,
  separate registered-model footprint, download size and estimated remaining space.
- Refresh storage after downloads/removal. Confirm model removal; protect active files.
- Model load/unload, failed-load recovery, context and quantization information.
- Advanced context expansion and automatic routing follow validated core execution.

## UI and daily operation

- Consistent settings with real controls, error/loading/empty/disabled states,
  keyboard access, focus, contrast and responsive desktop layouts.
- Preserve approved composer and genuine model/context/speed/TTFT strip.
- Place compaction status/action beside context; explain supported reasoning controls.
- Dictation microphone and distinct conversation control beside an improved send action.
- Plus menu: attachments, local files, skills and integrations with setup indicators.
- Chat rename, fork, archive, restore and delete flows; searchable history.
- Clear files/activity/context inspector using an app-managed working directory.
- Searchable skills library, enable/disable, Markdown import and chat injection;
  reconcile the full requested skill inventory rather than counting placeholders.
- Real integration connection actions and scope information for Google Workspace,
  GitHub, messaging and databases. Account login does not imply integration access.

## Voice and spatial entity

- Local speech recognition and synthesis, male/female natural voice choices with previews.
- Microphone, speed, speech threshold and silence controls.
- Barge-in cancels playback and model generation; prevent stale audio/replies.
- Persistent anatomical neural/DNA lattice for work; smooth morph to toroidal voice core.
- Functional regions and photon paths react to real memory, reasoning, generation and
  tool events. Explain these as activity visualization, not hidden thought inspection.
- Actual audio FFT/RMS drives radius, surface and vertical deformation.
- Ambient background, readable workspace layer, foreground conversational entity;
  restrained depth/parallax and smooth mode transitions.
- Idle/listening/generating/speaking/interrupted/error states, accessible controls,
  motion pause, reduced-motion support, graphics fallback and sustained performance checks.
- Verify tool approvals during voice and recovery from device/network/model failures.

## Memory, tools and workflows

- SQLite full-fidelity history and tool evidence, saved files and durable facts.
- Automatic compaction with reserved response budget; retain constraints, decisions,
  unfinished work and recent verbatim turns. Preserve original history and retrieval.
- File editing, shell, Python/JS, search/fetch/browser, vision/computer use, document
  creation and scheduled local workflows; test actual execution and failures.
- App-managed default file boundary; explicit broader-access behavior and approvals.
- Full Access applies only after restart and cannot grant OS permissions or credentials.
- File/folder and PDF/DOCX ingestion; cancel, approval denial and recovery paths.

## Authentication and accounts

- Mandatory server-verified sign-in with Google, GitHub or Discord; personal Cloudflare.
- Separate account profiles for history, memory, settings and files.
- Protect local sessions with Windows DPAPI; do not ship provider secrets to desktop.
- Verify real consent, denial, cancel, session expiry, restart recovery, logout/revocation
  and offline states before enabling release enforcement.
- Keep local model/chat/file/audio data on PC unless an explicit integration uses it.

## Distribution and acceptance

- Branded Windows installer/uninstaller, desktop icon, versions and release notes.
- GitHub release updater, verified downloads and data-preserving upgrades.
- Signing, clean-machine install/upgrade/uninstall and recovery checks before release.
- Keep source updated on GitHub; exclude credentials, private histories and weights.
- Complete desktop acceptance: login/restart, model load, chat/telemetry, approvals and
  Full Access tools, files/memory, compaction, voice interruptions/graphics, benchmark
  refresh, and update without losing profiles/data/models.

## Verified checkpoint and current implementation pass

- Installed 0.2.4 completed real GitHub pairing as xAaronEXE, including server identity
  validation and encrypted session storage. Restart recovery is not yet verified.
- User confirmed real microphone recognition/Qwen spoken answer and interruption of
  spoken playback followed by a new answer. Full matrix remains unverified.
- Chats in trash can now be deleted permanently, one at a time or with Empty trash,
  after a confirmation. This erases their messages, summaries, tool records, run
  snapshots and model checkpoints. Files saved in My files are kept. Route tests
  cover this against a temporary data folder; not yet tried in the packaged app.
- PDF and Word .docx files can be attached (up to 25 MB, 500 PDF pages). The original
  is kept in My files/Attachments and its extracted text is given to the model.
  Password-protected, scanned, damaged and legacy .doc files are refused with a
  reason. Folders can be attached: up to 200 supported files and 100 MB are copied
  to My files/Imports with their structure, and the model gets a contents list.
  The plus menu no longer gets cut off by the composer. Tested with generated
  files; not yet tried in the packaged app.
- Models now have a quality check separate from speed: 12 fixed coding and reasoning
  questions with exact answers. Code in the questions is read, never run. Results
  are stored apart from speed history and shown per question. It has not been run
  against a real model yet; tests use a simulated model server.
- Source now includes a downloadable Standard/Abliterated catalog, one-at-a-time
  queue, resume, checksum checks, the 100 GB budget, and disk-space refusal.
  Unit tests cover those paths with a local file server. A packaged Windows
  download, install, and model-manager reload has not been run.
- The catalog has 30 single-file GGUF models (15 Standard, 15 Abliterated) from 30
  publisher repositories, each pinned to a commit. refresh_model_catalog.py reads
  sizes and SHA256 from the LFS records and context and attention settings from
  the GGUF header, without downloading weights. All 34 published records checked
  live matched. Gemma 3 entries offer a shared vision projector. Memory figures
  are estimates from file size plus the q8_0 context cache the runtime allocates.
  The Models screen was reworked for the larger list and checked in the browser
  preview in both modes; no multi-gigabyte download has been run yet.
- Source now includes an update channel. The identity Worker reads releases from the
  private repository with a read-only token. The desktop app checks for updates
  through that Worker and verifies the installer's size and SHA-256 before it runs.
  The version comes from the VERSION file, and the installer leaves App\data and
  App\models in place. The release token is set and the Worker is deployed. v0.2.5
  is published, and the live channel returns it with a checksum that matches the
  GitHub asset digest. An in-app upgrade from 0.2.5 to a later release has not been
  run yet. Installers are not code-signed.
- The 3D core has distinct idle, listening, thinking, speaking, interrupted and
  error looks, driven by the real voice state. Checked in headless WebGL at 60 fps;
  not yet watched in the packaged app.
- Tools & integrations has real connections for GitHub (your own token), Linear and
  Notion (browser sign-in), Slack (your own Slack app client ID) and Gmail, Drive
  and Calendar (your own Google OAuth client). Read-only is offered where the
  service supports it. Credentials are DPAPI-encrypted. A service shows as connected
  only when its MCP tools loaded. Discord and databases have no official hosted
  server and use the custom MCP connector, which now starts without a restart.
  Tests run against a local MCP server with real OAuth; no real service has been
  connected yet. Integration tools still need Computer and command tools or Full Access.
- Skills: the original requested list was not available in this session, so the
  21 installed skills were reconciled instead. Each is categorized in
  skills/inventory.json with its real requirements, and the library shows Ready or
  exactly what is missing. Tests fail if a skill is installed but not inventoried, or
  the reverse. Send the original list to add any missing skills.
- Panels show loading and retry states; form field borders meet 3:1 contrast in both
  modes. Text colors were measured at 5:1 or higher.
- Model failures are explained: the model manager log is read for out-of-memory,
  damaged files, projector, port and load-timeout problems. A crashed manager that
  Luminaria started is restarted once automatically; otherwise Models shows the
  reason with a Restart button. Tested with simulated failures only.
- The Activity tab can search tool actions across all chats and filter errors,
  denials and interruptions, with links back to each chat.
- Required sign-in is built but off. It can be turned on in Accounts only while
  signed in and verified online. When on, the backend refuses everything except
  sign-in until the account is verified, local profiles cannot be opened, and
  automations wait. Offline use is allowed for 7 days after the last verification.
  This is an access gate for this app, not protection against the Windows account
  owner: removing require_sign_in from App\data\profiles.json turns it off.
  Not yet tried with the real sign-in service.
- Version 0.2.6 with release notes is prepared. See testing-0.2.6.md.
- Version 0.2.7 adds the expanded model library. See testing-0.2.7.md.
- See verification-0.2.4.md for detailed historical evidence and remaining checks.

## Spatial workspace and appearance (0.2.8 onward; testing releases)

The persistent conversational entity and neural lattice coexist. The entity moves
through recorded task nodes during text or voice work. The lattice is an execution
view, not a claim to hidden neural activations or private thoughts.

Implemented on codex/spatial-workspace:
- Existing persisted work events feed a bounded, replay-deduplicated browser scene.
  Chat changes and SSE reconnect recover history without accepting stale responses.
- Latest run expanded; older runs are inspectable clusters. Visible nodes are bounded;
  truncation is labelled. Plans/reasoning remain model-provided, distinct from tool evidence.
- Separate toroidal particle entity, seven functional regions, curved known edges,
  activity packets and event-driven travel. Stable node positions, adaptive resolution,
  reusable GPU buffers, actual audio-frame inputs, motion pause and reduced motion.
- Overview/follow/focus/return, visible node labels, keyboard inspection, evidence cards,
  Activity links in both directions and an accessible outline/WebGL fallback.
- Historical compaction summaries resolve by exact chat-scoped reference.
- Typed messages queue per chat during a run, can be cancelled before submission,
  retain failed sends for retry and dispatch after completion. Voice turns take priority.
  Queues are client memory only; closing warns about unsent messages.
- Voice chat recedes modestly while Stop, approvals and errors remain usable.
- Black/white light/dark/system appearance and existing customization tokens drive the
  complete interface and scene. The startup cache is still PC-wide; switching profiles
  can briefly show the prior profile's appearance.

Verified layers:
- Isolated Python tests for event recording, existing product behaviour and new scoped
  summary evidence. JS checks for graph ordering/recovery, queueing and renderer lifecycle.
- Browser preview with MOCKED APIs for theme variants, outline/evidence interaction,
  Activity links, queued dispatch and fault-injected unavailable WebGL. These are not
  real inference or native desktop acceptance.

Release blockers:
- Aaron's packaged Windows acceptance: real model/tool workflow, real microphone and
  output reactivity, voice/task continuity, barge-in and sustained performance.
- Real OS reduced-motion changes and update/persistence acceptance on Windows.
- 0.2.8 was published as an unsigned testing release; it does not certify the
  checks above. 0.2.9 (update handoff, light-mode lattice, task overview redesign)
  remains a testing release until the same acceptance is done.

## Locations

- Project root: C:\Users\desse\Desktop\Luminaria
- Installed app: App\LocalAIStudio.exe; data: App\data; models: App\models
- Runtime: runtime\local-ai; identity service source: auth-service
- Private source repository: xAaronEXE/luminaria, main
