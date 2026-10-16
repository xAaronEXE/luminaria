# Luminaria identity service

Deployed on the owner's personal Cloudflare account, separately from ACT resources.
Service: https://luminaria-identity.johnnycox4431836.workers.dev

GitHub is configured; Google and Discord remain unconfigured. Desktop 0.2.4 includes the
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

- GitHub: `https://luminaria-identity.johnnycox4431836.workers.dev/callback/github`
- Google: `https://luminaria-identity.johnnycox4431836.workers.dev/callback/google`
- Discord: `https://luminaria-identity.johnnycox4431836.workers.dev/callback/discord`

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
