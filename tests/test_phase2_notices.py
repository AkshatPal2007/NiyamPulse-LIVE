"""Captured real public notices, no paid inference in these tests."""
import pytest
from tests.test_v2_flow import client
from backend import schemas as s
from backend.services.sarvam import requires_rule_review,resolve_literal_spans

@pytest.mark.parametrize('text,required',[
 ('It is also an eligibility test for JEE (Advanced), which is conducted for admission to IITs.',False),
 ('For details of Papers, Scheme, Timing, Eligibility and other information, candidates are requested to refer to the Information Bulletin.',False),
 ('Minimum qualifying marks: 75%.',True),
 ('Candidates not complying with the instructions shall be summarily disqualified.',False),
 ('Candidates must be a citizen of India.',True),
 ('National Eligibility-cum-Entrance Test [(NEET (UG)] 2026',False),
 ('Candidates with a disability are exempt from the minimum marks requirement.',True),
 ('Eligibility criteria have been revised. Read the revised bulletin.',True),
 ('Only applicants domiciled in Delhi may apply.',True),
 ('Medical fitness is required for admission.',True),
])
def test_informational_mention_vs_operative_change(text,required):
 assert requires_rule_review(text)==required


def candidate(q):return s.SarvamCandidate(cycle_id='jee-main:2027:s1',notice_type='INFORMATIONAL',topics=['OTHER'],facts=[s.ExtractedFact(kind='ANNOUNCEMENT',page_number=1,literal_quote=q)],requires_rule_validation=False)


def test_quote_resolver_must_preserve_punctuation():
 with pytest.raises(ValueError):resolve_literal_spans(candidate('Fees INR 1000'),['Fees - INR - 1000'])
 assert resolve_literal_spans(candidate('Date of Examination 20 January 2027'),['Date of Examination\n20 January 2027']).facts[0].literal_quote=='Date of Examination\n20 January 2027'


def test_credit_floor_missing_stale_and_low_balance(client):
 from backend.services.sarvam import SarvamService
 from backend.storage import ServiceError
 from datetime import datetime,timezone,timedelta
 clock=[datetime.now(timezone.utc)]
 ai=SarvamService(client.app.state.exam_store,api_key='test-key',clock=lambda:clock[0]);ai.set_budget(5000)
 with pytest.raises(ServiceError,match='Paid processing paused'):ai._reserve('missing-balance')
 ai.record_credit_balance(50500)
 ai._reserve('synthetic-admission-no-network')
 assert ai.health().credit_safety.estimated_remaining_hundredths==50000
 assert not ai.health().credit_safety.paid_requests_allowed
 with pytest.raises(ServiceError,match='Paid processing paused'):ai._reserve('floor-protected')
 clock[0]+=timedelta(minutes=16)
 assert not ai.health().credit_safety.paid_requests_allowed
 with pytest.raises(ServiceError,match='Paid processing paused'):ai._reserve('stale-balance')


def test_existing_v2_disclaimer_remains_readable():
 from backend.schemas import InAppNotification
 from datetime import datetime,timezone
 now=datetime.now(timezone.utc)
 legacy='Decision support only; not official eligibility or application confirmation.'
 anchor=s.EvidenceAnchor(document_id='source-fixture',document_sha256='a'*64,page_number=1,literal_quote='SYNTHETIC source evidence')
 item=InAppNotification(match_id='old-match',notification_id='old-alert',user_id='synthetic-user',update_id='old-update',cycle_id='jee-main:2027:s1',headline='Synthetic prior alert',body='Saved before this migration',language='en',created_at=now,evidence=[anchor],disclaimer=legacy)
 assert item.disclaimer==legacy


def test_captured_upsc_informational_flow_with_mocked_extraction(client):
 # Real captured public source metadata; synthetic subscribers/operator and a
 # mocked provider. This is not runtime human approval or a paid API test.
 from pathlib import Path
 import json,hashlib,httpx
 from datetime import datetime,timezone
 from tests.test_v2_flow import session
 from backend.services.source_monitor import SourceMonitor,FetchResult,parse_listing
 from backend.services.sarvam import SarvamService
 root=Path(__file__).parent/'fixtures/official';store=client.app.state.exam_store
 source=next(x for x in store.sources() if x.source_id=='upsc-active')
 listing_bytes=(root/'upsc-listing.html').read_bytes();detail_bytes=(root/'upsc-ese-2027.html').read_bytes()
 manifest=json.loads((root/'capture_manifest.json').read_text(encoding='utf-8'))
 assert hashlib.sha256(detail_bytes).hexdigest()==manifest['upsc-ese-2027']['sha256']
 link=next(x for x in parse_listing(source,listing_bytes) if x.cycle_id=='upsc-ese:2027')
 listing=FetchResult(str(source.listing_url),str(source.listing_url),listing_bytes,'text/html',200)
 notice,_=SourceMonitor(store).ingest(source,link,FetchResult(link.url,link.url,detail_bytes,'text/html',200),listing=listing)
 facts=[dict(kind='ANNOUNCEMENT',page_number=1,literal_quote=q,date_value=None) for q in ['Date of Commencement of Examination\n31/01/2027','Last Date for Receipt of Applications\n06/10/2026 - 6:00pm']]
 payload=dict(cycle_id=notice.cycle_id,notice_type='ORIGINAL',topics=['EXAM_SCHEDULE','REGISTRATION'],facts=facts,requires_rule_validation=False)
 ai=SarvamService(store,api_key='test-key',transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(payload)}}]})))
 ai.set_budget(500);ai.record_credit_balance(59812);client.app.state.sarvam_service=ai
 result=ai.process(notice.notice_id,0);assert result.status=='VALIDATED' and not result.notice_changes
 learner,_=session(client,'engineering');outsider,_=session(client,'school');admin,operator=session(client,'operator')
 assert client.post('/api/v2/me/subscriptions',headers=learner,json={'cycle_id':notice.cycle_id}).status_code in {200,201}
 client.patch('/api/v2/me/profile',headers=learner,json={'preferred_language':'hi'})
 body=dict(notice_id=notice.notice_id,reviewer_id=operator['user_id'],action='APPROVE',reason='Synthetic operator acceptance of captured source/cycle/evidence',reviewed_at=datetime.now(timezone.utc).isoformat(),expected_revision=1)
 assert client.post(f'/api/v2/admin/notices/{notice.notice_id}/review',headers=outsider,json=body).status_code==403
 for _ in range(2):assert client.post(f'/api/v2/admin/notices/{notice.notice_id}/review',headers=admin,json=body).status_code==200
 inbox=client.get('/api/v2/me/notifications',headers=learner).json()
 assert len(inbox['notifications'])==1 and inbox['unread_count']==1
 alert=inbox['notifications'][0];assert alert['language']=='hi' and '06/10/2026 - 6:00pm' in alert['body']
 assert client.get('/api/v2/me/notifications',headers=outsider).json()['notifications']==[]
 assert client.post('/api/v2/me/notifications/'+alert['notification_id']+'/read',headers=learner).status_code==200
 assert client.get('/api/v2/me/notifications',headers=learner).json()['unread_count']==0
 with store.connect() as con:
  assert con.execute('SELECT status FROM v2_processing_jobs WHERE notice_id=?',(notice.notice_id,)).fetchone()[0]=='COMPLETE'
  assert con.execute('SELECT count(*) FROM v2_updates').fetchone()[0]==1
  assert con.execute('SELECT count(*) FROM v2_matches').fetchone()[0]==1
  assert con.execute('SELECT count(*) FROM v2_notifications').fetchone()[0]==1
 assert client.get('/api/v2/admin/dashboard',headers=admin).status_code==200
