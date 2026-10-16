# Luminaria 0.2.3 — graphics resilience

This release preserves Graphite/Ivory dark and light branding and the existing
voice pipeline. It does not complete the entire master specification.

## Changes

- WebGL context loss now stops further animation scheduling/draws and switches
  to a static voice interface. Chat, voice controls and tool approvals remain
  part of the normal app; graphics failure does not grant permissions.
- Missing WebGL and shader startup failure expose an honest fallback message
  in Appearance diagnostics instead of leaving “Measuring…” indefinitely.
- Reduced-motion preference applies before the first draw. Motion preference
  changes immediately refresh diagnostics instead of retaining an old FPS value.
- A system-controlled pause is labelled “System reduced motion” and cannot be
  overridden by the background-motion button.
- `LocalAIStudio.exe --safe-graphics` disables WebGL for that launch only.
  Close the app and reopen normally to retry 3D. No saved color, permission,
  model or voice preferences are changed by this flag.

## Automated evidence

Eleven existing Python regression tests pass. The renderer lifecycle test runs
the actual core.js with controlled DOM/WebGL boundaries and verifies unavailable
WebGL fallback, context-loss loop termination, initial reduced motion, subsequent
preference changes and continuing voice-status captions. These are behavioral
regression checks, not pixel/GPU or OS reduced-motion measurements.

## Native and model evidence

- Installer completed with exit 0. The installed API reports 0.2.3. Installed
  core.js and palettes.js SHA-256 hashes match source after the build.
- Launched the installed desktop with `--safe-graphics`. The neural canvas was
  absent; chat/settings and 63 discovered tools remained available. Appearance
  diagnostics displayed “3D graphics are unavailable. Voice and chat remain
  available.” This verifies fallback UI startup, not a new fallback audio test.
- Launched WebView with the temporary Chromium argument
  `--force-prefers-reduced-motion`. The native UI showed the disabled “System
  reduced motion” control and the static neural form. This exercises the real
  media-query path, not a change/test of the Windows-wide accessibility setting.
- Reopened normally without test arguments. Normal neural rendering and the
  motion control returned. Started voice: WebView reported microphone recording,
  the toroidal stage appeared, and Listening/Interrupt/End voice were visible.
  End voice removed the recording indicator and returned to the workspace and
  compact neural form. No new spoken phrase or playback interruption was tested.
- Three successive real-Qwen compactions retained OAK_923, the source-preservation
  constraint and phase-1.md / phase-2.md / phase-3.md decisions. Original message
  counts remained 4, 8 and 12. Fixture chat `5b721e9a3e83484494950155df374d84`
  was archived afterward. Detailed results are in ignored
  `data/compaction-0.2.3-live.json`. This is repeated bounded compaction, not
  a full-context or multi-hour endurance test.

The app was left open in normal graphics mode with voice capture ended, no
active agent runs, and 63 tools. Saved theme and permission settings were retained.

## Remaining scope

The outstanding items in verification-0.2.2.md remain open unless explicitly
superseded here. In particular, real OAuth provider login/desktop enforcement,
public release/signing, quality benchmarks, sustained voice/GPU measurements,
and deferred abliterated-model/context controls are not claimed complete.
