# 0.2.17 packaged-desktop acceptance

Status: **Not run**. Source/browser tests do not constitute desktop acceptance.
Run this checklist in the installed Windows application, not the local browser preview.
Keep required sign-in off. Do not publish a new release until the applicable checks pass.

## Record once

- Tester/date:
- Installed version and installer provenance:
- Windows version:
- Local model, quantization, runtime/version, configured context:
- PC A / PC B (use non-sensitive labels):
- Overall result / unresolved failures:

For each numbered check record **Pass / Fail / Blocked**, actual behavior, duration
where relevant, and evidence (screenshot or redacted local log). Never paste tokens,
private chats, or credentials. A blocked prerequisite is not a failed feature test.

## Prerequisites

- Preserve local data before update/migration testing; use disposable test chats and files.
- Existing installed models only; do not download weights for this checklist.
- Update check needs an actual eligible release and a 0.2.14 installation. If unavailable,
  mark blocked; do not downgrade the working installation or call a preview an update test.
- Account checks require the identity Worker plus D1 migrations 0002 and 0003.
  Verify deployed versions with the owner before testing; this checklist deploys nothing.
- Two PCs and provider sign-in are user-operated prerequisites. Do not automate login
  or microphone permission dialogs. Do not enable mandatory sign-in during acceptance.
- Offline grace is currently seven days in source; confirm behavior without changing
  the system clock or editing live credentials. Expiry testing needs an isolated fixture
  or naturally expired test device and must be labeled accordingly.

## Checks

### 1. Upgrade and launch notice
Update from 0.2.14 using the normal user-run installer. Confirm history/preferences remain.
Launch: newer-release notice appears once for that release; View opens Settings → Updates.
Relaunch and confirm no duplicate notice. No automatic download or installation occurs.

Result / evidence:

### 2. Checkpoint, failure stop, and recovery
In a disposable task, exercise enough distinct read steps to reach the 18-round budget.
Confirm a readable chat checkpoint with findings, completed actions, failures, remaining
work, and Continue task. Continue explicitly; verify completed writes are not repeated.
Exercise three identical missing-file failures and confirm early stop with an explanation.
Check that command/integration effects are not described as "no changes" without evidence.
When an interrupted action's outcome is uncertain, inspect it before approving a retry.
If the real model cannot reliably produce a case, mark it blocked; scripted tests are
separate evidence. Do not force a production failure or modify personal files.

Result / evidence:

### 3. Real-site retrieval
Choose public, non-sensitive examples of an article, text PDF, JavaScript-only page,
blocked page, and known 404. Record URL, category, elapsed time, usable text/source
reference, and fallback behavior for each. HTTP 200 alone is not a pass.
Blocked access must remain blocked; missing browser support must be explained.

Results (five cases):

### 4. Navigation, appearance, and controls
Check Memory → Tools → Integrations → Skills → Automations → Model library →
Archive & trash → account/settings. Confirm separate Tools/Integrations panels.
Exercise Memory & context controls with mouse and keyboard: values, bounds, presets,
save feedback, and reload/restart guidance. Test light/dark modes, semantic accents,
customization persistence, motion settings, and reduced-motion behavior.
Preserve the current visual layout and spatial appearance.

Result / evidence:

### 5. Orchestration boundaries
Compare the eligibility list with actually installed models. Exercise standard-only,
abliterated-only, both, and an explicit allowlist where installed models permit.
Confirm reasons for exclusions, image/context requirements, and no-eligible fallback.
No download or route outside the selected pool; router choice is separate from that pool.

Result / evidence:

### 6. Account and devices
Sign in separately with Google, GitHub, and Discord using provider dialogs yourself.
Check explicit provider linking; matching emails must not silently merge identities.
Restart and confirm remembered device. From PC A revoke PC B; confirm B becomes signed
out on its next online validation. Test offline grace and the explanatory offline state;
label any expiry fixture separately. Check each local-profile association/separate choice:
no history merging or data movement, and no integration permissions granted by login.

Result / evidence:

### 7. Insights and aggregate sync
Make a few real chats/tool calls. Check coverage start, token counts where supplied,
model/tool/skill usage and failures. Unmeasured values must say unavailable.
Inspect lifetime totals, explicitly labeled peak period, longest task active/wait time,
streak qualification/timezone, token history, requested reasoning, and speed measurements.
Change account timezone and verify day/streak behavior. Export and inspect locally.
In a disposable profile/account test deletion and explain local versus synced scope.
Opt into sync on two PCs; record before/after totals and retry sync to prove no duplicates.
Only aggregate daily data may leave the PC. No raw chats, files, or tool results.

Result / evidence:

### 8. Working brief and real compaction retention
Add, pin, edit, and remove entries; request an assistant proposal. Only you can add a
permission. Use a disposable exact path, a corrected fact, a denial, and pending work.
Continue a long real local-model chat through two compactions. Ask for those details
after each; verify against originals, not just the latest summary. All originals remain.

Result / evidence:

### 9. Compaction history and failure visibility
Open Memory & context → Compaction on this PC. Match real run times and counts to your
test. Inspect duration, context before/after, summary size, and validation failures when
available. If a failure occurs, verify the last good summary and full history survive.
Do not damage a personal profile to manufacture a failure; mark unavailable cases blocked.

Result / evidence:

## Acceptance gate

Return this checklist with failures and blocked prerequisites. Only confirmed cases may
move to **Desktop verified** in the roadmap. Do not advance the whole table together.
Next releases remain 0.2.18 hardening/polish, 0.2.19 measured tuning, 0.2.20 file-first
autonomy, each with its own release/branch/PR and only one open PR at a time.
