-- Run once against the deployed database created before 0.2.16. Fresh databases get these columns from schema.sql.
ALTER TABLE sessions ADD COLUMN created INTEGER;
ALTER TABLE sessions ADD COLUMN last_seen INTEGER;
ALTER TABLE sessions ADD COLUMN label TEXT;
