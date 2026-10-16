# Luminaria 0.2.1 — UI and voice verification

## Implemented
- Removed custom palette UI; branded Graphite dark and Ivory light modes persist per profile.
- Neural lattice morphs to a toroidal conversational core. Real microphone/output FFT bands and RMS drive deformation. Application phases select activity regions; no invented model metrics.
- Motion pause and system reduced-motion support; static fallback on WebGL failure.
- Separate dictation and conversation controls; conversation interruption cancels playback and active generation.
- Approval review restores readable chat. Inline chat renaming replaces the native prompt.
- Removed obsolete interactive-canvas controls and corrected light-mode notification/approval colors.

## Verified on 2026-10-16
- Built PyInstaller desktop and Inno Setup installer, version 0.2.1; installation returned exit code 0.
- Native Windows WebView2 inspection confirmed dark/light settings changes and neural lattice rendering. Fixed an actual shader precision mismatch found during this check.
- Persisted light mode read back from the packaged backend.
- Packaged backend synthesized non-empty PCM WAVs for Lessac, Amy and Ryan (2.84, 3.17 and 1.96 seconds for the test sentence).
- Whisper transcribed a prerecorded synthetic speech fixture correctly. This is not physical microphone validation.
- Installed backend completed a fresh Qwen request with answer `42`.
- JavaScript syntax and Git whitespace checks passed.

## Pending: do not describe as passed
- Native microphone permission is awaiting the user. Physical microphone capture, acoustic echo, spoken interruption and the full native voice-stage interaction are not yet verified for this revision.
- Final blending/contrast and RMS refinements are in installed files and the installer; the currently open window awaits reload after the microphone prompt is handled.
- Hosted sign-in, provider integrations, public signed releases and the remaining master-spec phases are separate unfinished work.

## Scope amendment
The user explicitly replaced the master specification's custom palette engine with two branded dark/light appearances. Original custom preference data is retained for non-destructive migration but is no longer exposed or applied.
