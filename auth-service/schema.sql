CREATE TABLE IF NOT EXISTS identities (
 id TEXT PRIMARY KEY, provider TEXT NOT NULL, subject TEXT NOT NULL,
 name TEXT NOT NULL, created INTEGER NOT NULL, UNIQUE(provider,subject)
);
CREATE TABLE IF NOT EXISTS devices (
 id TEXT PRIMARY KEY, secret_hash TEXT NOT NULL, provider TEXT NOT NULL,
 expires INTEGER NOT NULL, identity_id TEXT
);
CREATE TABLE IF NOT EXISTS oauth_states (
 state_hash TEXT PRIMARY KEY, cookie_hash TEXT NOT NULL, device_id TEXT NOT NULL,
 provider TEXT NOT NULL, verifier TEXT NOT NULL, expires INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, identity_id TEXT NOT NULL, expires INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS rate_limits (
 key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL
);
