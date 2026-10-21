# Local workflow interfaces

All routes use the existing local host/origin/session-token and account gates. No new
cloud synchronization is introduced. Existing API consumers retain their small-result
shapes; added retrieval fields describe source revisions, trust, bounds and freshness.

## Retrieval and skill contracts

- `read_file` returns bounded text with source ID, content revision, original-character
  reference ranges and representation/trust fields. Files are freshly read, not cached.
- `history_read` accepts message_id or action_id plus optional offset/limit in characters.
  Complete small JSON results retain message/output; larger results return verbatim JSON
  excerpts and guidance. Original tool outputs over 32 MB remain downloadable via Activity.
- `search_files` shares source-reference construction with file/history/web retrieval,
  prunes excluded directories, reports partial scans, and checks cancellation in a worker
  thread. Local search is literal; no semantic backend or reranker is advertised.
- `web_fetch.browser_fallback` explicitly authorizes supported browser navigation/snapshot
  after JavaScript/auth/extraction failure. Blocks are not bypassed; login remains manual.
- Skill catalog adds state/reason/inputs/outputs/permissions and last_run. load_skill
  preflights declared dependencies and folder access, then records Running. finish_skill
  requires successful source-action IDs and output paths in the current run, reads/hashes
  those files, and records Completed with semantic-review limitations. Missing outputs or
  unverified run endings cannot become Completed simply from loading instructions.
- Connector tool-list notifications invalidate cached schemas and queue rediscovery.
  Transport-call exceptions clear connected readiness; structured provider tool errors
  remain tool outcomes. Cancellation reaches the MCP call; remote side effects may remain
  uncertain and are never assumed undone.

## Hardware and tuning

- GET `/api/hardware`: system/driver inventory and configured installed-model choices.
- GET `/api/tuning`: active job, local history, rollback availability.
- POST `/api/tuning/start`: `{model, threads: [integers], gpu_layers: [integers], consent: true}`.
  Uses existing weights and runtime, three repetitions per variant; returns a background job.
- POST `/api/tuning/stop`: idempotent cancellation with owned runtime cleanup.
- POST `/api/tuning/apply`: `{job}` or `{rollback: true}`. Requires an idle app and matching
  provenance. Selection applies only after app/owned-manager restart. No schema migration;
  existing model registry entries acquire an optional tuning field.

Runtime RAM samples, whole-device VRAM snapshots, backend scheduling, browser scheduling
and renderer observations are labeled separately. Missing provider timing remains null.

## File-first workflows

- POST `/api/file-workflows`: `{objective, completion_criteria, allowed_locations, steps}`.
  Each step has action read/create/edit/trash and relative path; create includes content,
  edit includes old_text/new_text. Captures source observations and predicted final hashes.
- GET `/api/file-workflows`: latest 50 records, active ID, and latched Full Access flag.
- POST `/api/file-workflows/{id}/run`: `{approved: true, all_steps?: true}`. all_steps is
  permitted only in Full Access. Verified steps never replay. Inference/model-management
  and workflow execution exclude each other while file effects are in progress.
- POST `.../stop`: sets the cancellation flag; the current atomic operation settles.
- POST `.../inspect`: checks interrupted expected/observed states without repeating writes.
- POST `.../accept`: user accepts the objective after all steps verify and final checks pass.
- POST `.../restore`: `{step, approved: true}` restores a verified local recovery copy only
  when the original path is absent. No overwrite or permanent-purge endpoint exists.

States are Ready, Running, Stopped, Needs review, Awaiting review and Completed. Individual
steps are Ready, Running, Verified or Uncertain. Workflow records live in the existing
profile SQLite settings; recovery bytes live in its workflow-recovery directory. No
destructive database migration or personal-history rewrite is required.

## Insights snapshot compatibility repair

POST /insights/snapshot accepts the authenticated account's full retained daily snapshot for one device, including an empty snapshot. Validated rows replace only that device's rows in one D1 batch transaction. This removes stale days after timezone changes/deletion without clearing other devices. The old /insights/days POST remains for older clients. New desktop clients require the snapshot endpoint and fail with an upgrade-service message on 404; they do not fall back to delete/upload. The companion Worker was deployed before this local installation. No new table or destructive migration is required.
