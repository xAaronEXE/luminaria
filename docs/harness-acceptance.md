# Luminaria 0.3.0 and 0.4.0 acceptance tasks

Run each task against fresh copies of the same input, using the same Windows machine,
model, model settings, and permission mode. Save the run report, elapsed time, and
any approval or recovery events. Judge each run with the rule below. Record a
failure when a required outcome cannot be verified.

| Task | Input and request | Pass rule |
| --- | --- | --- |
| 1. Build a Python tool | Empty folder. Build a command that counts words in a UTF-8 text file and reports missing files. | Independent cases cover empty input, Unicode, and a missing file. All pass. |
| 2. Fix an existing bug | A tiny project whose invoice total rounds each line instead of the final sum. Include a failing regression test. | Regression and existing tests pass. Only relevant files change. |
| 3. Research with sources | Provide two source URLs and ask for three facts supported by them. | Every fact is supported by a retrieved source, and every citation resolves to a page the app read. |
| 4. Build and inspect a page | Empty folder. Build a responsive event page and inspect the desktop and narrow layouts. | Required content is present at both widths, and visual inspection finds no horizontal overflow. |
| 5. Run a saved plan | Save a plan to implement, test, and document a CSV converter. Start it with “go ahead.” | Steps run in order, the output matches an independent fixture, and the report reflects each check. |
| 6. Catch stale evidence | Ask for a test run and a follow-up source edit in the same plan step. | The final verdict requires a fresh test after the edit. |
| 7. Resume after a restart | Start a two-step plan with a completed first step and a second step waiting for approval. Close and reopen the app. | Resume preserves the completed step, restores approval, and runs each approved effect once. |
| 8. Refuse and recover | Deny a requested edit during a saved plan. | The target stays unchanged, dependent work stops, and the report gives the reason. |
| 9. Undo with a conflict | Have the plan modify two files, then edit one of them manually before Undo. | Undo restores the other file and reports the conflict without overwriting the manual edit. |
| 10. Cancel a Windows command | Run a benign command that starts a long-lived child process, then cancel it. | The command and child both stop, and the action journal reports the interruption. |

The scripted plan cases in `tests/plan_runner.py` replay turns without a live model.
`tests/plan_evidence.py` checks evidence and journal decisions with synthetic records.
The acceptance runs above also exercise the UI, Windows process behavior, and a real model.

For a new release, keep the comparison JSON with the build. Its `installer_sha256`
map must identify the exact baseline and candidate installers by version. Its
`cases` map must contain cases 01–10 and record a `PASS` or `FAIL` for both versions
in each case. Cases 06–10 must pass on the candidate individually. Keep the
run trace and independently checked outcome for each case, including failed trials.
Verify the candidate before publishing:

```powershell
./scripts/verify-release-comparison.ps1 -Report comparison.json -BaselineInstaller baseline.exe -CandidateInstaller release/Luminaria-0.4.0-Setup.exe
```

After pushing the release commit, use `scripts/publish-release.ps1` with the GitHub
repository, report, and baseline installer. It runs the same check before uploading
the candidate. A rebuild needs a comparison report for the new installer hash.
