# Luminaria 0.4.5 model-led verification

The tested Windows installer was built from `a097b4cdfd2aafc013c5125e3c1f74017dd9eedf`. Its SHA-256 is `730620f2fa79ac91e25f65250163ba89442214efca99b4d0a4a9e09d40027925`.

- [Installer and SHA-256](https://github.com/xAaronEXE/luminaria/actions/runs/43361961704/artifacts/14009525274)
- [Windows 0.4.4 upgrade and all three live chat modes](https://github.com/xAaronEXE/luminaria/actions/runs/43362257136)
- [Qwen2.5 0.5B Q4_K_M corrected workload report](https://github.com/xAaronEXE/luminaria/actions/runs/43366575102/artifacts/14010868418)
- [Qwen2.5 1.5B Q4_K_M corrected workload report](https://github.com/xAaronEXE/luminaria/actions/runs/43368853852/artifacts/14012049917)

The 1.5B run seeded an upgrade transcript because its 0.4.4 smoke prompt timed out on two prior runners. The candidate then ran Classic, Agent, and Direct on the same installed build. Both model configurations used local llama.cpp in Review mode.

| Workload | 0.5B Classic | 0.5B Agent | 0.5B Direct | 1.5B Classic | 1.5B Agent | 1.5B Direct |
| --- | --- | --- | --- | --- | --- | --- |
| Simple chat | Pass | Pass | Pass | Pass | Pass | Pass |
| Multi-file fix | Fail | Fail | — | Fail | Fail | — |
| Approval-gated write | Fail | Pass | — | Fail | Fail | — |
| Twenty sequential reads | Fail | Fail | — | Fail | Fail | — |
| Research with retrieved sources | Fail | Fail | — | Unverified | Fail | — |
| Restart and recover approval | Pass | Pass | — | Fail | Fail | — |
| Context pressure | Fail | Pass | Pass | Unverified | Unverified | Pass |

Agent verified 5 of 14 cases across both models and Classic verified 3 of 14. The 1.5B Classic run reached the previous cap after 18 reads. Agent ended after two reads on that model, so the live workload did not demonstrate continuation past the cap. A deterministic replay verifies 20 productive rounds in the new loop. The 1.5B approval failures included model-selected absolute paths outside the fixture workspace. The benchmark denied those actions.

The Windows upgrade preserved chat history, settings, the model registry, workspace files, and a saved plan. The focused regression suite passed 60 checks. The broader Linux run attempted 563 checks with 17 skips and 10 errors in Windows identity checks requiring `win32crypt`.

Release status is pending. The paired run showed improvements on the 0.5B configuration, with unresolved workloads and unverified cases on 1.5B. Live paired-PC and remote-provider verification remains unavailable in this environment. The repository's release verifier also requires a comparison with all ten existing acceptance cases and passing critical cases 06–10. The workload report above does not satisfy that verifier. Classic remains the default and 0.4.5 is unpublished.
