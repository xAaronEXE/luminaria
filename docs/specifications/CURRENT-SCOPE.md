# Luminaria delivery scope

User decisions through 2026-10-16. Requirements are not completion claims.
This addendum wins conflicts with older specifications. Existing non-conflicting
master-spec requirements remain in scope.

## Fixed product decisions

- Permanent identity: Luminaria; use existing approved logo and sharing imagery.
- Plain HTML/CSS/JavaScript, locally bundled assets, Python backend, Windows desktop.
- Graphite/Ivory dark and light modes only. No custom color editor or palette engine.
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
- Source now includes a downloadable Standard/Abliterated catalog, one-at-a-time
  queue, resume, checksum checks, the 100 GB budget, and disk-space refusal.
  Unit tests cover those paths with a local file server. A packaged Windows
  download, install, and model-manager reload has not been run.
- Source now includes an update channel. The identity Worker reads releases from the
  private repository with a read-only token. The desktop app checks for updates
  through that Worker and verifies the installer's size and SHA-256 before it runs.
  The version comes from the VERSION file, and the installer leaves App\data and
  App\models in place. The token secret and Worker deploy are still pending, and
  0.2.5 has not been built or published. Installers are not code-signed.
- See verification-0.2.4.md for detailed historical evidence and remaining checks.

## Locations

- Project root: C:\Users\desse\Desktop\Luminaria
- Installed app: App\LocalAIStudio.exe; data: App\data; models: App\models
- Runtime: runtime\local-ai; identity service source: auth-service
- Private source repository: xAaronEXE/luminaria, main
