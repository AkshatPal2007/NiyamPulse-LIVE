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
            con.execute("INSERT OR IGNORE INTO v2_migrations VALUES (3,?)",(utc_text(datetime.now(timezone.utc)),))
            con.execute("INSERT OR IGNORE INTO v2_migrations VALUES (1,?)",(utc_text(datetime.now(timezone.utc)),))
            con.commit()
        self.seed_config()
        with self.connect(write=True) as con:
            if not con.execute("SELECT 1 FROM v2_migrations WHERE version=2").fetchone():
                from backend.services.rule_engine import content_fingerprint
                for row in con.execute("SELECT id,cycle_id,observed_link_title,extraction_version,pages FROM v2_notices").fetchall():
                    digest=content_fingerprint([row["cycle_id"],row["observed_link_title"],row["extraction_version"],json.loads(row["pages"])])
                    con.execute("UPDATE v2_notices SET content_hash=? WHERE id=?",(digest,row["id"]))
                con.execute("INSERT INTO v2_migrations VALUES (2,?)",(utc_text(datetime.now(timezone.utc)),))

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

    def seed_demo_users(self):
        now=datetime.now(timezone.utc)
        with self.connect(write=True) as con:
            for persona,name,role in [("school","School learner","USER"),("engineering","Engineering learner","USER"),("operator","Platform operator","ADMIN")]:
                user_id="demo-"+persona
                if con.execute("SELECT 1 FROM metadata WHERE key=?",("v2_deleted:"+user_id,)).fetchone():
                    continue
                profile=UserProfileV2(user_id=user_id,display_name=name+" Â· SYNTHETIC DEMO",created_at=now,updated_at=now)
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
