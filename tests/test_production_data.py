"""Data cutover tests; synthetic identities and captured public source metadata."""
from pathlib import Path
from datetime import datetime,timezone
import pytest
from backend.tests.local_temp import LocalTemporaryDirectory
from backend.exam_store import ExamStore
from backend import schemas as s
from backend.production_data import prepare_production_data
from backend.services.source_monitor import SourceMonitor,parse_listing,FetchResult
from backend.services.exams import ExamService


def test_cutover_preserves_real_source_history_and_budget_not_demo_accounts():
    temp=LocalTemporaryDirectory()
    try:
        source=ExamStore(Path(temp.name)/'old.sqlite3');source.seed_demo_users()
        service=ExamService(source,demo=True)
        SourceMonitor(source).replay_demo()
        root=Path(__file__).parent/'fixtures/official'
        publisher=next(item for item in source.sources() if item.source_id=='upsc-active')
        listing=(root/'upsc-listing.html').read_bytes();detail=(root/'upsc-ese-2027.html').read_bytes()
        link=next(item for item in parse_listing(publisher,listing) if item.cycle_id=='upsc-ese:2027')
        notice,_=SourceMonitor(source).ingest(publisher,link,FetchResult(link.url,link.url,detail,'text/html',200),listing=FetchResult(str(publisher.listing_url),str(publisher.listing_url),listing,'text/html',200))
        service.review(notice.notice_id,s.NoticeReviewDecision(notice_id=notice.notice_id,reviewer_id='demo-operator',action='APPROVE',reason='Synthetic fixture source acceptance',reviewed_at=datetime.now(timezone.utc),expected_revision=0),'demo-operator')
        with source.connect(write=True) as con:con.execute('UPDATE v2_ai_budget SET limit_paise=5000')
        target=Path(temp.name)/'production.sqlite3'
        result=prepare_production_data(source.path,target,backup_dir=Path(temp.name)/'backups')
        assert Path(result['backup']).is_file()
        production=ExamStore(target)
        with production.connect() as con:
            assert con.execute('SELECT count(*) FROM v2_users').fetchone()[0]==0
            assert con.execute('SELECT count(*) FROM v2_notifications').fetchone()[0]==0
            assert con.execute('SELECT count(*) FROM v2_notices').fetchone()[0]==1
            assert con.execute('SELECT count(*) FROM v2_updates').fetchone()[0]==1
            assert con.execute('SELECT limit_paise FROM v2_ai_budget').fetchone()[0]==5000
            assert not con.execute('PRAGMA foreign_key_check').fetchall()
        assert ExamService(production).public_updates().total==1
        with pytest.raises(ValueError,match='already exists'):prepare_production_data(source.path,target,backup_dir=Path(temp.name)/'backups')
        with source.connect() as con:assert con.execute('SELECT count(*) FROM v2_users').fetchone()[0]==3
    finally:temp.cleanup()
