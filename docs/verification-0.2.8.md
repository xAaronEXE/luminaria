# 0.2.8 candidate verification

This is an implementation candidate, not an accepted or published release.

## Automated checks

- 53 existing Python tests passed across 11 separate module processes: work_events, appearance_preferences, model_recovery, chat_deletion, action_history, profiles_permissions, persistence_compaction, model_library, model_storage, quality and updates.
- Three new work_evidence tests passed: historical summary retrieval, cross-chat rejection and missing-token rejection. Total: 56 Python tests across 12 isolated module processes.
- Node suites passed: work-graph.cjs, message-queue.cjs and renderer-lifecycle.cjs. They cover replay/deduplication/order, bounded scenes, failure relationships, stale recovery rejection, queue isolation/cancellation/retry, voice priority, background completion and renderer lifecycle boundaries.
- Every web/*.js file passed node --check; git diff --check passed.
- Renderer unit tests stub DOM/WebGL boundaries. They do not establish native GPU performance or audible output.

## Direct browser checks

The isolated tests.spatial_preview server on port 3215 supplies mocked APIs. Its visible banner states that no model execution occurs. It does not call the installed app or alter its data.

Observed in the browser: actual WebGL rendering; light/dark/custom-accent modes; recorded node names and statuses; Arrow-key selection, Enter inspection and Escape return; outline selection; tool arguments/output inspection; Activity links in both directions; compact evidence replacing the outline and Back restoring selected-row focus; queued send dispatch after a fixture terminal event; and automatic outline fallback under an explicit no-WebGL fault shim. The browser error log was empty after final checks.

Fresh local captures: .impeccable/review/spatial-light.png, spatial-dark.png, spatial-accent.png, spatial-compact.png and spatial-fallback.png. These ignored local files are visual fixture evidence, not packaged acceptance.

The final design review cleared compact overlap, scene framing, recorded-node labeling and stale branding documentation. No additional material regression was identified in that bounded review.

## Remaining acceptance

Aaron must perform docs/testing-0.2.8.md against the packaged Windows candidate. Native WebView2 rendering, real model/tool event execution and history recovery, microphone/speaker interruption, entity motion during real concurrent voice/task activity, installation/update behavior and measured native performance remain unverified in this change. Prior-version voice results do not establish these outcomes for 0.2.8.

Do not publish, tag or merge as an accepted release until that acceptance passes. Model-provided plans/reasoning remain labeled; the scene does not expose otherwise unavailable internal model computation.

## Build result

The local build.ps1 completed successfully and produced release/Luminaria-0.2.8-Setup.exe (178967755 bytes). Its SHA-256 matches release/SHA256SUMS.txt: 423120c392d9931b2a86d346921f6343c13d44d87d0a0095916a5e0be1906c63. The bundled VERSION is 0.2.8. Build log: data/build-0.2.8-delivery.log (local ignored file). The installer was not launched, published or claimed signed. Build completion is not Windows acceptance.
