-- Migration 004: per-cycle deterministic rule history for the v2 rule bridge.
--
-- v2_rule_sets stores one row per (cycle_id, rule_id) — a versioned snapshot
-- of every RuleDefinition that has been approved through the notice review
-- pipeline. The payload is the full JSON of the legacy RuleDefinition; the
-- verified_hash is the content fingerprint computed by rule_engine.rule_fingerprint
-- so the evaluator can confirm the rule is source-verified.
--
-- v2_rule_set_versions tracks atomic publications: each approved
-- NoticeUpdate that carried rule_changes bumps the version for its cycle.
-- Only ONE version is "current" per cycle at any time.
--
-- Idempotent: all statements use IF NOT EXISTS / OR IGNORE.

CREATE TABLE IF NOT EXISTS v2_rule_sets (
    id            TEXT PRIMARY KEY,          -- rule_id (stable across edits)
    cycle_id      TEXT NOT NULL REFERENCES v2_cycles(id),
    update_id     TEXT NOT NULL REFERENCES v2_updates(id),  -- publication that introduced/replaced this row
    rule_type     TEXT NOT NULL,
    payload       TEXT NOT NULL,             -- JSON of legacy RuleDefinition
    verified_hash TEXT NOT NULL,             -- rule_engine.rule_fingerprint(rule)
    effective_from TEXT NOT NULL,
    effective_until TEXT,                    -- NULL = open-ended
    revoked_by_update TEXT REFERENCES v2_updates(id),  -- NULL = still active
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v2_rule_set_versions (
    cycle_id      TEXT NOT NULL REFERENCES v2_cycles(id),
    update_id     TEXT NOT NULL REFERENCES v2_updates(id),
    rule_set_sha256 TEXT NOT NULL,           -- rule_engine.rule_set_fingerprint over active rules
    applied_at    TEXT NOT NULL,
    PRIMARY KEY (cycle_id, update_id)
);

-- Immutability: once a rule row is inserted its payload and hash are frozen.
-- Revocation is recorded by setting revoked_by_update (a separate column update).
CREATE TRIGGER IF NOT EXISTS v2_rule_set_payload_freeze BEFORE UPDATE OF payload ON v2_rule_sets
    BEGIN SELECT RAISE(ABORT,'immutable rule payload'); END;
CREATE TRIGGER IF NOT EXISTS v2_rule_set_hash_freeze BEFORE UPDATE OF verified_hash ON v2_rule_sets
    BEGIN SELECT RAISE(ABORT,'immutable rule hash'); END;
