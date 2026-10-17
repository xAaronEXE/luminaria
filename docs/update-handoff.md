# Windows installer handoff

The 0.2.8 download was complete and checksum-valid, but Setup reported DeleteFile
code 5 for LocalAIStudio.exe and then _internal/runtime/llama-swap.exe. Those
processes still held files open. Stopping the app and its recorded model manager
released both locks; the installed VERSION subsequently read 0.2.8.

## Fix for the next build

After verification, the packaged app starts a separate Windows PowerShell handoff
outside the files Setup replaces. The API sends its response, then requests a
normal desktop shutdown. Normal shutdown closes the backend and owned runtime.
The helper waits up to 30 seconds for the original app; if it remains, it force-stops
that exact PID. It stops the originally owned llama-swap tree if still present,
checks that the known processes exited, rechecks the installer checksum, then opens
Setup with a local log. A failed handoff records handoff.log instead of opening Setup.

PID, expected process name and process start time bound fallback termination to
the captured processes. An already-running external model manager is not targeted.
The installer also checks Local\LuminariaDesktop, held until full process exit,
so future installers prompt before replacing files while the app remains alive.
Active agent tasks block the install endpoint. This does not bypass OS permissions.

The source fix is not retroactively included in the published 0.2.8 binary. It
requires a new version/build; do not silently replace that release's installer.

## Verification

- Nine updater tests passed, including corrupt/mismatched packages, packaged helper
  arguments and refusing to target an unowned model manager.
- Python compile and PowerShell parser checks passed.
- A direct Windows test used two disposable PowerShell processes and a fake payload.
  The helper waited for the test parent to exit, stopped the owned test manager,
  checked the payload hash and reached a mocked installer launch only afterward.
  No real installer was executed by that test.
- Real packaged automatic close/force fallback, failure logs and install/restart
  remain acceptance checks for the next build. The current recovery is not evidence
  that the new handoff has shipped or passed those checks.

Implementation follows Inno Setup's AppMutex guidance:
https://jrsoftware.org/ishelp/topic_setup_appmutex.htm
