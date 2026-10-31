"""Additive v2 persistence; the tested v1 Store and its tables stay intact."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path

from backend.schemas import CatalogResponse, ExamCatalogEntry, ExamCycle, OfficialSource, SourceHealth, UserProfileV2
from backend.storage import Store, utc_text

ROOT = Path(__file__).resolve().parents[1]


class ExamStore(Store):
    def __init__(self, path):
        super().__init__(path)
        with self.connect(snapshot=False) as con:
            con.executescript((ROOT / "backend/migrations/002_exam_notifications.sql").read_text(encoding="utf-8"))
            con.executescript((ROOT / "backend/migrations/003_sarvam.sql").read_text(encoding="utf-8"))
            con.executescript((ROOT / "backend/migrations/004_rule_bridge.sql").read_text(encoding="utf-8"))
            con.executescript((ROOT / "backend/migrations/005_pipeline.sql").read_text(encoding="utf-8"))
            con.execute("INSERT OR IGNORE INTO v2_migrations VALUES (5,?)",(utc_text(datetime.now(timezone.utc)),))
            con.execute("INSERT OR IGNORE INTO v2_migrations VALUES (3,?)",(utc_text(datetime.now(timezone.utc)),))
            con.execute("INSERT OR IGNORE INTO v2_migrations VALUES (1,?)",(utc_text(datetime.now(timezone.utc)),))
            con.execute("INSERT OR IGNORE INTO v2_migrations VALUES (4,?)",(utc_text(datetime.now(timezone.utc)),))
            con.commit()
        self.seed_config()
        self.migrate_accounts()
        with self.connect(write=True) as con:
            if not con.execute("SELECT 1 FROM v2_migrations WHERE version=2").fetchone():
                from backend.services.rule_engine import content_fingerprint
                for row in con.execute("SELECT id,cycle_id,observed_link_title,extraction_version,pages FROM v2_notices").fetchall():
                    digest=content_fingerprint([row["cycle_id"],row["observed_link_title"],row["extraction_version"],json.loads(row["pages"])])
                    con.execute("UPDATE v2_notices SET content_hash=? WHERE id=?",(digest,row["id"]))
                con.execute("INSERT INTO v2_migrations VALUES (2,?)",(utc_text(datetime.now(timezone.utc)),))

    def migrate_accounts(self):
        # SQLite cannot remove the original synthetic=1 CHECK with ALTER COLUMN.
        # Rebuild just this parent table with FK checks disabled on this dedicated
        # connection; retain every ID and child row, then verify all FK references.
        with self.connect(snapshot=False) as con:
            con.execute('PRAGMA foreign_keys=OFF')
            con.execute('BEGIN IMMEDIATE')
            try:
                if not con.execute('SELECT 1 FROM v2_migrations WHERE version=6').fetchone():
                    con.execute("CREATE TABLE v2_users_rebuilt(id TEXT PRIMARY KEY,role TEXT NOT NULL CHECK(role IN ('USER','ADMIN')),profile TEXT NOT NULL,synthetic INTEGER NOT NULL CHECK(synthetic IN (0,1)))")
                    con.execute('INSERT INTO v2_users_rebuilt SELECT * FROM v2_users')
                    con.execute('DROP TABLE v2_users')
                    con.execute('ALTER TABLE v2_users_rebuilt RENAME TO v2_users')
                    for statement in (ROOT/'backend/migrations/006_accounts.sql').read_text(encoding='utf-8').splitlines():
                        if statement.strip(): con.execute(statement)
                    if con.execute('PRAGMA foreign_key_check').fetchone(): raise RuntimeError('Account migration would break existing references')
                    con.execute('INSERT INTO v2_migrations VALUES (6,?)',(utc_text(datetime.now(timezone.utc)),))
                con.commit()
            except BaseException:
                con.rollback()
                raise
            finally:
                con.execute('PRAGMA foreign_keys=ON')

    def seed_config(self):
        catalog=json.loads((ROOT / "config/exam_catalog.json").read_text(encoding="utf-8"))
        sources=json.loads((ROOT / "config/source_registry.json").read_text(encoding="utf-8"))
        with self.connect(write=True) as con:
            for raw in catalog["exams"]:
                item=ExamCatalogEntry.model_validate(raw)
                con.execute("INSERT OR IGNORE INTO v2_exams VALUES (?,?)",(item.exam_id,item.model_dump_json()))
            for raw in catalog["cycles"]:
                item=ExamCycle.model_validate(raw)
                con.execute("INSERT OR IGNORE INTO v2_cycles VALUES (?,?,?)",(item.cycle_id,item.exam_id,item.model_dump_json()))
            for raw in sources["sources"]:
                item=OfficialSource.model_validate(raw)
                health=SourceHealth(source_id=item.source_id)
                con.execute("INSERT OR IGNORE INTO v2_sources VALUES (?,?,?)",(item.source_id,item.model_dump_json(),health.model_dump_json()))
                old=con.execute('SELECT payload FROM v2_sources WHERE id=?',(item.source_id,)).fetchone()
                if item.source_id=='nta-neet-ug' and old:
                    previous=OfficialSource.model_validate_json(old[0])
                    if not previous.enabled and previous.adapter_name is None and previous.allowed_hosts==['neet.nta.nic.in']:
                        con.execute('UPDATE v2_sources SET payload=? WHERE id=?',(previous.model_copy(update={'allowed_hosts':item.allowed_hosts,'notes':item.notes}).model_dump_json(),item.source_id))

    def seed_demo_users(self):
        now=datetime.now(timezone.utc)
        with self.connect(write=True) as con:
            for persona,name,role in [("school","School learner","USER"),("engineering","Engineering learner","USER"),("operator","Platform operator","ADMIN")]:
                user_id="demo-"+persona
                if con.execute("SELECT 1 FROM metadata WHERE key=?",("v2_deleted:"+user_id,)).fetchone():
                    continue
                profile=UserProfileV2(user_id=user_id,display_name=name+" · SYNTHETIC DEMO",created_at=now,updated_at=now)
                con.execute("INSERT OR IGNORE INTO v2_users VALUES (?,?,?,1)",(user_id,role,profile.model_dump_json()))

    def catalog(self,audience=None,search=None):
        with self.connect() as con:
            exams=[ExamCatalogEntry.model_validate_json(r[0]) for r in con.execute("SELECT payload FROM v2_exams ORDER BY rowid")]
            if audience: exams=[e for e in exams if audience in e.audiences]
            if search:
                term=search.casefold()
                exams=[e for e in exams if term in (e.display_name+" "+e.description+" "+e.organizer).casefold()]
            exam_ids={e.exam_id for e in exams}
            cycles=[ExamCycle.model_validate_json(r[0]) for r in con.execute("SELECT payload FROM v2_cycles ORDER BY rowid")]
            heartbeat=con.execute("SELECT value FROM metadata WHERE key='v2_monitor_heartbeat'").fetchone()
            running=bool(heartbeat and datetime.now(timezone.utc)-datetime.fromisoformat(heartbeat[0].replace('Z','+00:00'))<timedelta(seconds=90))
            source_states={r[0]:(OfficialSource.model_validate_json(r[1]),SourceHealth.model_validate_json(r[2])) for r in con.execute("SELECT id,payload,health FROM v2_sources")}
            coverage={}
            for exam in exams:
                states=[source_states[key] for key in exam.source_ids if key in source_states]
                live=any(src.enabled and health.status=='LIVE_OK' for src,health in states) and running
                tested=any(src.readiness.value=='ADAPTER_TESTED' for src,_ in states)
                coverage[exam.exam_id]='LIVE_MONITORED' if live else 'SOURCE_CONFIGURED' if tested else 'CATALOG_ONLY'
            return CatalogResponse(exams=exams,cycles=[c for c in cycles if c.exam_id in exam_ids],coverage=coverage)

    def sources(self,con=None):
        if con is None:
            with self.connect() as connection: return self.sources(connection)
        return [OfficialSource.model_validate_json(r[0]) for r in con.execute("SELECT payload FROM v2_sources ORDER BY rowid")]

    def rule_revision(self,con,cycle_id):
        row=con.execute('SELECT revision FROM v2_rule_heads WHERE cycle_id=?',(cycle_id,)).fetchone()
        return row[0] if row else 0

    def rule_set_for_cycle(self,con,cycle_id):
        from backend.services.rule_engine import validated_rules,rule_set_fingerprint
        row=con.execute('SELECT * FROM v2_rule_history WHERE cycle_id=? ORDER BY revision DESC LIMIT 1',(cycle_id,)).fetchone()
        if row:
            from pydantic import TypeAdapter
            from backend.legacy_schemas_v1 import RuleDefinition
            rules=TypeAdapter(list[RuleDefinition]).validate_json(row['rules'])
            hashes=frozenset(json.loads(row['verified_hashes']))
            if rule_set_fingerprint(rules,verified_rule_hashes=hashes)!=row['sha256']:
                from backend.storage import ServiceError
                raise ServiceError(409,'RULE_HISTORY_INTEGRITY_FAILED','Immutable rule snapshot checksum failed')
            return validated_rules(rules),hashes
        if con.execute('SELECT 1 FROM v2_rule_sets WHERE cycle_id=?',(cycle_id,)).fetchone():
            from backend.storage import ServiceError
            raise ServiceError(409,'LEGACY_RULE_HISTORY_REVIEW_REQUIRED','Existing draft rule history requires source-backed reconstruction before rollout')
        return [],frozenset()

    def persist_rule_changes(self,con,*,cycle_id,update_id,bridge_result,now_text,expected_revision=None):
        from backend.services.rule_engine import rule_set_fingerprint
        from backend.storage import ServiceError
        rules,hashes=self.rule_set_for_cycle(con,cycle_id)
        revision=self.rule_revision(con,cycle_id)
        if expected_revision is not None and expected_revision!=revision:
            raise ServiceError(409,'STALE_RULE_REVISION','Rule set changed after notice analysis')
        if bridge_result.before_rule_set_sha256!=rule_set_fingerprint(rules,verified_rule_hashes=hashes):
            raise ServiceError(409,'STALE_RULE_REVISION','Plan does not describe current complete rule history')
        payload=json.dumps([r.model_dump(mode='json') for r in bridge_result.after_rules],ensure_ascii=False,separators=(',',':'))
        proof=json.dumps(sorted(bridge_result.after_verified_hashes))
        digest=rule_set_fingerprint(list(bridge_result.after_rules),verified_rule_hashes=bridge_result.after_verified_hashes)
        if digest!=bridge_result.after_rule_set_sha256:
            raise ServiceError(409,'RULE_HISTORY_INTEGRITY_FAILED','Planned hash differs from rule history')
        con.execute('INSERT INTO v2_rule_history VALUES (?,?,?,?,?,?,?)',(cycle_id,revision+1,update_id,payload,proof,digest,now_text))
        con.execute('INSERT INTO v2_rule_heads VALUES (?,?,?) ON CONFLICT(cycle_id) DO UPDATE SET revision=excluded.revision,sha256=excluded.sha256',(cycle_id,revision+1,digest))
        con.execute('INSERT INTO v2_rule_set_versions VALUES (?,?,?,?)',(cycle_id,update_id,digest,now_text))
