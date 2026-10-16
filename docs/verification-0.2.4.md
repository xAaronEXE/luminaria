# Luminaria 0.2.4 — desktop identity client

This release wires the Accounts UI to the hosted identity service. It is not
evidence that Google, GitHub or Discord registrations or real logins are complete.
Development access remains enabled; mandatory release sign-in is still pending.

## Behavior

- Accounts shows Google, GitHub and Discord readiness from the live service.
  Missing provider registrations disable sign-in with “Publisher setup pending”.
- Configured providers can start a ten-minute pairing request and open its
  validated verification link in the browser. The UI polls for completion while
  the screen remains open and supports cancellation.
- Device secrets remain in backend memory. Issued bearer sessions are validated
  with the identity server before being saved. Neither secret is returned to the
  frontend, localStorage or the local API response.
- Session files use Windows current-user DPAPI protection, without a plaintext
  fallback. Files remain inside each account profile's app-data folder.
- A verified server identity maps to its own local profile. Existing local chats
  are not moved or uploaded. The selected account profile takes effect at restart.
  Reusing an identity reuses its profile; different providers are not merged by name.
- Sign-out revokes the server session before removing the local encrypted file.
  Network failure does not falsely report revocation or discard the saved session.
- Identity login does not authorize Gmail, Drive, GitHub repository or other tools.

## Automated checks

Twenty-two Python tests pass, including a real Windows DPAPI encryption/decryption
round-trip and rejection of a corrupt encrypted file. Mock-HTTP identity tests
cover redacted frontend results, server validation, profile reuse/isolation,
revoked sessions, provider mismatch, cancellation, unknown/expired pairing and
unconfigured publisher credentials, foreign redirect rejection and offline
sign-out retention. A cancellation-during-validation test confirms no profile is
selected and the issued session is revoked. Existing persistence, compaction, permission,
connector and updater tests also pass. Renderer lifecycle checks pass unchanged.

Mock-provider tests are not real OAuth login evidence. No provider client secret
has been provisioned and no existing user account/profile was changed by the tests.

## Native installation evidence

- Installer completed with exit 0; installed API reports 0.2.4. The Windows
  win32crypt extension is included in the packaged app. Accounts asset hashes
  matched source at installation.
- Live /accounts returned all three providers unconfigured and signed_in=false.
  A request without the local UI token returned 403. An authenticated request
  to start GitHub pairing returned the explicit publisher-setup error, not a
  fabricated sign-in success. Results: ignored data/identity-0.2.4-live.json.
- Native Accounts inspection showed Google/GitHub/Discord disabled with
  “Publisher setup pending”, the existing Personal profile, and local-profile
  controls. A final frontend fix adds status-loading copy and prevents a late
  Accounts response overwriting a different settings category.
  The frontend fix was repackaged and installed with exit 0; the final installed
  Accounts asset hash matches source, and the reopened desktop shows 63 tools.
- GitHub registration is prepared in the personal xAaronEXE browser account with
  the exact hosted callback and wildcard redirects disabled. Registration and
  client-secret creation await the requested action-time confirmation. Nothing
  was submitted and no provider secret was created during this pass.

## Remaining release blockers

Register provider OAuth applications using the callback URLs in
auth-service/README.md and provision secrets to the personal Cloudflare service.
Then test real browser consent, cancellation/denial, restart/session recovery,
revocation and offline behavior in the packaged app. Only then enable and test
mandatory sign-in enforcement. Service integrations require their own credentials.
The remaining UI/voice, quality benchmark, distribution/signing and deferred model
scope in earlier verification reports is not marked complete by this release.

Reference: [Microsoft DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata).
DPAPI is a Windows-user protection boundary; local app profiles are not separate
Windows security identities.
