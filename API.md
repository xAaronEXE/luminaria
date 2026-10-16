# API contract (local preview)

All /api routes except GET /api/bootstrap require X-Studio-Token returned by bootstrap. Host and Origin are restricted to loopback. Responses are JSON except SSE, WAV and downloads.

- GET /api/state?chat=ID: chats, selected messages/actions/summary, pinned memories, current run, context, tool/connector status.
- POST /api/chats {title}: {id}.
- POST /api/chats/ID/run {text, attachments:[], reasoning:false}: {run_id}.
- POST /api/chats/ID/stop: cancels and awaits the current task; closes pending tool pairs. Does not undo actions already performed.
- POST /api/chats/ID/resume: resume checkpoint after interruption.
- POST /api/chats/ID/compact: explicit compaction, original history retained.
- GET /api/events: SSE `data` objects. ready, changed, delta {chat,text}, reasoning {chat,text}, approval, compacted. Re-fetch /state on non-delta events. Reconnect and refresh on disconnection.
- GET /api/approvals; POST /api/approvals/ID/decision {decision:"allow"|"deny",scope:"once"|"always"}. Always scope only for eligible approve-tier tools.
- GET/POST /api/models; POST /api/models/ID/select. Selection blocked while a run is unfinished.
- GET/POST /api/settings; GET /api/tools; GET/POST /api/skills.
- GET /api/voice/status: readiness, recognition/speech labels, local/audio_saved flags.
- POST /api/voice/install: explicit model download for first-use setup.
- POST /api/voice/transcribe: binary mono PCM16 WAV at 16 kHz, at most 35 s; returns {text,seconds}. No chat side effect until client sends recognized text through normal /run.
- POST /api/voice/speak {text}: audio/wav, 1–1600 characters. Client cancels playback and discards stale responses on interruption.
- GET /api/updates; POST /api/updates/install: user-configured GitHub release workflow.

Frontend voice uses an epoch counter to discard stale speech/transcripts, AudioWorklet capture, browser echo-cancellation request, and continuous silence segmentation. Switching tasks or ending voice releases tracks. Model/tool approval is independent of voice.
