CREATE TABLE IF NOT EXISTS insight_days (
 account_id TEXT NOT NULL, device TEXT NOT NULL, day TEXT NOT NULL,
 metrics TEXT NOT NULL, updated INTEGER NOT NULL,
 PRIMARY KEY(account_id,device,day)
);
