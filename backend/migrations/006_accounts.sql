CREATE TABLE IF NOT EXISTS v2_credentials(user_id TEXT PRIMARY KEY REFERENCES v2_users(id) ON DELETE CASCADE, email TEXT NOT NULL UNIQUE, password_hash TEXT, email_verified_at TEXT, password_changed_at TEXT, adult_confirmed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v2_auth_sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES v2_users(id) ON DELETE CASCADE, created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS v2_auth_sessions_expiry ON v2_auth_sessions(expires_at);
CREATE TABLE IF NOT EXISTS v2_auth_tokens(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES v2_users(id) ON DELETE CASCADE, purpose TEXT NOT NULL CHECK(purpose IN ('VERIFY','RESET')), expires_at TEXT NOT NULL, used_at TEXT);
CREATE TABLE IF NOT EXISTS v2_auth_limits(key TEXT PRIMARY KEY, started_at REAL NOT NULL, count INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS v2_auth_events(id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, event TEXT NOT NULL);
