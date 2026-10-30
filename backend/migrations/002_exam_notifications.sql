CREATE TABLE IF NOT EXISTS v2_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_exams (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_cycles (id TEXT PRIMARY KEY, exam_id TEXT NOT NULL REFERENCES v2_exams(id), payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_sources (id TEXT PRIMARY KEY, payload TEXT NOT NULL, health TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_users (id TEXT PRIMARY KEY, role TEXT NOT NULL, profile TEXT NOT NULL, synthetic INTEGER NOT NULL CHECK(synthetic=1));
CREATE TABLE IF NOT EXISTS v2_sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES v2_users(id) ON DELETE CASCADE, expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_subscriptions (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES v2_users(id) ON DELETE CASCADE, cycle_id TEXT NOT NULL REFERENCES v2_cycles(id), payload TEXT NOT NULL, UNIQUE(user_id,cycle_id));
CREATE TABLE IF NOT EXISTS v2_snapshots (
    id TEXT PRIMARY KEY, source_id TEXT NOT NULL, url TEXT NOT NULL, sha256 TEXT NOT NULL,
    content_type TEXT NOT NULL, content BLOB NOT NULL, fetched_at TEXT NOT NULL,
    UNIQUE(source_id,url,sha256)
);
CREATE TABLE IF NOT EXISTS v2_notices (
    id TEXT PRIMARY KEY, source_id TEXT, cycle_id TEXT NOT NULL REFERENCES v2_cycles(id),
    canonical_url TEXT NOT NULL, content_hash TEXT NOT NULL,
    listing_snapshot_id TEXT REFERENCES v2_snapshots(id), document_snapshot_id TEXT NOT NULL REFERENCES v2_snapshots(id),
    pages TEXT NOT NULL, extraction_id TEXT NOT NULL, extraction_version TEXT NOT NULL,
    observed_link_title TEXT NOT NULL, listing_url TEXT,
    payload TEXT NOT NULL, UNIQUE(source_id,canonical_url,content_hash)
);
CREATE TABLE IF NOT EXISTS v2_extractions (id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES v2_snapshots(id), version TEXT NOT NULL, pages TEXT NOT NULL, pages_sha TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_updates (id TEXT PRIMARY KEY, notice_id TEXT NOT NULL UNIQUE REFERENCES v2_notices(id), cycle_id TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_matches (id TEXT PRIMARY KEY, update_id TEXT NOT NULL REFERENCES v2_updates(id), user_id TEXT NOT NULL REFERENCES v2_users(id) ON DELETE CASCADE, subscription_id TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(update_id,user_id));
CREATE TABLE IF NOT EXISTS v2_notifications (id TEXT PRIMARY KEY, update_id TEXT NOT NULL REFERENCES v2_updates(id), user_id TEXT NOT NULL REFERENCES v2_users(id) ON DELETE CASCADE, match_id TEXT NOT NULL REFERENCES v2_matches(id) ON DELETE CASCADE, payload TEXT NOT NULL, UNIQUE(update_id,user_id));
CREATE TABLE IF NOT EXISTS v2_reviews (notice_id TEXT NOT NULL REFERENCES v2_notices(id), expected_revision INTEGER NOT NULL, request_hash TEXT NOT NULL, response TEXT NOT NULL, reviewer_id TEXT NOT NULL, reviewed_at TEXT NOT NULL, PRIMARY KEY(notice_id,expected_revision));
CREATE TABLE IF NOT EXISTS v2_polls (id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT NOT NULL, checked_at TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS v2_snapshot_update BEFORE UPDATE ON v2_snapshots BEGIN SELECT RAISE(ABORT,'immutable source snapshot'); END;
CREATE TRIGGER IF NOT EXISTS v2_snapshot_delete BEFORE DELETE ON v2_snapshots BEGIN SELECT RAISE(ABORT,'immutable source snapshot'); END;
CREATE TRIGGER IF NOT EXISTS v2_extraction_update BEFORE UPDATE ON v2_extractions BEGIN SELECT RAISE(ABORT,'immutable extraction'); END;
CREATE TRIGGER IF NOT EXISTS v2_extraction_delete BEFORE DELETE ON v2_extractions BEGIN SELECT RAISE(ABORT,'immutable extraction'); END;
CREATE TRIGGER IF NOT EXISTS v2_update_update BEFORE UPDATE ON v2_updates BEGIN SELECT RAISE(ABORT,'immutable published update'); END;
CREATE TRIGGER IF NOT EXISTS v2_update_delete BEFORE DELETE ON v2_updates BEGIN SELECT RAISE(ABORT,'immutable published update'); END;
CREATE TRIGGER IF NOT EXISTS v2_review_update BEFORE UPDATE ON v2_reviews BEGIN SELECT RAISE(ABORT,'immutable review'); END;
CREATE TRIGGER IF NOT EXISTS v2_review_delete BEFORE DELETE ON v2_reviews BEGIN SELECT RAISE(ABORT,'immutable review'); END;
