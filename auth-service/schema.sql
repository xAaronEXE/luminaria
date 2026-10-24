CREATE TABLE IF NOT EXISTS identities (
 id TEXT PRIMARY KEY, provider TEXT NOT NULL, subject TEXT NOT NULL,
 name TEXT NOT NULL, created INTEGER NOT NULL, handle TEXT, UNIQUE(provider,subject)
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
 token_hash TEXT PRIMARY KEY, identity_id TEXT NOT NULL, expires INTEGER NOT NULL,
 created INTEGER, last_seen INTEGER, label TEXT
);
CREATE TABLE IF NOT EXISTS rate_limits (
 key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS account_members (
 identity_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, provider TEXT NOT NULL,
 UNIQUE(account_id,provider)
);
CREATE TABLE IF NOT EXISTS device_links (
 device_id TEXT PRIMARY KEY, session_hash TEXT NOT NULL, expires INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS insight_days (
 account_id TEXT NOT NULL, device TEXT NOT NULL, day TEXT NOT NULL,
 metrics TEXT NOT NULL, updated INTEGER NOT NULL,
 PRIMARY KEY(account_id,device,day)
);

CREATE TABLE IF NOT EXISTS sync_records(account_id TEXT NOT NULL,kind TEXT NOT NULL,id TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 0,data TEXT NOT NULL DEFAULT '{}',deleted INTEGER NOT NULL DEFAULT 0,mutation TEXT,updated INTEGER NOT NULL,PRIMARY KEY(account_id,kind,id));
CREATE TABLE IF NOT EXISTS sync_receipts(account_id TEXT NOT NULL,mutation TEXT NOT NULL,fingerprint TEXT NOT NULL,response TEXT NOT NULL,created INTEGER NOT NULL,PRIMARY KEY(account_id,mutation));
CREATE TABLE IF NOT EXISTS sync_blobs(account_id TEXT NOT NULL,hash TEXT NOT NULL,size INTEGER NOT NULL,ready INTEGER NOT NULL DEFAULT 0,created INTEGER NOT NULL,PRIMARY KEY(account_id,hash));
CREATE TABLE IF NOT EXISTS sync_budget(key TEXT PRIMARY KEY,used INTEGER NOT NULL);
