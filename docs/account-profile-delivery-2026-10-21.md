# Account and profile delivery — October 21, 2026

## Included in local 0.2.22

- Profile initials avatar, verified display name, public GitHub/Discord handle when available, linked providers, five headline stats, 53-week daily activity, weekly and cumulative views, keyboard navigation, local top tools/integrations/skills and a This PC / All devices scope control.
- Existing provider linking, remembered-device sessions, device revocation, login screen and offline policy retained. Required sign-in was enabled on this PC only after a successful live online session check. Remembered sessions avoid unnecessary prompts. New installations retain the existing policy; no universal policy change is claimed.
- Public handles use migration 0004, applied before personal Worker deployment. Existing identities acquire a handle at next provider sign-in. No email address is used as a public handle.
- Route/IP/session-aware rate limits: global IP 3,000/hour; sign-in start 20/10min; authorize/callback 60/10min; device polling 120/min; snapshot uploads and account deletion/revocation 20/min; remaining protected routes 300/min. Health is public. 429 includes Retry-After. D1 counters use hashed keys and expiry cleanup. Shared-IP limits and fixed-window boundary bursts remain operational considerations; this is not a full WAF or penetration-test certification.
- Both Profile and the existing Insights screen hide cached account totals unless sync is enabled and the current server-verified account owns them. Legacy unscoped snapshots require a new opted-in sync. Local metrics remain separate from cloud totals.
- Includes guided skill prerequisite setup: actual permission/GitHub forms, local installed connector start/reconnect and live recheck. No software installation, Full Access enablement or credential grants happen automatically.

## Actual checks

Real personal identity service: existing DPAPI session verified; remembered-device list returned; all three provider configurations reported ready. Unauthenticated session/device/Insights reads and snapshot writes rejected. Live sign-in rate limit returned 429 on request 21 with Retry-After, using unsupported-provider probes; no accounts or OAuth flows were created. Migration and Worker deployment completed.

Real installed local model: a disposable task completed with ACCOUNT-METRICS-OK. Recorded generations increased by one and total tokens by 2,961. The acceptance chat was archived, not permanently deleted. The displayed local data came from real recorded events, not seeded dashboard figures.

Packaged 0.2.22 backend with isolated database/session copies: existing account verified; 371-cell grid returned real history; required-login gate verified online; after removing only the isolated session copies and restarting, workspace/profile/Insights APIs returned 423. Original credentials were not revoked or removed. The profile contained six recorded generations and 53,293 recorded tokens at this checkpoint; those are coverage-limited records, not historical backfill.

Automated: profile grid/username/account-date tests 4, account-cache isolation 1, identity 13, devices 15, sign-in gate 7, Insights 14, guided setup 5; each Python module ran separately. Identity-service tests include mocked full provider flows, cross-account/device controls, replay protections, snapshot correctness and route-limit isolation; both service suites passed. JavaScript syntax and whitespace checks passed. These fixtures are distinct from the live checks above.

## Still needs user participation / acceptance

- Fresh Google, GitHub and Discord OAuth sign-ins, provider linking/cancellation and a new public handle; existing-session verification is not fresh-login acceptance.
- Two-PC synchronization and remote revocation on the second PC. Sync remains opt-in; no personal totals were uploaded by this work.
- Full native visual review in dark/light/narrow windows and keyboard review, because native/browser UI automation was unavailable in this session. Backend/packaged tests do not establish visual acceptance.
- Natural expiry/offline transitions, every voice mode and long-session endurance. Existing seven-day offline grace and gate check caching mean revocation cannot be instant while offline.
- Plugin-identity metrics, Showcase, avatar uploads and external marketplace release remain separate; no invented counts or placeholder completion claims.

## Operations

Backups: archive/pre-0.2.22-2026-10-21. Installer and log remain local. Marketplace code is excluded. No GitHub release or updater promotion was performed. Builds remain unsigned. Provider secrets stayed in the personal Worker, and stored desktop tokens were never printed or committed.

Final installation completed with exit code 0. Installed executable hash matches the final build; required sign-in is active and the saved session verified online. Profile and guided-setup APIs respond. Chat/message/memory counts were preserved in all three existing profile databases (nine comparisons). Native window was responding. A subsequent forced-close restart command was blocked by automatic approval review without a specific reason. It was not executed; final restart acceptance remains pending. Full native visual and fresh-provider/two-PC acceptance remain pending as listed above.
