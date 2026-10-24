# Candidate verification — 0.2.18 through 0.2.20

October 17, 2026. Local source work; no installer was built or published, no Worker
was deployed, no mandatory sign-in was enabled, and no desktop status was advanced.

## Automated checks

174 Python tests passed across 21 explicitly selected modules, each run in its own
process with isolated data. Broad discovery and tests/memory_denial.py were not run.
Modules: file_workflows (8), file_workflow_routes (2), hardware_tuning (6),
workflow_hardening (12), connector_cancellation (2), checkpoint_continuation (8),
retrieval_reliability (10), web_fetch_fixtures (14), work_events (5), skills_inventory (3),
usage_insights (12), working_brief (6), long_workflow_retention (5),
persistence_compaction (4), connectors (2), planning_mode (5),
orchestration_routing (27), identity (13), account_devices (15), sign_in_gate (7),
integrations (8).

Three Node suites passed: message-queue, renderer-lifecycle and work-graph. Renderer
boundaries are stubbed, not actual native GPU acceptance. Changed JavaScript passed
syntax checks; git diff whitespace checks passed.

auth-service npm test passed its identity-flow and release-channel suites. Provider and
release responses are mocked; integration tests use a local fixture MCP service. No
real Google/GitHub/Discord sign-in, published-release download or two-PC sync was tested.

Tests caught and corrected a planning-mode journal regression, history matching that
missed a late passage, cache copy compatibility, and immediate/repeated tuning-stop cases.
Windows sign-in test database cleanup was corrected after a shutdown warning.

## Browser and system evidence

An isolated source server on loopback port 3211 uses .build/preview-0.2.18 data, separate
from the user's app/profile on port 3210. Through its actual UI:

- Opened Tools → File workflows, created a disposable plan with objective/scope/criteria,
  approved create, observed Verified/Awaiting review, independently read file bytes and
  SHA-256, then accepted the test objective. Expected and observed hash:
  c361e47a5b41af03bcc7243ffa4d31abf12a5d2e9050bfd59f0c274fdbb2db05.
- Viewed Hardware & tuning in light and dark modes. Actual system/driver inventory:
  Ryzen 7 7800X3D, 8 physical/8 reported logical cores, approximately 31.6 GiB RAM,
  RTX 5070 Ti and approximately 15.9 GiB driver-reported VRAM. These are observations,
  not promised constants. No model was registered in this isolated profile, so benchmark
  controls remained disabled. No weights were downloaded or tuning profile applied.
- Preserved the existing sidebar, inspector, composer and spatial visuals. Scoped
  screenshots are stored under .build/verification for local review, not public assets.
- Impeccable's mechanical detector ran once. It reported typography/token, tiny-text,
  animation and decorative-pattern advisories in the existing interface. This is not a
  clean whole-app accessibility/performance audit; unrelated visual foundations were
  deliberately preserved. The source warning details are not a desktop acceptance result.

## Pending acceptance and limits

- Packaged WebView2, installer/update/migration regression, real local-model retention,
  actual tuning comparisons/resource-pressure cleanup, and real provider cancellation.
- Account Worker migrations/deployment, real provider dialogs, offline expiry, revocation
  on another PC and aggregate sync/deletion on two PCs. User runs dialogs/build/publish.
- A full desktop evidence/retrieve/produce/verify skill. Automated tests verify the
  lifecycle contract; the browser file test does not substitute for that desktop skill.
- Local retrieval is literal with bounded source passages; no embedding backend is
  available/advertised. No reranker was added. Separate plugin identities remain
  unavailable; measured connector/tool counts are retained without inventing plugins.
- Application-control expansion remains Planned after file-first desktop acceptance.
- File guards are optimistic, not an OS sandbox or universal cross-process transaction.
  Recovery inspects uncertain results instead of promising universal safe replay.

Use testing-0.2.17.md for the required installed-app results. The current local candidate
is suitable for review and further acceptance, not a claim that the full plan is released.

## Branch and PR handoff

Local stacked branches: fix/0.2.17-desktop-acceptance (0.2.18 candidate),
feature/0.2.19-hardware-tuning, feature/0.2.20-file-workflows. Planning-mode and repeated
tuning-stop corrections were backported to their respective earlier candidates; rebasing
changed only release documentation relative to the tested integrated source tree.

GitHub inspection found existing open PR #19, “Docs: full scope of work in detail (all
requirements, status, remaining)”. It was left untouched. No additional PR was opened and
no implementation branch was pushed, preserving the one-open-PR requirement. Sequential
PR creation follows resolution of that existing PR. User still owns build/publish steps.
