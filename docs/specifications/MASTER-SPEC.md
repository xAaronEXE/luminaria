Here is your complete, unedited, exhaustive Master Specification for Luminaria. Absolutely nothing has been omitted—every architectural rule, technical constraint, UI layer, visual theme parameter, voice workflow, benchmark rule, and execution phase is fully detailed below.
- Permanent Name: Luminaria (used consistently across the entire application interface, window frames, desktop icons, Windows installer, documentation, repository assets, and sharing distributions).
- Core Mission: A free, fully open-source, local-first AI harness and spatial desktop interface built to liberate artificial intelligence from corporate gatekeepers, paywalls, and telemetry. It champions human agency, absolute privacy, digital stewardship, intellectual freedom, and equal technological opportunity for all individuals regardless of wealth or status.
- Product Philosophy: Local-first compute priority. Everything runs on user-owned hardware by default. Cloud/external connections are strictly opt-in and permission-bounded.
- Core Aesthetic Standard: "Impeccable" UI execution—high scannability, precise spatial padding, crisp micro-typography, smooth 60 FPS CSS/WebGL transitions, and non-cluttered layouts.
- Primary Default Color Palette (Graphite & Ivory):
  - Surfaces & Backgrounds: Deep slate and forestry graphite dark surfaces (#141A17 / #181F1C).
  - Typography & UI Framing: Soft ivory text (#F4F4F0 / #E5E5DF) paired with subtle muted slate borders (#2D3632).
  - Accents & Glows: Warm-lit luminous highlights (#EAE6D9 / #D4CEB8) replacing cold neon/acid defaults.
- 3D Entity Aesthetics: Particle lighting, GLSL mesh uniforms, and photon trails adhere strictly to the neutral graphite/ivory theme with luminous warm highlights.
- Complete Customization Engine:
  - Granular Color Controls: Individual pickers for main backgrounds, floating panels, primary text, muted text, borders, active buttons, accent highlights, and reactive 3D shader glow colors.
  - Preset & Palette Management: Ships with curated themes; allows users to create, rename, save, apply, export, and delete personal palettes.
  - System Rules: Built-in contrast-ratio validation warnings for accessibility, persistence to local storage, and a single-click "Reset to Default Palette" control.
The central AI identity is a persistent, audio-reactive 3D metamorphic construct built using Three.js / React Three Fiber / Custom GLSL Shaders.
1. Workflow Mode (The Neural Lattice / DNA Brain):
   - Structure: An anatomical neural network / double-helix DNA lattice node graph representing cognitive pathways.
   - Reactive Synaptic Lighting: When executing local tasks (RAG search, code execution, file parsing, web browsing), bright photon trails travel along active wireframe connections directly to functional lobes (Memory, Logic, Tool Execution, Generation).
   - Thinking / Reasoning Phase: Rotation slows to a heavy crawl, and high-frequency internal electrical arcs jump between nodes inside the silhouette to signify active compute cycles before streaming output.
2. Conversational Mode (The Toroidal Energy Core):
   - Structure: Upon activating voice chat, the neural lattice collapses and uncoils inward, looping into a high-density, swirling 3D Toroidal Energy Vortex.
   - Audio-Reactivity: Connected to browser Web Audio API AnalyserNode. Low frequencies/bass pulse the inner core outward; mid/high frequencies deform the outer particle surface shell; audio pitch pulls geometry vertically along the spatial axis.
- Layer 0 (Ambient Background Canvas): Deep-space/particle void with subtle mouse/gyroscope parallax motion.
- Layer 1 (Desktop Workspace Canvas): Markdown chat logs, code editors, file trees, and system gauges.
- Layer 2 (Foreground Interactive Entity):
  - Text / Typing Mode: Entity stays compact, floating in an upper-corner glass pane or minimized dock.
  - Voice Mode Transition: The workspace layer scales back (scale(0.95)), moves backward in 3D perspective (translateZ(-100px)), and applies a dark backdrop filter blur (backdrop-filter: blur(16px)). The Toroidal entity translates to center-stage foreground.
- Drive deformations, shader glow sweeps, and particle speeds using real system data (actual CPU/GPU compute load, token generation rates, Web Audio FFT frequencies, active tool firing).
- STRICT PROHIBITION: Never use invented, simulated, or pseudo-random metrics for model confidence, temperature, or "internal thoughts."
- Expandable Plus Menu (+): Single entry point for file attachments, local workspace files, skills injection, and active integrations. Displays clear visual badges identifying tools requiring setup or external credentials.
- Model Selector & Reasoning Control: Model dropdown paired with an accurately explained "Think Harder" toggle for models supporting extended reasoning passes (e.g., Qwen thinking tokens).
- Dedicated Voice Action Controls:
  - Microphone Dictation Button: Transcribes speech directly into the text composer without sending automatically.
  - Conversational Waveform Button: Placed beside the Send button; immediately triggers full Z-axis 3D Toroidal voice mode and starts live audio streaming.
- Chat Management: Per-chat actions for inline renaming, branching/forking conversations into new threads, archiving, hard deletion, and soft-delete recovery windows. Clear UI states for streaming tokens, cancellation, errors, and agent tool approval requests.
- Engine: Local speech-to-text (STT) and text-to-speech (TTS) execution.
- Voice Variety: Multiple male and female local voice options accompanied by audible preview buttons in settings.
- Barge-In Interruption: User speech mid-response immediately halts TTS audio playback and cancels active LLM generation.
- Voice Settings: Controls for microphone device selection, speech playback speed, voice activity detection (VAD) sensitivity, silence timing, and pause durations.
- Engine Support: Native execution via Ollama / llama.cpp backends (default Qwen setup alongside custom user-downloaded models).
- Model Management: Manual loading, unloading, context size configuration, and quantization viewing. Displays best uses, strengths, vision/tool capabilities, disk footprint, and configured context bounds.
- Live Performance Strip:
  - Real-time metrics bar displaying context memory usage, tokens per second (t/s), and time-to-first-token (TTFT).
  - Strict Measurement Rule: Never display fake, hardcoded, or sample numbers—always render live backend telemetry.
- Benchmarking Suite:
  - "Benchmark" action placed beside "Use this model".
  - Runs actual local benchmarks separating generation speed tests from coding/reasoning quality evaluations.
  - Results immediately update model views and persist to SQLite across app restarts.
- Automatic Model Routing: Deferred feature; will be enabled only after benchmark data proves operational reliability across installed models.
- Storage Architecture: Persistent local SQLite database storing complete chat histories, durable memory facts, tool invocation logs, and benchmark records.
- Automatic Context Compaction: Triggers automatically as active tokens approach configured context limits, reserving space for the next generation. Compacts older turns while preserving core decisions, user constraints, unfinished tasks, and recent dialogue turns in active working memory.
- Retained Raw History: Original un-compacted transcripts are preserved on disk for search and retrieval.
- Status Bar Integration: Live compaction status indicator and manual compaction trigger placed directly beside model/context metrics.
- App-Managed Working Directory: Automatically provisions a sandboxed working folder inside the application's writable installation area. All default file creation and editing operations are strictly confined to this boundary.
- Explicit Permission Guardrails: System-wide file system access, terminal shell execution, or computer interaction requires explicit, non-silent user approval prompts per action/session.
- Agent Operations (--agent): Enabled by default with tool approval prompts.
  - Capabilities: Local file editing, code execution, shell commands, web search, page browsing, computer/vision interactions, document rendering, and scheduled local workflows.
- Searchable Skills Library: Searchable catalog with enable/disable toggles, in-chat skill injection, and Markdown import capabilities.
- Integration Connections: Dedicated integration management rows equipped with explicit "Connect / Sign in" controls.
  - Isolated Services: Distinct entries for Google Workspace, GitHub, Discord/Slack, and local databases.
  - Permission Boundaries: Signing into an integration displays granted scopes without implying cloud synchronization or data upload.
- Implementation Timeline: Auth features are built after UI, local model execution, voice, and 3D functionality are fully validated.
- Multi-Profile Isolation: Local user profile switcher providing independent chat histories, memory stores, preferences, and sandboxed files per profile.
- Mandatory Hosted Sign-In (Phase 7): Server-validated OAuth sign-in (Google, GitHub, Discord) hosted on personal Cloudflare infrastructure.
- Data Boundary: Account sign-in manages user identity and integration permissions without forcing cloud sync—all primary data remains strictly local.
- Windows Packaging: Native packaged Windows application featuring branded shortcuts, installer, uninstaller, and update manager.
- In-App Update Engine: Displays current build version, checks GitHub release sources behind the scenes, displays release notes, and performs verified data-preserving updates.
- Open-Source Repository Cleanliness: Public GitHub repository maintained with zero hardcoded API keys, personal credentials, machine-specific paths, or heavy embedded model weights.
```
Phase 1: Visual Polish & Custom Palette Engine (Graphite & Ivory Theme)
    ↓
Phase 2: Composer Layout, Settings Framework & Integration Rows
    ↓
Phase 3: Model Management & Persistent SQLite Benchmarking Engine
    ↓
Phase 4: Skills Library, Sandboxed File Workspace & Context Compaction
    ↓
Phase 5: Local Voice Pipeline & Reactive 3D Neural-Toroid Entity
    ↓
Phase 6: Desktop Packaging & Windows Installer Build Verification
    ↓
Phase 7: Hosted Authentication (Cloudflare) & Provider Connectors
    ↓
Phase 8: End-to-End System Verification & Public Release Readiness
```