PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY, config TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0,
    history TEXT NOT NULL DEFAULT '[]', trust TEXT NOT NULL DEFAULT '[]',
    decisions TEXT NOT NULL DEFAULT '[]', baseline_document_id TEXT
);
CREATE TABLE IF NOT EXISTS pdf_sources (sha TEXT PRIMARY KEY, content BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY, workspace TEXT NOT NULL REFERENCES workspaces(id),
    sha TEXT NOT NULL REFERENCES pdf_sources(sha), acquisition TEXT NOT NULL,
    origin_path TEXT, UNIQUE(workspace, sha)
);
CREATE TABLE IF NOT EXISTS document_states (
    id TEXT PRIMARY KEY REFERENCES documents(id), payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS extractions (
    id TEXT PRIMARY KEY, sha TEXT NOT NULL REFERENCES pdf_sources(sha),
    version TEXT NOT NULL, payload TEXT NOT NULL, payload_sha TEXT NOT NULL,
    UNIQUE(sha, version)
);
CREATE TABLE IF NOT EXISTS amendments (
    id TEXT PRIMARY KEY, workspace TEXT NOT NULL REFERENCES workspaces(id),
    document_id TEXT NOT NULL UNIQUE REFERENCES documents(id), payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
    workspace TEXT NOT NULL REFERENCES workspaces(id), revision INTEGER NOT NULL,
    recorded_at TEXT NOT NULL, history TEXT NOT NULL, trust TEXT NOT NULL,
    decisions TEXT NOT NULL, PRIMARY KEY(workspace, revision)
);
CREATE TABLE IF NOT EXISTS events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
    workspace TEXT NOT NULL REFERENCES workspaces(id), payload TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS immutable_pdf_update BEFORE UPDATE ON pdf_sources BEGIN SELECT RAISE(ABORT, 'immutable PDF'); END;
CREATE TRIGGER IF NOT EXISTS immutable_pdf_delete BEFORE DELETE ON pdf_sources BEGIN SELECT RAISE(ABORT, 'immutable PDF'); END;
CREATE TRIGGER IF NOT EXISTS immutable_extraction_update BEFORE UPDATE ON extractions BEGIN SELECT RAISE(ABORT, 'immutable extraction'); END;
CREATE TRIGGER IF NOT EXISTS immutable_extraction_delete BEFORE DELETE ON extractions BEGIN SELECT RAISE(ABORT, 'immutable extraction'); END;
CREATE TRIGGER IF NOT EXISTS immutable_acquisition_update BEFORE UPDATE ON documents BEGIN SELECT RAISE(ABORT, 'immutable acquisition'); END;
CREATE TRIGGER IF NOT EXISTS immutable_acquisition_delete BEFORE DELETE ON documents BEGIN SELECT RAISE(ABORT, 'immutable acquisition'); END;
CREATE TRIGGER IF NOT EXISTS immutable_snapshot_update BEFORE UPDATE ON snapshots BEGIN SELECT RAISE(ABORT, 'immutable snapshot'); END;
CREATE TRIGGER IF NOT EXISTS immutable_snapshot_delete BEFORE DELETE ON snapshots BEGIN SELECT RAISE(ABORT, 'immutable snapshot'); END;
CREATE TRIGGER IF NOT EXISTS immutable_event_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'immutable event'); END;
CREATE TRIGGER IF NOT EXISTS immutable_event_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'immutable event'); END;
PRAGMA user_version=1;
