> Superseded by [MASTER-SPEC.md](MASTER-SPEC.md), the complete user-supplied specification accepted October 16, 2026. The older scope below is retained for history, not as competing requirements. Implementation and verification status are tracked separately; specification text is not evidence of feature completion.
>
> Current priorities: Graphite & Ivory visual polish and full palette controls; composer/settings/integration rows; model management and SQLite benchmarks; skills/files/compaction; voice and neural-toroid visuals; desktop packaging; hosted authentication; final verification and public release readiness. Authentication uses the personal Cloudflare account. Retain the existing plain JavaScript frontend and local assets.

1. Product identity and visual direction
- One permanent, availability-checked name reflecting freedom, open access, and bringing powerful local AI to people.
- LibreKind is rejected. Luminaria is the selected name; users won’t choose between app names.
- Use Impeccable throughout.
- Preserve the composer, chat layout, model/context/speed strip, and background direction you approved.
- Default palette: acid mint #B7FF2E + forestry graphite #141A17.
- Add many theme presets, custom colors, and saved personal palettes.
2. Chat and composer
- The plus button opens an Add menu, like your reference: attachments, app files, skills, and integrations.
- Show usable capabilities clearly; identify integrations that require setup.
- Think harder toggles the model’s supported reasoning mode, with an accurate explanation.
- Separate microphone dictation from voice conversation.
- Put the conversational waveform icon beside the send button.
- Refine the send button without disrupting the layout you like.
- Add per-chat fork, archive, and delete actions, with clear behavior and recovery for deletion.
3. Local models and benchmarks
- Use the existing Qwen setup and downloaded model library.
- Support larger and smaller models with manual selection and load/unload management.
- Display purpose, strengths, vision support, quantization, file size, configured context, and measured performance.
- Put Benchmark beside Use this model and connect it to actual measurements.
- Distinguish generation-speed benchmarks from coding/reasoning quality tests, and historical results from current-chat metrics.
- Keep context usage, tokens per second, and first-token timing visible. Never substitute sample numbers for real measurements.
- Add automatic model routing only after benchmarks show a need.
4. Memory and context
- Persistent SQLite chat history, saved tool outputs, and durable memory.
- Automatic compaction as context approaches its configured limit.
- Preserve decisions, constraints, unfinished work, and recent turns in the working context.
- Retain original history on disk for retrieval.
- Move compaction status and the manual action beside the model/context performance strip.
5. Files and activity
- Replace the unclear “Workspace” presentation with a simpler Files & activity area.
- Automatically create an app-managed working folder, using the app’s installation area where writable.
- Confine default file operations to that folder.
- Preserve existing user files and history during migration and updates.
- Clearly separate this file boundary from broader shell or computer access, which requires explicit enablement and approvals.
6. Tools, skills, and integrations
- Keep agent operation enabled by default, including the requested --agent support.
- Support file operations, code execution, shell commands, search, browsing, vision, computer interaction, document creation, and scheduled workflows.
- Build a searchable skills library, using your supplied list as the requirements source.
- Provide skill descriptions, enable/disable controls, use-in-chat actions, and reviewed Markdown imports.
- Establish an extensible integration/catalog structure; don’t imply a functioning external marketplace before one is connected.
- Support future Google Workspace, GitHub, email, databases, and other integrations through their required credentials.
- Preserve tool approvals; a skill or plugin cannot silently grant itself permissions.
7. Conversational voice
- Local speech recognition and speech synthesis.
- Interruptible conversation: speaking can stop playback and the current response.
- Dictation fills the composer without sending automatically.
- Actual microphone, playback-speed, speech-detection, pause, and interruption settings.
- Test capture → transcription → model/tools → speech, including cancellation and interruption.
8. Reactive 3D entity
- Preserve the established UI while evolving the persistent background.
- A neural lattice/brain-inspired form during work, smoothly morphing into a toroidal voice core during conversation.
- Drive deformation with real microphone and playback amplitude/frequency data.
- Represent observable reasoning, generation, memory, and tool activity with distinct motion and pathways.
- Use restrained depth/parallax during conversation while keeping text, approvals, and controls readable.
- Respect reduced motion and maintain reasonable GPU usage.
- No invented model-confidence, temperature, or “internal thoughts” telemetry.
9. Functional Settings
- Clear sections for Models, Voice, Tools & permissions, Memory & context, Appearance, Accounts, and Updates.
- Real controls connected to persisted settings.
- Proper loading, saving, validation, error, unavailable, and restart-required states.
- Advanced inference details available when needed rather than dominating normal use.
10. Accounts and Google sign-in
- Separate local profiles with independent chats, memory, preferences, and working files.
- Safe profile switching without mixing active tasks.
- Lay the foundation for Google authentication and multiple connected accounts.
- Keep identity sign-in separate from permission to access Gmail, Drive, or other services.
- Google sign-in needs publisher OAuth configuration and an end-to-end verified flow before it is enabled.
- Signing in will not imply cloud sync.
11. Desktop packaging and updates
- A packaged Windows app with installer, shortcuts, and uninstaller.
- Show installed version, update availability, release notes, and an Update button.
- Configure the GitHub release source on the publisher/backend side—not as a normal user setting.
- Versioned releases, verified downloads, and preservation of user data.
- Prepare the repository for GitHub without personal histories, credentials, machine-specific configuration, or model weights.
- Public publishing, final branding, and code signing remain explicit release milestones.
12. Verification and delivery
- Test against the real Python backend and local model.
- Verify chat, tools, approvals, persistence, compaction, model selection, benchmarking, profiles, voice, and settings.
- Check keyboard access, window resizing, contrast, and performance.
- Package the resulting desktop build and distinguish verified functionality from outstanding release dependencies.
Additional requirements: selectable female and male local voices; real audio-reactive neural/toroid entity. No feature is complete until its acceptance test passes.
