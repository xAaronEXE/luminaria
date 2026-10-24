# Account cloud sync — October 22, 2026

User scope: chats, files, memory, settings and profile synced to the account. Desktop inference stays local; future phone pairing/remote execution is not implemented here.

## Implementation
- Account-scoped D1 records with compare-and-swap revisions, deletion tombstones and idempotent mutation receipts.
- Private Standard R2 content-addressed blobs for files and compressed chats. SHA256 and fixed-length streams reject corrupt/oversized bodies.
- Portable local export/import, offline state, explicit conflicts and local recovery copies; atomic chat transactions preserve tool/message history and summary boundaries. Imported actions are inert, never approvals or running tasks.
- Selected working folder, attachments and tool outputs; credential/key/environment files, model weights, local databases, dependency folders and links excluded. Device permissions, paths, credentials and executable setup never migrate.
- Portable appearance/voice preferences and reply/compaction settings. Device-specific model installation/hardware/permission configuration stays local.
- Empty workspaces pull account preferences; nonempty concurrent edits require explicit resolution. Active/paused conversations are protected.
- Five-minute idle sync, manual run, offline pause, first-upload review, budget backoff and conflict controls under Settings > Cloud sync.

## Conservative no-paid-fallback controls
- 128 MiB/account and 512 MiB for this entire sync service, including pending and retained blobs. 20 MiB maximum per file/compressed conversation.
- Across this service: 5,000 R2 writes/month, 50,000 R2 reads/month, 25,000 requests/month. Daily limits: 250 writes, 2,500 reads, 1,500 requests and 100 record changes. At most 1,000 record changes/month and 2,000 records total.
- D1 atomic reservations prevent concurrent requests overspending operation/storage budgets. Admission fails closed before R2 operations; quota exhaustion preserves local data and backs off.
- Only Standard R2 storage is used. Caps are substantially below published R2 included allowances, but ARE NOT an account-wide billing ceiling. Other buckets/products, operator changes or paid-plan account usage can still cause charges. Never promise absolute $0 billing.
- Workers/D1 must remain on Workers Free for provider hard limits rather than paid overages. OAuth token cannot read account subscriptions (403); owner confirmed Workers Free on October 22 before enabling sync.

## Hosted state
Private bucket luminaria-account-sync created; r2.dev public access disabled. Additive 0005 schema executed directly; older migrations had previously been applied outside the migration ledger, so migrations apply was deliberately not run.
Owner authorized hosted sync after confirming Workers Free. Version 661e654a-71bc-41e1-b2e0-097f2cf475ef deployed with SYNC_ENABLED=true. Installed 0.2.35 matches the tested executable; installer exited 0. First live sync: 2 chats, 27 files, portable settings and workspace profile; 29 private blobs totaling 169203 bytes, verified by remote D1 aggregate readback. No saved memories existed. Repeated sync completed without conflicts.

## Verification
17 isolated Python sync tests cover two-device data, summaries, settings/profile, conflicts/recovery, exclusions, paths, offline recovery, task guards, deletion, lost-response retry, inert action history and budget backoff. Existing account/profile suites remain passing.
Local real HTTP integration exercises the actual Worker, D1 and R2 APIs with encrypted fixture sessions on two isolated desktop stores. Chats/files/memory/settings/profile transfer and conflicting offline edits pass. This is not a claim of production two-PC or phone acceptance.
Node service tests cover bearer authentication, cross-account isolation, atomic revision races, idempotent retries, tombstones, private file reads, integrity rejection, empty files, revocation and concurrent budget/global-storage enforcement. All four service suites pass.

## Remaining gates
Workers Free confirmation, hosted enablement, installation and first live upload are complete. Production second-device/offline-conflict acceptance and native visual acceptance remain pending. On October 23, Aaron explicitly authorized publishing 0.2.35 as the latest release with these limitations disclosed. These acceptance items remain pending.
Cloud sync is not end-to-end encrypted. Retained historical/unreferenced blobs count against the cap; verified hosted deletion is currently handled through support rather than an in-app erase control. Multi-device identity-account merge with existing cloud data is blocked pending explicit workspace resolution.
