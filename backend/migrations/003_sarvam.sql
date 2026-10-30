CREATE TABLE IF NOT EXISTS v2_ai_budget (id INTEGER PRIMARY KEY CHECK(id=1), limit_paise INTEGER NOT NULL CHECK(limit_paise>=0));
INSERT OR IGNORE INTO v2_ai_budget VALUES(1,0);
CREATE TABLE IF NOT EXISTS v2_ai_calls (
 id TEXT PRIMARY KEY, cache_key TEXT NOT NULL, credential_fingerprint TEXT NOT NULL,
 started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL,
 reserved_paise INTEGER NOT NULL, prompt_tokens INTEGER NOT NULL DEFAULT 0,
 completion_tokens INTEGER NOT NULL DEFAULT 0, error_code TEXT, response TEXT
);
CREATE TABLE IF NOT EXISTS v2_ai_cache (cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_notice_analysis (notice_id TEXT PRIMARY KEY REFERENCES v2_notices(id), payload TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS v2_ai_cache_update BEFORE UPDATE ON v2_ai_cache BEGIN SELECT RAISE(ABORT,'immutable model cache'); END;
CREATE TRIGGER IF NOT EXISTS v2_ai_cache_delete BEFORE DELETE ON v2_ai_cache BEGIN SELECT RAISE(ABORT,'immutable model cache'); END;
CREATE TABLE IF NOT EXISTS v2_ocr_jobs (cache_key TEXT PRIMARY KEY, call_id TEXT NOT NULL, job_id TEXT, status TEXT NOT NULL, error_code TEXT);
