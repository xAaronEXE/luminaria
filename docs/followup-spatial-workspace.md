# Follow-up: spatial workspace and appearance

Version: 0.2.8 candidate. PR #7 consolidates the implementation and PR #6's
follow-up documentation. Do not publish until Aaron accepts the packaged app.

## Where things stand

Appearance, structured backend work events and the model-provided plan tool are
implemented. The scene store, entity/lattice renderer, evidence inspection,
Activity links, accessible outline and queued typing are implemented in this
candidate. Automated tests and browser fixtures verify the boundaries described
in [verification-0.2.8.md](verification-0.2.8.md); they do not establish native
desktop acceptance or how well each local model uses the plan tool.

The local candidate installer has been built and its checksum verified. Native
WebView2 rendering, real model/tool workflows, microphone/speaker interruption,
installation/update behavior and sustained performance still require Aaron's
acceptance. See [testing-0.2.8.md](testing-0.2.8.md) for the full numbered checklist.

## Build and install locally, without publishing

This block stops if local tracked or untracked edits exist, switches to the combined
branch and builds a candidate. It does not stash edits or publish a release.

```powershell
$ErrorActionPreference = 'Stop'
Set-Location C:\Users\desse\Desktop\Luminaria
if (git status --porcelain) { throw 'Save or commit your local edits before switching branches.' }
git fetch origin
if ($LASTEXITCODE) { throw 'Fetch failed' }
git switch codex/spatial-workspace
if ($LASTEXITCODE) { throw 'Branch switch failed' }
git pull --ff-only origin codex/spatial-workspace
if ($LASTEXITCODE) { throw 'Pull failed' }
if ((Get-Content VERSION -Raw).Trim() -ne '0.2.8') { throw 'Expected the 0.2.8 candidate' }
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\build.ps1
Start-Process .\release\Luminaria-0.2.8-Setup.exe
```

To return to main after saving any edits:

```powershell
$ErrorActionPreference = 'Stop'
Set-Location C:\Users\desse\Desktop\Luminaria
if (git status --porcelain) { throw 'Save or commit your local edits first.' }
git switch main
if ($LASTEXITCODE) { throw 'Branch switch failed' }
git pull --ff-only origin main
if ($LASTEXITCODE) { throw 'Pull failed' }
```

## Detailed appearance acceptance

Record pass/fail and what you observed. These are checks to perform, not claims of
packaged behavior already verified.

1. With no saved explicit theme choice, confirm white background and black text.
   A previously saved dark choice should remain dark.
2. Open Settings & updates > Appearance. Choose Dark; check the whole interface
   changes and the save status becomes Saved.
3. Choose Follow system. Change Windows Personalization > Colors between light
   and dark and confirm the app follows.
4. Enable Accent color in both modes and choose a color. Check Send, focus,
   selected items and progress. Set a different dark-mode accent and confirm
   Light and Dark use their respective choices.
5. Expand All dark mode colors. Make Secondary text low contrast; confirm a
   warning appears. Reset that row and confirm the warning clears.
6. Close and reopen the app; verify saved appearance and observe any first-paint
   flash. The per-PC cache limitation below still applies to profile switching.
7. Reset dark mode; verify only that mode's overrides reset. Then confirm Reset
   all appearance restores the default light monochrome configuration.
8. Check menus, approvals, errors, code blocks, Models and the spatial workspace
   remain readable in both modes and with an accent. Try the per-mode spatial
   colors as well as UI colors.

## Remaining work and limitations

- Run the full Windows acceptance checklist, fix observed failures and repeat
  affected checks before release. Do not mark it accepted from fixture screenshots.
- Startup appearance is cached per PC/browser, not per profile. Switching profiles
  can briefly show the previous profile's colors before preferences hydrate.
- Legacy custom palette values remain in settings but are not applied.
- Voice state is client-side and is not persisted in the execution record.
- Queued text is per-chat and memory-only, bounded to ten unsent messages. Closing
  with unsent messages warns; it does not persist them across app restarts.
- Plans/reasoning are model-provided; tool events are execution evidence. Unknown
  dependencies, internal activations and hidden thoughts are not fabricated.

## Release handling

PR #6's earlier 0.2.7 publishing instructions were conditional, not evidence that
0.2.7 was published or accepted. Check the live release and acceptance state before
any older-version release work. Never run publish-release.ps1 on a branch whose
VERSION differs from the release you intend to publish.

For 0.2.8, keep the do-not-publish marker until Aaron's acceptance passes. Merge,
tagging, release publication and update acceptance remain separate steps; combining
these PRs does not perform them.
