# Shared workers.dev subdomain migration

User-selected target: `dessellesoftwaresolutions.workers.dev`.
Personal account: `f891e584a6097b5480b2ccc6702631c7`.
Current verified subdomain: `johnnycox4431836`.

The documented PUT account-subdomain API rejected the attempted change with HTTP 409, Cloudflare code 10036: "Account already has an associated subdomain." No successful rename is claimed. Cloudflare documents changing an existing subdomain in Workers & Pages → Your subdomain → Change. The dashboard was opened and the user was asked to complete that step. No name availability claim has been made.

Affected workers: `luminaria-identity`, `gym-coach`, `orbit-license`. A metadata-only pre-change snapshot is saved in `archive/worker-subdomain-2026-10-21/before.json`. No provider credentials were printed or saved by this migration attempt.

## Required callback changes after the rename

- Google authorized redirect URI: `https://luminaria-identity.dessellesoftwaresolutions.workers.dev/callback/google`
- GitHub OAuth application 3938631 callback: `https://luminaria-identity.dessellesoftwaresolutions.workers.dev/callback/github`
- Discord OAuth redirect: `https://luminaria-identity.dessellesoftwaresolutions.workers.dev/callback/discord`

The Worker builds redirect URIs from the incoming request origin, so its new hostname must be registered with each provider. Do not claim successful OAuth acceptance from `/health` alone. Other clients of gym-coach and orbit-license need their own endpoint inventory and verification; they are not automatically repaired by changing the account label.

Desktop `backend/identity.py` still uses the old origin until the dashboard change is confirmed and callbacks are ready. The installed desktop remains 0.2.26. A local 0.2.27 candidate contains in-progress sign-in routing, browser opening and onboarding work; it has not been installed or published. Additional source guards were added after that candidate build, so it must be rebuilt before delivery.

## Account-flow investigation

The real Google session authenticated, while the selected legacy workspace was bound to Discord and Google was not linked to that account. Workspace rejection was observed directly. In-progress fixes route first-use sign-ins into account-owned containers, keep legacy history separate, allow linked providers only from server-verified membership, and distinguish fresh sign-in from explicit provider linking. A controlled desktop restart opens the selected container. A three-step onboarding configures workspace name, appearance and the working folder. These are implemented in source but not yet native-accepted.

Current isolated checks: identity 21, sign-in gate 11, onboarding 2, devices 15, account-cache isolation 1 passed (50 total). Identity tests exercise first-use routing for all three providers with mocked provider responses. Both identity-service suites also passed with mocked provider/release responses. Fresh Google/GitHub/Discord sign-in and native onboarding acceptance remain pending.
