# Luminaria identity service

Deployed on the owner's personal Cloudflare account, separately from ACT resources.
Service: https://luminaria-identity.dessellesoftwaresolutions.workers.dev

GitHub is configured. Google and Discord flows are implemented and tested with mocked
provider responses; each needs its OAuth application and secrets (steps below). Desktop 0.2.4 includes the
pairing client, server session validation, protected Windows session storage and
separate account profiles. Real provider login and mandatory release sign-in
remain unverified/incomplete; development access remains available.

GitHub setup progress (2026-10-16): the Luminaria OAuth application was created
under xAaronEXE (application 3938631), using the exact callback below with no
wildcard redirects. Its client ID is provisioned to the personal Cloudflare
Worker. The owner completed verification and GITHUB_CLIENT_SECRET was transferred
directly to Wrangler stdin without a local secret file. Live health and the
installed desktop accounts endpoint both report GitHub configured=true.
The owner authorized GitHub. Desktop pairing completed with server-validated
identity and encrypted session storage. Restart recovery remains unverified.

## Provider registration

Register separate OAuth applications for Luminaria. Exact callback URLs:

- GitHub: `https://luminaria-identity.dessellesoftwaresolutions.workers.dev/callback/github`
- Google: `https://luminaria-identity.dessellesoftwaresolutions.workers.dev/callback/google`
- Discord: `https://luminaria-identity.dessellesoftwaresolutions.workers.dev/callback/discord`

### Google

1. Google Cloud console → create or pick a project → APIs & Services → OAuth consent
   screen (Google Auth Platform → Branding/Audience). User type External, app name
   Luminaria, support and developer email. Scopes: `openid` and `.../auth/userinfo.profile`
   only; these are non-sensitive, so no verification review is required.
2. Audience → Publish app (In production). While in Testing, only listed test users
   can sign in and sessions are refused for everyone else.
3. Clients → Create client → Web application. Authorized redirect URI: the exact
   Google callback above. No JavaScript origins are needed.
4. Copy the client ID and secret straight into `wrangler secret put` (below).

### Discord

1. Discord Developer Portal → New Application → name Luminaria.
2. OAuth2 → Redirects → add the exact Discord callback above and save.
3. Copy the Client ID; Reset Secret and copy the Client Secret into Wrangler.
   Only the `identify` scope is requested (username and ID, no email or servers).

### Storing secrets

```
npx wrangler secret put GOOGLE_CLIENT_ID
npx wrangler secret put GOOGLE_CLIENT_SECRET
npx wrangler secret put DISCORD_CLIENT_ID
npx wrangler secret put DISCORD_CLIENT_SECRET
npx wrangler deploy
```

`GET /health` then reports `configured:true` for each provider and the desktop
Accounts page enables its button. Cancelling or denying consent in the browser
shows a cancellation page and the desktop stops waiting immediately.

Store each provider's client ID and secret through Wrangler secrets, never in
source, desktop assets, chat messages or configuration checked into Git:
`GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`.
Provider registration, real sign-in, production consent setup and desktop
enforcement remain acceptance work. Do not enable mandatory sign-in
before those pass.

## Contract

- `GET /health`: configured provider flags; no credentials.
- `POST /device/start` JSON `{provider}`: one-time pairing ID, private device
  secret, browser verification URL, expiry and polling interval.
- Open the verification URL in the system browser. OAuth uses a single-use state
  bound to a Secure/HttpOnly browser cookie. GitHub and Google use S256 PKCE.
- `POST /device/poll` JSON `{device_id,device_secret}`: 202 pending; approved
  requests return one opaque seven-day bearer session exactly once.
- `GET /session` with bearer: server-side identity/expiry verification.
- `POST /logout` with bearer: immediate server-side session revocation.

Session and device secrets are hashed in D1. OAuth access tokens are used only to
retrieve provider identity and are not saved or returned to the desktop. Account
identity is keyed by provider and subject; matching names do not merge accounts.
No email, chat, file, audio, model or tool data is requested by this service.
Hourly cleanup removes expired flow/session/rate-limit records. Identities remain
until an account deletion feature is implemented. Rate limits are 600 requests
per hashed client IP per hour. Shared network users share that limit.

## Release channel

The desktop app checks for updates here, so the repository stays private and no
token is shipped to the desktop. `RELEASE_REPO` in `wrangler.jsonc` names the
repository. `GITHUB_RELEASES_TOKEN` is a fine-grained token scoped to that one
repository with Contents read-only access, stored only as a Wrangler secret:

```
npx wrangler secret put GITHUB_RELEASES_TOKEN
npx wrangler deploy
```

- `GET /releases/latest`: `{version, tag, name, notes, published_at, installer}`
  where `installer` is `{name, size, sha256, url}`. Returns 503 when the channel is
  not configured, 404 when no release exists, and 409 when the release lacks
  `Luminaria-X.Y.Z-Setup.exe` or a matching line in `SHA256SUMS.txt`.
- `GET /releases/download/vX.Y.Z/Luminaria-X.Y.Z-Setup.exe`: streams that asset.

The desktop app requires the installer URL to be this service's download route,
then verifies the size and SHA-256 before it launches the installer. Publish with
`build.ps1` and then `publish-release.ps1` from the project root.

## Validation and development

`npm ci` then `npm test` runs a local workerd/D1 identity-flow test with intercepted
provider responses; it never makes a real OAuth login or executes external code.
The test covers missing configuration/cookie, PKCE, replay rejection, wrong device
secret, single-use session claim, server validation, hashed storage, logout, and
expired pairing. It is not evidence of real provider login.

`wrangler types`, `wrangler deploy --dry-run`, and `wrangler deploy` validated the
initial deployment. Apply `schema.sql` with D1 execute only to the intended
Luminaria database. No ACT database or DNS configuration is involved.

Live smoke checks: health 200 with three false configuration flags; missing
session 401; GitHub device start 503. Secrets have not been provisioned.

Provider references: [GitHub OAuth](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps),
[Google OAuth](https://developers.google.com/identity/protocols/oauth2/web-server),
[Discord OAuth](https://docs.discord.com/developers/topics/oauth2).

## Remembered devices (desktop 0.2.16)

Sessions now record a device label (the PC name sent by the desktop app), when they
were created and when they were last used. A session stays valid for 30 days after
its last use and never longer than 90 days after sign-in. `GET /sessions` lists the
signed-in devices of the caller's account; `POST /sessions/revoke` signs out one
device (`{"id": "<16 hex>"}`) or every other device (`{"others": true}`). Devices of
other accounts can never be listed or revoked.

The deployed database predates these columns. Apply the migration once, then deploy:

```
npx wrangler d1 execute luminaria-identity --remote --file migrations/0002_device_sessions.sql
npx wrangler deploy
```

Until this is deployed, desktop 0.2.16 shows "Device management needs the updated
sign-in service" and sign-in keeps working as before. Existing sessions keep working
after the migration and become 30-day sessions on their next use.

## Insights sync (desktop 0.2.17)

Opt-in only. A desktop that turns on insights sync sends one row per day for itself:
`POST /insights/days` with `{"device": "<32 hex>", "days": [{"day": "YYYY-MM-DD", "metrics": {...}}]}`,
up to 90 days per request. Only these whole-number counters are accepted:
`tokens_in`, `tokens_out`, `tokens_cached`, `generations`, `runs`, `active_seconds`,
`wait_seconds`, `tool_ok`, `tool_failed`, `reasoning_generations`, `skills_invoked`.
Anything else (text, model or tool names) is rejected. The key is
(account, device, day), and a new upload replaces the old row, so a retried upload never
double-counts. `GET /insights/days` returns per-day sums across the account's devices.
`POST /insights/delete` removes the account's rows (or one device's with `{"device": ...}`).
The scheduled job drops days older than two years. At most 20 devices per account.

Apply the migration once, then deploy:

```
npx wrangler d1 execute luminaria-identity --remote --file migrations/0003_insight_days.sql
npx wrangler deploy
```
