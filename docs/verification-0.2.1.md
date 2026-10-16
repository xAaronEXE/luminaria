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

- Physical microphone capture passed: the user spoke "What is six times seven?", Whisper produced "What is 6 times 7?", and Qwen answered "42." The user explicitly confirmed hearing the spoken answer. Acoustic echo and spoken interruption remain unverified.

- Final blending/contrast and RMS refinements are in installed files and the installer. The desktop was restarted to load them; light-mode persistence and removal of obsolete canvas controls were observed.

- Hosted sign-in, provider integrations, public signed releases and the remaining master-spec phases are separate unfinished work.



## Scope amendment

The user explicitly replaced the master specification's custom palette engine with two branded dark/light appearances. Original custom preference data is retained for non-destructive migration but is no longer exposed or applied.


## Follow-up desktop verification
- Installed core.js, voice.js and style.css hashes matched source at commit f79db42.
- Native light-mode voice stage displayed its caption above call controls and metrics without the previous overlap.
- During a generated rainbow explanation, the UI reached Speaking and the torus deformed. Clicking Interrupt returned it to Listening - reply interrupted with no playback error notification in the subsequent observations. This confirms the UI cancellation regression check; physical audibility after cancellation was not independently measured.
- Installer SHA256SUMS.txt was regenerated from the current 0.2.1 setup file.
- Spoken barge-in, active-generation voice cancellation, microphone resource release and small-window acceptance remain pending.

## Physical spoken barge-in result
The user confirmed that speaking during the solar-system playback stopped the old audio and produced the new answer. Saved chat 6bf8b230f51b49c4a12f62ace82f6dd1 contains the recognized utterance "Stop. What is 2.2? 2 plus 2?" followed by "2 plus 2 is 4." The follow-up run completed. This verifies physical playback barge-in and continued conversation. It does not establish interruption of still-running model generation: the preceding solar-system answer had already completed before its audio playback was interrupted.

## Active-generation cancellation observation
A long astronomy response was cancelled while streaming. The packaged backend reported Stopped, finished the run, cleared live text, and retained a partial assistant message with interrupted=true and [Stopped]. The captured 1.224-second audio was entirely removed by Whisper VAD and produced no recognized speech. This establishes the capture-triggered generation cancellation path, not successful recognition of the requested spoken command. Investigate false-positive speech detection and retest a clear utterance before marking this acceptance item passed.

## Confirmed active-generation spoken interruption
The follow-up star-evolution test (run 7d92dbb261d34f1a8261fac35832543c) retained a partial assistant answer with interrupted=true. The physical microphone captured "Stop. Answer only ready." The replacement run 20ab45bf47334487bdca0f4dd570eb94 completed with the exact answer "ready". This verifies recognized spoken interruption of active generation and successful continuation in the same chat. The earlier unrecognized-noise capture remains a separate sensitivity concern.
