# Luminaria 0.2.2 verification — 2026-10-16

Installed desktop: `C:\Users\desse\Desktop\Luminaria\App\LocalAIStudio.exe`.
All app data, models, runtime and build artifacts stay under the Luminaria root.
Build and installer both completed successfully; installation returned exit 0.
The installed backend is on port 3210. Preview ports are not installation evidence.

## Confirmed in this pass

- Installed Qwen read a new Markdown attachment, ran Python `print(6*7)` through
  the real agent tool, and answered the fixture codename ALDER_214 and 42.
  Chat: `7154219dc4054bc88482573d86e32d4c`.
- A real 256-token Qwen speed benchmark measured 35.8 tokens/s end-to-end,
  37.2 decode tokens/s, 0.30 s first token, 7.15 s elapsed, 32,768 configured
  context, UD-IQ4_XS. This is a short speed measurement, not a quality evaluation.
  The backend returned the new persisted benchmark, and the native Models panel
  displayed **35.8 tok/s** in both the model choice and details.
- Real Qwen compaction preserved MAPLE_522, the original-source preservation
  constraint and the pending review task. All six original synthetic fixture
  messages remained saved. Chat: `09f64bb46db6427fbc860cf658198b54`.
  This is a bounded fixture, not a many-hour/full-capacity endurance test.
- Rename, fork, archive/restore and trash/restore passed on disposable chats.
  No permanent deletion or timed trash expiry is claimed.
- Windows MCP discovery returned 21 tools; browser MCP returned 25. The desktop
  showed 63 available tools total. Discovery does not verify every tool's execution.
- CLI supports `--agent`, `--server`, `--version` and `--help`; agent is default.
  It does not implement a separate interactive terminal-chat client.
- Qwen created DOCX, PDF and XLSX files through the real code tool in disposable
  chat `275cf4884d564f7eabd8ca8449ffaaef`. Independent readers verified CEDAR_733
  in DOCX paragraphs and extracted PDF text, and CEDAR_733 plus numeric 42 in
  spreadsheet cells. This verifies file creation/content, not visual layout quality.
- A disposable schedule created a task and completed with SCHEDULE_022_OK, with
  no tool side effects. Fixture `7a8e8c510eb04e069c0f0a99e82a435e` was disabled
  afterward. Its own next_run was advanced in SQLite to exercise the scheduler;
  the normal five-minute waiting period was not tested. Chat:
  `1ffa3ea7d8094367a5a7d9aad8108821`.
- Nine Python regression tests pass: attachment validation/full-file retention,
  benchmark migration/persistence, bounded compaction/failure behavior,
  profile separation, restart-latched permissions, installer checksum acceptance
  and rejection. The updater launcher is mocked, never executed by these tests.
- Hosted identity service deployed to the personal Cloudflare account. Local
  workerd/D1 tests pass a mocked-provider flow and security rejection cases.
  Live endpoints correctly return 401/503 without credentials. Real Google,
  GitHub and Discord login and desktop sign-in enforcement remain incomplete.

## Implementation details that affect acceptance

Text/code attachments retain their full UTF-8 source in the app files folder;
the prompt includes a bounded 16,000-character excerpt and a retrieval path.
Maximum upload is 512,000 bytes, four files per message. PDFs and Office files
are not supported as attachments by this implementation.

Benchmark history now uses device-shared SQLite, importing legacy JSON results
idempotently. Legacy model registration data is retained. Compaction consumes
every fragment through rolling token-budgeted model calls and commits only after
successful completion. Unsummarizable input fails without deleting originals.

The updater now accepts both Luminaria and legacy installer filenames, verifies
the download against SHA256SUMS, and rejects corrupt payloads before launch.
The final 0.2.2 rebuild includes that fix and byte-preserving text attachment storage.
No public stable update channel or publisher code-signing certificate is configured.

## Earlier physical voice evidence retained

The user heard the real spoken answer 42. Playback interruption stopped an old
answer and answered four. A separate active-generation interruption recognized
“Stop. Answer only ready.”, stopped the partial answer, and completed “ready”.
See verification-0.2.1.md for run IDs and native UI observations. These are
observed tests, not a blanket claim that Phase A is complete.

## Remaining acceptance and scope

- OS reduced-motion, WebGL fallback, sustained voice/GPU performance and approval
  interaction during voice still need explicit verification. An earlier noise
  capture cancelled generation without a recognized phrase; sensitivity remains.
- Further spatial/voice refinement must follow Graphite/Ivory dark/light branding.
  No custom color controls. Current renderer timing counts draw submissions,
  not GPU completion or inference speed.
- Long-history repeated compaction, quality benchmarks, actual live token-speed
  updates, file/folder ingestion and full skills inventory reconciliation remain.
- Browser/desktop tool execution, document layout and scheduler endurance need their
  own evidence; tool discovery and package imports alone do not count.
- Desktop account wiring, secure token persistence, real provider consent flows,
  account lifecycle and required-sign-in enforcement remain.
- Credential-backed service integrations remain separate from identity login.
- Public distribution, release/update channel, signing, clean-machine install and
  uninstall/data-retention checks remain.
- Additional abliterated models, separated model groups, cracked styling and
  context-expansion controls remain explicitly deferred until after current phases.

Local detailed fixture logs are in ignored `data/*0.2.2*` files; user data,
credentials and model weights are excluded from Git.
