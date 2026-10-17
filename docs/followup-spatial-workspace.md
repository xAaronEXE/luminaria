# Follow-up: spatial workspace and appearance

Branch: `cursor/neural-workspace-11de` · Pull request #5 · Version on the branch: 0.2.8
(not for publishing yet)

## Where things stand

| Part | Status | Verified how |
|---|---|---|
| Appearance: black and white, light / dark / follow system, custom colors | Done | Browser preview with stand-in data, settings tests. **Not yet in the desktop app.** |
| Work record for each task (backend events) | Done | Engine tests with a simulated model. **Not yet in the desktop app.** |
| Optional plan tool for the model | Done | Tests only. Whether local models use it well is unknown. |
| Screen-side store for work events | Not started | — |
| New 3D entity and neural lattice | Not started | Current animation is the older brain-to-torus shape, now in your colors. |
| Clicking a step to inspect it, link to Activity panel, simple non-3D view | Not started | — |
| Typing while a task runs (messages queue) | Not started | Voice interruption already stops a run. |
| 0.2.8 release and Windows acceptance | Not started | — |

## Your to-do list

1. If 0.2.7 is not published yet, finish that first from `main` (see the 0.2.7 block
   at the end).
2. Build and install this branch locally to try the new appearance. Do **not** run
   `publish-release.ps1` on this branch yet.
3. Run the appearance checks below and note anything that looks wrong.
4. Tell the agent to continue with the remaining work, starting with the
   screen-side store for work events.

## Step 2 — build this branch on your PC (one block)

Paste into PowerShell. It saves any local edits, switches to the branch, builds and
opens the installer. Nothing is published.

```powershell
Set-Location C:\Users\desse\Desktop\Luminaria
git stash push -u -m "before neural-workspace test"
git fetch origin cursor/neural-workspace-11de
git checkout cursor/neural-workspace-11de
git pull origin cursor/neural-workspace-11de
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\build.ps1
Start-Process ".\release\Luminaria-0.2.8-Setup.exe"
```

To go back to `main` afterwards:

```powershell
Set-Location C:\Users\desse\Desktop\Luminaria
git checkout main
git pull origin main
```

## Step 3 — appearance checks

Write down anything that does not match, with what you saw.

1. Open the app. If you never chose dark mode before, it is white with black text.
   If you had chosen dark mode, it is black with white text.
2. Open **Settings & updates → Appearance**.
3. Click **Dark**. The whole app turns black with white text right away, and
   **Saved** appears next to the reset buttons.
4. Click **Follow system**. Change Windows between light and dark
   (Settings → Personalization → Colors). Luminaria follows within a second or two.
5. Tick **Accent color in both modes** and pick a color. The send button, focus
   outlines and selected items take that color.
6. Tick **Different accent in dark mode**, pick another color. Switch between Light and
   Dark: each mode shows its own accent.
7. Open **All dark mode colors**. Change **Secondary text** to a very dark gray. A
   **Low contrast** warning appears. Click **Reset** on that row; the warning goes.
8. Close and reopen the app. Your choices are still there and there is no flash of
   white or black before they appear.
9. Click **Reset dark mode**: only dark mode's colors and accent return to default.
10. Click **Reset all appearance**, confirm. Everything returns to black and white in
    light mode.
11. Check that menus, approvals, error messages, code blocks and the Models page are
    readable in both modes.

## Remaining engineering work (for the next session)

1. **Screen-side work store** (`web/work-graph.js`): listen for `work` events from the
   event stream, drop duplicates by `id`, order by `seq`, rebuild from
   `GET /api/chats/ID/work` on reconnect and chat switch, ignore events for other
   chats, keep older runs as collapsed clusters.
2. **Renderer rewrite** (`web/core.js`): entity (particle organism, deforming mesh,
   toroidal energy, internal circulation) with states idle, listening, generating,
   speaking, interrupted, waiting for approval, error, complete. Neural lattice with
   seven regions (planning, memory, retrieval, files, tools, generation,
   verification), curved pathways, directional pulses, nodes only for real events,
   entity travelling to the active node, failures linked to later attempts.
   Adaptive quality, bounded counts, buffer reuse, reduced motion, pause,
   context-loss fallback. Colors from the `studio-appearance` event.
3. **Inspection**: click or keyboard-select a node to see its tool call, result,
   approval, error, plan step or compaction; jump between the node and the Activity
   panel in both directions; controls for follow current activity, task overview,
   focus selection, return to conversation, pause motion; a simple non-3D list view.
4. **Typing during a run**: keep the message box enabled, queue the message, send it
   when the run ends, allow cancelling the queued message.
5. **Voice mode**: reduce how much the chat fades (currently strong blur) so Stop,
   approvals and errors stay readable.
6. **Release**: finish 0.2.8 notes and a `docs/testing-0.2.8.md`, then build, install
   and publish.

## Known limitations

- The saved look is cached per PC, not per profile, for the instant start. Switching
  profiles can show the previous profile's colors for a moment before the right ones
  load.
- The old custom palette from earlier versions (unused since 0.2.7) is kept in your
  settings but not applied.
- Voice states are shown on screen only; they are not saved in the work record.

## 0.2.7 publish (from main), if still pending

```powershell
Set-Location C:\Users\desse\Desktop\Luminaria
git stash push -u -m "before 0.2.7 build"
git checkout main
git pull origin main
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\build.ps1
.\publish-release.ps1
```

Then in the installed app: **Settings & updates → Updates → Check again → Install
0.2.7**, and run `docs/testing-0.2.7.md` and `docs/testing-0.2.6.md`.
