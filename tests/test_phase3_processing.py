"""Captured official markup and synthetic documents; no paid calls."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
import hashlib,json
import pytest
import pymupdf

from backend import schemas as s
from backend.services.source_monitor import SourceMonitor,SourceScheduler,ListingLink,FetchResult,parse_listing,parse_attachments,extract_pages
from backend.services.processing import ProcessingService
from backend.services.sarvam import SarvamService
from backend.services.exams import ExamService
from backend.storage import ServiceError
from tests.test_source_monitor import store,ROOT,mock_fetcher


def processor(store,clock=None):
 ai=SarvamService(store,api_key='test-key',clock=clock)
 return ProcessingService(ai,SimpleNamespace(process=lambda *_:None),clock=clock)


def discovered(store):
 monitor=SourceMonitor(store,fetcher=mock_fetcher());monitor.check('nta-jee-main',dry_run=False)
 with store.connect() as con:return con.execute('SELECT id FROM v2_notices').fetchone()[0]


def test_rotation_survives_restart_and_reaches_tail(store):
 monitor=SourceMonitor(store);links=[ListingLink(str(i),f'https://www.upsc.gov.in/{i}',None) for i in range(8)]
 assert [x.title for x in monitor.rotating_batch('audit',links)]==['0','1','2','3','4']
 assert [x.title for x in SourceMonitor(store).rotating_batch('audit',links)]==['5','6','7','0','1']


def test_neet_official_fixture_routes_2026_separately(store):
 source=next(x for x in store.sources() if x.source_id=='nta-neet-ug')
 data=(ROOT/'neet-listing.html').read_bytes();manifest=json.loads((ROOT/'capture_manifest.json').read_text(encoding='utf-8'))
 assert hashlib.sha256(data).hexdigest()==manifest['neet-listing']['sha256']
 links=parse_listing(source,data)
 assert any(x.cycle_id=='neet-ug:2026' for x in links)
 assert not any(x.cycle_id=='neet-ug:2027' for x in links)
 assert not any('toppers' in x.title.lower() for x in links)


def test_source_scheduler_isolates_unexpected_failure(store):
 with store.connect(write=True) as con:
  for source in store.sources(con)[:3]:
   if source.source_id not in {'nta-jee-main','upsc-active'}:continue
   source=s.OfficialSource.model_validate(source.model_dump(mode='json')|dict(enabled=True,readiness='ADAPTER_TESTED',adapter_name='synthetic-tested'))
   con.execute('UPDATE v2_sources SET payload=? WHERE id=?',(source.model_dump_json(),source.source_id))
 calls=[]
 def check(source_id,**_):
  calls.append(source_id)
  if source_id=='nta-jee-main':raise RuntimeError('synthetic poll failure')
 monitor=SourceMonitor(store);monitor.check=check
 SourceScheduler(monitor).tick()
 assert calls==['nta-jee-main','upsc-active']
 with store.connect() as con:assert json.loads(con.execute("SELECT health FROM v2_sources WHERE id='nta-jee-main'").fetchone()[0])['status']=='ERROR'


def test_job_claim_survives_restart_and_stale_owner_cannot_finish(store):
 notice_id=discovered(store);time=[datetime.now(timezone.utc)]
 first=processor(store,lambda:time[0]);claim=first.claim();assert claim[0]==notice_id
 second=processor(store,lambda:time[0]);assert second.claim() is None
 time[0]+=timedelta(minutes=6)
 assert second.claim() is None
 assert first.finish(*claim,'REVIEW_READY') is False
 job=second.queue().jobs[0]
 assert job.status=='PAUSED' and job.last_error=='WORKER_LEASE_EXPIRED'


def test_budget_pauses_queue_and_sends_no_alerts(store):
 discovered(store);service=processor(store)
 assert service.tick()
 job=service.queue().jobs[0]
 assert job.status=='PAUSED' and job.last_error=='SARVAM_BUDGET_EXCEEDED' and job.attempts==0
 with store.connect() as con:assert con.execute('SELECT count(*) FROM v2_notifications').fetchone()[0]==0


def test_cached_processing_can_finish_without_paid_admission(store):
 discovered(store);service=processor(store)
 service.ai.process=lambda *_:SimpleNamespace(status='VALIDATED',notice_changes=[],cache_hit=True)
 assert service.tick()
 assert service.queue().jobs[0].status=='REVIEW_READY'
 with store.connect() as con:
  assert con.execute('SELECT count(*) FROM v2_notifications').fetchone()[0]==0
  assert con.execute('SELECT count(*) FROM v2_ai_calls').fetchone()[0]==0


def synthetic_pdf(pages=1):
 with pymupdf.open() as pdf:
  for _ in range(pages):pdf.new_page().insert_text((60,60),'SYNTHETIC TEST. Application notice.')
  return pdf.tobytes()


def test_long_official_bulletins_have_full_bounded_extraction():
 pages,version,_=extract_pages(synthetic_pdf(62),'application/pdf','synthetic-bulletin')
 assert len(pages)==62 and all('SYNTHETIC TEST' in x for x in pages)
 assert version.startswith('pymupdf-100-pages-v1')
 with pytest.raises(ServiceError):extract_pages(synthetic_pdf(101),'application/pdf','over-bound')


def test_attachment_requires_observed_parent_chain(store):
 source=next(x for x in store.sources() if x.source_id=='upsc-active')
 listing_bytes=(ROOT/'upsc-listing.html').read_bytes()
 parent=next(x for x in parse_listing(source,listing_bytes) if x.cycle_id=='upsc-ese:2027')
 html=b'<main><a href="/sites/default/files/synthetic.pdf">Corrigendum</a></main>'
 parent_doc=FetchResult(parent.url,parent.url,html,'text/html',200)
 child=parse_attachments(source,parent,html)[0]
 listing=FetchResult(str(source.listing_url),str(source.listing_url),listing_bytes,'text/html',200)
 monitor=SourceMonitor(store)
 for valid in [True,False]:
  link=child if valid else ListingLink(child.title,child.url.replace('synthetic.pdf','unobserved.pdf'),child.cycle_id)
  document=FetchResult(link.url,link.url,synthetic_pdf(),'application/pdf',200)
  notice,_=monitor.ingest(source,link,document,listing=listing,parent=parent,parent_document=parent_doc)
  with store.connect() as con:
   row=con.execute('SELECT * FROM v2_notices WHERE id=?',(notice.notice_id,)).fetchone()
   if valid:ExamService(store)._verify_publication(con,row,notice,evidence_only=True)
   else:
    with pytest.raises(ServiceError,match='Attachment was not observed'):ExamService(store)._verify_publication(con,row,notice,evidence_only=True)


def test_ambiguous_year_or_session_is_unmapped(store):
 source=next(x for x in store.sources() if x.source_id=='nta-jee-main')
 for title in ['JEE Main 2026 / 2027 Session 1 update','JEE Main 2027 Session 1 and Session 2 update']:
  html=f'<div id="row-content"><a href="https://jeemain.nta.nic.in/test.pdf">{title}</a></div>'.encode()
  assert parse_listing(source,html)[0].cycle_id is None


def test_excerpt_offsets_account_for_trimmed_trailing_newlines(store):
 text='A'*1100+'\n\n'+'B'*200
 url='https://demo.invalid/whitespace-test'
 notice,_=SourceMonitor(store).ingest(None,ListingLink('SYNTHETIC whitespace regression',url,'jee-main:2027:s1'),FetchResult(url,url,text.encode(),'text/plain',200),offline=True)
 anchor=notice.evidence[0]
 assert text[anchor.start_char:anchor.end_char]==anchor.literal_quote


def test_legacy_excerpt_repair_preserves_quote_and_rechecks_lineage(store):
 text='A'*1100+'\n\n'+'B'*200;url='https://demo.invalid/legacy-whitespace'
 notice,_=SourceMonitor(store).ingest(None,ListingLink('SYNTHETIC excerpt test',url,'jee-main:2027:s1'),FetchResult(url,url,text.encode(),'text/plain',200),offline=True)
 notice.processing_mode='SOURCE_EXCERPT';notice.evidence[0].end_char+=1
 with store.connect(write=True) as con:con.execute('UPDATE v2_notices SET payload=? WHERE id=?',(notice.model_dump_json(),notice.notice_id))
 repaired=SourceMonitor(store).repair_legacy_excerpt(notice.notice_id,0)
 assert repaired.revision==1 and repaired.evidence[0].literal_quote==notice.evidence[0].literal_quote
 assert text[repaired.evidence[0].start_char:repaired.evidence[0].end_char]==repaired.evidence[0].literal_quote
 repaired.evidence[0].literal_quote='Z'+repaired.evidence[0].literal_quote[1:]
 with store.connect(write=True) as con:con.execute('UPDATE v2_notices SET payload=? WHERE id=?',(repaired.model_dump_json(),repaired.notice_id))
 with pytest.raises(ServiceError,match='differs beyond whitespace'):SourceMonitor(store).repair_legacy_excerpt(notice.notice_id,1)
