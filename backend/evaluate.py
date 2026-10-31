"""Measured synthetic text-clause benchmark, isolated from real accounts/notices."""
from datetime import datetime,timezone
import hashlib,json,uuid
from pathlib import Path
from backend import schemas as s
from backend.synthetic_demo import FIXTURE_ROOT,replay_case
from backend.services.rule_engine import ENGINE_VERSION

def run_evaluation(store):
    files=sorted(FIXTURE_ROOT.rglob('*.json'))
    cases=profiles=correct=0;counts_match=deterministic=True;digest=hashlib.sha256()
    for file in files:
        raw=json.loads(file.read_text(encoding='utf-8'))
        if 'gold' not in raw:continue
        event=replay_case(file);again=replay_case(file)
        digest.update(file.read_bytes())
        for name in raw['documents'].values():digest.update((file.parent/name).read_bytes())
        cases+=1;deterministic &= event==again
        gold=raw['gold'];counts_match &= event.counts.model_dump()==gold['counts']
        for transition in event.transitions:
            profiles+=1
            actual=[transition.before.status.value,transition.after.status.value,transition.direction.value]
            correct+=actual==gold['transitions'][transition.applicant_id]
    result=s.EvaluationReport(run_id='eval-'+uuid.uuid4().hex,created_at=datetime.now(timezone.utc),dataset_sha256=digest.hexdigest(),engine_version=ENGINE_VERSION,cases=cases,profiles=profiles,correct_transitions=correct,counts_match=counts_match,deterministic_replay=deterministic,limitations=['Three declared synthetic text original/corrigendum pairs; no production applicant data.','Measures deterministic transition/count/replay agreement with supplied gold only.','Does not measure OCR, source authenticity, classification, matching or real-world eligibility accuracy.','Curated trust assumptions; gold labels require maintainer review. No comparative baseline was run.'])
    with store.connect(write=True) as con:
        con.execute('CREATE TABLE IF NOT EXISTS v2_evaluations(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,payload TEXT NOT NULL)')
        con.execute("CREATE TRIGGER IF NOT EXISTS v2_evaluation_update BEFORE UPDATE ON v2_evaluations BEGIN SELECT RAISE(ABORT,'immutable evaluation'); END")
        con.execute('INSERT INTO v2_evaluations VALUES (?,?,?)',(result.run_id,result.created_at.isoformat(),result.model_dump_json()))
    return result

def latest(store):
    with store.connect() as con:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE name='v2_evaluations'").fetchone():return None
        row=con.execute('SELECT payload FROM v2_evaluations ORDER BY rowid DESC LIMIT 1').fetchone()
    return s.EvaluationReport.model_validate_json(row[0]) if row else None

if __name__=='__main__':
    import os
    from dotenv import load_dotenv
    from backend.exam_store import ExamStore
    load_dotenv(Path(__file__).resolve().parents[1]/'.env')
    print(run_evaluation(ExamStore(Path(os.environ.get('NIYAMPULSE_DATA_DIR','var/production'))/'niyampulse.sqlite3')).model_dump_json(indent=2))
