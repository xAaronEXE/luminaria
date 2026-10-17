# Luminaria 0.2.8 Windows acceptance — Aaron

Candidate only. Do not publish until these checks are accepted. Preserve your data.

1. Build with build.ps1 and install release/Luminaria-0.2.8-Setup.exe. Confirm version
   0.2.8. Existing chats, model files and sign-in settings remain. Do not enable sign-in
   requirements for this test.
2. In Appearance, try Light, Dark, Follow system and a custom accent. Open Models,
   tools, approvals and Task overview; text and controls remain readable. Restart:
   saved choices return. Record any profile-switch colour flash (known limitation).
3. Start a small real local task that reads a file and runs a harmless code check.
   Open Task overview. Only recorded steps appear. The entity follows active work;
   planned steps say model-provided. No hidden thoughts or confidence are invented.
4. Select nodes with mouse, then arrow keys and Enter. Inspect real arguments/results,
   errors, model output and compaction references where present. Focus selection,
   return with Escape and confirm the composer/Stop remain usable.
5. Choose Show in Activity, then Show in workspace. Both select the corresponding
   tool evidence. At narrow window sizes, evidence replaces the outline and Back to
   activity outline returns without obscuring selected controls.
6. During a task, type and submit another message. It shows Queued. Cancel one queued
   message; it never runs. Let another dispatch after the first task completes. Switch
   chats and verify messages never cross chats. Close with unsent items to check warning.
7. Cause a harmless tool failure followed by another attempt. Inspect the failure and
   follow-up relationship. Stop a run; its active branch stops and stays inspectable.
8. Switch chats, return and reopen the app. Recorded work recovers; no duplicate nodes
   or events from another chat appear. Earlier runs collapse and can be expanded.
9. Start voice and allow microphone access yourself if asked. Speak a task with tools.
   Confirm microphone/output reactivity and entity travel while it works. Speak again
   during speech/generation: old work/audio stop, the new spoken turn takes priority
   over queued text and no stale speech returns. Check approvals remain readable.
10. Pause motion, then try Windows reduced motion. Work evidence remains usable with
    reduced spatial motion. Repeat voice/work transitions and watch for audio/graphics
    leaks. Use --safe-graphics to verify the outline when 3D is unavailable.
11. Let a representative task run for several minutes. Note actual diagnostics and any
    freezes, heat or responsiveness problems; do not substitute browser fixture FPS.
12. Report pass/fail per step, screenshots and observed errors. Only after acceptance
    should the do-not-publish marker be removed and publication considered.

## Build candidate only

```powershell
Set-Location C:\Users\desse\Desktop\Luminaria
.\build.ps1
if ($LASTEXITCODE) { throw 'Build failed' }
Start-Process .\release\Luminaria-0.2.8-Setup.exe
```

Publishing and update commands are withheld until acceptance. The build is not claimed signed.
