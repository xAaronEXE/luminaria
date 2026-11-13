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

## Follow-up candidate

The follow-up candidate uses shorter Agent instructions with explicit workspace path and source guidance. It was built from `43cb48d577282e971f1f68dec7ec0b785371573e`. Its installer SHA-256 is `e6c6de07f0c4148463b04428b9522ed58d2bad48a62ddd0acbb08f748e7f2185`.

- [Installer and checksum](https://github.com/xAaronEXE/luminaria/actions/runs/43373393809/artifacts/14013477550)
- [0.5B benchmark](https://github.com/xAaronEXE/luminaria/actions/runs/43373450259/artifacts/14014094383)
- [1.5B benchmark](https://github.com/xAaronEXE/luminaria/actions/runs/43373450259/artifacts/14015460421)
- [Windows baseline and candidate regression comparison](https://github.com/xAaronEXE/luminaria/actions/runs/43375200447)

The Windows upgrade passed. The follow-up benchmark verified 4 of 14 Agent cases and 3 of 14 Classic cases. Direct verified 4 of 4 applicable cases. Agent's context recall improvement reproduced on 0.5B. Its previous approval-write pass did not reproduce. The multi-file, long-run, and research cases remained unresolved. The focused suite attempted 78 checks with one skip and no failures. Windows regression reruns found four failing modules in both the v0.4.4 baseline and the candidate: document attachments, persistence and compaction, peer sharing, and command isolation. Publication remains pending the required release verification.
