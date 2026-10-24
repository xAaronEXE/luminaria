# API contract (local preview)

All /api routes except GET /api/bootstrap require X-Studio-Token returned by bootstrap. Host and Origin are restricted to loopback. Responses are JSON except SSE, WAV and downloads.

- GET /api/state?chat=ID: chats, selected messages/actions/summary, pinned memories, current run, context, tool/connector status.
- POST /api/chats {title}: {id}.
- POST /api/chats/ID/run {text, attachments:[], reasoning:false}: {run_id}.
- POST /api/chats/ID/stop: cancels and awaits the current task; closes pending tool pairs. Does not undo actions already performed.
- POST /api/chats/ID/resume: resume checkpoint after interruption.
- POST /api/chats/ID/compact: explicit compaction, original history retained.
- GET /api/events: SSE `data` objects. ready, changed, delta {chat,text}, reasoning {chat,text}, approval, compacted. Re-fetch /state on non-delta events. Reconnect and refresh on disconnection.
- SSE `work` {event}: structured work event, also persisted. Event fields: id (stable, replays deduplicate), seq (per run), chat, run, type, at, status, label, node, parent, tool, tool_call, region (planning|memory|retrieval|files|tools|generation|verification), step (plan step marked active by the model), follows_failure (earlier failed call of the same tool), evidence ({action}|{message}|{summary}|{run}); never arguments, outputs or message text. Plan and reasoning events carry source "model-provided"; tool events are execution evidence recorded by the engine. Types: run.started|completed|failed|cancelled|interrupted|resumed, plan.created|revised (steps with id,title,status,depends_on), generation.started|completed, reasoning.started, tool.requested|started|completed|failed|denied|interrupted, approval.requested|allowed|denied, compaction.started|completed|skipped. Voice states are client-side only.
- GET /api/chats/ID/work?runs=12: persisted work events for the chat's most recent runs, ordered, plus active_run. Clients rebuild from this on reconnect or chat switch.
- Tool update_plan (automatic tier, not affected by "review read-only tools"): optional, model-provided plan with 1–24 steps.
- GET/POST /api/preferences `appearance`: {mode:"light"|"dark"|"system", accent:""|"#RRGGBB", modes:{dark|light:{accent?:"#RRGGBB", colors:{key:"#RRGGBB"}}}}. Color keys: bg, sidebar, panel, raised, hover, line, control-line, text, muted, dim, success, warning, danger, info, entity, particle, lattice, pathway, glow. Profiles without it migrate from a saved theme_mode, otherwise light.
- GET /api/approvals; POST /api/approvals/ID/decision {decision:"allow"|"deny",scope:"once"|"always"}. Always scope only for eligible approve-tier tools.
- GET/POST /api/models; POST /api/models/ID/select. Selection blocked while a run is unfinished.
- GET /api/model-library: storage, download budget, jobs and catalog entries. Entries carry configured and supported context, estimated context-cache bytes, pinned source and an optional shared vision projector.
- POST /api/model-library/ID/download|cancel|discard|use|remove. ID is a quantization or projector id. Remove needs {confirm:true}; active models and projectors are protected. Use restarts the model manager when the model or its projector is new to it.
- GET/POST /api/settings; GET /api/tools; GET/POST /api/skills.
- GET /api/voice/status: readiness, recognition/speech labels, local/audio_saved flags.
- POST /api/voice/install: explicit model download for first-use setup.
- POST /api/voice/transcribe: binary mono PCM16 WAV at 16 kHz, at most 35 s; returns {text,seconds}. No chat side effect until client sends recognized text through normal /run.
- POST /api/voice/speak {text}: audio/wav, 1–1600 characters. Client cancels playback and discards stale responses on interruption.
- GET /api/updates; POST /api/updates/install: user-configured GitHub release workflow.

Frontend voice uses an epoch counter to discard stale speech/transcripts, AudioWorklet capture, browser echo-cancellation request, and continuous silence segmentation. Switching tasks or ending voice releases tracks. Model/tool approval is independent of voice.

## Spatial browser contract (0.2.8)

- SSE work events dispatch studio-work without triggering a state fetch by themselves.
  Existing changed events still refresh state. SSE reconnect triggers work recovery.
- work-graph.js reduces evidence into studio-scene: chat, nodes, known edges, focus,
  selected, omitted count and recovery error. All references are namespaced per run.
- studio-appearance updates CSS and scene materials; no per-frame computed-style reads.
- studio-audio and studio-voice-state remain local/client-side. studio-voice-turn marks
  a pending spoken turn so typed queues cannot race barge-in/transcription.
- GET /api/chats/ID/summaries/SUMMARY_ID resolves exact historical summary evidence.
  Existing token, loopback, profile and chat boundaries apply; foreign references return404.
- Typed queues are client-side, per chat, bounded to ten unsent messages. A queued item
  is not a backend message until POST /chats/ID/run succeeds. Active submissions cannot
  be cancelled as unsent; errors remain available for explicit retry/cancel.
- Spatial overview enables pointer selection; normal conversation retains ordinary chat
  interaction. The accessible outline uses the same reduced nodes as WebGL.
